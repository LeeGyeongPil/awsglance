"""AWS 클라이언트를 만드는 유일한 곳.

- 실제 모드: 표준 자격증명 체인(환경 변수·AWS_PROFILE·SSO·역할)으로 boto3 세션을 만들고 읽기 전용 훅을 건다.
- 연습 모드: 같은 `client(service, region)` 메서드를 가진 가짜 세션(demo/fake_clients.py)을 대신 넣는다.

다른 모듈은 `boto3.client(...)` 를 직접 부르지 않는다(훅이 없는 우회로가 된다 — 테스트로 금지).
"""

from __future__ import annotations

import threading

import boto3
from botocore.config import Config

from . import guard

GLOBAL_REGION = "us-east-1"  # IAM·S3 목록·전역 CloudTrail 이벤트는 여기서 본다

# 느린 응답을 오류로 보지 않도록 넉넉히, 재시도는 botocore 표준 모드(쓰로틀 지수 백오프 포함)
_BOTO_CONFIG = Config(
    connect_timeout=10,
    read_timeout=60,
    retries={"max_attempts": 6, "mode": "standard"},
    user_agent_extra="awsglance",
)


class AwsSession:
    """읽기 전용 훅이 걸린 boto3 세션 + (서비스, 리전)별 클라이언트 캐시."""

    is_demo = False

    def __init__(self, profile: str | None = None, region: str | None = None) -> None:
        self.boto = boto3.session.Session(profile_name=profile, region_name=region)
        guard.install(self.boto)
        self.default_region = self.boto.region_name or GLOBAL_REGION
        self._clients: dict[tuple[str, str], object] = {}
        self._lock = threading.Lock()  # 스케줄러 스레드와 웹 스레드가 함께 부를 수 있다

    def client(self, service: str, region: str | None = None):
        region = region or self.default_region
        key = (service, region)
        with self._lock:
            if key not in self._clients:  # 클라이언트는 한 번 만들어 재사용(만들 때마다 엔드포인트 로딩 비용)
                self._clients[key] = self.boto.client(service, region_name=region, config=_BOTO_CONFIG)
            return self._clients[key]

    def identity(self) -> dict:
        """GetCallerIdentity — IAM 권한 없이도 되는 호출이라 연결 확인에 쓴다."""
        r = self.client("sts", GLOBAL_REGION).get_caller_identity()
        return {"account": r["Account"], "arn": r["Arn"], "user_id": r["UserId"]}

    def enabled_regions(self) -> list[str]:
        r = self.client("ec2", self.default_region).describe_regions(AllRegions=False)
        return sorted(x["RegionName"] for x in r["Regions"])

    def close(self) -> None:
        with self._lock:
            for c in self._clients.values():
                close = getattr(c, "close", None)
                if close:
                    close()  # HTTP 연결 풀 정리
            self._clients.clear()


def available_profiles() -> list[str]:
    """Profile names found in the AWS config files (used for a friendly 'profile not found' message)."""
    return sorted(boto3.session.Session().available_profiles)
