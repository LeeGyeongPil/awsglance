"""CloudTrail 이벤트의 호출 주체를 '사람(human)'·'자동(automated)'·'판단 보류(unknown)'로 나눈다.

순수 함수다(입력: CloudTrailEvent JSON 을 푼 dict, 출력: dict). 조직마다 역할 이름이 다르므로
기본값은 일반 규칙만 두고 config.toml 의 [classify] 로 덮어쓴다(덮어쓰기가 먼저 적용된다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

# 이름에 이런 단어가 들어간 역할은 대개 파이프라인·배포 도구다(일반 규칙만, 대소문자 무시)
DEFAULT_AUTOMATED_ROLES = [
    "*deploy*", "github-actions*", "*github*", "*gitlab*", "*pipeline*", "*jenkins*",
    "*terraform*", "*cicd*", "ci-*", "*-ci", "*-ci-*", "*codebuild*", "*codepipeline*",
]


@dataclass
class ClassifyRules:
    human_roles: list[str] = field(default_factory=list)       # 사용자가 '사람'이라고 지정한 역할 이름 패턴
    automated_roles: list[str] = field(default_factory=list)   # 사용자가 '자동'이라고 지정한 역할 이름 패턴
    default_automated_roles: list[str] = field(default_factory=lambda: list(DEFAULT_AUTOMATED_ROLES))


def _role_and_session(arn: str) -> tuple[str, str]:
    # arn:aws:sts::123456789012:assumed-role/<역할 이름>/<세션 이름>
    if ":assumed-role/" not in arn:
        return "", ""
    parts = arn.split(":assumed-role/", 1)[1].split("/")
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _via(detail: dict) -> str:
    ua = (detail.get("userAgent") or "").lower()
    if detail.get("sessionCredentialFromConsole") == "true" or ua.startswith("aws internal") \
            or "console.amazonaws.com" in ua or ua.startswith("mozilla/"):
        return "console"
    if ua.startswith("aws-cli/"):
        return "cli"
    if ua.endswith(".amazonaws.com"):
        return "service"
    return "sdk" if ua else ""


def _match(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name.lower(), p.lower()) for p in patterns)


def classify(detail: dict, rules: ClassifyRules | None = None) -> dict:
    """→ {"actor_class": human|automated|unknown, "actor": 표시 이름, "via": console|cli|sdk|service, "is_root": bool, "reason": 근거}"""
    rules = rules or ClassifyRules()
    uid = detail.get("userIdentity") or {}
    kind = uid.get("type", "")
    arn = uid.get("arn", "")
    via = _via(detail)
    ua = (detail.get("userAgent") or "")

    def out(cls: str, actor: str, reason: str, is_root: bool = False) -> dict:
        return {"actor_class": cls, "actor": actor, "via": via, "is_root": is_root, "reason": reason}

    # 1) AWS 서비스가 대신 부른 호출(오토스케일링 등)
    if kind == "AWSService" or uid.get("invokedBy"):
        return out("automated", uid.get("invokedBy") or "AWS service", "AWS 서비스 호출")
    # 2) 루트 사용자 — 사람. 별도 표시(루트 활동 규칙)
    if kind == "Root":
        return out("human", "root", "루트 사용자", is_root=True)
    # 3) IAM 사용자 — 사람(장기 키를 쓰는 자동화일 수도 있지만 기본은 사람)
    if kind == "IAMUser":
        return out("human", uid.get("userName") or arn.rsplit("/", 1)[-1], "IAM 사용자")
    if kind == "AssumedRole":
        role, sess = _role_and_session(arn)
        # 4) 사용자 덮어쓰기가 기본 규칙보다 먼저
        if _match(role, rules.human_roles):
            return out("human", sess or role, f"설정: 사람 역할({role})")
        if _match(role, rules.automated_roles):
            return out("automated", role, f"설정: 자동 역할({role})")
        # 5) 서비스 연결 역할
        if role.startswith("AWSServiceRole"):
            return out("automated", role, "서비스 연결 역할")
        # 6) IAM Identity Center(SSO) 로 들어온 사람 또는 콘솔 세션
        if role.startswith("AWSReservedSSO_"):
            return out("human", sess or role, "SSO 사용자")
        if detail.get("sessionCredentialFromConsole") == "true":
            return out("human", sess or role, "콘솔 세션")
        # 7) Lambda·ECS 실행 환경에서 나온 호출
        if "exec-env/AWS_Lambda" in ua or "exec-env/AWS_ECS" in ua:
            return out("automated", role, "Lambda/ECS 실행 역할")
        # 8) 이름으로 보아 파이프라인 역할
        if _match(role, rules.default_automated_roles):
            return out("automated", role, f"파이프라인 이름 패턴({role})")
        return out("unknown", sess or role or arn, "역할 이름만으로 판단 불가")
    if kind in ("FederatedUser", "IdentityCenterUser"):
        return out("human", uid.get("userName") or arn.rsplit("/", 1)[-1], "연동 사용자")
    return out("unknown", kind or "?", "알 수 없는 주체 유형")


# ---- 분류 근거의 코드화 -----------------------------------------------------------
# events.reason 열에는 위 classify() 가 만든 한국어 문장이 저장돼 있다(옛 데이터 포함).
# 화면이 언어에 맞게 보여 주도록 저장된 문장을 (코드, 파라미터)로 되돌린다. 모르는 문장은 코드 None.
_REASON_EXACT = {
    "AWS 서비스 호출": "aws_service",
    "루트 사용자": "root",
    "IAM 사용자": "iam_user",
    "서비스 연결 역할": "service_linked_role",
    "SSO 사용자": "sso_user",
    "콘솔 세션": "console_session",
    "Lambda/ECS 실행 역할": "exec_env",
    "역할 이름만으로 판단 불가": "role_name_unclear",
    "연동 사용자": "federated_user",
    "알 수 없는 주체 유형": "unknown_kind",
}
_REASON_PATTERNS = [
    (re.compile(r"^설정: 사람 역할\((.*)\)$", re.S), "config_human_role"),
    (re.compile(r"^설정: 자동 역할\((.*)\)$", re.S), "config_automated_role"),
    (re.compile(r"^파이프라인 이름 패턴\((.*)\)$", re.S), "pipeline_name_pattern"),
]


def reason_info(reason: str) -> dict:
    """저장된 분류 근거 문장 → {"code": 코드|None, "params": {...}}."""
    if reason in _REASON_EXACT:
        return {"code": _REASON_EXACT[reason], "params": {}}
    for pattern, code in _REASON_PATTERNS:
        m = pattern.match(reason or "")
        if m:
            return {"code": code, "params": {"role": m.group(1)}}
    return {"code": None, "params": {}}
