"""보안 태세 — 보안 서비스가 리전마다 켜져 있는지 행렬로 모은다.

값: "on" | "off" | "denied"(권한 없음) | "error". 꺼짐과 권한 없음을 구분해야 오탐을 줄인다.
"""

from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

from ..aws.guard import ReadOnlyViolation
from ..aws.permissions import DENIED_CODES
from ..aws.session import GLOBAL_REGION

REGIONAL_FEATURES = ["guardduty", "securityhub", "config", "accessanalyzer"]
GLOBAL_FEATURES = ["cloudtrail_multi_region", "s3_account_public_access_block"]


def _guardduty(session, region):
    return "on" if session.client("guardduty", region).list_detectors().get("DetectorIds") else "off"


def _securityhub(session, region):
    try:
        session.client("securityhub", region).describe_hub()
        return "on"
    except ClientError as exc:
        # 구독하지 않은 계정은 InvalidAccessException 을 낸다 — 오류가 아니라 '꺼짐'
        if exc.response["Error"]["Code"] in ("InvalidAccessException", "ResourceNotFoundException"):
            return "off"
        raise


def _config(session, region):
    st = session.client("config", region).describe_configuration_recorder_status()
    return "on" if any(r.get("recording") for r in st.get("ConfigurationRecordersStatus", [])) else "off"


def _accessanalyzer(session, region):
    r = session.client("accessanalyzer", region).list_analyzers()
    return "on" if any(a.get("status") == "ACTIVE" for a in r.get("analyzers", [])) else "off"


def _trail(session):
    ct = session.client("cloudtrail", GLOBAL_REGION)
    for t in ct.describe_trails(includeShadowTrails=True).get("trailList", []):
        if t.get("IsMultiRegionTrail"):
            status = ct.get_trail_status(Name=t.get("TrailARN") or t["Name"])
            if status.get("IsLogging"):
                return "on"
    return "off"


def _account_pab(session, account: str):
    try:
        cfg = session.client("s3control", GLOBAL_REGION).get_public_access_block(AccountId=account)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
            return "off"
        raise
    c = cfg["PublicAccessBlockConfiguration"]
    keys = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")
    return "on" if all(c.get(k) for k in keys) else "off"


def _safe(fn, *args) -> str:
    try:
        return fn(*args)
    except ClientError as exc:
        return "denied" if exc.response["Error"].get("Code") in DENIED_CODES else "error"
    except (BotoCoreError, ReadOnlyViolation):
        return "error"


def collect_posture(session, regions: list[str], account: str) -> dict:
    """→ {"regions": [...], "matrix": {기능: {리전|global: 상태}}}"""
    fns = {"guardduty": _guardduty, "securityhub": _securityhub, "config": _config, "accessanalyzer": _accessanalyzer}
    matrix: dict[str, dict[str, str]] = {f: {} for f in REGIONAL_FEATURES + GLOBAL_FEATURES}
    for region in regions:
        for feature in REGIONAL_FEATURES:
            matrix[feature][region] = _safe(fns[feature], session, region)
    matrix["cloudtrail_multi_region"]["global"] = _safe(_trail, session)
    matrix["s3_account_public_access_block"]["global"] = _safe(_account_pab, session, account)
    return {"regions": list(regions), "matrix": matrix}
