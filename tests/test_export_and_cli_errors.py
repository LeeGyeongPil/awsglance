"""Static export (opens from file:// with no server), friendly CLI errors, and 4xx for bad request bodies."""

from __future__ import annotations

import json
import re
import socket

import pytest
from fastapi.testclient import TestClient

from awsglance.cli import main, parse_args, port_is_free
from awsglance.demo import load_demo
from awsglance.export import HASH_ROUTES, collect_snapshot, export_static, render_html
from awsglance.web.app import create_app

LOCAL = "http://127.0.0.1:8730"
SNAPSHOT_RE = re.compile(r"window\.__AWSGLANCE_SNAPSHOT__=(.*?);</script>", re.S)


@pytest.fixture
def demo_store(store):
    load_demo(store)
    return store


def _snapshot_from(html: str) -> dict:
    m = SNAPSHOT_RE.search(html)
    assert m, "snapshot script missing"
    return json.loads(m.group(1))


# ---- export ----------------------------------------------------------------------

def test_export_writes_one_self_contained_file(demo_store, tmp_path):
    target = export_static(demo_store, tmp_path / "out")
    html = target.read_text(encoding="utf-8")
    assert target.name == "index.html"
    # file:// 에서 모듈 스크립트·외부 자산은 열리지 않는다 → 한 파일 안에 모두 들어 있어야 한다
    assert 'type="module"' not in html and 'src="/assets' not in html and 'href="/assets' not in html
    assert '<div id="root">' in html and "<style>" in html
    assert not [p for p in (tmp_path / "out").iterdir() if p.name != "index.html"]


def test_snapshot_has_every_screen_and_details(demo_store, tmp_path):
    snap = _snapshot_from(export_static(demo_store, tmp_path).read_text(encoding="utf-8"))
    api = snap["api"]
    for key in ("/api/status", "/api/setup", "/api/overview", "/api/rules",
                "/api/resources?type=&region=&q=",
                "/api/changes?tab=human&q=&days=14&noise=false",
                "/api/changes?tab=all&q=&days=14&noise=false",
                "/api/findings?status=open&severity=&rule="):
        assert key in api, key
    first = api["/api/findings?status=open&severity=&rule="]["items"][0]
    assert f"/api/findings/{first['id']}" in api
    res = api["/api/resources?type=&region=&q="]["items"]
    assert len(res) >= 30
    detail_keys = [k for k in api if k.startswith("/api/resources/")]
    assert len(detail_keys) == len(res)
    assert api["/api/status"]["mode"] == "demo"


def test_export_contains_no_secrets(demo_store, tmp_path):
    html = export_static(demo_store, tmp_path).read_text(encoding="utf-8")
    assert not re.search(r"AKIA[0-9A-Z]{16}", html)
    assert "aws_secret_access_key" not in html.lower()
    assert "eyJ" not in html  # JWT 머리


def test_snapshot_matches_live_api_responses(demo_store):
    """내보낸 응답은 서버가 주는 응답과 같다(같은 앱을 직접 호출해 만들기 때문)."""
    snap = collect_snapshot(demo_store)["api"]
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        assert c.get("/api/overview").json() == snap["/api/overview"]
        assert c.get("/api/changes?tab=human&q=&days=14&noise=false").json() == snap[
            "/api/changes?tab=human&q=&days=14&noise=false"]


def test_script_tag_cannot_be_closed_by_data():
    html = render_html({"api": {"/api/x": {"v": "</script><b>x</b>"}}})
    assert "</script><b>" not in html
    assert _snapshot_from(html)["api"]["/api/x"]["v"] == "</script><b>x</b>"


def test_export_cli_demo_prints_hash_urls(tmp_path, capsys):
    out = tmp_path / "site"
    assert main(["export", "--demo", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert (out / "index.html").is_file()
    for route in HASH_ROUTES:
        assert f"index.html{route}" in printed
    assert "file://" in printed


def test_export_without_data_explains_how_to_fix(tmp_path, capsys):
    assert main(["export", "--data-dir", str(tmp_path / "empty"), "--out", str(tmp_path / "o")]) == 2
    err = capsys.readouterr().err
    assert "No collected data" in err and "export --demo" in err
    assert not (tmp_path / "o").exists()


def test_export_out_is_a_file_is_a_clear_error(tmp_path, capsys):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    assert main(["export", "--demo", "--out", str(blocker)]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_exported_page_opens_in_headless_browser(demo_store, tmp_path):
    """playwright 가 있으면 file:// 로 열어 5개 화면이 그려지는지 본다(없으면 건너뜀)."""
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    target = export_static(demo_store, tmp_path)
    try:
        with sync_api.sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for route, needle in (("#/", "개요"), ("#/changes?tab=human", "alice"), ("#/findings", "열림"),
                                  ("#/resources", "demo"), ("#/setup", "권한")):
                page.goto(target.as_uri() + route)
                page.wait_for_selector("h1, h2", timeout=5000)
                assert needle in page.inner_text("body"), route
            browser.close()
    except Exception as exc:  # 브라우저 실행 파일이 없거나 샌드박스가 막으면 건너뜀
        if "Executable doesn't exist" in str(exc) or "launch" in str(exc).lower():
            pytest.skip(f"browser unavailable: {exc}")
        raise
    assert not errors


# ---- CLI errors -------------------------------------------------------------------

def test_unknown_profile_gives_friendly_message(tmp_path, capsys, monkeypatch):
    cfg = tmp_path / "config"
    cfg.write_text("[profile work]\nregion = us-east-1\n[profile lab]\nregion = us-east-1\n")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(cfg))
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit) as ei:
        main(["--profile", "nope", "--no-browser", "--data-dir", str(tmp_path / "d")])
    err = capsys.readouterr().err
    assert ei.value.code == 2
    assert "Profile 'nope' not found" in err and "lab, work" in err and "--demo" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("bad", ["0", "99999", "-1", "abc"])
def test_port_out_of_range_is_rejected_with_hint(bad, capsys):
    with pytest.raises(SystemExit) as ei:
        parse_args(["--port", bad])
    assert ei.value.code == 2
    assert "1 and 65535" in capsys.readouterr().err


def test_port_in_use_tells_user_to_pick_another(tmp_path, capsys):
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        assert not port_is_free("127.0.0.1", port)
        code = main(["--demo", "--no-browser", "--port", str(port), "--data-dir", str(tmp_path / "d")])
    assert code == 2
    assert f"Port {port} is in use" in capsys.readouterr().err
    assert port_is_free("127.0.0.1", port)  # 닫은 뒤에는 다시 비어 있다


# ---- bad POST bodies --------------------------------------------------------------

@pytest.mark.parametrize("path,body", [
    ("suppress", "notjson"),
    ("suppress", "[1]"),
    ("suppress", '{"reason":"x","days":"abc"}'),
    ("suppress", '{"reason":"x","days":null}'),
    ("close", "notjson"),
    ("close", '"text"'),
])
def test_bad_post_bodies_are_400_not_500(demo_store, path, body):
    fid = demo_store.query("SELECT id FROM findings WHERE status='open' AND severity IN ('low','medium') LIMIT 1")[0]["id"]
    with TestClient(create_app(demo_store), base_url=LOCAL) as c:
        r = c.post(f"/api/findings/{fid}/{path}", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_body"


# ---- data folder errors: one-line hint + exit code 2 ------------------------------

import os  # noqa: E402
import sqlite3  # noqa: E402


def _assert_data_folder_hint(capsys, code, path):
    err = capsys.readouterr().err
    assert code == 2
    assert "--data-dir" in err and "AWSGLANCE_DATA_DIR" in err and str(path) in err
    assert "Traceback" not in err


def _exit_code(argv):
    try:
        return main(argv)
    except SystemExit as exc:
        return exc.code


@pytest.fixture
def readonly_parent(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("permission checks are bypassed for root")
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    yield ro
    ro.chmod(0o700)  # let tmp_path cleanup work


def test_demo_with_unwritable_parent_gives_hint(readonly_parent, capsys):
    target = readonly_parent / "d"
    code = _exit_code(["--demo", "--no-browser", "--data-dir", str(target)])
    _assert_data_folder_hint(capsys, code, target)


def test_data_dir_is_a_file_gives_hint(tmp_path, capsys):
    afile = tmp_path / "afile"
    afile.write_text("x")
    code = _exit_code(["--demo", "--no-browser", "--data-dir", str(afile)])
    _assert_data_folder_hint(capsys, code, afile)


def test_unknown_profile_with_unwritable_folder_reports_folder_first(readonly_parent, capsys):
    target = readonly_parent / "d"
    code = _exit_code(["--profile", "nosuchprof", "--no-browser", "--data-dir", str(target)])
    _assert_data_folder_hint(capsys, code, target)


def test_export_with_readonly_db_gives_hint(tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip("permission checks are bypassed for root")
    data = tmp_path / "data"
    data.mkdir()
    db = data / "awsglance.db"
    sqlite3.connect(db).close()  # empty DB file
    db.chmod(0o400)
    try:
        code = _exit_code(["export", "--data-dir", str(data), "--out", str(tmp_path / "out")])
    finally:
        db.chmod(0o600)
    _assert_data_folder_hint(capsys, code, data)
