"""모든 테스트가 실제 AWS·내 컴퓨터의 ~/.aws 를 절대 건드리지 않도록 가짜 자격증명 환경을 만든다."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

# boto3 를 import 하기 전에 정해 둔다 — 실제 프로필·자격증명 파일을 읽지 않게
_FAKE_ENV = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_CONFIG_FILE": os.devnull,
    "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    "AWS_EC2_METADATA_DISABLED": "true",
}
for _k in ("AWS_PROFILE", "AWS_REGION"):
    os.environ.pop(_k, None)
os.environ.update(_FAKE_ENV)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """테스트는 오프라인이어야 한다: 내 컴퓨터(127.0.0.1·::1) 밖으로 나가는 연결은 즉시 실패시킨다."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost") and not isinstance(address, (str, bytes)):
            raise RuntimeError(f"network access in tests is not allowed: {address!r}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture
def store(tmp_path: Path):
    from awsglance.store import Store

    s = Store(tmp_path / "data" / "awsglance.db")
    yield s
    s.close()


class StubSession:
    """AwsSession 처럼 client(service, region) 를 주되, 테스트가 미리 만든(Stubber 가 걸린) 클라이언트를 돌려준다."""

    is_demo = False

    def __init__(self, clients: dict[str, object]):
        self.clients = clients

    def client(self, service: str, region: str | None = None):
        return self.clients[service]
