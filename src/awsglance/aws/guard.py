"""읽기 전용 강제 — 허용 목록 밖의 AWS 작업은 요청이 만들어지기 전에 거부한다.

IAM 정책(서버 쪽)과 별개로, 이 프로그램 코드 쪽에서 한 번 더 막는 이중 방어다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


class ReadOnlyViolation(Exception):
    """허용 목록에 없는 AWS 작업을 부르려 했다(쓰기·비밀값 작업 등)."""

    def __init__(self, service: str, operation: str) -> None:
        self.service = service
        self.operation = operation
        super().__init__(f"read-only guard blocked {service}:{operation} (not in allowlist)")


@lru_cache(maxsize=1)
def load_allowlist() -> dict[str, dict[str, str]]:
    """allowlist.json → {botocore 서비스 이름: {API 작업: IAM 작업}}."""
    text = resources.files("awsglance.aws").joinpath("allowlist.json").read_text(encoding="utf-8")
    return json.loads(text)["services"]


def is_allowed(service: str, operation: str) -> bool:
    return operation in load_allowlist().get(service, {})


def check(service: str, operation: str) -> None:
    """허용 목록에 없으면 ReadOnlyViolation. 가짜(연습 모드) 클라이언트도 이 함수를 그대로 부른다."""
    if not is_allowed(service, operation):
        raise ReadOnlyViolation(service, operation)


def _provide_client_params_hook(model, params, **_kwargs):
    # model.service_model.service_name 은 'secretsmanager', 'service-quotas' 처럼 botocore 의 실제 이름.
    # 이벤트 이름 문자열(서비스 ID)로 서비스별 등록하면 이름 표기가 달라 놓칠 수 있어 와일드카드 1개로 판정한다.
    check(model.service_model.service_name, model.name)


def install(boto_session) -> None:
    """boto3 세션에 훅을 건다. 이후 이 세션으로 만드는 모든 클라이언트에 적용된다.

    'provide-client-params' 는 클라이언트 호출의 가장 이른 이벤트다(파라미터 검증·Stubber 보다 먼저).
    'before-call' 에 걸면 테스트용 Stubber 가 먼저 응답해 거부 테스트가 거짓으로 통과할 수 있다.
    """
    boto_session.events.register("provide-client-params", _provide_client_params_hook,
                                 unique_id="awsglance-readonly-guard")
