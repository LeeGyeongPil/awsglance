"""발견 사항 수명주기.

같은 (규칙, 대상)은 한 건으로 유지한다.

    열림(open) ──다음 평가에서 사라짐──▶ 해결(resolved) ──다시 나타남──▶ 열림(재발, reopen_count+1)
    열림 ──사용자 숨김(사유·기한)──▶ 숨김(suppressed) ──기한 지남──▶ 열림
    열림/숨김 ──사용자 닫기(오탐/처리함)──▶ 닫힘(closed)  ──사용자 다시 열기──▶ 열림

치명(critical) 심각도는 숨길 수 없다. 모든 사용자 처리는 finding_actions 에 남는다.
"""

from __future__ import annotations

import datetime as dt

from .store import Store, iso, parse

# 심각도별 최대 숨김 기한(일). 치명은 숨김 불가.
MAX_SUPPRESS_DAYS = {"high": 30, "medium": 90, "low": 180}


class FindingActionError(ValueError):
    pass


def _log(c, finding_id: int, now: dt.datetime, action: str, note: str | None = None) -> None:
    c.execute("INSERT INTO finding_actions(finding_id, at, action, note) VALUES(?,?,?,?)",
              (finding_id, iso(now), action, note))


def apply(store: Store, hits: list[dict], evaluated_rules: set[str], now: dt.datetime) -> dict:
    """규칙 평가 결과를 DB 에 반영한다 → {"opened","reopened","resolved"} 개수."""
    t = iso(now)
    counts = {"opened": 0, "reopened": 0, "resolved": 0, "unsuppressed": 0}
    seen: set[tuple[str, str]] = set()
    with store.tx() as c:
        for h in hits:
            key = (h["rule_id"], h["target"])
            seen.add(key)
            row = c.execute("SELECT id, status, suppress_until FROM findings WHERE rule_id=? AND target=?", key).fetchone()
            if row is None:
                cur = c.execute(
                    "INSERT INTO findings(rule_id,target,severity,title,detail,region,resource_key,status,first_seen,last_seen) "
                    "VALUES(?,?,?,?,?,?,?,'open',?,?)",
                    (h["rule_id"], h["target"], h["severity"], h["title"], h["detail"], h["region"], h["resource_key"], t, t))
                _log(c, cur.lastrowid, now, "opened")
                counts["opened"] += 1
                continue
            fid, status = row["id"], row["status"]
            new_status = status
            if status == "resolved":
                new_status = "open"  # 고쳤던 문제가 다시 생겼다
                c.execute("UPDATE findings SET reopen_count=reopen_count+1, resolved_at=NULL WHERE id=?", (fid,))
                _log(c, fid, now, "reopened")
                counts["reopened"] += 1
            elif status == "suppressed" and row["suppress_until"] and parse(row["suppress_until"]) <= now:
                new_status = "open"  # 숨김 기한이 지났다
                _log(c, fid, now, "suppress_expired")
                counts["unsuppressed"] += 1
            c.execute("UPDATE findings SET status=?, detail=?, severity=?, title=?, last_seen=? WHERE id=?",
                      (new_status, h["detail"], h["severity"], h["title"], t, fid))
        # 이번에 평가한 규칙의 열린/숨긴 발견 사항 중 다시 나오지 않은 것은 해결됨
        for row in c.execute("SELECT id, rule_id, target FROM findings WHERE status IN ('open','suppressed')").fetchall():
            if row["rule_id"] in evaluated_rules and (row["rule_id"], row["target"]) not in seen:
                c.execute("UPDATE findings SET status='resolved', resolved_at=? WHERE id=?", (t, row["id"]))
                _log(c, row["id"], now, "resolved")
                counts["resolved"] += 1
    return counts


def _get(c, finding_id: int):
    row = c.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
    if row is None:
        raise FindingActionError("not_found")
    return row


def suppress(store: Store, finding_id: int, reason: str, days: int, now: dt.datetime) -> None:
    if not reason.strip():
        raise FindingActionError("reason_required")
    with store.tx() as c:
        row = _get(c, finding_id)
        if row["severity"] == "critical":
            raise FindingActionError("critical_cannot_be_suppressed")
        if row["status"] not in ("open", "suppressed"):
            raise FindingActionError("only_open_can_be_suppressed")
        limit = MAX_SUPPRESS_DAYS[row["severity"]]
        if not 1 <= days <= limit:
            raise FindingActionError(f"days_must_be_1_to_{limit}")
        until = iso(now + dt.timedelta(days=days))
        c.execute("UPDATE findings SET status='suppressed', suppress_reason=?, suppress_until=? WHERE id=?",
                  (reason.strip()[:500], until, finding_id))
        _log(c, finding_id, now, "suppressed", f"{reason.strip()[:500]} (until {until})")


def close(store: Store, finding_id: int, reason: str, now: dt.datetime) -> None:
    if reason not in ("false_positive", "fixed", "accepted"):
        raise FindingActionError("reason_must_be_false_positive_fixed_or_accepted")
    with store.tx() as c:
        _get(c, finding_id)
        c.execute("UPDATE findings SET status='closed', close_reason=? WHERE id=?", (reason, finding_id))
        _log(c, finding_id, now, "closed", reason)


def reopen(store: Store, finding_id: int, now: dt.datetime) -> None:
    with store.tx() as c:
        _get(c, finding_id)
        c.execute("UPDATE findings SET status='open', close_reason=NULL, suppress_reason=NULL, suppress_until=NULL, "
                  "resolved_at=NULL WHERE id=?", (finding_id,))
        _log(c, finding_id, now, "reopened_by_user")
