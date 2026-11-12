"""English / Korean screen language: CLI message table, language priority, translated errors,
rule-id + params findings, DB migration, HTTP error codes, and the web table run under node."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from awsglance import findings, i18n
from awsglance.classify import classify, reason_info
from awsglance.cli import main
from awsglance.demo import load_demo
from awsglance.export import collect_snapshot
from awsglance.rules import all_rules
from awsglance.store import SCHEMA, Store
from awsglance.web.app import STATIC_DIR, create_app

REPO = Path(__file__).resolve().parent.parent
HANGUL = re.compile(r"[가-힣]")
LOCAL = "http://127.0.0.1:8730"


# ---- message table ----------------------------------------------------------------

def test_python_tables_have_the_same_keys_and_placeholders():
    en, ko = i18n.MESSAGES["en"], i18n.MESSAGES["ko"]
    assert set(en) == set(ko)
    names = lambda text: sorted(re.findall(r"\{(\w+)\}", text))  # noqa: E731
    for key in en:
        assert names(en[key]) == names(ko[key]), key
    assert not [k for k, v in en.items() if HANGUL.search(v)], "English table contains Hangul"


def test_every_message_formats_with_its_own_placeholders():
    for lang, table in i18n.MESSAGES.items():
        for key, text in table.items():
            params = {name: "x" for name in re.findall(r"\{(\w+)\}", text)}
            assert text.format(**params), (lang, key)


# ---- language priority: --lang > AWSGLANCE_LANG > LC_ALL > LC_MESSAGES > LANG --------------

@pytest.mark.parametrize("cli,env,expected", [
    ("ko", {"AWSGLANCE_LANG": "en", "LANG": "en_US.UTF-8"}, "ko"),
    ("en", {"AWSGLANCE_LANG": "ko", "LANG": "ko_KR.UTF-8"}, "en"),
    (None, {"AWSGLANCE_LANG": "ko", "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"AWSGLANCE_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}, "en"),
    (None, {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"LC_ALL": "", "LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "ko"}, "ko"),
    (None, {"LANG": "fr_FR.UTF-8"}, "en"),
    (None, {"LANG": "C"}, "en"),
    (None, {}, "en"),
    ("fr", {"LANG": "ko_KR.UTF-8"}, "ko"),  # 알 수 없는 --lang 값은 무시하고 다음 순위로
])
def test_language_priority(cli, env, expected):
    assert i18n.resolve_lang(cli, env) == expected


def test_set_lang_rejects_unknown_language():
    with pytest.raises(ValueError, match="en, ko"):
        i18n.set_lang("fr")


# ---- CLI output follows the language; machine-readable output does not ---------------------

def _run(argv, monkeypatch, capsys, env=None):
    for k in ("AWSGLANCE_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code
    out = capsys.readouterr()
    return code, out.out, out.err


def test_help_is_translated_by_flag_env_and_locale(monkeypatch, capsys):
    _, en_help, _ = _run(["--help"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    assert "Read-only dashboard for one AWS account." in en_help and not HANGUL.search(en_help)
    _, ko_flag, _ = _run(["--lang", "ko", "--help"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    assert "읽기 전용" in ko_flag and "--lang" in ko_flag
    _, ko_env, _ = _run(["--help"], monkeypatch, capsys, {"AWSGLANCE_LANG": "ko"})
    assert ko_env == ko_flag
    _, ko_locale, _ = _run(["--help"], monkeypatch, capsys, {"LANG": "ko_KR.UTF-8"})
    assert ko_locale == ko_flag
    _, en_wins, _ = _run(["--lang=en", "--help"], monkeypatch, capsys, {"AWSGLANCE_LANG": "ko"})
    assert en_wins == en_help


def test_machine_readable_output_is_identical_in_both_languages(tmp_path, monkeypatch, capsys):
    _, en_policy, _ = _run(["policy"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    _, ko_policy, _ = _run(["--lang", "ko", "policy"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    assert en_policy == ko_policy and json.loads(en_policy)
    _, en_ver, _ = _run(["--version"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    _, ko_ver, _ = _run(["--lang", "ko", "--version"], monkeypatch, capsys, {})
    assert en_ver == ko_ver and en_ver.startswith("awsglance ")
    lines = {}
    for lang in ("en", "ko"):
        code, out, _ = _run(["--demo", "--selftest", "--lang", lang, "--data-dir", str(tmp_path / lang)], monkeypatch, capsys)
        assert code == 0
        lines[lang] = out.strip().splitlines()
    assert lines["en"][-1] == lines["ko"][-1]
    assert re.match(r"^SELFTEST_OK screens=5 resources=\d+ changes=\d+ findings=\d+ human_changes=\d+$", lines["ko"][-1])
    assert lines["en"][0].startswith("[demo] fictional account") and "가상 계정" in lines["ko"][0]
    assert any("setup:" in ln and "permission checks" in ln for ln in lines["en"])
    assert any("setup:" in ln and "권한 점검" in ln for ln in lines["ko"])


def test_language_does_not_leak_between_main_calls(monkeypatch, capsys):
    _run(["--lang", "ko", "policy"], monkeypatch, capsys)
    assert i18n.current_lang() == "en"  # conftest 가 AWSGLANCE_LANG=en 을 고정, main 이 끝나면 --lang 고정을 푼다


def test_cli_errors_are_translated(tmp_path, monkeypatch, capsys):
    code, _, err = _run(["--selftest", "--lang", "ko", "--data-dir", str(tmp_path)], monkeypatch, capsys)
    assert code == 2 and "--selftest 는 --demo 와 함께" in err
    code, _, err = _run(["--selftest", "--data-dir", str(tmp_path)], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    assert code == 2 and "--selftest needs --demo" in err
    _, _, err = _run(["--lang", "ko", "--port", "0"], monkeypatch, capsys)
    assert "1~65535" in err
    _, _, err = _run(["--port", "abc"], monkeypatch, capsys, {"AWSGLANCE_LANG": "en"})
    assert "is not a number" in err
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        for lang, needle in (("ko", f"포트 {port} 는 이미 사용 중"), ("en", f"Port {port} is in use")):
            code, _, err = _run(["--demo", "--no-browser", "--lang", lang, "--port", str(port),
                                 "--data-dir", str(tmp_path / f"d-{lang}")], monkeypatch, capsys)
            assert code == 2 and needle in err


def test_unknown_profile_message_in_korean(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config"
    cfg.write_text("[profile work]\nregion = us-east-1\n[profile lab]\nregion = us-east-1\n")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(cfg))
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(k, raising=False)
    code, _, err = _run(["--profile", "nope", "--lang", "ko", "--no-browser", "--data-dir", str(tmp_path / "d")],
                        monkeypatch, capsys)
    assert code == 2 and "프로필 'nope'" in err and "lab, work" in err and "Traceback" not in err


@pytest.mark.parametrize("lang,needle", [("en", "Cannot create or open the data folder"), ("ko", "데이터 폴더")])
def test_data_folder_permission_error_message(lang, needle, tmp_path, monkeypatch, capsys):
    """OSError(권한 없음)가 나도 트레이스백 없이 사용자가 고른 폴더와 이유를 두 언어로 보여 준다."""
    target = tmp_path / "locked"
    real_chmod = os.chmod

    def deny(path, *a, **kw):
        if str(path) == str(target):
            raise PermissionError(13, "Permission denied", str(path))
        return real_chmod(path, *a, **kw)

    monkeypatch.setattr(os, "chmod", deny)
    code, _, err = _run(["--demo", "--selftest", "--lang", lang, "--data-dir", str(target)], monkeypatch, capsys)
    assert code == 2 and needle in err and str(target) in err and "Permission denied" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("lang,needle", [("en", "Cannot write the export to"), ("ko", "내보내기를 쓸 수 없습니다")])
def test_export_write_error_shows_the_users_path(lang, needle, tmp_path, monkeypatch, capsys):
    """출력 폴더에 쓰는 도중 OSError(권한)가 나면 사용자가 --out 으로 고른 경로를 보여 주고 종료 코드 2."""
    real_write = Path.write_text

    def deny(self, *a, **kw):
        if self.name == "index.html" and self.parent == tmp_path / "out":
            raise PermissionError(13, "Permission denied", str(self))
        return real_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", deny)
    code, _, err = _run(["export", "--demo", "--lang", lang, "--out", str(tmp_path / "out")], monkeypatch, capsys)
    assert code == 2 and needle in err and str(tmp_path / "out") in err and "Permission denied" in err
    assert "Traceback" not in err


def test_export_messages_in_korean(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    code, _, err = _run(["export", "--demo", "--lang", "ko", "--out", str(blocker)], monkeypatch, capsys)
    assert code == 2 and "폴더가 아닙니다" in err
    code, _, err = _run(["export", "--lang", "ko", "--data-dir", str(tmp_path / "none")], monkeypatch, capsys)
    assert code == 2 and "수집된 데이터가 없습니다" in err
    code, out, _ = _run(["export", "--demo", "--lang", "ko", "--out", str(tmp_path / "ok")], monkeypatch, capsys)
    assert code == 0 and "읽기 전용 사본을 만들었습니다" in out and "file://" in out


def _subprocess(args, env_extra):
    env = {k: v for k, v in os.environ.items() if k not in ("AWSGLANCE_LANG", "LC_ALL", "LC_MESSAGES", "LANG")}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "awsglance.cli", *args], capture_output=True, text=True,
                          env=env, timeout=120, cwd=REPO)


def test_subprocess_error_has_our_message_and_no_traceback(tmp_path):
    """줄 수가 아니라 '트레이스백이 없다 + 우리 메시지 줄이 있다'로 확인한다."""
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    for env, needle in (({"LANG": "ko_KR.UTF-8"}, "데이터 폴더"), ({"AWSGLANCE_LANG": "en", "LANG": "ko_KR.UTF-8"},
                                                                 "Cannot create or open the data folder")):
        proc = _subprocess(["--demo", "--selftest", "--data-dir", str(blocker / "sub")], env)
        assert proc.returncode == 2, proc.stderr
        assert "Traceback" not in proc.stderr
        assert any(needle in line for line in proc.stderr.splitlines()), proc.stderr


def test_subprocess_help_follows_flag_env_and_locale():
    """실제 명령줄(argv=None 경로): --lang > AWSGLANCE_LANG > LANG."""
    en = _subprocess(["--lang", "en", "--help"], {"LANG": "ko_KR.UTF-8"})
    assert en.returncode == 0 and "Read-only dashboard" in en.stdout and not HANGUL.search(en.stdout)
    ko = _subprocess(["--help"], {"AWSGLANCE_LANG": "ko", "LANG": "en_US.UTF-8"})
    assert ko.returncode == 0 and "읽기 전용" in ko.stdout
    loc = _subprocess(["--help"], {"LANG": "ko_KR.UTF-8"})
    assert loc.stdout == ko.stdout
    default = _subprocess(["--help"], {})
    assert "Read-only dashboard" in default.stdout


# ---- rules carry params; the database keeps them -------------------------------------------

def test_every_rule_hit_has_params_and_stored_detail_is_unchanged(store):
    load_demo(store)
    rows = store.query("SELECT rule_id, detail, params FROM findings")
    assert rows
    for r in rows:
        assert r["params"], r["rule_id"]
        assert isinstance(json.loads(r["params"]), dict)
        assert HANGUL.search(r["detail"]), "stored detail keeps its original sentence"
    assert {r["rule_id"] for r in rows} >= {"sg-open-world", "root-activity", "iam-key-old", "posture-off"}


def test_old_database_gets_the_params_column_and_keeps_old_rows(tmp_path):
    """버전 1 DB(params 열 없음)를 열면 열만 추가되고 옛 행은 params NULL + 저장 문구 그대로."""
    db = tmp_path / "data" / "awsglance.db"
    db.parent.mkdir()
    old_schema = SCHEMA.replace("  params TEXT,\n", "")
    assert "params" not in old_schema
    con = sqlite3.connect(db)
    con.executescript(old_schema)
    con.execute("INSERT INTO findings(rule_id,target,severity,title,detail,region,resource_key,status,first_seen,last_seen) "
                "VALUES('rds-public','rds:1','high','t','옛 저장 문구','us-east-1',NULL,'open','2026-11-01','2026-11-01')")
    con.commit()
    con.close()
    s = Store(db)
    try:
        assert "params" in {r["name"] for r in s.query("PRAGMA table_info(findings)")}
        old = s.query("SELECT detail, params FROM findings")[0]
        assert old == {"detail": "옛 저장 문구", "params": None}
        s.close()
        s = Store(db)  # 다시 열어도 안전(열을 두 번 추가하지 않는다)
        with TestClient(create_app(s), base_url=LOCAL) as c:
            item = c.get("/api/findings").json()["items"][0]
            assert item["detail"] == "옛 저장 문구" and item["params"] is None
        # 같은 (규칙, 대상)이 다음 평가에서 다시 나오면 params 가 채워진다
        import datetime as dt
        hit = {"rule_id": "rds-public", "severity": "high", "title": "t", "target": "rds:1", "detail": "새 문구",
               "region": "us-east-1", "resource_key": None, "params": {"name": "db1", "engine": "mysql"}}
        findings.apply(s, [hit], {"rds-public"}, dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc))
        assert json.loads(s.query("SELECT params FROM findings")[0]["params"]) == {"engine": "mysql", "name": "db1"}
    finally:
        s.close()


def test_api_adds_params_and_codes_without_changing_existing_fields(store):
    load_demo(store)
    with TestClient(create_app(store), base_url=LOCAL) as c:
        items = c.get("/api/findings?status=all").json()["items"]
        for f in items:
            assert {"title", "detail", "severity", "rule_id"} <= set(f) and isinstance(f["params"], dict)
        overview = c.get("/api/overview").json()
        assert overview["checks"][0]["example_params"]
        trust = c.get("/api/status").json()["trust"]
        assert trust["code"] in ("top_finding", "no_open_findings") and trust["reason"] and "params" in trust
        events = c.get("/api/changes?tab=all").json()["events"]
        assert events and all("reason" in e and "reason_code" in e for e in events)
        assert all(e["reason_code"] for e in events), "every stored reason maps to a code"


def test_trust_reason_codes(store):
    with TestClient(create_app(store), base_url=LOCAL) as c:
        trust = c.get("/api/status").json()["trust"]
    assert trust["code"] == "never_collected" and trust["reason"] == "아직 수집한 적이 없음"


def test_reason_info_covers_every_classify_branch():
    cases = [
        {"userIdentity": {"type": "AWSService", "invokedBy": "autoscaling.amazonaws.com"}},
        {"userIdentity": {"type": "Root", "arn": "arn:aws:iam::111122223333:root"}},
        {"userIdentity": {"type": "IAMUser", "userName": "alice"}},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/AWSServiceRoleForX/s"}},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/AWSReservedSSO_Admin_1/bob"}},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/r/s"},
         "sessionCredentialFromConsole": "true"},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/r/s"},
         "userAgent": "exec-env/AWS_Lambda_python3.12"},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/my-deploy/s"}},
        {"userIdentity": {"type": "AssumedRole", "arn": "arn:aws:sts::111122223333:assumed-role/plain/s"}},
        {"userIdentity": {"type": "FederatedUser", "userName": "fed"}},
        {"userIdentity": {"type": "Mystery"}},
    ]
    from awsglance.classify import ClassifyRules
    codes = set()
    for detail in cases:
        out = classify(detail)
        info = reason_info(out["reason"])
        assert info["code"], out
        codes.add(info["code"])
    for rules, role in ((ClassifyRules(human_roles=["ops-*"]), "ops-admin"), (ClassifyRules(automated_roles=["bot-*"]), "bot-1")):
        detail = {"userIdentity": {"type": "AssumedRole", "arn": f"arn:aws:sts::111122223333:assumed-role/{role}/s"}}
        info = reason_info(classify(detail, rules)["reason"])
        assert info["code"] and info["params"] == {"role": role}
        codes.add(info["code"])
    assert len(codes) == 13
    assert reason_info("something else") == {"code": None, "params": {}}


def test_http_errors_carry_a_code_and_params(store):
    load_demo(store)
    with TestClient(create_app(store), base_url=LOCAL) as c:
        crit = next(f["id"] for f in c.get("/api/findings").json()["items"] if f["severity"] == "critical")
        r = c.post(f"/api/findings/{crit}/suppress", json={"reason": "x", "days": 3})
        assert r.status_code == 400 and r.json() == {"detail": "critical_cannot_be_suppressed",
                                                     "code": "critical_cannot_be_suppressed", "params": {}}
        high = next(f["id"] for f in c.get("/api/findings").json()["items"] if f["severity"] == "high")
        r = c.post(f"/api/findings/{high}/suppress", json={"reason": "x", "days": 999})
        assert r.json()["code"] == "days_out_of_range" and r.json()["params"] == {"max": 30}
        assert r.json()["detail"] == "days_must_be_1_to_30"  # 기존 필드는 그대로
        r = c.get("/api/findings/99999")
        assert r.status_code == 404 and r.json() == {"detail": "finding not found", "code": "finding_not_found"}
        r = c.get("/api/nope")
        assert r.status_code == 404 and r.json()["code"] == "no_such_api"
        r = c.post(f"/api/findings/{high}/close", content="notjson", headers={"content-type": "application/json"})
        assert r.status_code == 400 and r.json()["code"] == "invalid_body"


# ---- the web screen: language switch exists in the committed build -------------------------

def test_built_frontend_has_language_switch_and_both_tables():
    js = "".join(p.read_text(encoding="utf-8") for p in (STATIC_DIR / "assets").glob("*.js"))
    assert "awsglance-lang" in js, "language choice is saved in localStorage"
    for needle in ("English", "한국어", "· read-only (AWS", "· 읽기 전용(허용", "Connection check", "연결 확인"):
        assert needle in js, needle
    assert '<html lang="en">' in (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def _node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed")
    try:
        version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        major, minor = (int(x) for x in version.lstrip("v").split(".")[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        pytest.skip("cannot run node")
    if (major, minor) < (22, 6):
        pytest.skip(f"node {version} cannot strip TypeScript types (needs 22.6+)")
    return exe


def test_web_i18n_table_runs_under_node():
    """web/test/i18n.test.ts 를 node 로 실제 실행한다: en·ko 키 일치, 언어 결정, 날짜·상대 시간, 규칙 문구."""
    proc = subprocess.run([_node(), "--experimental-strip-types", "--test", "test/i18n.test.ts"], capture_output=True,
                          text=True, cwd=REPO / "web", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_demo_screens_render_in_both_languages_under_node(store, tmp_path):
    """연습 모드 API 응답을 화면 문구 함수로 두 언어 모두 그려 본다 — 영어 화면에 한글이 새지 않는다."""
    load_demo(store)
    api = tmp_path / "api.json"
    api.write_text(json.dumps(collect_snapshot(store)["api"], ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([_node(), "--experimental-strip-types", "test/render-check.ts", str(api)], capture_output=True,
                          text=True, cwd=REPO / "web", timeout=120)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    stored = {(f["rule_id"], f["target"]): f["detail"] for f in store.query("SELECT rule_id, target, detail FROM findings")}
    assert out["en"]["findings"] and len(out["en"]["findings"]) == len(out["ko"]["findings"]) == len(stored)
    for lang in ("en", "ko"):
        assert len(out[lang]["rules"]) == len(all_rules())
    for item in out["en"]["findings"]:
        assert item["hasParams"]
        assert not HANGUL.search(item["detail"]) and not HANGUL.search(item["title"]) and "{" not in item["detail"], item
    for rule in out["en"]["rules"]:
        assert not HANGUL.search(rule["title"] + rule["description"] + rule["remediation"]), rule["id"]
    for rule in out["ko"]["rules"]:
        assert HANGUL.search(rule["title"] + rule["description"] + rule["remediation"]), rule["id"]
    assert not HANGUL.search(out["en"]["trust"]) and HANGUL.search(out["ko"]["trust"])
    assert out["en"]["events"] and not any(HANGUL.search(r) for r in out["en"]["events"])
    assert out["en"]["perms"] and not any(HANGUL.search(p) for p in out["en"]["perms"])
    # 한국어 화면의 문장은 규칙이 저장한 한국어 문장과 같다(시각이 들어가는 규칙은 날짜 모양만 언어에 맞게 바뀜)
    ko_by_rule = {}
    for item in out["ko"]["findings"]:
        ko_by_rule.setdefault(item["rule"], []).append(item["detail"])
    for rule_id in ("sg-open-world", "rds-public", "iam-key-old", "posture-off", "logs-no-retention"):
        saved = {d for (rid, _), d in stored.items() if rid == rule_id}
        assert saved and set(ko_by_rule[rule_id]) == saved, rule_id


# ---- argparse's own fixed words are translated too ------------------------------------------

ARGPARSE_ENGLISH = ("usage:", "positional arguments:", "options:", "error:", "optional arguments:")


def test_korean_help_has_no_argparse_english_words():
    ko = _subprocess(["--lang", "ko", "--help"], {})
    assert ko.returncode == 0 and "Traceback" not in ko.stderr
    for word in ARGPARSE_ENGLISH:
        assert word not in ko.stdout, word
    assert "사용법:" in ko.stdout


def test_korean_argument_error_uses_our_wording_without_traceback():
    for argv, needle in ((["--lang", "ko", "--port", "abc"], "숫자가 아닙니다"),
                         (["--lang", "ko", "--bogus"], "인식할 수 없는"),
                         (["--lang", "ko", "nope"], "선택지")):
        proc = _subprocess(argv, {})
        assert proc.returncode == 2 and "Traceback" not in proc.stderr, proc.stderr
        assert any(needle in line and "오류" in line for line in proc.stderr.splitlines()), proc.stderr
        for word in ARGPARSE_ENGLISH:
            assert word not in proc.stderr, (word, proc.stderr)


def test_english_help_and_errors_keep_argparse_wording():
    en = _subprocess(["--lang", "en", "--help"], {})
    assert "usage:" in en.stdout and "options:" in en.stdout
    bad = _subprocess(["--lang", "en", "--port", "abc"], {})
    assert bad.returncode == 2 and "awsglance: error:" in bad.stderr and "not a number" in bad.stderr
