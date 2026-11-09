"""AC-6 — 권한 점검은 AccessDenied·미구독을 오류가 아닌 '상태'로 표시하고, 어떤 경우에도 예외를 던지지 않는다."""

from __future__ import annotations

from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from awsglance.aws.permissions import CHECKS, check_permissions
from awsglance.aws.session import AwsSession

from .conftest import StubSession

REGION = "us-east-1"

# 수집기별로 Stubber 가 돌려줄 것: 성공 응답(dict) 또는 오류 코드(str)
PLAN = {
    "sts": [{}],
    "ec2": ["UnauthorizedOperation"],                    # EC2 의 '권한 없음' 코드
    "s3": [{"Buckets": []}],
    "iam": ["AccessDenied"],
    "rds": [{"DBInstances": []}],
    "lambda": [{"Functions": []}],
    "elbv2": [{"LoadBalancers": []}],
    "logs": ["AccessDeniedException"],
    "cloudtrail": [{"Events": []}, {"trailList": []}],    # lookup_events, describe_trails 순서
    "guardduty": [{"DetectorIds": []}],
    "securityhub": ["InvalidAccessException"],           # Security Hub 를 켜지 않은 계정 → 사용 불가
    "config": [{"ConfigurationRecordersStatus": []}],
    "s3control": ["NoSuchPublicAccessBlockConfiguration"],  # 설정 없음 = 읽기 권한은 있음
}


class Exploding:
    """네트워크가 끊긴 것처럼 예외를 던지는 클라이언트."""

    def __getattr__(self, _name):
        def call(**_kw):
            raise EndpointConnectionError(endpoint_url="https://access-analyzer.us-east-1.amazonaws.com")
        return call


def test_matrix_denied_and_unavailable():
    aws = AwsSession(region=REGION)
    clients, stubs = {}, []
    try:
        methods = {}
        for _name, _label, service, _g, method, _kw in CHECKS:
            methods.setdefault(service, []).append(method)
        for service, answers in PLAN.items():
            client = aws.client(service, REGION)
            stub = Stubber(client)
            for method, answer in zip(methods[service], answers, strict=True):
                if isinstance(answer, str):
                    stub.add_client_error(method, service_error_code=answer, http_status_code=403)
                else:
                    stub.add_response(method, answer)
            stub.activate()
            stubs.append(stub)
            clients[service] = client
        clients["accessanalyzer"] = Exploding()

        rows = check_permissions(StubSession(clients), REGION, "123456789012")  # 예외 없이 끝나야 한다

        for stub in stubs:
            stub.assert_no_pending_responses()
    finally:
        for stub in stubs:
            stub.deactivate()
        aws.close()

    status = {r["collector"]: r["status"] for r in rows}
    assert len(rows) == len(CHECKS)
    assert status["connection"] == "allowed"
    assert status["ec2"] == "denied" and status["iam"] == "denied" and status["logs"] == "denied"
    assert status["securityhub"] == "unavailable"
    assert status["s3_account"] == "allowed"
    assert status["accessanalyzer"] == "error"
    assert {status[k] for k in ("s3", "rds", "lambda", "elbv2", "cloudtrail", "trails", "guardduty", "config")} == {"allowed"}
    denied = next(r for r in rows if r["collector"] == "iam")
    assert denied["detail"] == "AccessDenied" and denied["region"] == "us-east-1"  # 전역 서비스는 us-east-1 에서


def test_every_check_uses_an_allowlisted_operation():
    """점검 자체도 허용 목록 안의 작업만 부른다(점검하다가 가드에 막히지 않게)."""
    from botocore import xform_name

    import botocore.session

    from awsglance.aws.guard import is_allowed

    bc = botocore.session.get_session()
    for _name, _label, service, _g, method, _kw in CHECKS:
        ops = {xform_name(op): op for op in bc.get_service_model(service).operation_names}
        assert is_allowed(service, ops[method]), (service, method)
