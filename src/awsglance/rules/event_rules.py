"""이벤트 규칙 4개 — 최근 7일 CloudTrail 이벤트(사람/자동 분류·가림이 끝난 행)를 본다.

이벤트가 7일 창 밖으로 나가면 다음 평가에서 '해결'로 바뀐다.
"""

from __future__ import annotations

from collections import defaultdict

from . import Context, Hit, Rule

TRAIL_TAMPER = {"StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors"}
WORLD = ("0.0.0.0/0", "::/0")


def root_activity(ctx: Context) -> list[Hit]:
    root = [e for e in ctx.events if e["is_root"]]
    if not root:
        return []
    names = sorted({e["name"] for e in root})
    return [Hit("root", f"최근 7일 루트 사용자 활동 {len(root)}건: {', '.join(names[:5])} (마지막 {root[0]['time']})",
                params={"count": len(root), "names": ", ".join(names[:5]), "time": root[0]["time"]})]


def trail_tampering(ctx: Context) -> list[Hit]:
    # 권한이 없어 실패한 '시도'도 잡는다 — 기록을 끄려 했다는 사실 자체가 경고 신호다
    hits = {}
    for e in ctx.events:  # 최신 순이라 트레일마다 가장 최근 시도가 남는다
        if e["name"] in TRAIL_TAMPER:
            trail = e["request"].get("name") or e["request"].get("trailName") or "?"
            denied = bool(e.get("error_code"))
            outcome = f"시도했으나 거부됨({e['error_code']})" if denied else "실행함"
            hits.setdefault(trail, Hit(f"trail:{trail}",
                                       f"{e['actor']} 가 트레일 {trail} 에 {e['name']} {outcome} ({e['time']})",
                                       e["region"],
                                       params={"actor": e["actor"], "trail": trail, "name": e["name"],
                                               "denied": denied, "error_code": e.get("error_code"),
                                               "time": e["time"]}))
    return list(hits.values())


def console_login_failed(ctx: Context) -> list[Hit]:
    fails = defaultdict(list)
    for e in ctx.events:
        if e["name"] == "ConsoleLogin" and e.get("error_code"):
            fails[e["actor"]].append(e)
    return [Hit(f"login:{actor}", f"{actor} 콘솔 로그인 실패 {len(es)}건 (마지막 {es[0]['time']})", es[0]["region"],
                params={"actor": actor, "count": len(es), "time": es[0]["time"]})
            for actor, es in sorted(fails.items())]


def _world_cidrs(request: dict) -> bool:
    text = str(request)
    return any(w in text for w in WORLD)


def sg_opened_world_event(ctx: Context) -> list[Hit]:
    hits = {}
    for e in ctx.events:
        if e["name"] == "AuthorizeSecurityGroupIngress" and not e.get("error_code") and _world_cidrs(e["request"]):
            group_id = e["request"].get("groupId")
            group = group_id or e["request"].get("groupName") or "?"
            # 자원 연결은 그룹 ID 가 있을 때만 — 그룹 이름(groupName)은 자원 키가 아니라서 정확히 가리킬 수 없다
            resource_key = f"security_group:{e['region']}:{group_id}" if isinstance(group_id, str) else None
            hits.setdefault(group, Hit(f"sg-event:{e['region']}:{group}",
                                       f"{e['actor']}({e['actor_class']}, {e['via'] or '?'}) 가 {group} 인바운드를 "
                                       f"인터넷 전체에 열었음 ({e['time']})",
                                       e["region"], resource_key,
                                       {"actor": e["actor"], "actor_class": e["actor_class"], "via": e["via"] or "?",
                                        "group": group, "time": e["time"]}))
    return list(hits.values())


RULES = [
    Rule("root-activity", "critical", "event", "루트 사용자 활동",
         "루트 사용자는 모든 권한을 가진다. 결제·계정 설정 같은 몇 가지 외에는 쓰지 않는 것이 원칙이다.",
         "본인 활동인지 확인한다. 아니라면 즉시 루트 비밀번호를 바꾸고 MFA 를 확인한다. 평소 작업은 IAM Identity Center 사용자로 한다.",
         root_activity),
    Rule("trail-tampering", "critical", "event", "CloudTrail 트레일 중지·삭제·변경",
         "공격자는 흔적을 지우려고 트레일 기록을 먼저 끈다. 권한이 없어 실패한 시도도 함께 보여 준다.",
         "누가 했는지 확인하고, 의도한 변경이 아니면 트레일 기록을 다시 켠 뒤 해당 주체의 자격증명을 회수한다.",
         trail_tampering),
    Rule("console-login-failed", "medium", "event", "콘솔 로그인 실패",
         "같은 사용자에게 로그인 실패가 이어지면 비밀번호 추측 시도일 수 있다.",
         "본인 실수인지 확인하고, 반복되면 비밀번호 변경과 MFA 강제를 검토한다.", console_login_failed),
    Rule("sg-opened-world-event", "high", "event", "보안 그룹을 인터넷 전체에 연 변경",
         "AuthorizeSecurityGroupIngress 로 0.0.0.0/0 을 허용한 기록. 임시로 열고 잊어버리는 일이 흔하다.",
         "필요한 변경이었는지 작업자에게 확인하고, 아니면 해당 인바운드 규칙을 지운다.", sg_opened_world_event),
]
