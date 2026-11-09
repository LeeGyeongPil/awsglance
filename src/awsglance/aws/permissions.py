"""권한 점검 — 수집기마다 대표 읽기 작업을 한 번씩 불러 허용/거부/사용 불가를 표로 만든다.

AccessDenied 나 '구독 안 함'은 오류가 아니라 '상태'다. 이 함수는 어떤 경우에도 예외를 밖으로 던지지 않는다.
"""

from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

from .guard import ReadOnlyViolation

# AWS 가 "권한 없음"을 알리는 오류 코드들(서비스마다 이름이 다르다)
DENIED_CODES = {
    "AccessDenied", "AccessDeniedException", "UnauthorizedOperation",
    "AuthorizationError", "UnauthorizedException", "AuthFailure",
}
# 기능을 켜지 않았거나 지원 플랜·옵트인이 필요한 경우 — 권한 문제가 아니다
UNAVAILABLE_CODES = {
    "InvalidAccessException", "SubscriptionRequiredException", "OptInRequired",
    "NoSuchPublicAccessBlockConfiguration",
}

# (수집기 이름, 설명, 서비스, 전역 리전 사용 여부, 메서드, 인자)
CHECKS = [
    ("connection", "계정 연결(GetCallerIdentity)", "sts", True, "get_caller_identity", {}),
    ("ec2", "EC2·VPC·서브넷·보안 그룹", "ec2", False, "describe_security_groups", {"MaxResults": 5}),
    ("s3", "S3 버킷 목록", "s3", True, "list_buckets", {}),
    ("iam", "IAM 사용자·액세스 키·역할", "iam", True, "list_users", {"MaxItems": 1}),
    ("rds", "RDS 데이터베이스", "rds", False, "describe_db_instances", {"MaxRecords": 20}),
    ("lambda", "Lambda 함수", "lambda", False, "list_functions", {"MaxItems": 1}),
    ("elbv2", "로드 밸런서", "elbv2", False, "describe_load_balancers", {"PageSize": 1}),
    ("logs", "CloudWatch 로그 그룹", "logs", False, "describe_log_groups", {"limit": 1}),
    ("cloudtrail", "CloudTrail 변경 이력(LookupEvents)", "cloudtrail", False, "lookup_events", {"MaxResults": 1}),
    ("trails", "CloudTrail 트레일 설정", "cloudtrail", True, "describe_trails", {}),
    ("guardduty", "GuardDuty", "guardduty", False, "list_detectors", {}),
    ("securityhub", "Security Hub", "securityhub", False, "describe_hub", {}),
    ("config", "AWS Config", "config", False, "describe_configuration_recorder_status", {}),
    ("accessanalyzer", "IAM Access Analyzer", "accessanalyzer", False, "list_analyzers", {}),
    ("s3_account", "계정 수준 S3 공개 차단", "s3control", True, "get_public_access_block", {"AccountId": "{account}"}),
]


def _classify_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "") or ""
        if code in DENIED_CODES:
            return "denied", code
        if code in UNAVAILABLE_CODES:
            # 계정 공개 차단이 '설정 안 됨'이면 읽기 권한은 있는 것이다
            if code == "NoSuchPublicAccessBlockConfiguration":
                return "allowed", code
            return "unavailable", code
        return "error", code or type(exc).__name__
    if isinstance(exc, ReadOnlyViolation):
        return "blocked", str(exc)
    return "error", type(exc).__name__


def check_permissions(session, region: str, account: str) -> list[dict]:
    """수집기별 결과 행 목록. status ∈ allowed|denied|unavailable|error."""
    rows = []
    for name, label, service, use_global, method, kwargs in CHECKS:
        call_region = "us-east-1" if use_global else region
        args = {k: (v.format(account=account) if isinstance(v, str) else v) for k, v in kwargs.items()}
        status, detail = "allowed", ""
        try:
            getattr(session.client(service, call_region), method)(**args)
        except (ClientError, BotoCoreError, ReadOnlyViolation) as exc:
            status, detail = _classify_error(exc)
        except Exception as exc:  # 점검 화면은 어떤 오류로도 죽지 않는다
            status, detail = "error", type(exc).__name__
        rows.append({"collector": name, "label": label, "service": service,
                     "operation": method, "region": call_region, "status": status, "detail": detail})
    return rows
