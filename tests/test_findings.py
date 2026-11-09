"""AC-5(2) — 발견 사항 수명주기: 열림 → 해결 → 재발 → 숨김(기한) → 기한 지나면 열림, 닫기·다시 열기. 치명은 숨김 거부."""

from __future__ import annotations

import datetime as dt

import pytest

from awsglance import findings
from awsglance.findings import FindingActionError

T0 = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc)
RULES = {"sg-open-world", "root-activity"}


def hit(rule_id="sg-open-world", target="sg:1", severity="high"):
    return {"rule_id": rule_id, "severity": severity, "title": "t", "target": target, "detail": "d",
            "region": "us-east-1", "resource_key": None}


def row(store, rule_id="sg-open-world", target="sg:1"):
    return store.query("SELECT * FROM findings WHERE rule_id=? AND target=?", (rule_id, target))[0]


def actions(store, fid):
    return [a["action"] for a in store.query("SELECT action FROM finding_actions WHERE finding_id=? ORDER BY id", (fid,))]


def test_lifecycle(store):
    # 1) 처음 보임 → 열림
    assert findings.apply(store, [hit()], RULES, T0)["opened"] == 1
    f = row(store)
    assert f["status"] == "open"
    # 2) 다음 평가에서 사라짐 → 해결
    assert findings.apply(store, [], RULES, T0 + dt.timedelta(hours=1))["resolved"] == 1
    assert row(store)["status"] == "resolved"
    # 3) 다시 나타남 → 같은 행이 재발(새 행 아님)
    assert findings.apply(store, [hit()], RULES, T0 + dt.timedelta(hours=2))["reopened"] == 1
    f = row(store)
    assert (f["status"], f["reopen_count"], f["id"]) == ("open", 1, f["id"])
    assert store.query("SELECT COUNT(*) n FROM findings")[0]["n"] == 1

    # 4) 숨김: 사유 필수, 심각도별 최대 기한
    with pytest.raises(FindingActionError, match="reason_required"):
        findings.suppress(store, f["id"], "  ", 7, T0)
    with pytest.raises(FindingActionError, match="days_must_be_1_to_30"):
        findings.suppress(store, f["id"], "의도한 공개", 31, T0)
    findings.suppress(store, f["id"], "의도한 공개", 7, T0 + dt.timedelta(hours=3))
    assert row(store)["status"] == "suppressed"
    # 숨긴 동안에도 계속 보이면 숨김 유지
    findings.apply(store, [hit()], RULES, T0 + dt.timedelta(days=3))
    assert row(store)["status"] == "suppressed"
    # 기한이 지나면 다시 열림
    assert findings.apply(store, [hit()], RULES, T0 + dt.timedelta(days=8))["unsuppressed"] == 1
    assert row(store)["status"] == "open"

    # 5) 닫기(사유 제한) → 평가가 다시 봐도 닫힘 유지 → 사용자가 다시 열기
    with pytest.raises(FindingActionError):
        findings.close(store, f["id"], "whatever", T0)
    findings.close(store, f["id"], "false_positive", T0 + dt.timedelta(days=9))
    findings.apply(store, [hit()], RULES, T0 + dt.timedelta(days=9, hours=1))
    assert row(store)["status"] == "closed"
    findings.reopen(store, f["id"], T0 + dt.timedelta(days=10))
    assert row(store)["status"] == "open"

    # 모든 전이가 처리 기록에 남는다
    assert actions(store, f["id"]) == ["opened", "resolved", "reopened", "suppressed", "suppress_expired",
                                       "closed", "reopened_by_user"]


def test_critical_cannot_be_suppressed(store):
    findings.apply(store, [hit("root-activity", "root", "critical")], RULES, T0)
    f = row(store, "root-activity", "root")
    with pytest.raises(FindingActionError, match="critical_cannot_be_suppressed"):
        findings.suppress(store, f["id"], "내가 했음", 1, T0)
    assert row(store, "root-activity", "root")["status"] == "open"
    findings.close(store, f["id"], "accepted", T0)  # 닫기(사유 남김)는 가능
    assert row(store, "root-activity", "root")["status"] == "closed"


def test_rules_not_evaluated_do_not_resolve(store):
    """이번에 평가하지 않은 규칙의 발견 사항은 '해결'로 바꾸지 않는다."""
    findings.apply(store, [hit()], RULES, T0)
    findings.apply(store, [], {"root-activity"}, T0 + dt.timedelta(hours=1))
    assert row(store)["status"] == "open"


def test_unknown_finding_is_not_found(store):
    with pytest.raises(FindingActionError, match="not_found"):
        findings.close(store, 999, "fixed", T0)
