"""인벤토리 수집 — 자원 종류별 Describe/List 결과를 정규화한 dict 로 모은다.

정규화 자원 하나: {"key", "type", "region", "id", "name", "props", "tags"}
- key 는 "<type>:<region>:<id>" 로, 두 스냅샷을 비교(diff)할 때 같은 자원을 찾는 열쇠다.
- props 에는 규칙·diff 에 쓰는 속성만 담는다. 비밀값(환경 변수 값, 전체 액세스 키 ID)은 담지 않는다.

한 종류가 권한 거부로 실패해도 나머지는 계속 모은다. 성공한 범위(scope)만 diff 에 쓰므로
'권한이 없어 못 본 자원'이 '삭제됨'으로 잘못 나오지 않는다.
"""

from __future__ import annotations

import datetime as dt

from botocore.exceptions import BotoCoreError, ClientError

from ..aws.guard import ReadOnlyViolation
from ..aws.session import GLOBAL_REGION
from ..redact import env_keys_only, short_key_id

GLOBAL_TYPES = {"s3_bucket", "iam_user", "iam_access_key", "iam_role"}


def scope_of(resource_type: str, region: str) -> str:
    """diff 범위: 전역 자원은 종류만, 리전 자원은 종류@리전."""
    return resource_type if resource_type in GLOBAL_TYPES else f"{resource_type}@{region}"


def _iso(value) -> str | None:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.timezone.utc).isoformat()
    return value


def _tags(tag_list) -> dict:
    return {t["Key"]: t["Value"] for t in (tag_list or []) if "Key" in t}


def _res(rtype: str, region: str, rid: str, name: str, props: dict, tags: dict | None = None) -> dict:
    return {"key": f"{rtype}:{region}:{rid}", "type": rtype, "region": region, "id": rid,
            "name": name or rid, "props": props, "tags": tags or {}}


def _pages(client, method: str, **kwargs):
    """페이지네이터가 있으면 쓰고, 없으면 한 번 부른다."""
    if client.can_paginate(method):
        yield from client.get_paginator(method).paginate(**kwargs)
    else:
        yield getattr(client, method)(**kwargs)


# ---- 리전 자원 -------------------------------------------------------------

def _rules_text(perms: list[dict]) -> list[str]:
    """SG 규칙을 비교하기 쉬운 문자열 목록으로: 'tcp:22-22:0.0.0.0/0'."""
    out = []
    for p in perms or []:
        proto = p.get("IpProtocol", "-1")
        ports = "all" if proto == "-1" else f"{p.get('FromPort')}-{p.get('ToPort')}"
        proto = "all" if proto == "-1" else proto
        for r in p.get("IpRanges", []):
            out.append(f"{proto}:{ports}:{r['CidrIp']}")
        for r in p.get("Ipv6Ranges", []):
            out.append(f"{proto}:{ports}:{r['CidrIpv6']}")
        for g in p.get("UserIdGroupPairs", []):
            out.append(f"{proto}:{ports}:sg:{g.get('GroupId')}")
    return sorted(set(out))


def collect_ec2(session, region: str) -> list[dict]:
    ec2 = session.client("ec2", region)
    out = []
    for page in _pages(ec2, "describe_instances"):
        for resv in page.get("Reservations", []):
            for i in resv.get("Instances", []):
                tags = _tags(i.get("Tags"))
                out.append(_res("ec2_instance", region, i["InstanceId"], tags.get("Name", ""), {
                    "state": i.get("State", {}).get("Name"),
                    "instance_type": i.get("InstanceType"),
                    "public_ip": i.get("PublicIpAddress"),
                    "vpc_id": i.get("VpcId"),
                    "subnet_id": i.get("SubnetId"),
                    "security_groups": sorted(g["GroupId"] for g in i.get("SecurityGroups", [])),
                    "iam_profile": (i.get("IamInstanceProfile") or {}).get("Arn"),
                    "launch_time": _iso(i.get("LaunchTime")),
                }, tags))
    for page in _pages(ec2, "describe_vpcs"):
        for v in page.get("Vpcs", []):
            tags = _tags(v.get("Tags"))
            out.append(_res("vpc", region, v["VpcId"], tags.get("Name", ""),
                            {"cidr": v.get("CidrBlock"), "is_default": v.get("IsDefault", False)}, tags))
    for page in _pages(ec2, "describe_subnets"):
        for s in page.get("Subnets", []):
            tags = _tags(s.get("Tags"))
            out.append(_res("subnet", region, s["SubnetId"], tags.get("Name", ""), {
                "vpc_id": s.get("VpcId"), "cidr": s.get("CidrBlock"), "az": s.get("AvailabilityZone"),
                "public_ip_on_launch": s.get("MapPublicIpOnLaunch", False)}, tags))
    for page in _pages(ec2, "describe_security_groups"):
        for g in page.get("SecurityGroups", []):
            tags = _tags(g.get("Tags"))
            out.append(_res("security_group", region, g["GroupId"], g.get("GroupName", ""), {
                "group_name": g.get("GroupName"), "vpc_id": g.get("VpcId"),
                "description": g.get("Description"),
                "ingress": _rules_text(g.get("IpPermissions")),
                "egress": _rules_text(g.get("IpPermissionsEgress")),
            }, tags))
    return out


def collect_rds(session, region: str) -> list[dict]:
    rds = session.client("rds", region)
    out = []
    for page in _pages(rds, "describe_db_instances"):
        for d in page.get("DBInstances", []):
            out.append(_res("rds_instance", region, d["DBInstanceIdentifier"], d["DBInstanceIdentifier"], {
                "engine": d.get("Engine"), "engine_version": d.get("EngineVersion"),
                "status": d.get("DBInstanceStatus"), "class": d.get("DBInstanceClass"),
                "publicly_accessible": d.get("PubliclyAccessible", False),
                "storage_encrypted": d.get("StorageEncrypted", False),
                "multi_az": d.get("MultiAZ", False),
            }, _tags(d.get("TagList"))))
    return out


def collect_lambda(session, region: str) -> list[dict]:
    lam = session.client("lambda", region)
    out = []
    for page in _pages(lam, "list_functions"):
        for f in page.get("Functions", []):
            name = f["FunctionName"]
            url_auth = None
            for upage in _pages(lam, "list_function_url_configs", FunctionName=name):
                for u in upage.get("FunctionUrlConfigs", []):
                    url_auth = u.get("AuthType")
            out.append(_res("lambda_function", region, name, name, {
                "runtime": f.get("Runtime"), "memory": f.get("MemorySize"), "timeout": f.get("Timeout"),
                "role": f.get("Role"),
                # 환경 변수는 '이름'만 저장한다. 값에는 DB 비밀번호·API 키가 들어 있곤 하다.
                "env_keys": env_keys_only((f.get("Environment") or {}).get("Variables")),
                "url_auth": url_auth,
                "last_modified": f.get("LastModified"),
            }))
    return out


def collect_elbv2(session, region: str) -> list[dict]:
    elb = session.client("elbv2", region)
    out = []
    for page in _pages(elb, "describe_load_balancers"):
        for lb in page.get("LoadBalancers", []):
            out.append(_res("load_balancer", region, lb["LoadBalancerName"], lb["LoadBalancerName"], {
                "type": lb.get("Type"), "scheme": lb.get("Scheme"),
                "state": (lb.get("State") or {}).get("Code"), "dns_name": lb.get("DNSName"),
                "security_groups": sorted(lb.get("SecurityGroups", [])),
            }))
    return out


def collect_logs(session, region: str) -> list[dict]:
    logs = session.client("logs", region)
    out = []
    for page in _pages(logs, "describe_log_groups"):
        for g in page.get("logGroups", []):
            out.append(_res("log_group", region, g["logGroupName"], g["logGroupName"], {
                "retention_days": g.get("retentionInDays"),
                "stored_bytes": g.get("storedBytes"),
            }))
    return out


# ---- 전역 자원(us-east-1 에서 한 번) ---------------------------------------

def collect_s3(session) -> list[dict]:
    s3 = session.client("s3", GLOBAL_REGION)
    out = []
    for page in _pages(s3, "list_buckets"):
        for b in page.get("Buckets", []):
            name = b["Name"]
            try:
                cfg = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
                pab = all(cfg.get(k, False) for k in
                          ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"))
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchPublicAccessBlockConfiguration":
                    raise
                pab = False  # 설정이 아예 없음 = 공개 차단 꺼짐
            out.append(_res("s3_bucket", "global", name, name, {
                "bucket_region": b.get("BucketRegion"),
                "public_access_block": pab,
                "created": _iso(b.get("CreationDate")),
            }))
    return out


def collect_iam(session) -> list[dict]:
    iam = session.client("iam", GLOBAL_REGION)
    out = []
    for page in _pages(iam, "list_users"):
        for u in page.get("Users", []):
            user = u["UserName"]
            out.append(_res("iam_user", "global", user, user, {
                "arn": u.get("Arn"), "created": _iso(u.get("CreateDate")),
                "password_last_used": _iso(u.get("PasswordLastUsed")),
            }))
            for kpage in _pages(iam, "list_access_keys", UserName=user):
                for k in kpage.get("AccessKeyMetadata", []):
                    short = short_key_id(k["AccessKeyId"])  # 전체 키 ID 는 저장하지 않는다
                    out.append(_res("iam_access_key", "global", f"{user}/{short[-4:]}", f"{user} {short}", {
                        "user": user, "status": k.get("Status"), "created": _iso(k.get("CreateDate")),
                    }))
    for page in _pages(iam, "list_roles"):
        for r in page.get("Roles", []):
            out.append(_res("iam_role", "global", r["RoleName"], r["RoleName"], {
                "arn": r.get("Arn"), "path": r.get("Path"), "created": _iso(r.get("CreateDate")),
            }))
    return out


REGIONAL = [("ec2", collect_ec2, ["ec2_instance", "vpc", "subnet", "security_group"]),
            ("rds", collect_rds, ["rds_instance"]),
            ("lambda", collect_lambda, ["lambda_function"]),
            ("elbv2", collect_elbv2, ["load_balancer"]),
            ("logs", collect_logs, ["log_group"])]
GLOBAL = [("s3", collect_s3, ["s3_bucket"]), ("iam", collect_iam, ["iam_user", "iam_access_key", "iam_role"])]


def collect_inventory(session, regions: list[str]) -> dict:
    """→ {"resources": {key: res}, "scopes": 성공한 diff 범위 집합, "errors": [...]}"""
    resources: dict[str, dict] = {}
    scopes: set[str] = set()
    errors: list[dict] = []

    def run(name, fn, types, region, *args):
        try:
            for r in fn(session, *args):
                resources[r["key"]] = r
            scopes.update(scope_of(t, region) for t in types)
        except ReadOnlyViolation as exc:  # 코드 버그로 허용 밖 작업을 불렀다 — 이력에 남기고 계속
            errors.append({"collector": name, "region": region, "error": str(exc)})
        except ClientError as exc:
            errors.append({"collector": name, "region": region, "error": exc.response["Error"].get("Code", "ClientError")})
        except BotoCoreError as exc:
            errors.append({"collector": name, "region": region, "error": type(exc).__name__})

    for name, fn, types in GLOBAL:
        run(name, fn, types, "global")
    for region in regions:
        for name, fn, types in REGIONAL:
            run(name, fn, types, region, region)
    return {"resources": resources, "scopes": scopes, "errors": errors}
