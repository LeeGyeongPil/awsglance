"""인벤토리 스냅샷 diff — 두 시점의 {자원 키: 자원} 을 비교해 생성·삭제·속성 변경을 뽑는다.

CloudTrail 이 놓친 변경(트레일 없는 리전, 90일 밖, 지연)도 '결과'로 잡아 준다.
시각 필드(마지막 사용 시각 등)만 바뀐 변경은 noise=True 로 표시해 화면·규칙에 올리지 않는다. 순수 함수.
"""

from __future__ import annotations

# 값이 바뀌어도 '설정 변경'이 아닌 필드(시각·사용 기록)
NOISE_FIELDS = {"last_used", "last_modified", "state_transition", "launch_time", "status_time"}


def _field_changes(before: dict, after: dict) -> list[dict]:
    changes = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) != after.get(name):
            changes.append({"field": name, "before": before.get(name), "after": after.get(name)})
    return changes


def diff_snapshots(old: dict[str, dict], new: dict[str, dict]) -> list[dict]:
    """old/new: {key: {"type","region","id","name","props","tags"}} → 변경 목록(키 순서 고정)."""
    out = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a is None:
            out.append({"key": key, "type": b["type"], "region": b["region"], "name": b["name"],
                        "kind": "created", "fields": [], "noise": False})
        elif b is None:
            out.append({"key": key, "type": a["type"], "region": a["region"], "name": a["name"],
                        "kind": "deleted", "fields": [], "noise": False})
        else:
            fields = _field_changes(a["props"], b["props"])
            if a.get("tags") != b.get("tags"):
                fields.append({"field": "tags", "before": a.get("tags"), "after": b.get("tags")})
            if not fields:
                continue
            noise = all(f["field"] in NOISE_FIELDS for f in fields)
            out.append({"key": key, "type": b["type"], "region": b["region"], "name": b["name"],
                        "kind": "modified", "fields": fields, "noise": noise})
    return out


def summarize(change: dict) -> str:
    """한 줄 요약: 'SG demo-web 수정: ingress'."""
    verb = {"created": "생성", "deleted": "삭제", "modified": "수정"}[change["kind"]]
    text = f"{change['type']} {change['name']} {verb}"
    if change["fields"]:
        text += ": " + ", ".join(f["field"] for f in change["fields"])
    return text
