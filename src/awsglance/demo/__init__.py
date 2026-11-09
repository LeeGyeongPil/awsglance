"""연습(mock) 모드 — 자격증명 없이 가상의 예제 계정으로 모든 화면을 채운다.

미리 계산한 결과를 DB 에 넣지 않는다. 실제 모드의 스케줄러가 2주 동안 돈 것처럼,
가짜 AWS 응답을 '실제' 수집기·diff·분류·규칙 코드에 시간 순서대로 통과시킨다.

    14일 전  인벤토리 1차 스냅샷(기준선) + CloudTrail 첫 수집(24시간 백필)
     7일 전  CloudTrail 증분 수집(커서 − 20분부터)
     지금    CloudTrail 증분 수집 → 인벤토리 2차 스냅샷 → diff → 규칙 평가

그래서 화면의 '변경'·'사람이 한 작업'·'발견 사항(열림/해결)'은 모두 코드가 계산한 값이다.
"""

from __future__ import annotations

import datetime as dt

from .. import pipeline
from ..aws.permissions import check_permissions
from ..config import Settings
from ..store import Store, iso, now_utc
from .fake_clients import FakeSession


def load_demo(store: Store, settings: Settings | None = None, now: dt.datetime | None = None) -> dict:
    """예제 계정을 store 에 채운다 → 요약 dict."""
    settings = settings or Settings()
    now = now or now_utc()
    session = FakeSession(phase="before", now=now)
    no_sleep = lambda _seconds: None  # 가짜 응답이라 LookupEvents 2 TPS 대기는 건너뛴다(실제 모드는 기다린다)
    try:
        who = session.identity()
        regions = session.enabled_regions()
        t0, t1 = now - dt.timedelta(days=14), now - dt.timedelta(days=7)

        # 1) 14일 전: 첫 스냅샷은 기준선이다(변경으로 쏟아내지 않는다)
        first = pipeline.run_inventory(session, store, settings, regions, who["account"], t0)
        trail_0 = pipeline.run_cloudtrail(session, store, settings, regions, t0, sleep=no_sleep)
        # 2) 7일 전·지금: CloudTrail 증분 수집(겹침 20분은 EventId 로 걸러진다)
        trail_1 = pipeline.run_cloudtrail(session, store, settings, regions, t1, sleep=no_sleep)
        trail_2 = pipeline.run_cloudtrail(session, store, settings, regions, now, sleep=no_sleep)
        # 3) 지금: 두 번째 스냅샷 → 1차와 diff → 규칙 재평가(고친 문제는 '해결', 새 문제는 '열림')
        session.set_phase("after")
        second = pipeline.run_inventory(session, store, settings, regions, who["account"], now)

        store.set_meta("mode", "demo")
        store.set_meta("identity", who)
        store.set_meta("regions", regions)
        store.set_meta("permissions", check_permissions(session, regions[0], who["account"]))
        store.set_meta("permissions_at", iso(now))
        # 실행 이력도 실제 모드처럼 남긴다(수집 상태 확인용)
        for name, at, summary in (("inventory", t0, first), ("cloudtrail", t0, trail_0), ("cloudtrail", t1, trail_1),
                                  ("cloudtrail", now, trail_2), ("inventory", now, second)):
            run_id = store.start_run(name, at)
            store.finish_run(run_id, "partial" if summary.get("errors") else "ok", at,
                             calls=int(summary.get("calls", 0)), summary=summary)
        return {"account": who["account"], "resources": second["resources"], "changes": second["changes"],
                "noise": second["noise"], "events": trail_0["added"] + trail_1["added"] + trail_2["added"],
                "findings": second["findings"]}
    finally:
        session.close()
