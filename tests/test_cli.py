"""AC-9 — 연습 모드가 자격증명 없이 실제 수집기·diff·규칙 코드를 거쳐 모든 화면 API 를 채운다.
그리고 저장소·스케줄러의 자원 정리(파일 권한·보존 정리·고아 실행 기록·스레드 종료).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import stat
import threading
import time

from awsglance.cli import main
from awsglance.demo import load_demo
from awsglance.scheduler import Job, Scheduler
from awsglance.store import Store

SELFTEST_LINE = re.compile(
    r"^SELFTEST_OK screens=5 resources=(\d+) changes=(\d+) findings=(\d+) human_changes=(\d+)$")


def test_demo_selftest_without_credentials(tmp_path, capsys, monkeypatch):
    for k in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert main(["--demo", "--selftest", "--data-dir", str(tmp_path / "d")]) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    m = SELFTEST_LINE.match(last)
    assert m, last
    resources, changes, findings, human = map(int, m.groups())
    assert resources >= 30 and changes >= 10 and findings >= 8 and human >= 3


def test_demo_results_are_computed_by_the_real_pipeline(store):
    """예제 결과는 미리 계산된 값이 아니다: 두 스냅샷의 diff·사람 분류·해결된 발견 사항이 코드로 생긴다."""
    summary = load_demo(store)
    kinds = {(c["kind"], c["name"]) for c in store.query("SELECT kind, name FROM resource_changes WHERE noise=0")}
    assert ("created", "demo-admin") in kinds and ("deleted", "demo-tmp-export") in kinds
    assert summary["noise"] >= 1  # Lambda 의 LastModified 만 바뀐 변경은 노이즈로 빠진다
    # alice 가 연 22번 포트: 사람(SSO 콘솔) 이벤트 + 스냅샷 diff + 설정 규칙이 같은 SG 를 가리킨다
    alice = store.query("SELECT * FROM events WHERE actor='alice' AND name='AuthorizeSecurityGroupIngress'")[0]
    assert alice["actor_class"] == "human" and alice["via"] == "console"
    assert store.query("SELECT COUNT(*) n FROM findings WHERE rule_id='sg-open-world' AND target LIKE "
                       "'%sg-0demoweb0000002'")[0]["n"] == 1
    # 보존 기간을 정한 로그 그룹은 첫 스냅샷에서 열렸다가 두 번째 스냅샷에서 해결됐다
    assert store.query("SELECT status FROM findings WHERE rule_id='logs-no-retention' AND target LIKE "
                       "'%demo-cron'")[0]["status"] == "resolved"
    # 권한 점검 표에 거부·사용 불가가 함께 보인다(ViewOnly 주체)
    perms = {p["collector"]: p["status"] for p in store.get_meta("permissions")}
    assert perms["s3_account"] == "denied" and perms["securityhub"] == "unavailable"
    assert store.get_meta("posture")["matrix"]["s3_account_public_access_block"]["global"] == "denied"


def test_live_mode_wiring_on_moto(tmp_path, capsys):
    """실제 모드 준비(연결 확인 → 권한 점검 → 스케줄러 작업)를 moto 계정으로 끝까지 돌린다."""
    import argparse

    from moto import mock_aws

    from awsglance.cli import prepare_live
    from awsglance.config import Settings

    args = argparse.Namespace(profile=None, regions="us-east-1")
    with mock_aws():
        store, sched, session = prepare_live(args, tmp_path, Settings())
        try:
            assert store.get_meta("mode") == "live" and store.get_meta("identity")["account"]
            perms = {p["collector"]: p["status"] for p in store.get_meta("permissions")}
            assert perms["connection"] == "allowed" and perms["ec2"] == "allowed"
            sched.run_job(sched.jobs["inventory"])  # 스레드 없이 작업 하나만 실행
            run = store.query("SELECT * FROM runs WHERE collector='inventory'")[0]
            assert run["status"] in ("ok", "partial") and store.get_meta("last_inventory")
        finally:
            session.close()
            store.close()
    assert "Connected: account" in capsys.readouterr().out


def test_policy_command(capsys):
    assert main(["policy"]) == 0
    assert '"sts:GetCallerIdentity"' in capsys.readouterr().out


def test_selftest_requires_demo(tmp_path, capsys):
    assert main(["--selftest", "--data-dir", str(tmp_path)]) == 2  # 실제 AWS 는 절대 부르지 않는다


def test_store_file_permissions(tmp_path):
    s = Store(tmp_path / "data" / "awsglance.db")
    try:
        assert stat.S_IMODE(os.stat(tmp_path / "data").st_mode) == 0o700
        assert stat.S_IMODE(os.stat(tmp_path / "data" / "awsglance.db").st_mode) == 0o600
    finally:
        s.close()


def test_prune_keeps_storage_bounded(store):
    now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
    old = now - dt.timedelta(days=200)
    store.insert_events([{"event_id": "old", "region": "r", "time": old.isoformat(), "name": "X", "source": "s",
                          "actor": "a", "actor_class": "human", "via": "", "is_root": False, "reason": "",
                          "resources": [], "request": {}},
                         {"event_id": "new", "region": "r", "time": now.isoformat(), "name": "X", "source": "s",
                          "actor": "a", "actor_class": "human", "via": "", "is_root": False, "reason": "",
                          "resources": [], "request": {}}])
    for _ in range(12):
        store.finish_run(store.start_run("inventory", now), "ok", now)
    out = store.prune(now, retention_days=180, max_runs=5)
    assert out["events"] == 1 and out["runs"] == 7
    assert [r["event_id"] for r in store.query("SELECT event_id FROM events")] == ["new"]


def test_scheduler_runs_jobs_records_runs_and_stops(store):
    now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
    orphan = store.start_run("inventory", now)  # 지난 프로세스가 남긴 '실행 중'
    ran = threading.Event()

    def ok():
        ran.set()
        return {"calls": 3}

    def boom():
        raise RuntimeError("collector bug")

    sched = Scheduler(store, [Job("a", 3600, ok), Job("b", 3600, boom)], tick=0.05)
    sched.start()
    try:
        assert ran.wait(5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(store.query("SELECT id FROM runs WHERE status!='running'")) < 3:
            time.sleep(0.02)
    finally:
        sched.stop(timeout=5)
    assert not sched._thread.is_alive()  # 종료 경로에서 스레드가 끝난다
    runs = {r["collector"]: r for r in store.query("SELECT * FROM runs WHERE id != ?", (orphan,))}
    assert runs["a"]["status"] == "ok" and runs["a"]["calls"] == 3
    assert runs["b"]["status"] == "error" and "collector bug" in runs["b"]["error"]  # 한 작업 실패가 전체를 죽이지 않음
    assert store.query("SELECT status FROM runs WHERE id=?", (orphan,))[0]["status"] == "aborted"


def test_network_guard_blocks_outside_connections():
    """AC-10 의 '네트워크 호출 없음'을 지키는 장치가 실제로 동작하는지(conftest.no_network)."""
    import socket

    import pytest

    with socket.socket() as s, pytest.raises(RuntimeError, match="network access"):
        s.connect(("203.0.113.1", 443))
