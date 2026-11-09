"""저장 전 비밀값 가림.

읽기 API 도 비밀을 돌려줄 수 있다: Lambda ListFunctions 는 환경 변수 '값'을, CloudTrail 이벤트의
requestParameters 에는 사용자가 넣은 비밀번호·토큰이 들어갈 수 있다. DB 에 쓰기 전에 지운다.
"""

from __future__ import annotations

import re

MASK = "***"

# 값 모양으로 알아보는 비밀(키 이름이 평범해도 잡는다)
_PATTERNS = [
    re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA|ANPA|AGPA)[0-9A-Z]{16}\b"),              # AWS 키 ID
    re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+=])"),         # 40자 비밀 액세스 키 모양
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),                                  # GitHub 토큰
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),                                # Slack 토큰
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                                       # 흔한 API 키 접두
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# 연결 문자열 안의 비밀번호: scheme://user:PASSWORD@host
_URL_PASSWORD = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s@]+:)([^@\s]+)(@)")
# key=value 꼴의 비밀번호. ARN 안의 ':secret:이름' 은 비밀이 아니라 위치라서 ':' '/' 뒤에 붙은 단어는 건너뛴다
_KV_SECRET = re.compile(r"(?i)(?<![:/])\b(password|passwd|pwd|secret|token|api[_-]?key)(\s*[=:]\s*)([^\s,;&]+)")
# 환경 변수 묶음(Lambda 'variables', ECS 'environment' 의 name/value 목록) — 값은 이름과 상관없이 전부 가린다
_ENV_MAP_KEYS = {"variables", "environmentvariables"}
_ENV_LIST_KEYS = {"environment", "secrets"}

# 이 이름의 키는 값을 통째로 가린다. secretArn·SecretId 같은 '이름'은 비밀이 아니라 남긴다.
_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret(?!(arn|id|name))|^token$|(access|refresh|id|auth|session)token"
    r"|private_?key|api_?key|connectionstring)"
)


def mask_text(text: str) -> str:
    """문자열 안의 비밀값 모양을 *** 로 바꾼다."""
    for pat in _PATTERNS:
        text = pat.sub(MASK, text)
    text = _URL_PASSWORD.sub(lambda m: m.group(1) + MASK + m.group(3), text)
    text = _KV_SECRET.sub(lambda m: m.group(1) + m.group(2) + MASK, text)
    return text


def redact(obj):
    """dict/list/str 를 재귀로 돌며 비밀 이름의 값과 비밀 모양 문자열을 가린 사본을 돌려준다."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            name = k.lower() if isinstance(k, str) else ""
            if name in _ENV_MAP_KEYS and isinstance(v, dict):
                out[k] = {ek: MASK for ek in v}  # 환경 변수: 이름은 남기고 값은 모두 가림
            elif name in _ENV_LIST_KEYS and isinstance(v, list):
                out[k] = [{**i, "value": MASK} if isinstance(i, dict) and "value" in i else redact(i) for i in v]
            elif name and _SENSITIVE_KEY.search(k) and isinstance(v, (str, int, float)) and v != "":
                out[k] = MASK
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return mask_text(obj)
    return obj


def env_keys_only(env: dict | None) -> list[str]:
    """환경 변수는 이름만 남긴다(값은 저장하지 않는다)."""
    return sorted((env or {}).keys())


def short_key_id(access_key_id: str) -> str:
    """액세스 키 ID 는 앞 4자·끝 4자만 남긴다: AKIA…WXYZ (전체 ID 를 DB 에 두지 않는다)."""
    return f"{access_key_id[:4]}…{access_key_id[-4:]}" if len(access_key_id) > 8 else MASK
