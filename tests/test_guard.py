"""AC-1 — 쓰기·비밀값 작업은 요청이 만들어지기 전에 거부된다(Stubber 가 걸려 있어도)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from botocore.stub import Stubber

from awsglance.aws.guard import ReadOnlyViolation
from awsglance.aws.session import AwsSession

SRC = Path(__file__).resolve().parent.parent / "src" / "awsglance"

# (서비스, 메서드, 인자, Stubber 에 넣어 둘 '성공' 응답)
FORBIDDEN_CALLS = [
    ("ec2", "terminate_instances", {"InstanceIds": ["i-0123456789abcdef0"]},
     {"TerminatingInstances": []}),
    ("secretsmanager", "get_secret_value", {"SecretId": "prod/db"},
     {"SecretString": "should-never-be-read"}),
    ("s3", "get_object", {"Bucket": "demo-bucket", "Key": "secret.txt"}, {}),
    ("ssm", "get_parameter", {"Name": "/prod/db/password", "WithDecryption": True},
     {"Parameter": {"Name": "/prod/db/password", "Value": "should-never-be-read"}}),
]


@pytest.mark.parametrize("service,method,params,stub_response", FORBIDDEN_CALLS,
                         ids=[f"{s}:{m}" for s, m, _, _ in FORBIDDEN_CALLS])
def test_write_and_secret_calls_blocked_before_request(service, method, params, stub_response):
    session = AwsSession(region="us-east-1")
    client = session.client(service, "us-east-1")
    # Stubber 는 '성공 응답'을 쥐고 기다린다. 가드가 늦게 걸려 있으면 이 응답이 소비되어 호출이 성공해 버린다.
    with Stubber(client) as stub:
        stub.add_response(method, stub_response, params)
        with pytest.raises(ReadOnlyViolation) as info:
            getattr(client, method)(**params)
        assert info.value.service == service
        # 요청이 만들어지지 않았다 = Stubber 의 응답이 그대로 남아 있다
        with pytest.raises(AssertionError):
            stub.assert_no_pending_responses()
    session.close()


def test_allowed_read_call_passes_guard_with_stubber():
    """반대쪽 확인: 허용 목록의 읽기 작업은 가드를 통과해 Stubber 응답을 받는다(가드가 전부 막는 것이 아님)."""
    session = AwsSession(region="us-east-1")
    client = session.client("ec2", "us-east-1")
    with Stubber(client) as stub:
        stub.add_response("describe_security_groups", {"SecurityGroups": []}, {})
        assert client.describe_security_groups()["SecurityGroups"] == []
        stub.assert_no_pending_responses()
    session.close()


def test_no_direct_boto3_clients_outside_session():
    """훅이 없는 우회로 금지: boto3.client(...)·boto3.resource(...) 는 aws/session.py 밖에서 쓰지 않는다."""
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "session.py" and path.parent.name == "aws":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bboto3\.(client|resource)\(", text) or re.search(r"\bboto3\.session\.Session\(", text):
            offenders.append(str(path.relative_to(SRC)))
    assert offenders == []
