"""CloudTrail LookupEvents 증분 수집.

LookupEvents 의 성질(공식 문서, 2026-11-09 확인):
- 리전·계정당 초당 2회, 쪽당 최대 50건, 최신 순, 최근 90일, 속성 필터 1개.
- 이벤트는 호출 직후가 아니라 몇 분 뒤에 보인다.

그래서
- 리전마다 커서(지난번 수집 끝 시각)를 두고, '커서 − 20분'부터 다시 읽는다(늦게 도착한 이벤트 보완).
- 겹친 구간에서 다시 받은 이벤트는 EventId 로 걸러낸다(DB 기본 키 + INSERT OR IGNORE).
- 호출 사이에 0.5초 이상 쉰다(2 TPS). 한 번에 읽는 쪽 수에 상한을 두고, 못 읽은 구간은 '빈 구간(gap)'으로
  저장해 다음 회차에 이어 받는다.
- 첫 회는 24시간만 거슬러 올라간다(활성 리전이 많으면 90일 백필은 수십 분 걸린다).
"""

from __future__ import annotations

import datetime as dt
import json
import time

from botocore.exceptions import BotoCoreError, ClientError

from ..aws.guard import ReadOnlyViolation
from ..classify import ClassifyRules, classify
from ..redact import redact
from ..store import iso, parse

OVERLAP = dt.timedelta(minutes=20)
FIRST_BACKFILL = dt.timedelta(hours=24)
MAX_LOOKBACK = dt.timedelta(days=90)
PAGE_SIZE = 50
MIN_CALL_INTERVAL = 0.5  # 초. 리전당 초당 2회 한도
WRITE_EVENTS_ONLY = [{"AttributeKey": "ReadOnly", "AttributeValue": "false"}]


def to_row(region: str, e: dict, rules: ClassifyRules) -> dict:
    """LookupEvents 의 이벤트 1건 → 저장할 행. 분류는 원문으로, 저장은 가린 사본으로."""
    detail = json.loads(e.get("CloudTrailEvent") or "{}")
    who = classify(detail, rules)
    error_code = detail.get("errorCode")
    if (detail.get("responseElements") or {}).get("ConsoleLogin") == "Failure":
        error_code = error_code or "ConsoleLoginFailure"
    return {
        "event_id": e["EventId"],
        "region": region,
        "time": iso(e["EventTime"]),
        "name": e.get("EventName", ""),
        "source": e.get("EventSource", ""),
        **who,
        "error_code": error_code,
        "resources": [{"type": r.get("ResourceType"), "name": r.get("ResourceName")} for r in e.get("Resources", [])],
        # 요청 파라미터에는 사용자가 넣은 비밀번호·토큰이 있을 수 있다 → 저장 전 가림
        "request": redact(detail.get("requestParameters") or {}),
        "read_only": str(e.get("ReadOnly", "false")).lower() == "true",
    }


class _Pacer:
    """같은 리전 호출 사이 간격을 MIN_CALL_INTERVAL 이상으로 유지한다."""

    def __init__(self, sleep, clock=time.monotonic):
        self.sleep, self.clock, self.last = sleep, clock, None

    def wait(self):
        if self.last is not None:
            gap = MIN_CALL_INTERVAL - (self.clock() - self.last)
            if gap > 0:
                self.sleep(gap)
        self.last = self.clock()


def _fetch_window(client, start, end, page_budget, pacer, region, rules):
    """[start, end] 를 최신 순으로 읽는다 → (rows, pages, complete, oldest_time)"""
    rows, pages, token, oldest = [], 0, None, None
    while True:
        if pages >= page_budget:
            return rows, pages, False, oldest
        kwargs = {"LookupAttributes": WRITE_EVENTS_ONLY, "StartTime": start, "EndTime": end, "MaxResults": PAGE_SIZE}
        if token:
            kwargs["NextToken"] = token  # NextToken 은 같은 파라미터로만 다시 쓸 수 있다
        pacer.wait()
        page = client.lookup_events(**kwargs)
        pages += 1
        for e in page.get("Events", []):
            rows.append(to_row(region, e, rules))
            t = e["EventTime"]
            oldest = t if oldest is None or t < oldest else oldest
        token = page.get("NextToken")
        if not token:
            return rows, pages, True, oldest


def _merge(gap, start, end):
    if gap is None:
        return (start, end)
    return (min(gap[0], start), max(gap[1], end))


def collect_cloudtrail(session, store, regions: list[str], now: dt.datetime, rules: ClassifyRules | None = None,
                       max_pages: int = 20, sleep=time.sleep) -> dict:
    """리전마다 증분 수집해 DB 에 넣는다 → {"added", "fetched", "calls", "errors", "gaps"}"""
    rules = rules or ClassifyRules()
    summary = {"added": 0, "fetched": 0, "calls": 0, "errors": [], "gaps": 0}
    for region in regions:
        client = session.client("cloudtrail", region)
        pacer = _Pacer(sleep)
        cur = store.get_cursor(region)
        if cur is None:
            windows = [(now - FIRST_BACKFILL, now)]
        else:
            start = max(parse(cur["cursor"]) - OVERLAP, now - MAX_LOOKBACK)
            windows = [(start, now)]  # 최신 구간을 먼저(화면이 최신을 보여 주도록)
            if cur["gap_start"]:
                windows.append((max(parse(cur["gap_start"]), now - MAX_LOOKBACK), parse(cur["gap_end"])))
        budget, new_gap, failed = max_pages, None, False
        for start, end in windows:
            if start >= end:
                continue
            try:
                rows, pages, complete, oldest = _fetch_window(client, start, end, budget, pacer, region, rules)
            except (ClientError, BotoCoreError, ReadOnlyViolation) as exc:
                code = exc.response["Error"].get("Code") if isinstance(exc, ClientError) else type(exc).__name__
                summary["errors"].append({"region": region, "error": code})
                new_gap, failed = _merge(new_gap, start, end), True
                continue
            budget -= pages
            summary["calls"] += pages
            summary["fetched"] += len(rows)
            summary["added"] += store.insert_events(rows)
            if not complete:
                # 오래된 쪽을 다 못 읽었다 → [start, 가장 오래 읽은 시각] 을 다음 회차로 미룬다
                new_gap = _merge(new_gap, start, (oldest or end) + dt.timedelta(seconds=1))
        if new_gap:
            summary["gaps"] += 1
        if failed and cur is None:
            continue  # 첫 회가 통째로 실패하면 커서를 만들지 않는다(다음에 처음부터)
        store.set_cursor(region, iso(now), iso(new_gap[0]) if new_gap else None, iso(new_gap[1]) if new_gap else None)
    return summary
