"""태세 규칙 1묶음 — 보안 서비스가 꺼진 리전을 찾는다(권한이 없어 모르는 칸은 '꺼짐'으로 단정하지 않는다)."""

from __future__ import annotations

from . import Context, Hit, Rule

FEATURE_NAMES = {
    "guardduty": "GuardDuty(위협 탐지)",
    "securityhub": "Security Hub(점검 모음)",
    "config": "AWS Config(설정 기록)",
    "accessanalyzer": "IAM Access Analyzer(외부 공유 탐지)",
    "cloudtrail_multi_region": "다중 리전 CloudTrail 트레일(90일 넘는 기록 보관)",
    "s3_account_public_access_block": "계정 수준 S3 퍼블릭 액세스 차단",
}


def posture_off(ctx: Context) -> list[Hit]:
    hits = []
    for feature, by_region in ctx.posture.get("matrix", {}).items():
        for region, state in sorted(by_region.items()):
            if state == "off":
                where = "계정 전체" if region == "global" else region
                hits.append(Hit(f"posture:{feature}:{region}", f"{FEATURE_NAMES.get(feature, feature)} 꺼짐 — {where}",
                                region, params={"feature": feature, "region": region}))
    return hits


RULES = [
    Rule("posture-off", "medium", "posture", "꺼져 있는 보안 기능",
         "GuardDuty·Security Hub·Config·Access Analyzer·다중 리전 트레일·계정 S3 공개 차단은 사고를 일찍 알아차리고 "
         "나중에 원인을 추적하는 기본 장치다.",
         "해당 리전 콘솔에서 기능을 켠다. 비용이 걱정되면 GuardDuty·Access Analyzer(무료 등급)·계정 S3 공개 차단(무료)부터 켠다.",
         posture_off),
]
