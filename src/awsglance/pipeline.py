"""수집 → diff → 저장 → 규칙 평가를 잇는 순서. 실제 모드(스케줄러)와 연습 모드가 같은 함수를 부른다."""

from __future__ import annotations

import datetime as dt
import time

from . import findings
from .collect.cloudtrail import collect_cloudtrail
from .collect.inventory import collect_inventory, scope_of
from .collect.posture import collect_posture
from .config import Settings
from .diff import diff_snapshots
from .rules import EVENT_WINDOW, Context, all_rules, evaluate
from .store import Store, iso


def run_inventory(session, store: Store, settings: Settings, regions: list[str], account: str,
                  now: dt.datetime) -> dict:
    inv = collect_inventory(session, regions)
    posture = collect_posture(session, regions, account)
    new = inv["resources"]
    # 이번에 '성공적으로 본' 범위의 옛 자원만 비교한다 — 권한 거부로 못 본 자원을 '삭제'로 오해하지 않게
    old = {k: v for k, v in store.current_resources().items() if scope_of(v["type"], v["region"]) in inv["scopes"]}
    first = store.get_meta("baseline_at") is None
    changes = [] if first else diff_snapshots(old, new)  # 첫 스냅샷은 기준선(전부 '생성'으로 쏟아내지 않는다)
    deleted = [c["key"] for c in changes if c["kind"] == "deleted"]
    store.save_inventory(new, deleted, changes, now)
    store.set_meta("posture", posture)
    store.set_meta("last_inventory", iso(now))
    if first:
        store.set_meta("baseline_at", iso(now))
    result = evaluate_rules(store, now)
    return {"resources": len(new), "changes": sum(not c["noise"] for c in changes),
            "noise": sum(c["noise"] for c in changes), "errors": inv["errors"], "findings": result}


def run_cloudtrail(session, store: Store, settings: Settings, regions: list[str], now: dt.datetime,
                   sleep=time.sleep) -> dict:
    summary = collect_cloudtrail(session, store, regions, now, settings.classify, settings.max_trail_pages, sleep)
    store.set_meta("last_cloudtrail", iso(now))
    summary["findings"] = evaluate_rules(store, now)
    return summary


def evaluate_rules(store: Store, now: dt.datetime) -> dict:
    ctx = Context(resources=store.current_resources(), posture=store.get_meta("posture", {}),
                  events=store.events_since(now - EVENT_WINDOW), now=now)
    hits = evaluate(ctx)
    return findings.apply(store, hits, {r.id for r in all_rules()}, now)
