"""Command-line messages in English and Korean, kept in one table.

Language is decided in this order (first match wins):

1. ``--lang en|ko``
2. ``AWSGLANCE_LANG``
3. ``LC_ALL``, ``LC_MESSAGES``, ``LANG`` (first one that is set)

A value starting with ``ko`` means Korean; anything else (or nothing) means English.

Machine-readable output is never translated: ``SELFTEST_OK`` / ``SELFTEST_FAIL`` lines, the
``policy`` JSON and ``--version``. The web screens have their own table in ``web/src/i18n.ts``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

LANGS = ("en", "ko")
ENV_VAR = "AWSGLANCE_LANG"
_FALLBACK_VARS = ("LC_ALL", "LC_MESSAGES", "LANG")

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "arg.usage": "usage: ",
        "arg.positional": "positional arguments",
        "arg.options": "options",
        "arg.error": "{prog}: error: {message}",
        "arg.unrecognized": "unrecognized arguments: {value}",
        "arg.invalid_choice": "argument {name}: invalid choice: {value} (choose from {choices})",
        "arg.expected_one": "argument {name}: expected one argument",
        "arg.required": "the following arguments are required: {value}",
        "arg.argument": "argument {name}: {value}",
        "help.show_help": "show this help message and exit",
        "help.description": "Read-only dashboard for one AWS account.",
        "help.command": "serve (default); policy: print the minimal IAM policy JSON; "
                        "export: write a static copy that opens from file:// (see --out)",
        "help.demo": "practice mode with a fictional example account (no credentials)",
        "help.profile": "AWS profile name (default: AWS_PROFILE)",
        "help.regions": "comma-separated regions (default: all enabled regions)",
        "help.host": "bind address (default 127.0.0.1; others require a token)",
        "help.port": "listen port 1-65535 (default {default})",
        "help.out": "export: output folder; index.html is written inside (default ./awsglance-export)",
        "help.allow_host": "extra Host header to accept (repeatable)",
        "help.data_dir": "where the SQLite DB lives (default ~/.local/share/awsglance)",
        "help.no_browser": "do not open a browser tab",
        "help.selftest": "start, check every screen API, print SELFTEST_OK and exit",
        "help.lang": "language of messages: en or ko (default: AWSGLANCE_LANG, then LC_ALL/LC_MESSAGES/LANG, else en)",
        "help.version": "show the version and exit",
        "err.port_nan": "'{value}' is not a number; use a port between 1 and 65535",
        "err.port_range": "{port} is out of range; use a port between 1 and 65535",
        "err.data_folder": "Cannot create or open the data folder {path}: {reason}. "
                           "Use --data-dir <folder> or set AWSGLANCE_DATA_DIR to a folder you can write to.",
        "err.profile_missing": "Profile '{profile}' not found. Available: {available}.\n"
                               "Use --profile <name>, set AWS_PROFILE, or create one with `aws configure sso`. "
                               "To look around first without AWS: awsglance --demo",
        "err.profile_none": "none found in your AWS config files",
        "err.aws_connect": "Could not connect to AWS: {reason}\n"
                           "Check your credentials (AWS_PROFILE, `aws sso login`, environment variables), "
                           "or try the practice mode first: awsglance --demo",
        "err.port_in_use": "Port {port} is in use — pick another with --port (for example --port {next}).",
        "err.export_failed": "Export failed: {reason}",
        "err.export_write": "Cannot write the export to {path}: {reason}. Pick a folder you can write to with --out <folder>.",
        "err.export_no_front_end": "Front-end build not found. Run: cd web && npm ci && npm run build",
        "err.export_not_dir": "{path} exists and is not a directory; pick another folder with --out",
        "err.no_data": "No collected data at {path}. Run awsglance --profile <name> first and let it collect, "
                       "or try: awsglance export --demo",
        "err.selftest_needs_demo": "--selftest needs --demo (it never calls AWS)",
        "out.demo_summary": "[demo] fictional account {account}: {resources} resources, {events} CloudTrail events, "
                            "{changes} resource changes (practice mode, mock data — no AWS calls)",
        "out.connected": "Connected: account {account} as {arn}",
        "out.regions": "Regions: {regions} — checking permissions…",
        "out.denied": "  denied: {collectors} — see the setup screen or run `awsglance policy`",
        "out.listening": "awsglance {version} — open {url}  (Ctrl+C to stop)",
        "out.exported": "Exported a read-only copy: {path}",
        "out.export_open": "Open it in a browser (no server needed). Screens:",
        "out.selftest_setup": "  setup: {perms} permission checks, overview trust={trust}, spa_deeplink={spa}",
        "out.spa_ok": "ok",
        "out.spa_missing": "missing",
    },
    "ko": {
        "arg.usage": "사용법: ",
        "arg.positional": "위치 인자",
        "arg.options": "옵션",
        "arg.error": "{prog}: 오류: {message}",
        "arg.unrecognized": "인식할 수 없는 인자: {value}",
        "arg.invalid_choice": "인자 {name}: 선택지에 없는 값 {value} (선택 가능: {choices})",
        "arg.expected_one": "인자 {name}: 값이 하나 필요합니다",
        "arg.required": "필수 인자가 빠졌습니다: {value}",
        "arg.argument": "인자 {name}: {value}",
        "help.show_help": "이 도움말을 보여 주고 종료",
        "help.description": "AWS 계정 하나를 읽기 전용으로 훑어보는 상황판.",
        "help.command": "serve(기본값); policy: 필요한 최소 IAM 정책 JSON 출력; "
                        "export: file:// 로 열리는 정적 사본 생성(--out 참고)",
        "help.demo": "가상의 예제 계정으로 쓰는 연습 모드(자격증명 불필요)",
        "help.profile": "AWS 프로필 이름(기본값: AWS_PROFILE)",
        "help.regions": "쉼표로 구분한 리전(기본값: 사용 가능한 모든 리전)",
        "help.host": "바인드 주소(기본값 127.0.0.1, 다른 주소는 토큰 필요)",
        "help.port": "수신 포트 1-65535(기본값 {default})",
        "help.out": "export: 출력 폴더, 안에 index.html 을 씀(기본값 ./awsglance-export)",
        "help.allow_host": "추가로 허용할 Host 헤더(여러 번 지정 가능)",
        "help.data_dir": "SQLite DB 위치(기본값 ~/.local/share/awsglance)",
        "help.no_browser": "브라우저 탭을 열지 않음",
        "help.selftest": "서버를 띄워 모든 화면 API 를 점검하고 SELFTEST_OK 를 출력한 뒤 종료",
        "help.lang": "메시지 언어: en 또는 ko(기본값: AWSGLANCE_LANG, 다음 LC_ALL/LC_MESSAGES/LANG, 그 외 en)",
        "help.version": "버전을 출력하고 종료",
        "err.port_nan": "'{value}' 는 숫자가 아닙니다. 1~65535 사이의 포트를 쓰세요",
        "err.port_range": "{port} 는 범위를 벗어났습니다. 1~65535 사이의 포트를 쓰세요",
        "err.data_folder": "데이터 폴더 {path} 를 만들거나 열 수 없습니다: {reason}. "
                           "--data-dir <폴더> 를 쓰거나 AWSGLANCE_DATA_DIR 을 쓸 수 있는 폴더로 지정하세요.",
        "err.profile_missing": "프로필 '{profile}' 을(를) 찾을 수 없습니다. 있는 프로필: {available}.\n"
                               "--profile <이름> 을 쓰거나 AWS_PROFILE 을 지정하거나 `aws configure sso` 로 만드세요. "
                               "AWS 없이 먼저 둘러보려면: awsglance --demo",
        "err.profile_none": "AWS 설정 파일에서 찾지 못함",
        "err.aws_connect": "AWS 에 연결하지 못했습니다: {reason}\n"
                           "자격증명(AWS_PROFILE, `aws sso login`, 환경 변수)을 확인하거나 "
                           "먼저 연습 모드를 써 보세요: awsglance --demo",
        "err.port_in_use": "포트 {port} 는 이미 사용 중입니다 — --port 로 다른 포트를 고르세요(예: --port {next}).",
        "err.export_failed": "내보내기에 실패했습니다: {reason}",
        "err.export_write": "{path} 에 내보내기를 쓸 수 없습니다: {reason}. --out <폴더> 로 쓸 수 있는 폴더를 고르세요.",
        "err.export_no_front_end": "프런트엔드 빌드를 찾을 수 없습니다. 실행: cd web && npm ci && npm run build",
        "err.export_not_dir": "{path} 이(가) 이미 있고 폴더가 아닙니다. --out 으로 다른 폴더를 고르세요",
        "err.no_data": "{path} 에 수집된 데이터가 없습니다. 먼저 awsglance --profile <이름> 으로 실행해 수집하거나 "
                       "연습 모드를 쓰세요: awsglance export --demo",
        "err.selftest_needs_demo": "--selftest 는 --demo 와 함께 써야 합니다(AWS 를 절대 호출하지 않습니다)",
        "out.demo_summary": "[demo] 가상 계정 {account}: 자원 {resources}개, CloudTrail 이벤트 {events}건, "
                            "자원 변경 {changes}건 (연습 모드, 가짜 데이터 — AWS 호출 없음)",
        "out.connected": "연결됨: 계정 {account}, 주체 {arn}",
        "out.regions": "리전: {regions} — 권한을 점검하는 중…",
        "out.denied": "  거부됨: {collectors} — 연결 화면을 보거나 `awsglance policy` 를 실행하세요",
        "out.listening": "awsglance {version} — {url} 을(를) 여세요  (중지: Ctrl+C)",
        "out.exported": "읽기 전용 사본을 만들었습니다: {path}",
        "out.export_open": "브라우저로 여세요(서버 불필요). 화면:",
        "out.selftest_setup": "  setup: 권한 점검 {perms}개, overview trust={trust}, spa_deeplink={spa}",
        "out.spa_ok": "ok",
        "out.spa_missing": "missing",
    },
}

_override: str | None = None


def normalize(value: str | None) -> str | None:
    """'ko_KR.UTF-8' -> 'ko'; anything else that is non-empty -> 'en'; empty -> None."""
    if value is None or not value.strip():
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: str | None = None, environ: Mapping[str, str] | None = None) -> str:
    """Decide the message language: ``--lang`` > ``AWSGLANCE_LANG`` > ``LC_ALL``/``LC_MESSAGES``/``LANG`` > en."""
    env = os.environ if environ is None else environ
    if cli_value in LANGS:
        return str(cli_value)
    for name in (ENV_VAR, *_FALLBACK_VARS):
        found = normalize(env.get(name))
        if found:
            return found
    return "en"


def set_lang(lang: str | None) -> None:
    """Pin the language for this process (``None`` goes back to reading the environment each time)."""
    global _override
    if lang is not None and lang not in LANGS:
        raise ValueError(f"unsupported language {lang!r}; use one of: {', '.join(LANGS)}")
    _override = lang


def current_lang() -> str:
    return _override or resolve_lang()


def msg(key: str, **params: object) -> str:
    """Look up ``key`` in the current language and fill in ``{params}``."""
    return MESSAGES[current_lang()][key].format(**params)


def early_lang(argv: list[str] | None) -> str | None:
    """Find ``--lang X`` / ``--lang=X`` before argparse runs, so ``--help`` itself can be translated."""
    args = list(argv or [])
    for i, a in enumerate(args):
        if a == "--lang" and i + 1 < len(args):
            return args[i + 1] if args[i + 1] in LANGS else None
        if a.startswith("--lang="):
            value = a.split("=", 1)[1]
            return value if value in LANGS else None
    return None
