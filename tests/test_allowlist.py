"""AC-2 — 허용 목록에 쓰기 동사·비밀값 작업이 없고, IAM 정책이 허용 목록과 정확히 일치한다.

botocore 에 들어 있는 서비스 모델(오프라인)을 전수로 돌며 확인한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import botocore.session
import pytest

from awsglance.aws import guard
from awsglance.aws.policy import build_policy, iam_actions, policy_json
from awsglance.cli import main

ROOT = Path(__file__).resolve().parent.parent

# 읽기 작업으로 인정하는 동사(이 동사로 시작해야 허용 목록에 들어갈 수 있다)
READ_VERBS = ("Describe", "List", "Get", "Lookup")
# 상태를 바꾸는 동사 — 하나라도 허용 목록에 있으면 실패
WRITE_VERBS = (
    "Create", "Put", "Delete", "Update", "Modify", "Attach", "Detach", "Associate", "Disassociate", "Run", "Start",
    "Stop", "Terminate", "Reboot", "Authorize", "Revoke", "Enable", "Disable", "Tag", "Untag", "Add", "Remove",
    "Set", "Replace", "Reset", "Restore", "Copy", "Import", "Export", "Invoke", "Publish", "Send", "Upload",
    "Accept", "Reject", "Register", "Deregister", "Cancel", "Allocate", "Release", "Assume", "Change", "Upgrade",
)
# 읽기 동사지만 비밀을 돌려주는 작업 — 접두사(Get*) 허용이 위험한 이유
SECRET_OPS = {
    ("secretsmanager", "GetSecretValue"), ("secretsmanager", "BatchGetSecretValue"),
    ("ssm", "GetParameter"), ("ssm", "GetParameters"), ("ssm", "GetParametersByPath"),
    ("s3", "GetObject"), ("s3", "GetObjectTorrent"), ("ec2", "GetPasswordData"),
    ("lambda", "GetFunction"),                      # 코드 다운로드 URL
    ("lambda", "GetFunctionConfiguration"),         # 환경 변수 값
    ("kms", "Decrypt"), ("iam", "GetCredentialReport"), ("sts", "GetSessionToken"),
    ("ecr", "GetAuthorizationToken"), ("codecommit", "GetFile"),
}
SECRET_WORDS = re.compile(r"Secret|Password|Decrypt|Credential|Token|Object$|Parameter")

# API 이름과 IAM 작업 이름이 다른 경우(나머지는 같아야 한다)
IAM_NAME_EXCEPTIONS = {
    ("s3", "ListBuckets"): "s3:ListAllMyBuckets",
    ("s3", "GetPublicAccessBlock"): "s3:GetBucketPublicAccessBlock",
    ("s3control", "GetPublicAccessBlock"): "s3:GetAccountPublicAccessBlock",
}


@pytest.fixture(scope="module")
def botocore_session():
    return botocore.session.get_session()


def test_no_write_verbs_or_secret_ops(botocore_session):
    allow = guard.load_allowlist()
    assert allow, "allowlist.json is empty"
    for service, ops in allow.items():
        model = botocore_session.get_service_model(service)
        for op in ops:
            # 1) 모델에 실제로 있는 작업 이름이어야 한다(오타로 아무것도 허용 못 하는 일 방지)
            assert op in model.operation_names, f"{service}:{op} not in botocore model"
            # 2) 읽기 동사로 시작하고 쓰기 동사로 시작하지 않는다
            assert op.startswith(READ_VERBS), f"{service}:{op} is not a read verb"
            assert not op.startswith(WRITE_VERBS), f"{service}:{op} looks like a write"
            # 3) 비밀값 작업이 아니다
            assert (service, op) not in SECRET_OPS, f"{service}:{op} returns secrets"
            assert not SECRET_WORDS.search(op), f"{service}:{op} looks secret-bearing"


def test_every_write_operation_in_botocore_is_blocked(botocore_session):
    """전수 검사: 허용 목록 서비스 + 비밀 서비스의 모든 작업 중 쓰기·비밀 작업은 is_allowed()==False."""
    services = set(guard.load_allowlist()) | {"secretsmanager", "ssm", "kms"}
    checked = 0
    for service in sorted(services):
        model = botocore_session.get_service_model(service)
        for op in model.operation_names:
            if op.startswith(WRITE_VERBS) or (service, op) in SECRET_OPS:
                assert not guard.is_allowed(service, op), f"{service}:{op} should be blocked"
                checked += 1
    assert checked > 500  # ec2 하나만 해도 쓰기 작업이 수백 개 — 실제로 전수로 돌았는지 확인


def test_iam_policy_matches_allowlist(botocore_session, capsys):
    allow = guard.load_allowlist()
    # 1) 정책의 작업 = 허용 목록의 IAM 작업(더도 덜도 없이)
    expected = sorted({iam for ops in allow.values() for iam in ops.values()})
    assert iam_actions() == expected
    statement = build_policy()["Statement"]
    assert len(statement) == 1 and statement[0]["Effect"] == "Allow"
    assert statement[0]["Action"] == expected
    # 2) IAM 작업 이름이 API 이름·서비스 접두어와 맞는다(예외는 표에 적힌 것만)
    for service, ops in allow.items():
        prefix = botocore_session.get_service_model(service).signing_name
        for op, iam in ops.items():
            assert iam == IAM_NAME_EXCEPTIONS.get((service, op), f"{prefix}:{op}"), (service, op, iam)
    # 3) 레포의 iam-policy.json 사본 == `awsglance policy` 출력
    assert main(["policy"]) == 0
    printed = capsys.readouterr().out
    assert printed == policy_json()
    assert (ROOT / "iam-policy.json").read_text(encoding="utf-8") == printed
    json.loads(printed)  # 붙여 넣을 수 있는 올바른 JSON
