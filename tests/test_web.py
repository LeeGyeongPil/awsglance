"""AC-8 — 웹 서빙(SPA 딥 링크·API 404)과 접근 보호(비로컬 바인드 토큰·Host 허용 목록·교차 출처 POST 차단).

빌드된 프론트엔드(src/awsglance/static, 레포에 커밋)를 그대로 서빙한다 — 사용자는 Node 가 필요 없다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from awsglance.demo import load_demo
from awsglance.web.app import STATIC_DIR, create_app

LOCAL = "http://127.0.0.1:8730"


@pytest.fixture
def demo_store(store):
    load_demo(store)
    return store


def test_built_frontend_is_packaged():
    assert (STATIC_DIR / "index.html").is_file(), "run: cd web && npm ci && npm run build"
    assert any((STATIC_DIR / "assets").glob("*.js"))


def test_spa_deeplink_and_api_404(demo_store):
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        page = c.get("/changes?tab=human")
        assert page.status_code == 200 and '<div id="root">' in page.text
        assert page.headers["cache-control"] == "no-cache"
        assert c.get("/findings").status_code == 200  # 다른 화면 주소도 index.html

        nope = c.get("/api/nope")
        assert nope.status_code == 404 and nope.headers["content-type"].startswith("application/json")

        asset = next((STATIC_DIR / "assets").glob("*.js")).name
        assert c.get(f"/assets/{asset}").status_code == 200
        # 정적 폴더 밖으로 나가는 경로는 파일을 주지 않고 index.html 로 대체
        escaped = c.get("/..%2F..%2Fpyproject.toml")
        assert "[project]" not in escaped.text

        # 화면 5개의 API 가 데이터를 돌려준다
        assert c.get("/api/setup").json()["identity"]["account"] == "123456789012"
        assert c.get("/api/overview").json()["trust"]["level"] == "danger"
        assert c.get("/api/resources").json()["total"] >= 30
        human = c.get("/api/changes?tab=human").json()
        assert human["events"] and all(e["actor_class"] == "human" for e in human["events"])
        assert c.get("/api/findings?status=open").json()["items"]
        # 기본 보안 헤더
        assert page.headers["x-frame-options"] == "DENY"


def test_nonlocal_bind_requires_token(demo_store):
    with pytest.raises(ValueError):
        create_app(demo_store, bind_host="0.0.0.0")  # 토큰 없이 외부 바인드는 시작조차 안 된다

    app = create_app(demo_store, bind_host="0.0.0.0", token="s3cret-token")
    with TestClient(app, base_url=LOCAL) as c:
        assert c.get("/api/status").status_code == 401
        assert c.get("/").status_code == 401
        assert c.get("/api/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/api/status", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200
        # 처음 한 번 ?token= 으로 열면 HttpOnly 쿠키가 생기고, 이후에는 쿠키로 통과
        first = c.get("/?token=s3cret-token")
        assert first.status_code == 200 and "httponly" in first.headers["set-cookie"].lower()
        assert c.get("/api/status").status_code == 200

    # 로컬 바인드는 토큰 없이 열린다
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        assert c.get("/api/status").status_code == 200


def test_bad_host_rejected(demo_store):
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        # DNS 리바인딩: 악성 도메인이 127.0.0.1 로 풀려도 Host 헤더가 다르다
        assert c.get("/api/status", headers={"Host": "evil.example:8730"}).status_code == 400
        assert c.get("/api/status", headers={"Host": "localhost:8730"}).status_code == 200
    app = create_app(demo_store, allowed_hosts=["glance.lan"])
    with TestClient(app, base_url="http://glance.lan:8730") as c:
        assert c.get("/api/status").status_code == 200


def test_state_changing_requests_need_json_and_same_origin(demo_store):
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        fid = next(f["id"] for f in c.get("/api/findings").json()["items"] if f["severity"] == "medium")
        # 다른 사이트에서 몰래 보내는 요청 차단
        evil = c.post(f"/api/findings/{fid}/suppress", json={"reason": "x", "days": 7},
                      headers={"Origin": "https://evil.example"})
        assert evil.status_code == 403
        # 폼 전송(단순 요청)은 거부 — JSON 만
        form = c.post(f"/api/findings/{fid}/suppress", data={"reason": "x", "days": "7"})
        assert form.status_code == 415
        ok = c.post(f"/api/findings/{fid}/suppress", json={"reason": "의도한 설정", "days": 7},
                    headers={"Origin": LOCAL})
        assert ok.status_code == 200
        assert c.get(f"/api/findings/{fid}").json()["status"] == "suppressed"
        # 치명은 숨김 거부(400)
        crit = next(f["id"] for f in c.get("/api/findings").json()["items"] if f["severity"] == "critical")
        assert c.post(f"/api/findings/{crit}/suppress", json={"reason": "x", "days": 1}).status_code == 400
        # 연습 모드에는 수집 스케줄러가 없다
        assert c.post("/api/collect", json={}).status_code == 409
