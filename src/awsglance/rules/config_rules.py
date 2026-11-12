"""설정 규칙 7개 — 현재 자원 스냅샷만 보고 흔한 실수를 찾는다."""

from __future__ import annotations

import datetime as dt

from . import Context, Hit, Rule

WORLD = ("0.0.0.0/0", "::/0")
SENSITIVE_PORTS = {
    22: "SSH", 3389: "RDP", 3306: "MySQL", 5432: "PostgreSQL", 1433: "SQL Server", 6379: "Redis",
    27017: "MongoDB", 9200: "Elasticsearch", 5601: "Kibana", 11211: "Memcached", 2375: "Docker API",
}
KEY_MAX_AGE_DAYS = 90


def _of_type(ctx: Context, rtype: str):
    return [r for r in ctx.resources.values() if r["type"] == rtype]


def _open_sensitive_ports(ingress: list[str]) -> list[int]:
    """'tcp:22-22:0.0.0.0/0' 같은 규칙 문자열에서 전 세계에 열린 민감 포트를 찾는다."""
    found = set()
    for rule in ingress:
        proto, ports, cidr = rule.split(":", 2)
        if cidr not in WORLD:
            continue
        if ports == "all":
            found.update(SENSITIVE_PORTS)
            continue
        lo, hi = (int(x) for x in ports.split("-"))
        found.update(p for p in SENSITIVE_PORTS if lo <= p <= hi)
    return sorted(found)


def sg_open_world(ctx: Context) -> list[Hit]:
    hits = []
    for sg in _of_type(ctx, "security_group"):
        ports = _open_sensitive_ports(sg["props"].get("ingress", []))
        if ports:
            names = ", ".join(f"{p}({SENSITIVE_PORTS[p]})" for p in ports)
            hits.append(Hit(sg["key"], f"{sg['name']}({sg['id']}): {names} 포트가 인터넷 전체(0.0.0.0/0)에 열려 있음",
                            sg["region"], sg["key"], {"name": sg["name"], "id": sg["id"], "ports": names, "count": len(ports)}))
    return hits


def sg_default_has_rules(ctx: Context) -> list[Hit]:
    hits = []
    for sg in _of_type(ctx, "security_group"):
        if sg["props"].get("group_name") != "default":
            continue
        cidr_rules = [r for r in sg["props"].get("ingress", []) if ":sg:" not in r]
        if cidr_rules:
            hits.append(Hit(sg["key"], f"기본 보안 그룹({sg['id']})에 인바운드 규칙 {len(cidr_rules)}개", sg["region"], sg["key"],
                            {"id": sg["id"], "count": len(cidr_rules)}))
    return hits


def rds_public(ctx: Context) -> list[Hit]:
    return [Hit(d["key"], f"{d['name']}({d['props'].get('engine')}) 가 공개 접근 가능으로 설정됨", d["region"], d["key"],
                {"name": d["name"], "engine": d["props"].get("engine")})
            for d in _of_type(ctx, "rds_instance") if d["props"].get("publicly_accessible")]


def s3_bucket_pab_off(ctx: Context) -> list[Hit]:
    # 계정 수준 공개 차단이 켜져 있으면 버킷별 설정이 꺼져 있어도 공개될 수 없다
    if ctx.posture.get("matrix", {}).get("s3_account_public_access_block", {}).get("global") == "on":
        return []
    return [Hit(b["key"], f"버킷 {b['name']} 의 퍼블릭 액세스 차단이 꺼져 있음(계정 수준 차단도 없음)",
                b["props"].get("bucket_region") or "global", b["key"], {"name": b["name"]})
            for b in _of_type(ctx, "s3_bucket") if not b["props"].get("public_access_block")]


def lambda_url_no_auth(ctx: Context) -> list[Hit]:
    return [Hit(f["key"], f"함수 {f['name']} 의 함수 URL 이 인증 없이(AuthType=NONE) 열려 있음", f["region"], f["key"],
                {"name": f["name"]})
            for f in _of_type(ctx, "lambda_function") if f["props"].get("url_auth") == "NONE"]


def logs_no_retention(ctx: Context) -> list[Hit]:
    return [Hit(g["key"], f"로그 그룹 {g['name']} 의 보존 기간이 '영구'(설정 없음)", g["region"], g["key"], {"name": g["name"]})
            for g in _of_type(ctx, "log_group") if g["props"].get("retention_days") is None]


def iam_key_old(ctx: Context) -> list[Hit]:
    hits = []
    for k in _of_type(ctx, "iam_access_key"):
        created = k["props"].get("created")
        if k["props"].get("status") != "Active" or not created:
            continue
        age = (ctx.now - dt.datetime.fromisoformat(created)).days
        if age > KEY_MAX_AGE_DAYS:
            hits.append(Hit(k["key"], f"{k['name']}: 활성 액세스 키가 {age}일째 교체되지 않음", "global", k["key"],
                            {"name": k["name"], "days": age}))
    return hits


RULES = [
    Rule("sg-open-world", "high", "config", "민감한 포트가 인터넷 전체에 열린 보안 그룹",
         "SSH(22)·RDP(3389)·DB 포트가 0.0.0.0/0 또는 ::/0 에 열려 있으면 전 세계 스캐너가 곧바로 접속을 시도한다.",
         "인바운드 규칙의 원본을 내 IP·사내 대역·다른 보안 그룹으로 좁힌다. 원격 접속은 Session Manager 로 대신할 수 있다.",
         sg_open_world),
    Rule("sg-default-has-rules", "low", "config", "기본 보안 그룹에 인바운드 규칙이 있음",
         "기본 보안 그룹은 새 자원에 자동으로 붙기 쉽다. 규칙이 있으면 의도치 않게 열린다.",
         "기본 보안 그룹의 인바운드 규칙을 지우고, 용도별 보안 그룹을 따로 만들어 쓴다.", sg_default_has_rules),
    Rule("rds-public", "high", "config", "공개 접근 가능한 RDS 데이터베이스",
         "PubliclyAccessible=true 이면 인터넷에서 DB 엔드포인트에 닿을 수 있다(보안 그룹이 마지막 방어선).",
         "DB 인스턴스를 수정해 '퍼블릭 액세스 가능'을 끄고, 애플리케이션과 같은 VPC 안에서만 접속한다.", rds_public),
    Rule("s3-bucket-pab-off", "medium", "config", "퍼블릭 액세스 차단이 꺼진 S3 버킷",
         "버킷 정책·ACL 실수 한 번으로 객체가 공개될 수 있다.",
         "계정 수준 S3 퍼블릭 액세스 차단을 켜는 것이 가장 간단하다. 공개가 꼭 필요한 버킷만 CloudFront 로 내보낸다.",
         s3_bucket_pab_off),
    Rule("lambda-url-no-auth", "medium", "config", "인증 없는 Lambda 함수 URL",
         "AuthType=NONE 인 함수 URL 은 주소만 알면 누구나 호출할 수 있다(요금·데이터 노출).",
         "의도한 공개 API 가 아니면 AuthType 을 AWS_IAM 으로 바꾸거나 API Gateway 뒤로 옮긴다.", lambda_url_no_auth),
    Rule("logs-no-retention", "low", "config", "보존 기간이 없는 로그 그룹",
         "보존 기간을 정하지 않으면 로그가 영구 보관되어 저장 비용이 계속 늘어난다.",
         "로그 그룹에 보존 기간(예: 30·90일)을 설정한다.", logs_no_retention),
    Rule("iam-key-old", "medium", "config", "90일 넘게 교체하지 않은 액세스 키",
         "오래된 장기 키는 유출됐을 때 피해 기간이 길다.",
         "새 키를 만들어 바꿔 끼운 뒤 옛 키를 비활성화·삭제한다. 가능하면 SSO·역할 기반 임시 자격증명으로 옮긴다.",
         iam_key_old),
]
