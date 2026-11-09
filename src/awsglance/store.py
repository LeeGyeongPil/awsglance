"""SQLite 저장소 — 파일 하나(WAL 모드). 스케줄러 스레드와 웹 스레드가 연결 1개를 락으로 나눠 쓴다.

- 데이터 폴더 권한 0700, DB 파일 0600(같은 컴퓨터의 다른 사용자가 못 읽게).
- 보존 기간이 지난 이벤트·변경·해결된 발견 사항과 상한을 넘는 실행 이력은 prune() 이 지운다(상한 없는 축적 금지).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resources (
  key TEXT PRIMARY KEY, type TEXT NOT NULL, region TEXT NOT NULL, rid TEXT NOT NULL, name TEXT NOT NULL,
  props TEXT NOT NULL, tags TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS resource_changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, key TEXT NOT NULL, type TEXT NOT NULL,
  region TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, fields TEXT NOT NULL, noise INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_changes_at ON resource_changes(at);
CREATE INDEX IF NOT EXISTS ix_changes_key ON resource_changes(key);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY, region TEXT NOT NULL, time TEXT NOT NULL, name TEXT NOT NULL, source TEXT NOT NULL,
  actor TEXT NOT NULL, actor_class TEXT NOT NULL, via TEXT NOT NULL, is_root INTEGER NOT NULL, reason TEXT NOT NULL,
  error_code TEXT, resources TEXT NOT NULL, request TEXT NOT NULL, read_only INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_time ON events(time);
CREATE TABLE IF NOT EXISTS trail_cursors (
  region TEXT PRIMARY KEY, cursor TEXT NOT NULL, gap_start TEXT, gap_end TEXT
);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, rule_id TEXT NOT NULL, target TEXT NOT NULL, severity TEXT NOT NULL,
  title TEXT NOT NULL, detail TEXT NOT NULL, region TEXT NOT NULL, resource_key TEXT,
  status TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, resolved_at TEXT,
  reopen_count INTEGER NOT NULL DEFAULT 0, suppress_reason TEXT, suppress_until TEXT, close_reason TEXT,
  UNIQUE(rule_id, target)
);
CREATE TABLE IF NOT EXISTS finding_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id INTEGER NOT NULL, at TEXT NOT NULL, action TEXT NOT NULL, note TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, collector TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
  status TEXT NOT NULL, calls INTEGER NOT NULL DEFAULT 0, error TEXT, summary TEXT
);
"""


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t: dt.datetime) -> str:
    """모든 시각은 UTC ISO 문자열로 저장한다(문자열 비교 = 시간 비교가 되도록 같은 형식)."""
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)  # IF NOT EXISTS — 다시 열어도 안전
        self.set_meta("schema_version", SCHEMA_VERSION)
        for suffix in ("", "-wal", "-shm"):  # 본 파일과 WAL 보조 파일 모두 0600
            p = Path(str(self.path) + suffix)
            if p.exists():
                os.chmod(p, 0o600)

    # ---- 기본 도구 ----------------------------------------------------------
    @contextmanager
    def tx(self):
        """락 + 트랜잭션. 안에서 예외가 나면 되돌린다."""
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            self.conn.execute("COMMIT")

    def query(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ---- meta --------------------------------------------------------------
    def set_meta(self, key: str, value) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (key, json.dumps(value, default=str)))

    def get_meta(self, key: str, default=None):
        rows = self.query("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    # ---- 인벤토리 ------------------------------------------------------------
    def current_resources(self) -> dict[str, dict]:
        rows = self.query("SELECT * FROM resources WHERE deleted_at IS NULL")
        return {r["key"]: {"key": r["key"], "type": r["type"], "region": r["region"], "id": r["rid"],
                           "name": r["name"], "props": json.loads(r["props"]), "tags": json.loads(r["tags"])}
                for r in rows}

    def save_inventory(self, resources: dict[str, dict], deleted_keys: list[str], changes: list[dict],
                       now: dt.datetime) -> None:
        t = iso(now)
        with self.tx() as c:
            for r in resources.values():
                c.execute(
                    "INSERT INTO resources(key,type,region,rid,name,props,tags,first_seen,last_seen,deleted_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,NULL) ON CONFLICT(key) DO UPDATE SET name=excluded.name, "
                    "props=excluded.props, tags=excluded.tags, last_seen=excluded.last_seen, deleted_at=NULL",
                    (r["key"], r["type"], r["region"], r["id"], r["name"], json.dumps(r["props"], sort_keys=True),
                     json.dumps(r["tags"], sort_keys=True), t, t))
            for key in deleted_keys:
                c.execute("UPDATE resources SET deleted_at=? WHERE key=?", (t, key))
            for ch in changes:
                c.execute("INSERT INTO resource_changes(at,key,type,region,name,kind,fields,noise) VALUES(?,?,?,?,?,?,?,?)",
                          (t, ch["key"], ch["type"], ch["region"], ch["name"], ch["kind"],
                           json.dumps(ch["fields"], default=str), int(ch["noise"])))

    # ---- CloudTrail ---------------------------------------------------------
    def insert_events(self, rows: list[dict]) -> int:
        """EventId 가 이미 있으면 건너뛴다(겹침 구간 중복 제거). 새로 들어간 개수를 돌려준다."""
        added = 0
        with self.tx() as c:
            for e in rows:
                cur = c.execute(
                    "INSERT OR IGNORE INTO events(event_id,region,time,name,source,actor,actor_class,via,is_root,reason,"
                    "error_code,resources,request,read_only) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (e["event_id"], e["region"], e["time"], e["name"], e["source"], e["actor"], e["actor_class"],
                     e["via"], int(e["is_root"]), e["reason"], e.get("error_code"), json.dumps(e["resources"]),
                     json.dumps(e["request"], default=str), int(e.get("read_only", False))))
                added += cur.rowcount
        return added

    def get_cursor(self, region: str) -> dict | None:
        rows = self.query("SELECT * FROM trail_cursors WHERE region=?", (region,))
        return rows[0] if rows else None

    def set_cursor(self, region: str, cursor: str, gap_start: str | None, gap_end: str | None) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO trail_cursors(region,cursor,gap_start,gap_end) VALUES(?,?,?,?) ON CONFLICT(region) "
                "DO UPDATE SET cursor=excluded.cursor, gap_start=excluded.gap_start, gap_end=excluded.gap_end",
                (region, cursor, gap_start, gap_end))

    def events_since(self, since: dt.datetime) -> list[dict]:
        rows = self.query("SELECT * FROM events WHERE time >= ? ORDER BY time DESC", (iso(since),))
        for r in rows:
            r["resources"] = json.loads(r["resources"])
            r["request"] = json.loads(r["request"])
        return rows

    # ---- 실행 이력 -----------------------------------------------------------
    def start_run(self, collector: str, now: dt.datetime) -> int:
        with self._lock:
            cur = self.conn.execute("INSERT INTO runs(collector,started_at,status) VALUES(?,?,'running')",
                                    (collector, iso(now)))
            return cur.lastrowid

    def finish_run(self, run_id: int, status: str, now: dt.datetime, calls: int = 0,
                   error: str | None = None, summary: dict | None = None) -> None:
        with self._lock:
            self.conn.execute("UPDATE runs SET ended_at=?, status=?, calls=?, error=?, summary=? WHERE id=?",
                              (iso(now), status, calls, error, json.dumps(summary or {}), run_id))

    def abort_orphan_runs(self, now: dt.datetime) -> int:
        """지난번 프로세스가 끝나며 남긴 '실행 중' 기록을 '중단됨'으로 닫는다."""
        with self._lock:
            return self.conn.execute("UPDATE runs SET status='aborted', ended_at=? WHERE status='running'",
                                     (iso(now),)).rowcount

    # ---- 보존 정리 -----------------------------------------------------------
    def prune(self, now: dt.datetime, retention_days: int = 180, max_runs: int = 500) -> dict:
        cut = iso(now - dt.timedelta(days=retention_days))
        with self.tx() as c:
            n_events = c.execute("DELETE FROM events WHERE time < ?", (cut,)).rowcount
            n_changes = c.execute("DELETE FROM resource_changes WHERE at < ?", (cut,)).rowcount
            n_find = c.execute("DELETE FROM findings WHERE status IN ('resolved','closed') AND last_seen < ?",
                               (cut,)).rowcount
            c.execute("DELETE FROM finding_actions WHERE finding_id NOT IN (SELECT id FROM findings)")
            c.execute("DELETE FROM resources WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cut,))
            n_runs = c.execute("DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT ?)",
                               (max_runs,)).rowcount
        return {"events": n_events, "changes": n_changes, "findings": n_find, "runs": n_runs}
