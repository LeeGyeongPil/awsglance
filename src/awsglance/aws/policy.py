"""허용 목록(allowlist.json) → 최소 IAM 정책 JSON.

코드의 허용 목록과 IAM 정책을 손으로 따로 관리하면 언젠가 어긋난다. 그래서 같은 원천에서 만든다.
API 작업 이름과 IAM 작업 이름이 다른 경우(ListBuckets → s3:ListAllMyBuckets 등)는 allowlist.json 의 값이 맡는다.
"""

from __future__ import annotations

import json

from .guard import load_allowlist


def iam_actions() -> list[str]:
    actions = {iam for ops in load_allowlist().values() for iam in ops.values()}
    return sorted(actions)


def build_policy() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AwsglanceReadOnly",
                "Effect": "Allow",
                "Action": iam_actions(),
                "Resource": "*",
            }
        ],
    }


def policy_json() -> str:
    return json.dumps(build_policy(), indent=2) + "\n"
