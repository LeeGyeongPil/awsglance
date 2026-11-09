"""AC-3 — 인벤토리 스냅샷 diff 가 생성·삭제·속성 변경을 잡고, 시각만 바뀐 변경은 노이즈로 둔다.

moto 로 가짜 AWS 계정을 만들고, 실제 수집기(읽기 전용 훅이 걸린 AwsSession)로 두 번 수집해 비교한다.
쓰기 작업(자원 만들기·지우기)은 테스트 준비용 별도 boto3 클라이언트로 한다 — awsglance 세션은 쓰기를 못 한다.
"""

from __future__ import annotations

import datetime as dt

import boto3
from moto import mock_aws

from awsglance import pipeline
from awsglance.aws.session import AwsSession
from awsglance.collect.inventory import collect_inventory
from awsglance.config import Settings
from awsglance.diff import diff_snapshots

REGION = "us-east-1"


def _setup_account():
    """테스트 준비(쓰기): VPC·SG·인스턴스·버킷 2개."""
    ec2 = boto3.client("ec2", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    web_sg = ec2.create_security_group(GroupName="web", Description="web", VpcId=vpc)["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=web_sg, IpPermissions=[
        {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    images = ec2.describe_images()["Images"]
    inst = ec2.run_instances(ImageId=images[0]["ImageId"], MinCount=1, MaxCount=1, SubnetId=subnet,
                             SecurityGroupIds=[web_sg])["Instances"][0]["InstanceId"]
    s3.create_bucket(Bucket="keep-bucket")
    s3.create_bucket(Bucket="tmp-bucket")
    return {"ec2": ec2, "s3": s3, "vpc": vpc, "web_sg": web_sg, "instance": inst}


@mock_aws
def test_snapshot_diff_detects_changes():
    acct = _setup_account()
    session = AwsSession(region=REGION)
    try:
        before = collect_inventory(session, [REGION])
        # 수집기가 허용 목록 밖 작업을 부르지 않았다(불렀다면 가드 위반이 오류 목록에 남는다)
        assert not [e for e in before["errors"] if "read-only guard" in e["error"]], before["errors"]
        assert "security_group@us-east-1" in before["scopes"] and "s3_bucket" in before["scopes"]

        # --- 사이에 일어난 변경 4가지(준비용 쓰기 클라이언트로) ---
        ec2, s3 = acct["ec2"], acct["s3"]
        ec2.create_security_group(GroupName="admin", Description="admin", VpcId=acct["vpc"])
        s3.delete_bucket(Bucket="tmp-bucket")
        ec2.stop_instances(InstanceIds=[acct["instance"]])
        ec2.authorize_security_group_ingress(GroupId=acct["web_sg"], IpPermissions=[
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])

        after = collect_inventory(session, [REGION])
    finally:
        session.close()

    changes = diff_snapshots(before["resources"], after["resources"])
    real = [c for c in changes if not c["noise"]]
    found = {(c["kind"], c["type"], c["name"]) for c in real}
    assert ("created", "security_group", "admin") in found
    assert ("deleted", "s3_bucket", "tmp-bucket") in found

    inst = next(c for c in real if c["type"] == "ec2_instance")
    state = next(f for f in inst["fields"] if f["field"] == "state")
    assert (state["before"], state["after"]) == ("running", "stopped")

    sg = next(c for c in real if c["kind"] == "modified" and c["type"] == "security_group")
    ingress = next(f for f in sg["fields"] if f["field"] == "ingress")
    assert "tcp:22-22:0.0.0.0/0" in ingress["after"] and "tcp:22-22:0.0.0.0/0" not in ingress["before"]

    # 정확히 이 4건 — 다른 자원이 '변경'으로 잘못 승격되지 않았다
    assert len(real) == 4, real


def _fake_collectors(monkeypatch, snapshots):
    """pipeline 의 수집 단계만 바꿔 끼운다(diff·저장·규칙은 실제 코드). snapshots 를 차례로 돌려준다."""
    queue = list(snapshots)
    monkeypatch.setattr(pipeline, "collect_inventory", lambda _s, _r: queue.pop(0))
    monkeypatch.setattr(pipeline, "collect_posture", lambda _s, regions, _a: {"regions": regions, "matrix": {}})


def test_time_only_changes_are_noise_and_not_counted(store, monkeypatch):
    """시각 필드만 바뀐 자원은 noise=True 이고, 파이프라인 요약의 changes 로 승격되지 않는다."""
    base = {"key": "lambda_function:us-east-1:fn", "type": "lambda_function", "region": "us-east-1", "id": "fn",
            "name": "fn", "tags": {}, "props": {"runtime": "python3.12", "last_modified": "2026-01-01T00:00:00Z"}}
    later = {**base, "props": {**base["props"], "last_modified": "2026-02-01T00:00:00Z"}}
    changes = diff_snapshots({base["key"]: base}, {base["key"]: later})
    assert len(changes) == 1 and changes[0]["noise"] is True

    scope = {"lambda_function@us-east-1"}
    _fake_collectors(monkeypatch, [{"resources": {base["key"]: base}, "scopes": scope, "errors": []},
                                   {"resources": {later["key"]: later}, "scopes": scope, "errors": []}])
    now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
    pipeline.run_inventory(None, store, Settings(), [REGION], "123456789012", now)
    second = pipeline.run_inventory(None, store, Settings(), [REGION], "123456789012", now + dt.timedelta(minutes=30))
    assert second["changes"] == 0 and second["noise"] == 1


def test_scope_not_seen_is_not_reported_as_deleted(store, monkeypatch):
    """권한 거부로 못 본 종류의 자원을 '삭제됨'으로 잘못 보고하지 않는다."""
    bucket = {"key": "s3_bucket:global:b", "type": "s3_bucket", "region": "global", "id": "b", "name": "b",
              "tags": {}, "props": {"public_access_block": True}}
    _fake_collectors(monkeypatch, [
        {"resources": {bucket["key"]: bucket}, "scopes": {"s3_bucket"}, "errors": []},
        {"resources": {}, "scopes": set(), "errors": [{"collector": "s3", "region": "global", "error": "AccessDenied"}]},
    ])
    now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
    pipeline.run_inventory(None, store, Settings(), [], "123456789012", now)
    second = pipeline.run_inventory(None, store, Settings(), [], "123456789012", now + dt.timedelta(hours=1))
    assert second["changes"] == 0
    assert store.query("SELECT deleted_at FROM resources WHERE key=?", (bucket["key"],))[0]["deleted_at"] is None
