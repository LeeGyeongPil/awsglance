"""AC-11 — 자원 상세의 '관련 CloudTrail' 은 자원 ID·ARN 이 정확히 같은 이벤트만 보여 준다.

이전에는 이름을 부분 문자열로 찾아서 보안 그룹 'demo-web' 에 Lambda 'demo-webhook' 의 배포 이벤트가 붙었다.
여기서는 (1) 연습 계정 전 자원 (2) 'web'·'api' 같은 짧은 이름이 여러 종류·리전에 겹친 합성 계정
(3) 정확히 맞춰 볼 수 없는 종류(IAM 액세스 키)를 확인한다.

오연결 검사는 related.match 를 쓰지 않는 독립 검사다: 붙은 이벤트마다 resources[].name 이나 요청 파라미터 값 중
하나가 자원 ID/ARN 과 '완전히 같은 값' 이어야 한다.
"""

from __future__ import annotations

import datetime as dt
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from awsglance import related
from awsglance.demo import load_demo
from awsglance.export import collect_snapshot
from awsglance.rules import Context, evaluate
from awsglance.web.app import create_app

LOCAL = "http://127.0.0.1:8730"
NOW = dt.datetime(2026, 11, 9, 9, 0, tzinfo=dt.timezone.utc)


# ---- 독립 검사 도구 -----------------------------------------------------------------

def _leaves(obj):
    """요청 파라미터 안의 모든 문자열 값(키 이름과 상관없이)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaves(v)
    elif isinstance(obj, str):
        yield obj


def _exact_ids(resource: dict) -> set[str]:
    out = {resource["id"]}
    if resource["props"].get("arn"):
        out.add(resource["props"]["arn"])
    return out


def _false_links(resource: dict, events: list[dict]) -> list[str]:
    """자원 ID/ARN 이 이벤트 어디에도 '정확한 값' 으로 들어 있지 않은데 붙은 이벤트(= 오연결)."""
    ids = _exact_ids(resource)
    bad = []
    for e in events:
        named = {x.get("name") for x in e["resources"]}
        if not (ids & named) and not (ids & set(_leaves(e["request"]))):
            bad.append(f"{resource['key']} <- {e['name']} {e['request']}")
    return bad


def _detail(client, key: str) -> dict:
    return client.get("/api/resources/" + quote(key, safe="")).json()


def _function_names(events: list[dict]) -> set[str]:
    return {e["request"].get("functionName") for e in events if e["source"] == "lambda.amazonaws.com"}


@pytest.fixture
def demo_store(store):
    load_demo(store)
    return store


# ---- (1) 연습 계정 ----------------------------------------------------------------

def test_demo_account_has_no_false_links(demo_store):
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        assert c.get("/api/resources").json()["total"] >= 47
        items = c.get("/api/resources?deleted=true").json()["items"]  # 삭제된 자원까지 전부
        details = {r["key"]: _detail(c, r["key"]) for r in items}

    bad = [b for d in details.values() for b in _false_links(d["resource"], d["events"])]
    assert bad == [], bad  # 오연결 0건

    sg_web = details["security_group:ap-northeast-2:sg-0demoweb0000002"]
    assert sg_web["resource"]["name"] == "demo-web"
    assert sg_web["events_match"] == "exact"
    assert [e["name"] for e in sg_web["events"]] == ["AuthorizeSecurityGroupIngress"]
    assert sg_web["events"][0]["request"]["groupId"] == "sg-0demoweb0000002"
    assert "demo-webhook" not in _function_names(sg_web["events"])  # 이름이 겹치는 Lambda 이벤트가 섞이지 않는다

    # 'demo-db' 라는 이름의 RDS 와 SG 에 Lambda 'demo-thumbnail'(환경 변수 DB_HOST=demo-db...) 이벤트가 붙지 않는다
    for key in ("rds_instance:ap-northeast-2:demo-db", "security_group:ap-northeast-2:sg-0demodb00000003"):
        assert "demo-thumbnail" not in _function_names(details[key]["events"]), key
        assert details[key]["events"] == [], key

    # 놓침 없음: Lambda demo-webhook 은 자기 이벤트 3건을 모두 보여 준다
    webhook = details["lambda_function:ap-northeast-2:demo-webhook"]
    assert len(webhook["events"]) == 3
    assert _function_names(webhook["events"]) == {"demo-webhook"}
    times = [e["time"] for e in webhook["events"]]
    assert times == sorted(times, reverse=True)  # 최신순


def test_export_snapshot_carries_the_same_exact_links(demo_store):
    """서버 없이 여는 정적 사본도 같은 응답(events_match 포함)을 담는다."""
    snap = collect_snapshot(demo_store)["api"]
    key = "security_group:ap-northeast-2:sg-0demoweb0000002"
    detail = snap["/api/resources/" + quote(key, safe="")]
    assert detail["events_match"] == "exact"
    assert [e["name"] for e in detail["events"]] == ["AuthorizeSecurityGroupIngress"]


# ---- (2) 짧고 흔한 이름이 겹친 합성 계정 ----------------------------------------------

def _res(rtype, region, rid, name, props=None):
    return {"key": f"{rtype}:{region}:{rid}", "type": rtype, "region": region, "id": rid, "name": name,
            "props": props or {}, "tags": {}}


def _ev(event_id, region, source, name, request=None, resources=None, minutes_ago=60):
    return {"event_id": event_id, "region": region, "time": (NOW - dt.timedelta(minutes=minutes_ago)).isoformat(),
            "name": name, "source": source, "actor": "alice", "actor_class": "human", "via": "console",
            "is_root": False, "reason": "test", "error_code": None, "request": request or {},
            "resources": resources or [], "read_only": False}


SEOUL, VIRGINIA = "ap-northeast-2", "us-east-1"
SG_WEB = "sg-0aaa0000000web1"
SYNTH_RESOURCES = [
    _res("lambda_function", SEOUL, "web", "web"),
    _res("lambda_function", VIRGINIA, "web", "web"),                     # 같은 이름, 다른 리전
    _res("security_group", SEOUL, SG_WEB, "web", {"group_name": "web"}),   # 그룹 이름이 'web'
    _res("ec2_instance", SEOUL, "i-0aaa000000000001", "web"),             # Name 태그가 'web'
    _res("s3_bucket", "global", "web-assets", "web-assets"),
    _res("rds_instance", SEOUL, "api", "api"),
    _res("iam_user", "global", "web", "web", {"arn": "arn:aws:iam::123456789012:user/web"}),
    _res("iam_role", "global", "api", "api", {"arn": "arn:aws:iam::123456789012:role/api"}),
    _res("log_group", SEOUL, "/aws/lambda/web_1", "/aws/lambda/web_1"),   # LIKE 의 '_' 와일드카드 확인용
    _res("iam_access_key", "global", "web/0001", "web AKIA…0001", {"user": "web", "status": "Active"}),
]
LAMBDA, EC2, S3, RDS, IAM, LOGS = (f"{s}.amazonaws.com" for s in ("lambda", "ec2", "s3", "rds", "iam", "logs"))
SYNTH_EVENTS = [
    _ev("fn-web-seoul", SEOUL, LAMBDA, "UpdateFunctionCode20150331v2", {"functionName": "web"},
        [{"type": "AWS::Lambda::Function", "name": "web"}]),
    _ev("fn-web-virginia", VIRGINIA, LAMBDA, "UpdateFunctionCode20150331v2", {"functionName": "web"},
        [{"type": "AWS::Lambda::Function", "name": "web"}]),
    _ev("fn-webhook", SEOUL, LAMBDA, "UpdateFunctionCode20150331v2", {"functionName": "webhook"},
        [{"type": "AWS::Lambda::Function", "name": "webhook"}]),
    _ev("fn-api", SEOUL, LAMBDA, "UpdateFunctionCode20150331v2", {"functionName": "api"},
        [{"type": "AWS::Lambda::Function", "name": "api"}]),
    # 그룹 '이름' 으로만 부른 요청 — 이름은 식별자가 아니므로 SG 에 붙이지 않는다
    _ev("sg-by-name", SEOUL, EC2, "AuthorizeSecurityGroupIngress", {"groupName": "web"}),
    # 종류가 null 이어도 고유 ID(sg-...)면 인정
    _ev("sg-by-id", SEOUL, EC2, "AuthorizeSecurityGroupIngress", {"groupId": SG_WEB},
        [{"type": None, "name": SG_WEB}]),
    # 종류가 null 인데 이름이 'web' — 어느 자원인지 확신할 수 없다
    _ev("null-type-web", SEOUL, EC2, "CreateTags", {}, [{"type": None, "name": "web"}]),
    _ev("tag-instance", SEOUL, EC2, "CreateTags",
        {"resourcesSet": {"items": [{"resourceId": "i-0aaa000000000001"}]},
         "tagSet": {"items": [{"key": "Name", "value": "web"}]}},
        [{"type": "AWS::EC2::Instance", "name": "i-0aaa000000000001"}]),
    _ev("bucket-web", SEOUL, S3, "CreateBucket", {"bucketName": "web"}, [{"type": "AWS::S3::Bucket", "name": "web"}]),
    _ev("bucket-web-assets-backup", SEOUL, S3, "CreateBucket", {"bucketName": "web-assets-backup"},
        [{"type": "AWS::S3::Bucket", "name": "web-assets-backup"}]),
    _ev("rds-api-replica", SEOUL, RDS, "CreateDBInstanceReadReplica",
        {"dBInstanceIdentifier": "api-replica", "sourceDBInstanceIdentifier": "api"},
        [{"type": "AWS::RDS::DBInstance", "name": "api-replica"}]),
    _ev("iam-user-web", VIRGINIA, IAM, "CreateLoginProfile", {"userName": "web"},
        [{"type": "AWS::IAM::User", "name": "web"}]),
    _ev("iam-role-api-arn", VIRGINIA, IAM, "UpdateAssumeRolePolicy", {"roleName": "api"},
        [{"type": "AWS::IAM::Role", "name": "arn:aws:iam::123456789012:role/api"}]),
    _ev("iam-key-web", VIRGINIA, IAM, "UpdateAccessKey", {"userName": "web", "accessKeyId": "AKIA…0001"}),
    _ev("log-web_1", SEOUL, LOGS, "PutRetentionPolicy", {"logGroupName": "/aws/lambda/web_1"},
        [{"type": "AWS::Logs::LogGroup", "name": "/aws/lambda/web_1"}]),
    _ev("log-webX1", SEOUL, LOGS, "PutRetentionPolicy", {"logGroupName": "/aws/lambda/webX1"},
        [{"type": "AWS::Logs::LogGroup", "name": "/aws/lambda/webX1"}]),
]
# 자원 키 → 붙어야 하는 이벤트 전부(이것보다 많으면 오연결, 적으면 놓침)
EXPECTED = {
    f"lambda_function:{SEOUL}:web": {"fn-web-seoul"},
    f"lambda_function:{VIRGINIA}:web": {"fn-web-virginia"},
    f"security_group:{SEOUL}:{SG_WEB}": {"sg-by-id"},
    f"ec2_instance:{SEOUL}:i-0aaa000000000001": {"tag-instance"},
    "s3_bucket:global:web-assets": set(),
    f"rds_instance:{SEOUL}:api": set(),
    "iam_user:global:web": {"iam-user-web", "iam-key-web"},
    "iam_role:global:api": {"iam-role-api-arn"},
    f"log_group:{SEOUL}:/aws/lambda/web_1": {"log-web_1"},
    "iam_access_key:global:web/0001": set(),
}


@pytest.fixture
def synth_store(store):
    store.save_inventory({r["key"]: r for r in SYNTH_RESOURCES}, [], [], NOW)
    assert store.insert_events(SYNTH_EVENTS) == len(SYNTH_EVENTS)
    return store


def test_short_common_names_do_not_cross_link(synth_store):
    with TestClient(create_app(synth_store), base_url=LOCAL) as c:
        details = {r["key"]: _detail(c, r["key"]) for r in SYNTH_RESOURCES}
    assert set(EXPECTED) == set(details)
    for key, d in details.items():
        assert _false_links(d["resource"], d["events"]) == [], key
        assert {e["event_id"] for e in d["events"]} == EXPECTED[key], key


def test_match_is_exact_not_partial_case_or_prefix():
    """순수 함수 규칙: 부분 문자열·대소문자·접두·다른 종류·다른 출처·다른 리전은 모두 불일치."""
    fn = _res("lambda_function", SEOUL, "demo-web", "demo-web")
    sg = _res("security_group", SEOUL, "sg-0demoweb0000002", "demo-web")

    def ev(**kw):
        base = {"region": SEOUL, "source": LAMBDA, "resources": [], "request": {}}
        return {**base, **kw}

    assert related.match(fn, ev(request={"functionName": "demo-web"}))
    assert not related.match(fn, ev(request={"functionName": "demo-webhook"}))          # 부분 문자열
    assert not related.match(fn, ev(request={"functionName": "DEMO-WEB"}))              # 대소문자
    assert not related.match(fn, ev(request={"functionName": "demo-we"}))               # 접두
    assert not related.match(fn, ev(request={"description": "demo-web"}))              # ID 키가 아님
    assert not related.match(fn, ev(source=EC2, request={"functionName": "demo-web"}))  # 다른 서비스
    assert not related.match(fn, ev(region=VIRGINIA, request={"functionName": "demo-web"}))  # 다른 리전
    assert not related.match(fn, ev(resources=[{"type": "AWS::EC2::SecurityGroup", "name": "demo-web"}]))
    assert related.match(fn, ev(resources=[{"type": "AWS::Lambda::Function", "name": "demo-web"}]))
    # 보안 그룹은 그룹 이름이 아니라 그룹 ID 로만
    assert not related.match(sg, ev(source=EC2, request={"groupName": "demo-web"}))
    assert related.match(sg, ev(source=EC2, request={"ipPermissions": {"items": [
        {"groups": {"items": [{"groupId": "sg-0demoweb0000002"}]}}]}}))  # 중첩·목록 안의 ID 키
    assert related.match(sg, ev(source="other", resources=[{"type": None, "name": "sg-0demoweb0000002"}]))
    assert not related.match(sg, ev(resources=[{"type": None, "name": "demo-web"}]))  # null 종류 + 이름


def test_non_matching_candidates_do_not_push_out_real_events(store):
    """SQL 후보 중 판정에서 떨어지는 이벤트가 많아도 진짜 관련 이벤트를 놓치지 않고, 최대 50건만 준다."""
    fn = _res("lambda_function", SEOUL, "web", "web")
    store.save_inventory({fn["key"]: fn}, [], [], NOW)
    # 따옴표째 "web" 은 들어 있지만 ID 키가 아닌 값(설명) — 후보로는 걸리지만 연결되면 안 된다. 더 최신이다
    noise = [_ev(f"noise-{i:03d}", SEOUL, LAMBDA, "TagResource", {"description": "web"}, minutes_ago=i)
             for i in range(1, 251)]
    real = [_ev(f"real-{i:03d}", SEOUL, LAMBDA, "UpdateFunctionCode20150331v2", {"functionName": "web"},
                minutes_ago=1000 + i) for i in range(60)]
    store.insert_events(noise + real)
    with TestClient(create_app(store), base_url=LOCAL) as c:
        events = _detail(c, fn["key"])["events"]
    assert len(events) == 50
    assert all(e["event_id"].startswith("real-") for e in events)
    assert events[0]["event_id"] == "real-000"  # 가장 최신부터


# ---- (3) 정확히 맞춰 볼 수 없는 종류 ------------------------------------------------

def test_unsupported_type_links_nothing(demo_store):
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        keys = [r["key"] for r in c.get("/api/resources?type=iam_access_key").json()["items"]]
        assert keys, "demo account has access keys"
        for key in keys:
            d = _detail(c, key)
            assert d["events"] == [] and d["events_match"] == "unsupported", key
        # 지원하는 종류는 exact
        sg = _detail(c, "security_group:ap-northeast-2:sg-0demoweb0000002")
        assert sg["events_match"] == "exact"

    key = _res("iam_access_key", "global", "web/0001", "web AKIA…0001", {"user": "web"})
    assert related.support("iam_access_key") == "unsupported"
    assert related.support("not_a_known_type") == "unsupported"  # 표에 없는 새 종류도 연결하지 않는다
    # 요청에 키 표시값이 그대로 있어도 연결하지 않는다
    assert not related.match(key, {"region": VIRGINIA, "source": IAM, "request": {"accessKeyId": "web/0001"},
                                   "resources": [{"type": "AWS::IAM::AccessKey", "name": "web/0001"}]})


# ---- 같은 종류의 결함: 발견 사항의 자원 연결도 이름으로 하지 않는다 ------------------------

def test_sg_event_finding_links_resource_by_group_id_only():
    world = {"ipPermissions": {"items": [{"ipRanges": {"items": [{"cidrIp": "0.0.0.0/0"}]}}]}}
    events = [_ev("by-id", SEOUL, EC2, "AuthorizeSecurityGroupIngress", {"groupId": SG_WEB, **world}),
              _ev("by-name", SEOUL, EC2, "AuthorizeSecurityGroupIngress", {"groupName": "web", **world})]
    hits = [h for h in evaluate(Context(resources={}, posture={}, events=events, now=NOW))
            if h["rule_id"] == "sg-opened-world-event"]
    by_target = {h["target"]: h["resource_key"] for h in hits}
    assert by_target == {f"sg-event:{SEOUL}:{SG_WEB}": f"security_group:{SEOUL}:{SG_WEB}",
                         f"sg-event:{SEOUL}:web": None}
