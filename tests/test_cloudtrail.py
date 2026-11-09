"""AC-4 — CloudTrail 증분 수집(겹침 구간 중복 제거·쪽 상한·쓰로틀)과 사람/자동 분류.

moto 는 LookupEvents 를 구현하지 않는다 → 실제 boto3 클라이언트(읽기 전용 훅 포함)에 Stubber 로 응답을 주입한다.
"""

from __future__ import annotations

import datetime as dt
import json

from botocore.stub import Stubber

from awsglance.aws.session import AwsSession
from awsglance.classify import ClassifyRules, classify
from awsglance.collect.cloudtrail import OVERLAP, WRITE_EVENTS_ONLY, collect_cloudtrail
from awsglance.config import load

from .conftest import StubSession

REGION = "us-east-1"
T = dt.datetime(2026, 11, 9, 9, 0, tzinfo=dt.timezone.utc)

SSO_ALICE = {"type": "AssumedRole",
             "arn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_AdminAccess_abc/alice"}


def _event(event_id: str, at: dt.datetime, name: str = "AuthorizeSecurityGroupIngress", identity=None, **extra) -> dict:
    detail = {"eventID": event_id, "eventName": name, "eventTime": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "userIdentity": identity or SSO_ALICE, "userAgent": "AWS Internal",
              "sessionCredentialFromConsole": "true", "requestParameters": {"groupId": "sg-1"}, **extra}
    return {"EventId": event_id, "EventName": name, "ReadOnly": "false", "EventTime": at,
            "EventSource": "ec2.amazonaws.com", "Resources": [{"ResourceType": "AWS::EC2::SecurityGroup",
                                                              "ResourceName": "sg-1"}],
            "CloudTrailEvent": json.dumps(detail)}


def _params(start, end, token=None):
    p = {"LookupAttributes": WRITE_EVENTS_ONLY, "StartTime": start, "EndTime": end, "MaxResults": 50}
    if token:
        p["NextToken"] = token
    return p


def _client():
    session = AwsSession(region=REGION)
    return session, session.client("cloudtrail", REGION)


def test_incremental_overlap_dedup(store):
    aws, ct = _client()
    sleeps: list[float] = []
    try:
        with Stubber(ct) as stub:
            # 1회차(커서 없음): 24시간 백필, 2쪽
            t1 = T
            stub.add_response("lookup_events", {"Events": [_event("e1", t1 - dt.timedelta(minutes=5)),
                                                           _event("e2", t1 - dt.timedelta(minutes=10))],
                                                "NextToken": "page2"},
                              _params(t1 - dt.timedelta(hours=24), t1))
            stub.add_response("lookup_events", {"Events": [_event("e3", t1 - dt.timedelta(hours=3))]},
                              _params(t1 - dt.timedelta(hours=24), t1, "page2"))
            first = collect_cloudtrail(StubSession({"cloudtrail": ct}), store, [REGION], t1, sleep=sleeps.append)

            # 2회차(5분 뒤): 커서 − 20분부터 다시 읽는다 → 겹친 e1 이 다시 오고, 새 e4 가 온다
            t2 = T + dt.timedelta(minutes=5)
            stub.add_response("lookup_events", {"Events": [_event("e4", t2 - dt.timedelta(minutes=1)),
                                                           _event("e1", t1 - dt.timedelta(minutes=5))]},
                              _params(t1 - OVERLAP, t2))
            second = collect_cloudtrail(StubSession({"cloudtrail": ct}), store, [REGION], t2, sleep=sleeps.append)
            stub.assert_no_pending_responses()
    finally:
        aws.close()

    assert first == {"added": 3, "fetched": 3, "calls": 2, "errors": [], "gaps": 0}
    assert second["fetched"] == 2 and second["added"] == 1  # e1 은 EventId 로 걸러졌다
    ids = [r["event_id"] for r in store.query("SELECT event_id FROM events ORDER BY event_id")]
    assert ids == ["e1", "e2", "e3", "e4"]  # 중복 0건
    # 같은 리전 연속 호출 사이에는 2 TPS 를 지키려고 쉰다
    assert sleeps and all(0 < s <= 0.5 for s in sleeps)
    assert store.get_cursor(REGION)["cursor"] == t2.isoformat()


def test_page_budget_leaves_gap_then_resumes(store):
    """쪽 상한에 걸리면 못 읽은 오래된 구간을 gap 으로 남기고, 다음 회차에 이어 받는다."""
    aws, ct = _client()
    try:
        with Stubber(ct) as stub:
            old = T - dt.timedelta(hours=2)
            stub.add_response("lookup_events", {"Events": [_event("n1", T - dt.timedelta(minutes=1)),
                                                           _event("n2", old)], "NextToken": "more"},
                              _params(T - dt.timedelta(hours=24), T))
            first = collect_cloudtrail(StubSession({"cloudtrail": ct}), store, [REGION], T, max_pages=1,
                                       sleep=lambda _s: None)
            cur = store.get_cursor(REGION)
            assert first["gaps"] == 1 and cur["gap_start"] == (T - dt.timedelta(hours=24)).isoformat()

            t2 = T + dt.timedelta(minutes=5)
            gap_end = old + dt.timedelta(seconds=1)
            stub.add_response("lookup_events", {"Events": []}, _params(T - OVERLAP, t2))  # 최신 구간 먼저
            stub.add_response("lookup_events", {"Events": [_event("o1", T - dt.timedelta(hours=20))]},
                              _params(T - dt.timedelta(hours=24), gap_end))  # 그다음 밀린 구간
            second = collect_cloudtrail(StubSession({"cloudtrail": ct}), store, [REGION], t2, max_pages=5,
                                        sleep=lambda _s: None)
            stub.assert_no_pending_responses()
    finally:
        aws.close()
    assert second["added"] == 1 and second["gaps"] == 0
    assert store.get_cursor(REGION)["gap_start"] is None


def test_throttling_is_recorded_not_raised(store):
    aws, ct = _client()
    try:
        with Stubber(ct) as stub:
            stub.add_client_error("lookup_events", "ThrottlingException", "Rate exceeded")
            out = collect_cloudtrail(StubSession({"cloudtrail": ct}), store, [REGION], T, sleep=lambda _s: None)
    finally:
        aws.close()
    assert out["errors"] == [{"region": REGION, "error": "ThrottlingException"}]
    assert store.get_cursor(REGION) is None  # 첫 회가 실패하면 커서를 만들지 않는다(다음에 처음부터)


def _detail(identity: dict, ua: str = "aws-cli/2.17.0", console: bool = False) -> dict:
    d = {"userIdentity": identity, "userAgent": ua}
    if console:
        d["sessionCredentialFromConsole"] = "true"
    return d


def _role(name: str, session: str = "s") -> dict:
    return {"type": "AssumedRole", "arn": f"arn:aws:sts::123456789012:assumed-role/{name}/{session}"}


def test_classify_human_vs_automated(tmp_path):
    cases = {
        "sso_console": (_detail(SSO_ALICE, "AWS Internal", console=True), "human"),
        "iam_user": (_detail({"type": "IAMUser", "userName": "bob",
                              "arn": "arn:aws:iam::123456789012:user/bob"}), "human"),
        "root": (_detail({"type": "Root", "arn": "arn:aws:iam::123456789012:root"}, "Mozilla/5.0"), "human"),
        "service_linked": (_detail(_role("AWSServiceRoleForECS", "ecs")), "automated"),
        "aws_service": (_detail({"type": "AWSService", "invokedBy": "autoscaling.amazonaws.com"},
                                "autoscaling.amazonaws.com"), "automated"),
        "deploy_role": (_detail(_role("prod-deploy-role", "run-1"), "Boto3/1.43"), "automated"),
        "github_actions": (_detail(_role("github-actions-oidc", "GitHubActions"), "Boto3/1.43"), "automated"),
        "plain_role": (_detail(_role("ops-admin", "carol")), "unknown"),
    }
    for name, (detail, expected) in cases.items():
        assert classify(detail)["actor_class"] == expected, name
    assert classify(cases["root"][0])["is_root"] is True
    assert classify(cases["sso_console"][0])["actor"] == "alice"
    assert classify(cases["sso_console"][0])["via"] == "console"

    # 설정 파일로 덮어쓰기: 조직마다 역할 이름이 다르다
    (tmp_path / "config.toml").write_text(
        '[classify]\nhuman_roles = ["ops-*"]\nautomated_roles = ["AWSReservedSSO_Admin*"]\n', encoding="utf-8")
    rules = load(tmp_path).classify
    assert classify(cases["plain_role"][0], rules)["actor_class"] == "human"
    assert classify(cases["sso_console"][0], rules)["actor_class"] == "automated"  # 덮어쓰기가 기본 규칙보다 먼저
    # 덮어쓰기는 역할에만 — 루트·IAM 사용자 판정은 그대로
    assert classify(cases["root"][0], rules)["actor_class"] == "human"
    assert classify(cases["deploy_role"][0], ClassifyRules(human_roles=["prod-deploy-*"]))["actor_class"] == "human"
