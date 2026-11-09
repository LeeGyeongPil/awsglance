"""CloudTrail 이벤트의 호출 주체를 '사람(human)'·'자동(automated)'·'판단 보류(unknown)'로 나눈다.

순수 함수다(입력: CloudTrailEvent JSON 을 푼 dict, 출력: dict). 조직마다 역할 이름이 다르므로
기본값은 일반 규칙만 두고 config.toml 의 [classify] 로 덮어쓴다(덮어쓰기가 먼저 적용된다).
"""

from __future__ import annotations

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
