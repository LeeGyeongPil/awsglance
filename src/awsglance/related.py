"""자원 상세의 '관련 CloudTrail' 판정 — 자원 ID·ARN 이 **정확히 같은** 이벤트만 연결한다.

원칙: 틀린 것을 보이느니 덜 보인다.
- 이름 부분 일치는 하지 않는다. 'demo-web' 이 'demo-webhook' 안에 들어 있다고 같은 자원이 아니다.
- 표시 이름(Name 태그, 보안 그룹 이름, 액세스 키 표시명)으로는 연결하지 않는다. 실제 계정에는 'web'·'api' 같은
  짧은 이름이 여러 종류·여러 리전에 겹쳐 있다.
- 정확히 맞춰 볼 수 없는 종류(IAM 액세스 키 — 전체 키 ID 를 저장하지 않는다)는 연결하지 않는다(unsupported).
- 그래서 놓치는 이벤트(거짓 음성)는 있을 수 있다. 오연결(거짓 양성)은 0 이 목표다. 화면에 한 줄로 밝힌다.

이벤트가 자원 R 과 관련 있다고 보는 조건(둘 중 하나, 그리고 리전 조건):
  (A) event.resources 의 항목 x 가  x.name ∈ V(R)  그리고  x.type == 표의 CloudTrail 종류.
      x.type 이 null 이면(CloudTrail 이 종류를 못 정한 경우) x.name 이 AWS 가 만든 고유 ID(sg-·i-·vpc-·subnet-)
      또는 'arn:' 으로 시작할 때만 인정한다.
  (B) event.source 가 표의 이벤트 출처와 같고, 요청 파라미터(중첩 포함)에서 표의 ID 키 값이 V(R) 원소와 완전히 같다.
  리전: 리전 자원은 event.region == R.region 이어야 한다. 전역 자원(S3 버킷·IAM)은 리전을 보지 않는다.
  V(R) = {R.id} ∪ {R.props.arn (있을 때)}

근거: CloudTrail Resource 형식 — ResourceName 은 사용자가 만든 이름 또는 EC2 인스턴스의 "i-1234567" 같은 ID,
ResourceType 은 "종류를 정할 수 없으면 null" (https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_Resource.html,
2026-11-09 확인).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .collect.inventory import GLOBAL_TYPES


@dataclass(frozen=True)
class Mapping:
    trail_type: str           # CloudTrail Resource.ResourceType 값
    source: str | None        # 요청 파라미터를 볼 이벤트 출처. None 이면 요청 파라미터는 보지 않는다
    keys: tuple[str, ...]     # 요청 파라미터 중 '이 자원의 ID' 를 담는 키 이름


# 자원 종류 → 맞춰 볼 방법. 여기에 없는 종류는 연결하지 않는다(unsupported).
# 새 자원 종류를 인벤토리에 더하면 이 표에 행을 넣거나, 넣지 않아 unsupported 로 둔다.
TABLE: dict[str, Mapping] = {
    "security_group": Mapping("AWS::EC2::SecurityGroup", "ec2.amazonaws.com", ("groupId",)),
    "ec2_instance": Mapping("AWS::EC2::Instance", "ec2.amazonaws.com", ("instanceId",)),
    "vpc": Mapping("AWS::EC2::VPC", "ec2.amazonaws.com", ("vpcId",)),
    "subnet": Mapping("AWS::EC2::Subnet", "ec2.amazonaws.com", ("subnetId",)),
    "s3_bucket": Mapping("AWS::S3::Bucket", "s3.amazonaws.com", ("bucketName",)),
    "lambda_function": Mapping("AWS::Lambda::Function", "lambda.amazonaws.com", ("functionName",)),
    "rds_instance": Mapping("AWS::RDS::DBInstance", "rds.amazonaws.com", ("dBInstanceIdentifier",)),
    "log_group": Mapping("AWS::Logs::LogGroup", "logs.amazonaws.com", ("logGroupName",)),
    "iam_user": Mapping("AWS::IAM::User", "iam.amazonaws.com", ("userName",)),
    "iam_role": Mapping("AWS::IAM::Role", "iam.amazonaws.com", ("roleName",)),
    # 인벤토리에 로드 밸런서 ARN 을 저장하지 않으므로 요청 파라미터는 보지 않는다((A) 만)
    "load_balancer": Mapping("AWS::ElasticLoadBalancingV2::LoadBalancer", None, ()),
    # "iam_access_key" 는 일부러 없다 — 전체 키 ID 를 저장하지 않아 정확히 비교할 수 없다
}

# 종류가 null 인 항목이라도 이 모양이면 AWS 가 만든 고유 값이라 이름 겹침이 없다
UNIQUE_ID_PREFIXES = ("sg-", "i-", "vpc-", "subnet-", "arn:")


def support(resource_type: str) -> str:
    """'exact' — 정확 일치로 연결한다 / 'unsupported' — 이 종류는 연결하지 않는다."""
    return "exact" if resource_type in TABLE else "unsupported"


def values(resource: dict) -> set[str]:
    """V(R): 자원을 가리키는 '정확한' 값들 — ID 와 (있으면) ARN. 표시 이름은 넣지 않는다."""
    out = {resource["id"]}
    arn = (resource.get("props") or {}).get("arn")
    if isinstance(arn, str) and arn:
        out.add(arn)
    return out


def _request_values(obj, keys: tuple[str, ...]):
    """요청 파라미터를 중첩까지 훑어, 키 이름이 keys 에 있는 문자열 값(또는 문자열 목록의 각 항목)을 내놓는다.

    예: {"instancesSet": {"items": [{"instanceId": "i-0abc"}]}} → "i-0abc"
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys:
                if isinstance(v, str):
                    yield v
                elif isinstance(v, list):
                    yield from (x for x in v if isinstance(x, str))
            if isinstance(v, (dict, list)):
                yield from _request_values(v, keys)
    elif isinstance(obj, list):
        for v in obj:
            yield from _request_values(v, keys)


def match(resource: dict, event: dict) -> bool:
    """이 이벤트가 이 자원을 '정확히' 가리키는가. 부분 문자열·대소문자 무시·접두 비교는 하지 않는다.

    resource: {"type", "region", "id", "props"}  (API 의 자원 행)
    event:    {"region", "source", "resources": [{"type", "name"}], "request": {...}}  (JSON 을 푼 이벤트 행)
    """
    m = TABLE.get(resource["type"])
    if m is None:
        return False  # unsupported 종류는 아무 이벤트와도 연결하지 않는다
    # 리전 자원은 같은 리전의 이벤트만(같은 이름의 Lambda 가 두 리전에 있을 수 있다)
    if resource["type"] not in GLOBAL_TYPES and event.get("region") != resource["region"]:
        return False
    v = values(resource)

    # (A) CloudTrail 이 이벤트에 붙여 준 대상 자원 목록
    for x in event.get("resources") or []:
        name, rtype = x.get("name"), x.get("type")
        if name not in v:
            continue
        if rtype == m.trail_type:
            return True
        if rtype is None and name.startswith(UNIQUE_ID_PREFIXES):
            return True  # 종류를 못 정했어도 고유 ID·ARN 이면 겹칠 수 없다

    # (B) 요청 파라미터의 ID 키 — 같은 서비스(이벤트 출처)일 때만
    if m.source and event.get("source") == m.source:
        request = event.get("request") or {}
        if any(val in v for val in _request_values(request, m.keys)):
            return True
    return False


def _like_escape(text: str) -> str:
    """LIKE 의 와일드카드(%, _)와 이스케이프 문자를 글자 그대로 찾도록 바꾼다(ESCAPE '\\')."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def candidate_patterns(resource: dict) -> list[str]:
    """SQL 로 후보만 좁히는 LIKE 패턴들 — 따옴표까지 포함한 JSON 문자열 값.

    '"demo-web"' 은 '"demo-webhook"' 에 들어 있지 않다. DB 는 json.dumps(기본 설정)로 저장하므로
    같은 방식으로 값을 감싸면 저장된 모양과 똑같다. 최종 판정은 match() 가 한다.
    """
    return [f"%{_like_escape(json.dumps(val))}%" for val in sorted(values(resource))]
