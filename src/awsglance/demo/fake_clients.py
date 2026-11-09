"""연습(mock) 모드용 가짜 AWS 세션 — 예제 JSON 을 boto3 응답 모양으로 돌려준다.

중요한 점: 이 가짜는 '결과'를 흉내 내지 않고 '원본 API 응답'만 흉내 낸다.
수집기·diff·사람/자동 분류·규칙 엔진은 실제 모드와 똑같은 코드가 이 응답을 처리한다.
그리고 호출마다 읽기 전용 허용 목록(guard.check)을 그대로 통과해야 한다 — 연습 모드에서도 쓰기 호출은 막힌다.

예제 파일(demo/fixtures/):
- account.json    : 계정 ID·주체·활성 리전
- inventory.json  : {서비스: {리전: {API 작업: 응답}}}. 항목에 "_only": "before"|"after" 를 달면 그 시점 스냅샷에만 있다.
- cloudtrail.json : {리전: [이벤트]} — LookupEvents 가 돌려줄 원본 이벤트(CloudTrailEvent JSON 의 내용)

시각 값 "@ago:3h" · "@ago:2d" · "@ago:30m" 은 '지금' 기준 상대 시각으로 바뀐다(예제가 늘 최근 데이터처럼 보이게).
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from functools import lru_cache
from importlib import resources

import botocore.session
from botocore import xform_name
from botocore.exceptions import ClientError

from ..aws import guard

_AGO = re.compile(r"^@ago:(\d+)([mhd])$")
_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def load_fixture(name: str) -> dict:
    text = resources.files("awsglance.demo").joinpath("fixtures", name).read_text(encoding="utf-8")
    return json.loads(text)


def resolve_times(obj, now: dt.datetime, as_text: bool = False):
    """'@ago:..' 문자열을 datetime(boto3 응답과 같은 형태) 또는 ISO 문자열(CloudTrailEvent 안)로 바꾼다."""
    if isinstance(obj, dict):
        return {k: resolve_times(v, now, as_text) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_times(v, now, as_text) for v in obj]
    if isinstance(obj, str):
        m = _AGO.match(obj)
        if m:
            t = now - dt.timedelta(**{_UNITS[m.group(2)]: int(m.group(1))})
            return t.strftime("%Y-%m-%dT%H:%M:%SZ") if as_text else t
    return obj


def pick_phase(obj, phase: str):
    """'_only' 표시가 다른 시점인 항목을 빼고, 표시 자체는 지운다."""
    if isinstance(obj, dict):
        return {k: pick_phase(v, phase) for k, v in obj.items() if k != "_only"}
    if isinstance(obj, list):
        return [pick_phase(v, phase) for v in obj
                if not (isinstance(v, dict) and v.get("_only") not in (None, phase))]
    return obj


@lru_cache(maxsize=None)
def _operations(service: str) -> dict[str, str]:
    """botocore 에 들어 있는 서비스 모델(오프라인)에서 '메서드 이름 → API 작업 이름' 표를 만든다.

    describe_db_instances → DescribeDBInstances 처럼 대소문자가 규칙적이지 않아서 직접 변환하지 않는다.
    """
    model = botocore.session.get_session().get_service_model(service)
    return {xform_name(op): op for op in model.operation_names}


def _error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": f"{code} (demo account)"}}, operation)


class FakeClient:
    """boto3 클라이언트처럼 `client.describe_instances(...)` 로 부른다."""

    def __init__(self, service: str, region: str, data: dict, trail: list[dict], now: dt.datetime) -> None:
        self.service, self.region = service, region
        self._data = data          # 이 서비스의 {리전|*: {작업: 응답}}
        self._trail = trail        # 이 리전의 CloudTrail 이벤트(cloudtrail 클라이언트만)
        self._now = now
        self.calls: list[str] = []  # 테스트·자체 점검용 호출 기록

    # 연습 모드는 한 번에 전부 돌려주므로 페이지네이터를 쓰지 않는다(수집기는 단일 호출 경로로 처리)
    def can_paginate(self, method: str) -> bool:
        return False

    def close(self) -> None:
        pass

    def __getattr__(self, method: str):
        ops = _operations(self.service)
        if method not in ops:
            raise AttributeError(method)
        operation = ops[method]

        def call(**params):
            guard.check(self.service, operation)  # 실제 모드와 같은 허용 목록 검사
            self.calls.append(operation)
            if self.service == "cloudtrail" and operation == "LookupEvents":
                return self._lookup_events(**params)
            return self._respond(operation, params)

        return call

    def _respond(self, operation: str, params: dict) -> dict:
        by_region = self._data.get(self.region) or self._data.get("*") or {}
        answer = by_region.get(operation)
        if answer is None:
            return {}  # 예제에 없는 작업 = 빈 목록(그 리전에 자원 없음)
        # 인자별로 다른 응답: {"_by": "Bucket", "values": {"이름": 응답}}
        if isinstance(answer, dict) and "_by" in answer:
            answer = answer["values"].get(str(params.get(answer["_by"])), answer.get("default", {}))
        if isinstance(answer, dict) and "_error" in answer:
            raise _error(answer["_error"], operation)
        return copy.deepcopy(answer)

    def _lookup_events(self, StartTime=None, EndTime=None, MaxResults=50, NextToken=None, LookupAttributes=None, **_):
        """LookupEvents 를 흉내 낸다: 시간 구간 필터 → 최신 순 → MaxResults 쪽 나눔 → NextToken."""
        StartTime = StartTime or self._now - dt.timedelta(days=90)  # 실제 API 도 구간을 안 주면 최근 90일
        EndTime = EndTime or self._now
        want_read_only = None
        for attr in LookupAttributes or []:
            if attr["AttributeKey"] == "ReadOnly":
                want_read_only = attr["AttributeValue"] == "true"
        events = []
        for raw in self._trail:
            detail = resolve_times(raw, self._now, as_text=True)
            t = dt.datetime.strptime(detail["eventTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            read_only = bool(detail.get("readOnly", False))
            if not (StartTime <= t <= EndTime) or (want_read_only is not None and read_only != want_read_only):
                continue
            events.append({
                "EventId": detail["eventID"],
                "EventName": detail["eventName"],
                "ReadOnly": "true" if read_only else "false",
                "EventTime": t,
                "EventSource": detail["eventSource"],
                "Username": (detail.get("userIdentity") or {}).get("userName", ""),
                "Resources": detail.get("resources", []),
                "CloudTrailEvent": json.dumps(detail),
            })
        events.sort(key=lambda e: e["EventTime"], reverse=True)
        start = int(NextToken or 0)
        page = events[start:start + MaxResults]
        out = {"Events": page}
        if start + MaxResults < len(events):
            out["NextToken"] = str(start + MaxResults)
        return out


class FakeSession:
    """AwsSession 과 같은 모양(client·identity·enabled_regions·close). phase 로 스냅샷 시점을 고른다."""

    is_demo = True

    def __init__(self, phase: str = "after", now: dt.datetime | None = None) -> None:
        self.now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.account = load_fixture("account.json")
        inventory = load_fixture("inventory.json")["services"]
        self._inventory = resolve_times(pick_phase(inventory, phase), self.now)
        self._trail = load_fixture("cloudtrail.json")["regions"]
        self.default_region = self.account["regions"][0]
        self._clients: dict[tuple[str, str], FakeClient] = {}

    def set_phase(self, phase: str) -> None:
        inventory = load_fixture("inventory.json")["services"]
        self._inventory = resolve_times(pick_phase(inventory, phase), self.now)
        self._clients.clear()

    def client(self, service: str, region: str | None = None) -> FakeClient:
        region = region or self.default_region
        key = (service, region)
        if key not in self._clients:
            self._clients[key] = FakeClient(service, region, self._inventory.get(service, {}),
                                            self._trail.get(region, []), self.now)
        return self._clients[key]

    def identity(self) -> dict:
        r = self.client("sts", "us-east-1").get_caller_identity()
        return {"account": r["Account"], "arn": r["Arn"], "user_id": r["UserId"]}

    def enabled_regions(self) -> list[str]:
        return list(self.account["regions"])

    def close(self) -> None:
        self._clients.clear()
