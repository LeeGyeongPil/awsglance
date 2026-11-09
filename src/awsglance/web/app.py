"""웹 서버 — FastAPI `/api/*` + 빌드된 React SPA.

- 웹 요청은 SQLite 만 읽는다. AWS 를 직접 부르지 않는다(수집은 스케줄러 몫).
- 접근 보호(미들웨어 하나에서 차례로 검사):
  1) Host 헤더 허용 목록 — 악성 웹페이지가 DNS 를 127.0.0.1 로 돌려 붙는 'DNS 리바인딩'을 막는다 → 아니면 400
  2) 로컬이 아닌 주소에 바인드했으면 토큰 필수 — Bearer 헤더, 쿠키, 또는 처음 한 번 `?token=` → 아니면 401
  3) 상태를 바꾸는 요청(POST)은 JSON 만 받고, Origin 이 있으면 같은 호스트여야 한다 — 다른 사이트의 몰래 보내기 차단 → 403
"""

from __future__ import annotations

import datetime as dt
import hmac
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import __version__, findings, related
from ..aws.policy import build_policy
from ..collect.inventory import GLOBAL_TYPES
from ..diff import summarize
from ..rules import SEVERITIES, all_rules
from ..store import Store, iso, now_utc, parse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
TOKEN_COOKIE = "awsglance_token"
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def is_loopback(host: str) -> bool:
    return host.strip("[]") in LOOPBACK_HOSTS


def _host_only(host_header: str) -> str:
    """'127.0.0.1:8730' → '127.0.0.1', '[::1]:8730' → '::1'."""
    h = host_header.strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def create_app(store: Store, bind_host: str = "127.0.0.1", token: str | None = None,
               allowed_hosts: list[str] | None = None, scheduler=None, static_dir: Path | None = None) -> FastAPI:
    static_dir = Path(static_dir or STATIC_DIR)
    need_token = not is_loopback(bind_host)
    if need_token and not token:
        raise ValueError("a token is required when binding to a non-loopback address")
    hosts = set(LOOPBACK_HOSTS) | {h.lower() for h in (allowed_hosts or [])}
    if bind_host not in ("0.0.0.0", "::", ""):
        hosts.add(bind_host.strip("[]").lower())

    app = FastAPI(title="awsglance", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)

    # ---- 접근 보호 미들웨어 ---------------------------------------------------
    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = _host_only(request.headers.get("host", ""))
        if host not in hosts:
            return PlainTextResponse(f"Host '{host}' is not allowed. Start awsglance with --allow-host {host}.", 400)
        set_cookie = False
        if need_token:
            given = ""
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                given = auth[7:].strip()
            given = given or request.cookies.get(TOKEN_COOKIE, "")
            if not given and request.query_params.get("token"):
                given, set_cookie = request.query_params["token"], True
            if not hmac.compare_digest(given.encode(), token.encode()):  # 길이·내용 비교를 일정 시간에
                return PlainTextResponse("Unauthorized: open the URL with ?token=... printed in the terminal.", 401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and _host_only(urlsplit(origin).netloc) not in hosts:
                return PlainTextResponse("Forbidden origin", 403)
            if not request.headers.get("content-type", "").startswith("application/json"):
                return PlainTextResponse("Use Content-Type: application/json", 415)
        response: Response = await call_next(request)
        if set_cookie:  # 주소창에 토큰을 남기지 않도록 이후로는 HttpOnly 쿠키로
            response.set_cookie(TOKEN_COOKIE, token, httponly=True, samesite="strict")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # ---- 공통 정보 ------------------------------------------------------------
    rules_by_id = {r.id: r for r in all_rules()}

    def open_findings() -> list[dict]:
        return store.query("SELECT * FROM findings WHERE status='open'")

    def trust_signal() -> dict:
        """맨 위 점 하나: ok(정상)·warn(주의)·danger(위험)·unknown(판단 보류) + 가장 큰 사유."""
        last = store.get_meta("last_inventory")
        if not last:
            return {"level": "unknown", "reason": "아직 수집한 적이 없음", "at": None}
        if store.get_meta("mode") != "demo":
            age = now_utc() - parse(last)
            if age > dt.timedelta(hours=3):
                return {"level": "unknown", "reason": f"마지막 수집이 {int(age.total_seconds() // 3600)}시간 전 — 자격증명·권한 확인",
                        "at": last}
        rows = sorted(open_findings(), key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
        if not rows:
            return {"level": "ok", "reason": "열린 문제 없음", "at": last}
        top = rows[0]
        count = sum(1 for f in rows if f["severity"] == top["severity"])
        level = "danger" if top["severity"] in ("critical", "high") else "warn"
        return {"level": level, "reason": f"{top['severity']} {count}건 — {top['title']}", "at": last}

    # ---- API: 상태·연결 ------------------------------------------------------
    @app.get("/api/status")
    def status():
        return {"version": __version__, "mode": store.get_meta("mode", "live"),
                "identity": store.get_meta("identity"), "regions": store.get_meta("regions", []),
                "last_inventory": store.get_meta("last_inventory"), "last_cloudtrail": store.get_meta("last_cloudtrail"),
                "trust": trust_signal(), "collecting": getattr(scheduler, "running", None)}

    @app.get("/api/setup")
    def setup():
        perms = store.get_meta("permissions", [])
        counts = Counter(p["status"] for p in perms)
        return {"identity": store.get_meta("identity"), "mode": store.get_meta("mode", "live"),
                "regions": store.get_meta("regions", []), "checked_at": store.get_meta("permissions_at"),
                "permissions": perms, "counts": dict(counts), "policy": build_policy(),
                "managed_policies": ["arn:aws:iam::aws:policy/job-function/ViewOnlyAccess",
                                     "arn:aws:iam::aws:policy/SecurityAudit"]}

    @app.get("/api/policy")
    def policy():
        return build_policy()

    @app.get("/api/rules")
    def rules():
        return [r.public() for r in all_rules()]

    @app.get("/api/runs")
    def runs(limit: int = 50):
        rows = store.query("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),))
        for r in rows:
            r["summary"] = json.loads(r["summary"] or "{}")
        return rows

    @app.post("/api/collect")
    def collect():
        if scheduler is None:
            raise HTTPException(409, "collection is not running in this mode (demo)")
        for name in ("inventory", "cloudtrail"):
            scheduler.run_now(name)
        return {"queued": ["inventory", "cloudtrail"]}

    # ---- API: 개요 ------------------------------------------------------------
    @app.get("/api/overview")
    def overview():
        now = now_utc()
        day_ago, two_weeks_ago = iso(now - dt.timedelta(hours=24)), iso(now - dt.timedelta(days=14))
        resources = store.query("SELECT COUNT(*) n FROM resources WHERE deleted_at IS NULL")[0]["n"]
        events_24h = store.query("SELECT actor_class, COUNT(*) n FROM events WHERE time >= ? GROUP BY actor_class", (day_ago,))
        changes_24h = store.query("SELECT COUNT(*) n FROM resource_changes WHERE noise=0 AND at >= ?", (day_ago,))[0]["n"]
        opened = open_findings()
        # "지금 확인할 것": 규칙별 한 줄, 심각도 순, 최대 6줄
        by_rule: dict[str, list[dict]] = {}
        for f in opened:
            by_rule.setdefault(f["rule_id"], []).append(f)
        checks = []
        for rule_id, items in by_rule.items():
            items.sort(key=lambda f: f["last_seen"], reverse=True)
            checks.append({"rule_id": rule_id, "severity": items[0]["severity"], "title": items[0]["title"],
                           "count": len(items), "example": items[0]["detail"], "finding_id": items[0]["id"]})
        checks.sort(key=lambda c: (SEVERITY_ORDER.get(c["severity"], 9), -c["count"]))
        # 14일 변경 막대: 날짜별 사람/자동/판단 보류 CloudTrail 쓰기 + 스냅샷 diff 변경
        days = [(now - dt.timedelta(days=i)).date().isoformat() for i in range(13, -1, -1)]
        bars = {d: {"date": d, "human": 0, "automated": 0, "unknown": 0, "resource_changes": 0} for d in days}
        for r in store.query("SELECT substr(time,1,10) d, actor_class, COUNT(*) n FROM events WHERE time >= ? "
                             "GROUP BY d, actor_class", (two_weeks_ago,)):
            if r["d"] in bars and r["actor_class"] in bars[r["d"]]:
                bars[r["d"]][r["actor_class"]] += r["n"]
        for r in store.query("SELECT substr(at,1,10) d, COUNT(*) n FROM resource_changes WHERE noise=0 AND at >= ? "
                             "GROUP BY d", (two_weeks_ago,)):
            if r["d"] in bars:
                bars[r["d"]]["resource_changes"] += r["n"]
        since = {
            "new": store.query("SELECT COUNT(*) n FROM findings WHERE first_seen >= ?", (day_ago,))[0]["n"],
            "reopened": store.query("SELECT COUNT(*) n FROM finding_actions WHERE action='reopened' AND at >= ?",
                                    (day_ago,))[0]["n"],
            "resolved": store.query("SELECT COUNT(*) n FROM findings WHERE status='resolved' AND resolved_at >= ?",
                                    (day_ago,))[0]["n"],
            "human_changes": sum(r["n"] for r in events_24h if r["actor_class"] == "human"),
        }
        severity_counts = Counter(f["severity"] for f in opened)
        return {"trust": trust_signal(), "checks": checks[:6],
                "kpi": {"resources": resources, "events_24h": sum(r["n"] for r in events_24h),
                        "changes_24h": changes_24h, "open_findings": len(opened),
                        "last_collect": store.get_meta("last_inventory")},
                "severity_counts": {s: severity_counts.get(s, 0) for s in SEVERITIES},
                "since_24h": since, "bars": list(bars.values()), "posture": store.get_meta("posture", {})}

    # ---- API: 자원 ------------------------------------------------------------
    def _resource_row(r: dict) -> dict:
        return {"key": r["key"], "type": r["type"], "region": r["region"], "id": r["rid"], "name": r["name"],
                "props": json.loads(r["props"]), "tags": json.loads(r["tags"]), "first_seen": r["first_seen"],
                "last_seen": r["last_seen"], "deleted_at": r["deleted_at"]}

    @app.get("/api/resources")
    def resources(type: str = "", region: str = "", q: str = "", deleted: bool = False):
        rows = [_resource_row(r) for r in store.query("SELECT * FROM resources ORDER BY type, region, name")]
        open_by_key = Counter(f["resource_key"] for f in open_findings() if f["resource_key"])
        facets = {"types": dict(Counter(r["type"] for r in rows if not r["deleted_at"])),
                  "regions": dict(Counter(r["region"] for r in rows if not r["deleted_at"]))}
        out = []
        needle = q.strip().lower()
        for r in rows:
            if (r["deleted_at"] and not deleted) or (type and r["type"] != type) or (region and r["region"] != region):
                continue
            if needle and needle not in f"{r['name']} {r['id']} {json.dumps(r['tags'])}".lower():
                continue
            r["open_findings"] = open_by_key.get(r["key"], 0)
            out.append(r)
        return {"items": out, "total": len(out), "facets": facets}

    @app.get("/api/resources/{key:path}")
    def resource_detail(key: str):
        rows = store.query("SELECT * FROM resources WHERE key=?", (key,))
        if not rows:
            raise HTTPException(404, "resource not found")
        r = _resource_row(rows[0])
        changes = store.query("SELECT * FROM resource_changes WHERE key=? ORDER BY at DESC LIMIT 100", (key,))
        for c in changes:
            c["fields"] = json.loads(c["fields"])
            c["summary"] = summarize(c)
        # 관련 CloudTrail: 자원 ID·ARN 이 '정확히' 같은 이벤트만(related.py). 이름 부분 일치는 하지 않는다.
        events_match = related.support(r["type"])
        events = related_events(r) if events_match == "exact" else []
        linked = store.query("SELECT * FROM findings WHERE resource_key=? ORDER BY status, severity", (key,))
        return {"resource": r, "changes": changes, "events": events, "events_match": events_match,
                "findings": linked}

    def related_events(r: dict, limit: int = 50, batch: int = 200) -> list[dict]:
        """후보를 SQL 로 좁힌 뒤(따옴표째 JSON 값 LIKE) related.match 로 최종 판정, 최신순 최대 limit 건.

        후보 중 match 에서 떨어지는 것이 있을 수 있으므로 SQL 에 LIMIT 50 을 바로 걸지 않고
        batch 단위로 넘기며 limit 건을 채운다(events 표는 보존 기간 정리로 크기가 묶여 있다).
        """
        patterns = related.candidate_patterns(r)
        where = " OR ".join(["resources LIKE ? ESCAPE '\\' OR request LIKE ? ESCAPE '\\'"] * len(patterns))
        params: list = [p for p in patterns for _ in (0, 1)]
        sql = f"SELECT * FROM events WHERE ({where})"
        if r["type"] not in GLOBAL_TYPES:
            sql, params = sql + " AND region = ?", params + [r["region"]]  # 리전 자원은 같은 리전만
        sql += " ORDER BY time DESC, event_id DESC LIMIT ? OFFSET ?"
        out, offset = [], 0
        while len(out) < limit:
            rows = store.query(sql, (*params, batch, offset))
            for e in rows:
                e["resources"], e["request"] = json.loads(e["resources"]), json.loads(e["request"])
                if related.match(r, e):
                    out.append(e)
                    if len(out) >= limit:
                        break
            if len(rows) < batch:
                break
            offset += batch
        return out

    # ---- API: 변경 이력 ---------------------------------------------------------
    @app.get("/api/changes")
    def changes(tab: str = "human", q: str = "", region: str = "", days: int = 14, noise: bool = False):
        since = iso(now_utc() - dt.timedelta(days=max(1, min(days, 180))))
        sql, params = "SELECT * FROM events WHERE time >= ?", [since]
        if tab in ("human", "automated", "unknown"):
            sql += " AND actor_class = ?"
            params.append(tab)
        if region:
            sql += " AND region = ?"
            params.append(region)
        if q.strip():
            sql += " AND (name LIKE ? OR actor LIKE ? OR resources LIKE ? OR request LIKE ?)"
            params += [f"%{q.strip()}%"] * 4
        events = store.query(sql + " ORDER BY time DESC LIMIT 500", tuple(params))
        for e in events:
            e["resources"], e["request"] = json.loads(e["resources"]), json.loads(e["request"])
            e["is_root"], e["read_only"] = bool(e["is_root"]), bool(e["read_only"])
        csql = "SELECT * FROM resource_changes WHERE at >= ?" + ("" if noise else " AND noise = 0")
        res_changes = store.query(csql + " ORDER BY at DESC, id DESC LIMIT 500", (since,))
        for c in res_changes:
            c["fields"] = json.loads(c["fields"])
            c["noise"] = bool(c["noise"])
            c["summary"] = summarize(c)
        counts = dict(Counter(r["actor_class"] for r in store.query(
            "SELECT actor_class FROM events WHERE time >= ?", (since,))))
        return {"tab": tab, "events": events, "resource_changes": res_changes, "counts": counts}

    # ---- API: 문제(발견 사항) ----------------------------------------------------
    def _finding_out(f: dict) -> dict:
        rule = rules_by_id.get(f["rule_id"])
        f["rule"] = rule.public() if rule else None
        return f

    @app.get("/api/findings")
    def list_findings(status: str = "open", severity: str = "", rule: str = "", q: str = ""):
        sql, params = "SELECT * FROM findings WHERE 1=1", []
        if status != "all":
            sql += " AND status = ?"
            params.append(status)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if rule:
            sql += " AND rule_id = ?"
            params.append(rule)
        if q.strip():
            sql += " AND (title LIKE ? OR detail LIKE ? OR target LIKE ?)"
            params += [f"%{q.strip()}%"] * 3
        rows = store.query(sql, tuple(params))
        rows.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["rule_id"], f["target"]))
        counts = dict(Counter(r["status"] for r in store.query("SELECT status FROM findings")))
        return {"items": [_finding_out(f) for f in rows], "counts": counts}

    @app.get("/api/findings/{finding_id}")
    def finding_detail(finding_id: int):
        rows = store.query("SELECT * FROM findings WHERE id=?", (finding_id,))
        if not rows:
            raise HTTPException(404, "finding not found")
        f = _finding_out(rows[0])
        f["actions"] = store.query("SELECT * FROM finding_actions WHERE finding_id=? ORDER BY id DESC", (finding_id,))
        f["max_suppress_days"] = findings.MAX_SUPPRESS_DAYS.get(f["severity"])
        return f

    def _act(fn, *args):
        try:
            fn(store, *args)
        except findings.FindingActionError as exc:
            code = 404 if str(exc) == "not_found" else 400
            return JSONResponse({"detail": str(exc)}, code)
        return {"ok": True}

    async def _json_body(request: Request) -> dict:
        """본문이 JSON 객체가 아니면 500 대신 400 invalid_body."""
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "invalid_body") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "invalid_body")
        return body

    @app.post("/api/findings/{finding_id}/suppress")
    async def suppress(finding_id: int, request: Request):
        body = await _json_body(request)
        try:
            days = int(body.get("days", 0))
        except (TypeError, ValueError):
            raise HTTPException(400, "invalid_body") from None
        return _act(findings.suppress, finding_id, str(body.get("reason", "")), days, now_utc())

    @app.post("/api/findings/{finding_id}/close")
    async def close(finding_id: int, request: Request):
        body = await _json_body(request)
        return _act(findings.close, finding_id, str(body.get("reason", "")), now_utc())

    @app.post("/api/findings/{finding_id}/reopen")
    async def reopen(finding_id: int):
        return _act(findings.reopen, finding_id, now_utc())

    @app.get("/api/{rest:path}", include_in_schema=False)
    def api_not_found(rest: str):
        raise HTTPException(404, "no such API")

    # ---- SPA ----------------------------------------------------------------
    if (static_dir / "assets").is_dir():
        # 해시가 붙은 자산은 내용이 바뀌면 이름도 바뀌므로 오래 캐시해도 된다
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        index = static_dir / "index.html"
        if not index.is_file():
            return PlainTextResponse("Front-end build not found. Run: cd web && npm ci && npm run build", 503)
        target = (static_dir / path).resolve()
        if path and target.is_file() and static_dir.resolve() in target.parents:  # 폴더 밖 탈출 차단
            return FileResponse(target)
        # /changes?tab=human 같은 화면 주소는 모두 index.html — 화면 고르기는 브라우저 라우터가 한다
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
