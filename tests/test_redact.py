"""AC-7 — 비밀값은 DB 에 쓰기 전에 가려진다.

읽기 API 도 비밀을 돌려준다: Lambda ListFunctions 는 환경 변수 '값'을, CloudTrail 요청 파라미터에는 사용자가 넣은
비밀번호·키가 들어 있을 수 있다. 실제 수집기에 Stubber 응답을 넣고, DB 전체를 덤프해 비밀 문자열이 없는지 본다.
"""

from __future__ import annotations

import datetime as dt
import json

from botocore.stub import Stubber

from awsglance.aws.session import AwsSession
from awsglance.collect.cloudtrail import collect_cloudtrail
from awsglance.collect.inventory import collect_iam, collect_lambda
from awsglance.redact import mask_text, redact

from .conftest import StubSession

REGION = "us-east-1"
NOW = dt.datetime(2026, 11, 9, 9, 0, tzinfo=dt.timezone.utc)

# 저장되면 안 되는 값들(모두 지어낸 가짜 값)
SECRETS = [
    "hunter2-db-password-value",
    "sk-live-abcdefghijklmnopqrstuvwx",
    "db-primary.internal.example",
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "P@ssw0rd-in-request",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "s3cr3t-conn-pw",
    "AKIAEXAMPLEFULLKEYID9",
]


def _dump(store) -> str:
    with store._lock:
        return "\n".join(store.conn.iterdump())


def test_lambda_env_and_trail_params_masked(store):
    aws = AwsSession(region=REGION)
    lam, iam, ct = aws.client("lambda", REGION), aws.client("iam", REGION), aws.client("cloudtrail", REGION)
    detail = {
        "eventID": "ev-1", "eventName": "CreateDBInstance", "eventTime": "2026-11-09T08:55:00Z",
        "userIdentity": {"type": "IAMUser", "userName": "bob", "arn": "arn:aws:iam::123456789012:user/bob"},
        "userAgent": "aws-cli/2.17.0",
        "requestParameters": {
            "dBInstanceIdentifier": "app-db",
            "masterUserPassword": "P@ssw0rd-in-request",
            "environment": {"variables": {"GITHUB_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"}},
            "description": "rotated key AKIAIOSFODNN7EXAMPLE secret wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "connection": "postgres://admin:s3cr3t-conn-pw@db:5432/app",
        },
    }
    try:
        with Stubber(lam) as ls, Stubber(iam) as ist, Stubber(ct) as cs:
            ls.add_response("list_functions", {"Functions": [{
                "FunctionName": "api", "Runtime": "python3.12",
                "Environment": {"Variables": {"DB_PASSWORD": "hunter2-db-password-value",
                                              "API_KEY": "sk-live-abcdefghijklmnopqrstuvwx",
                                              "DB_HOST": "db-primary.internal.example"}}}]})
            ls.add_response("list_function_url_configs", {"FunctionUrlConfigs": []}, {"FunctionName": "api"})
            ist.add_response("list_users", {"Users": [{"Path": "/", "UserName": "bob", "UserId": "AIDAEXAMPLEUSERID001",
                                                       "Arn": "arn:aws:iam::123456789012:user/bob", "CreateDate": NOW}]})
            ist.add_response("list_access_keys", {"AccessKeyMetadata": [{
                "UserName": "bob", "AccessKeyId": "AKIAEXAMPLEFULLKEYID9", "Status": "Active", "CreateDate": NOW}]},
                {"UserName": "bob"})
            ist.add_response("list_roles", {"Roles": []})
            cs.add_response("lookup_events", {"Events": [{
                "EventId": "ev-1", "EventName": "CreateDBInstance", "EventTime": NOW - dt.timedelta(minutes=5),
                "EventSource": "rds.amazonaws.com", "ReadOnly": "false", "CloudTrailEvent": json.dumps(detail)}]})

            session = StubSession({"lambda": lam, "iam": iam, "cloudtrail": ct})
            resources = collect_lambda(session, REGION) + collect_iam(session)
            store.save_inventory({r["key"]: r for r in resources}, [], [], NOW)
            collect_cloudtrail(session, store, [REGION], NOW, sleep=lambda _s: None)
    finally:
        aws.close()

    dump = _dump(store)
    for secret in SECRETS:
        assert secret not in dump, f"secret leaked into DB: {secret}"
    # 키 이름은 남는다(무엇이 설정돼 있는지는 보여 준다)
    fn = store.current_resources()[f"lambda_function:{REGION}:api"]
    assert fn["props"]["env_keys"] == ["API_KEY", "DB_HOST", "DB_PASSWORD"]
    key = next(r for r in store.current_resources().values() if r["type"] == "iam_access_key")
    assert key["name"] == "bob AKIA…YID9"  # 액세스 키 ID 는 앞 4자·끝 4자만
    # 요청 파라미터: 비밀 이름의 값은 ***, 이름이 평범한 곳의 비밀 모양 문자열도 ***
    req = store.events_since(NOW - dt.timedelta(days=1))[0]["request"]
    assert req["masterUserPassword"] == "***"
    assert req["environment"]["variables"]["GITHUB_TOKEN"] == "***"
    assert req["dBInstanceIdentifier"] == "app-db"  # 비밀이 아닌 값은 그대로
    assert "***" in req["description"] and "rotated key" in req["description"]
    assert req["connection"] == "postgres://admin:***@db:5432/app"


def test_mask_text_patterns_and_safe_names():
    assert mask_text("token=abc123def") == "token=***"
    assert mask_text("xoxb-1234567890-abcdefghij") == "***"
    # 가짜 JWT 는 조각을 이어 만든다 — 소스에 시크릿 모양 리터럴을 두지 않기 위해
    fake_jwt = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0", "x" * 20 + "Abc_123-45"])
    assert mask_text(fake_jwt) == "***"
    # 비밀의 '이름·위치'는 비밀이 아니다 — 남겨야 무엇이 바뀌었는지 알 수 있다
    out = redact({"secretId": "prod/db", "secretArn": "arn:aws:secretsmanager:us-east-1:1:secret:x",
                  "password": "", "groupId": "sg-1"})
    assert out == {"secretId": "prod/db", "secretArn": "arn:aws:secretsmanager:us-east-1:1:secret:x",
                   "password": "", "groupId": "sg-1"}


def test_demo_fixture_secrets_never_reach_db(store):
    """연습 모드 예제에 일부러 넣은 가짜 비밀값도 실제 코드 경로에서 가려진다."""
    from awsglance.demo import load_demo
    from awsglance.demo.fake_clients import load_fixture

    load_demo(store)
    dump = _dump(store)
    raw_values = []
    for region in load_fixture("inventory.json")["services"]["lambda"].values():
        for f in region.get("ListFunctions", {}).get("Functions", []):
            env = (f.get("Environment") or {}).get("Variables", {})
            # 비밀 이름의 값만(호스트 이름처럼 다른 곳—요청 설명문 등—에 정당하게 나올 수 있는 값은 제외)
            raw_values += [v for k, v in env.items() if any(w in k for w in ("PASSWORD", "KEY", "TOKEN", "SECRET"))]
    assert raw_values, "demo fixture should contain example secret env values"
    for v in raw_values:
        assert str(v) not in dump
