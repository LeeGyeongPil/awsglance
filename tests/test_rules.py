"""AC-5(1) — 규칙이 moto 계정에서 흔한 실수를 찾고, 고치면 해결·다시 생기면 재발로 바뀐다.

수집 → 저장 → 규칙 → 발견 사항까지 실제 파이프라인을 그대로 돌린다(AwsSession 은 읽기 전용 훅 포함).
"""

from __future__ import annotations

import datetime as dt
import re

import boto3
from moto import mock_aws

from awsglance import pipeline
from awsglance.aws.session import AwsSession
from awsglance.config import Settings
from awsglance.rules import Context, all_rules, evaluate

REGION = "us-east-1"
WORLD_SSH = {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
WORLD_RDP = {"IpProtocol": "tcp", "FromPort": 3389, "ToPort": 3389, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
PAB_ON = {"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True}


def _open(store, rule_id: str) -> list[dict]:
    return store.query("SELECT * FROM findings WHERE rule_id=? AND status='open'", (rule_id,))


def test_rules_on_moto_account(store):
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)
        iam = boto3.client("iam", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        ssh_sg = ec2.create_security_group(GroupName="ssh-open", Description="x", VpcId=vpc)["GroupId"]
        rdp_sg = ec2.create_security_group(GroupName="rdp-open", Description="x", VpcId=vpc)["GroupId"]
        ec2.authorize_security_group_ingress(GroupId=ssh_sg, IpPermissions=[WORLD_SSH])
        ec2.authorize_security_group_ingress(GroupId=rdp_sg, IpPermissions=[WORLD_RDP])
        s3.create_bucket(Bucket="no-pab-bucket")
        s3.create_bucket(Bucket="safe-bucket")
        s3.put_public_access_block(Bucket="safe-bucket", PublicAccessBlockConfiguration=PAB_ON)
        iam.create_user(UserName="ci-legacy")
        key_id = iam.create_access_key(UserName="ci-legacy")["AccessKey"]["AccessKeyId"]

        # moto 는 키 생성 시각을 '지금'으로 둔다 → 평가 시각을 121일 뒤로 잡아 '오래된 키'를 만든다
        later = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) + dt.timedelta(days=121)
        session = AwsSession(region=REGION)
        try:
            run = lambda now: pipeline.run_inventory(session, store, Settings(), [REGION], "123456789012", now)  # noqa: E731
            run(later)

            sg_hits = {f["target"]: f["detail"] for f in _open(store, "sg-open-world")}
            assert any(ssh_sg in t and "22(SSH)" in d for t, d in sg_hits.items()), sg_hits
            assert any(rdp_sg in t and "3389(RDP)" in d for t, d in sg_hits.items()), sg_hits
            pab = [f["target"] for f in _open(store, "s3-bucket-pab-off")]
            assert pab == ["s3_bucket:global:no-pab-bucket"]  # 차단을 켠 버킷은 걸리지 않는다
            keys = _open(store, "iam-key-old")
            assert len(keys) == 1 and re.search(r"12[01]일째", keys[0]["detail"]), keys
            assert key_id not in keys[0]["detail"]  # 전체 키 ID 는 저장·표시하지 않는다
            # 계정 수준 S3 공개 차단이 없다(moto: NoSuchPublicAccessBlockConfiguration) → 태세 규칙
            assert any(f["target"] == "posture:s3_account_public_access_block:global"
                       for f in _open(store, "posture-off"))

            # --- 고친다: SSH 규칙 회수, 버킷 차단 켜기, 키 삭제 → 다음 평가에서 해결 ---
            ec2.revoke_security_group_ingress(GroupId=ssh_sg, IpPermissions=[WORLD_SSH])
            s3.put_public_access_block(Bucket="no-pab-bucket", PublicAccessBlockConfiguration=PAB_ON)
            iam.delete_access_key(UserName="ci-legacy", AccessKeyId=key_id)
            run(later + dt.timedelta(minutes=30))
            resolved = {(f["rule_id"], f["target"]) for f in
                        store.query("SELECT rule_id, target FROM findings WHERE status='resolved'")}
            assert ("sg-open-world", f"security_group:{REGION}:{ssh_sg}") in resolved
            assert ("s3-bucket-pab-off", "s3_bucket:global:no-pab-bucket") in resolved
            assert any(r == "iam-key-old" for r, _ in resolved)
            assert len(_open(store, "sg-open-world")) == 1  # RDP 는 그대로 열림

            # --- 다시 연다 → 같은 발견 사항이 재발(reopened)로 돌아온다(새 행이 아니다) ---
            ec2.authorize_security_group_ingress(GroupId=ssh_sg, IpPermissions=[WORLD_SSH])
            run(later + dt.timedelta(hours=1))
            row = store.query("SELECT * FROM findings WHERE rule_id='sg-open-world' AND target=?",
                              (f"security_group:{REGION}:{ssh_sg}",))
            assert len(row) == 1 and row[0]["status"] == "open" and row[0]["reopen_count"] == 1
            # 재발한 SG 변경은 스냅샷 diff 에도 남는다
            assert store.query("SELECT COUNT(*) n FROM resource_changes WHERE key=? AND noise=0",
                               (f"security_group:{REGION}:{ssh_sg}",))[0]["n"] == 2
        finally:
            session.close()


def test_rule_catalog_has_twelve_rules_with_remediation():
    rules = all_rules()
    assert len(rules) == 12
    assert len({r.id for r in rules}) == 12
    assert {r.category for r in rules} == {"config", "posture", "event"}
    for r in rules:
        assert r.severity in ("critical", "high", "medium", "low")
        assert r.title and r.description and r.remediation


def _ev(name, **kw):
    base = {"event_id": name, "region": "us-east-1", "time": "2026-11-09T00:00:00+00:00", "name": name,
            "actor": "x", "actor_class": "human", "via": "console", "is_root": False, "error_code": None,
            "request": {}, "resources": []}
    return {**base, **kw}


def test_event_rules():
    now = dt.datetime(2026, 11, 9, 1, tzinfo=dt.timezone.utc)
    events = [
        _ev("ConsoleLogin", is_root=True, actor="root"),
        _ev("StopLogging", request={"name": "main"}, error_code="AccessDenied"),  # 실패한 시도도 경고
        _ev("ConsoleLogin", actor="bob", error_code="ConsoleLoginFailure", event_id="f1"),
        _ev("ConsoleLogin", actor="bob", error_code="ConsoleLoginFailure", event_id="f2"),
        _ev("AuthorizeSecurityGroupIngress", request={"groupId": "sg-9", "ipPermissions": {"items": [
            {"ipRanges": {"items": [{"cidrIp": "0.0.0.0/0"}]}}]}}),
        _ev("AuthorizeSecurityGroupIngress", event_id="private", request={"groupId": "sg-8", "ipPermissions": {
            "items": [{"ipRanges": {"items": [{"cidrIp": "10.0.0.0/8"}]}}]}}),
    ]
    hits = evaluate(Context(resources={}, posture={}, events=events, now=now))
    by_rule = {}
    for h in hits:
        by_rule.setdefault(h["rule_id"], []).append(h)
    assert len(by_rule["root-activity"]) == 1
    assert "거부됨" in by_rule["trail-tampering"][0]["detail"]
    assert "2건" in by_rule["console-login-failed"][0]["detail"]
    assert [h["target"] for h in by_rule["sg-opened-world-event"]] == ["sg-event:us-east-1:sg-9"]
