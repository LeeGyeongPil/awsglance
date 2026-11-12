"""규칙 엔진 — 규칙은 (id·심각도·제목·설명·대응 방법) + 순수 함수다.

규칙 함수는 Context(현재 자원·보안 태세·최근 이벤트·지금 시각)를 받아 Hit 목록을 돌려준다.
DB·AWS 를 직접 보지 않으므로 테스트가 쉽고, 연습 모드와 실제 모드가 같은 코드를 쓴다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Callable

SEVERITIES = ["critical", "high", "medium", "low"]  # 치명·높음·보통·낮음


@dataclass
class Context:
    resources: dict[str, dict]
    posture: dict
    events: list[dict]          # 최근 EVENT_WINDOW 안의 CloudTrail 이벤트(분류·가림 끝난 행)
    now: dt.datetime


@dataclass
class Hit:
    target: str                 # 같은 규칙 안에서 발견 사항을 구분하는 열쇠(보통 자원 키)
    detail: str                 # 사람이 읽는 한 줄 근거
    region: str = "global"
    resource_key: str | None = None
    # 화면이 언어에 맞게 문장을 다시 만들 재료(규칙 id + params). detail 은 기존대로 저장·표시용 문장
    params: dict = field(default_factory=dict)


@dataclass
class Rule:
    id: str
    severity: str
    category: str               # config | posture | event
    title: str
    description: str
    remediation: str
    check: Callable[[Context], list[Hit]] = field(repr=False)

    def public(self) -> dict:
        return {"id": self.id, "severity": self.severity, "category": self.category, "title": self.title,
                "description": self.description, "remediation": self.remediation}


EVENT_WINDOW = dt.timedelta(days=7)


def all_rules() -> list[Rule]:
    from .config_rules import RULES as CONFIG
    from .event_rules import RULES as EVENT
    from .posture_rules import RULES as POSTURE
    return CONFIG + POSTURE + EVENT


def evaluate(ctx: Context) -> list[dict]:
    """모든 규칙을 돌려 발견 사항 후보 목록을 만든다."""
    out = []
    for rule in all_rules():
        for hit in rule.check(ctx):
            out.append({"rule_id": rule.id, "severity": rule.severity, "title": rule.title,
                        "target": hit.target, "detail": hit.detail, "region": hit.region,
                        "resource_key": hit.resource_key, "params": hit.params})
    return out
