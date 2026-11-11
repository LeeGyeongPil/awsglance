"""awsglance 명령줄 진입점.

    awsglance --demo              # 자격증명 없이 가상의 예제 계정(연습용 mock)
    awsglance --profile myprof    # 내 계정(표준 자격증명 체인), 읽기 전용
    awsglance policy              # 필요한 최소 IAM 정책 JSON 출력
    awsglance export --demo --out DIR   # 서버 없이 file:// 로 열리는 정적 사본(index.html 한 장)
    awsglance --demo --selftest   # 서버를 잠깐 띄워 모든 화면 API 를 점검하고 끝냄
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import __version__
from .config import Settings, default_data_dir, load
from .store import Store

DEFAULT_PORT = 8730


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number; use a port between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"{port} is out of range; use a port between 1 and 65535")
    return port


def port_is_free(host: str, port: int) -> bool:
    """실제로 bind 해 보고 곧바로 닫는다(uvicorn 과 같은 SO_REUSEADDR 설정)."""
    try:
        family, _, _, _, addr = socket.getaddrinfo(host or None, port, type=socket.SOCK_STREAM,
                                                   flags=socket.AI_PASSIVE)[0]
    except socket.gaierror:
        return True  # 주소 해석 문제는 uvicorn 이 자기 오류로 알려 준다
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(addr)
        except OSError:
            return False
    return True


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="awsglance", description="Read-only dashboard for one AWS account.")
    p.add_argument("command", nargs="?", default="serve", choices=["serve", "policy", "export"],
                   help="serve (default); policy: print the minimal IAM policy JSON; "
                        "export: write a static copy that opens from file:// (see --out)")
    p.add_argument("--demo", action="store_true", help="practice mode with a fictional example account (no credentials)")
    p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"), help="AWS profile name (default: AWS_PROFILE)")
    p.add_argument("--regions", default="", help="comma-separated regions (default: all enabled regions)")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1; others require a token)")
    p.add_argument("--port", type=_port, default=DEFAULT_PORT, help=f"listen port 1-65535 (default {DEFAULT_PORT})")
    p.add_argument("--out", type=Path, default=Path("awsglance-export"),
                   help="export: output folder; index.html is written inside (default ./awsglance-export)")
    p.add_argument("--allow-host", action="append", default=[], help="extra Host header to accept (repeatable)")
    p.add_argument("--data-dir", type=Path, default=None, help="where the SQLite DB lives (default ~/.local/share/awsglance)")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    p.add_argument("--selftest", action="store_true", help="start, check every screen API, print SELFTEST_OK and exit")
    p.add_argument("--version", action="version", version=f"awsglance {__version__}")
    return p.parse_args(argv)


@contextmanager
def _data_folder_errors(data_dir: Path) -> Iterator[None]:
    """데이터 폴더·DB 를 만들거나 여는 중 나는 OS·SQLite 오류를 한 줄 안내 + 종료 코드 2 로 바꾼다."""
    try:
        yield
    except (OSError, sqlite3.OperationalError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        print(f"Cannot create or open the data folder {data_dir}: {reason}. "
              "Use --data-dir <folder> or set AWSGLANCE_DATA_DIR to a folder you can write to.", file=sys.stderr)
        raise SystemExit(2) from None


def _token_for(data_dir: Path) -> str:
    """비로컬 바인드용 토큰: 환경 변수 → 데이터 폴더의 token 파일(0600) → 새로 만들기."""
    env = os.environ.get("AWSGLANCE_TOKEN")
    if env:
        return env
    path = data_dir / "token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    with _data_folder_errors(data_dir):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token + "\n")
    return token


# ---- 연습 모드 ----------------------------------------------------------------

def prepare_demo(data_dir: Path) -> Store:
    """연습 모드 DB 는 실제 계정 DB 와 섞이지 않게 demo/ 아래에 매번 새로 만든다."""
    from .demo import load_demo

    demo_dir = data_dir / "demo"
    with _data_folder_errors(data_dir):
        if demo_dir.exists():
            shutil.rmtree(demo_dir)
        store = Store(demo_dir / "awsglance.db")
    summary = load_demo(store)
    print(f"[demo] fictional account {summary['account']}: {summary['resources']} resources, "
          f"{summary['events']} CloudTrail events, {summary['changes']} resource changes "
          f"(practice mode, mock data — no AWS calls)", flush=True)
    return store


# ---- 실제 모드 ----------------------------------------------------------------

def prepare_live(args, data_dir: Path, settings: Settings):
    """계정 연결 확인 → 권한 점검 → 스케줄러 준비. (store, scheduler, session) 을 돌려준다."""
    from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound

    from . import pipeline
    from .aws.permissions import check_permissions
    from .aws.session import GLOBAL_REGION, AwsSession, available_profiles
    from .scheduler import Job, Scheduler
    from .store import iso, now_utc

    try:
        session = AwsSession(profile=args.profile, region=os.environ.get("AWS_REGION") or None)
    except ProfileNotFound:  # 프로필 이름 오타: traceback 대신 있는 프로필을 보여 준다
        available = available_profiles()
        listed = ", ".join(available) if available else "none found in your AWS config files"
        print(f"Profile '{args.profile}' not found. Available: {listed}.\n"
              "Use --profile <name>, set AWS_PROFILE, or create one with `aws configure sso`. "
              "To look around first without AWS: awsglance --demo", file=sys.stderr)
        raise SystemExit(2)
    try:
        who = session.identity()
    except (ClientError, BotoCoreError) as exc:
        session.close()
        print(f"Could not connect to AWS: {exc}\n"
              "Check your credentials (AWS_PROFILE, `aws sso login`, environment variables), "
              "or try the practice mode first: awsglance --demo", file=sys.stderr)
        raise SystemExit(2)
    regions = [r.strip() for r in args.regions.split(",") if r.strip()] or settings.regions
    if not regions:
        try:
            regions = session.enabled_regions()
        except (ClientError, BotoCoreError):
            regions = [session.default_region]
    # IAM·로그인 같은 전역 이벤트는 us-east-1 의 LookupEvents 에만 보인다 → CloudTrail 은 항상 포함
    trail_regions = sorted(set(regions) | {GLOBAL_REGION})

    with _data_folder_errors(data_dir):
        store = Store(data_dir / "awsglance.db")
        store.set_meta("mode", "live")
        store.set_meta("identity", who)
        store.set_meta("regions", regions)
    print(f"Connected: account {who['account']} as {who['arn']}", flush=True)
    print(f"Regions: {', '.join(regions)} — checking permissions…", flush=True)
    perms = check_permissions(session, regions[0], who["account"])
    store.set_meta("permissions", perms)
    store.set_meta("permissions_at", iso(now_utc()))
    denied = [p["collector"] for p in perms if p["status"] == "denied"]
    if denied:
        print(f"  denied: {', '.join(denied)} — see the setup screen or run `awsglance policy`", flush=True)

    jobs = [
        Job("inventory", settings.inventory_minutes * 60,
            lambda: pipeline.run_inventory(session, store, settings, regions, who["account"], now_utc())),
        Job("cloudtrail", settings.cloudtrail_minutes * 60,
            lambda: pipeline.run_cloudtrail(session, store, settings, trail_regions, now_utc())),
        Job("prune", 24 * 3600, lambda: store.prune(now_utc(), settings.retention_days, settings.max_runs)),
    ]
    return store, Scheduler(store, jobs), session


# ---- 자체 점검 ----------------------------------------------------------------

SCREEN_APIS = {"setup": "/api/setup", "overview": "/api/overview", "resources": "/api/resources",
               "changes": "/api/changes?tab=all", "findings": "/api/findings?status=open"}


def selftest(app) -> int:
    """임시 포트로 실제 HTTP 서버를 띄워 화면 5개의 API 와 SPA 주소를 확인한다."""
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):  # 최대 10초 기다린다
            if server.started:
                break
            time.sleep(0.05)
        if not server.started:
            print("SELFTEST_FAIL server did not start within 10s", flush=True)
            return 1
        port = server.servers[0].sockets[0].getsockname()[1]

        def get(path: str):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=30) as r:
                body = r.read().decode("utf-8")
                return json.loads(body) if path.startswith("/api/") else body

        try:
            data = {name: get(path) for name, path in SCREEN_APIS.items()}
            human = get("/api/changes?tab=human")
            spa_ok = "<div id=\"root\">" in get("/changes?tab=human")  # 화면 주소로 바로 들어와도 SPA 가 뜨는지
        except (OSError, ValueError) as exc:  # HTTP 오류(예: 프론트 빌드 없음 503)·JSON 오류 → 실패로 보고
            print(f"SELFTEST_FAIL {type(exc).__name__}: {exc}", flush=True)
            return 1
        screens = sum(1 for d in data.values() if d)
        resources = data["resources"]["total"]
        changes = len(data["changes"]["events"]) + len(data["changes"]["resource_changes"])
        open_findings = len(data["findings"]["items"])
        human_changes = len(human["events"])
        print(f"  setup: {len(data['setup']['permissions'])} permission checks, overview trust={data['overview']['trust']['level']}, "
              f"spa_deeplink={'ok' if spa_ok else 'missing'}")
        ok = (screens == 5 and resources >= 30 and changes >= 10 and open_findings >= 8 and human_changes >= 3 and spa_ok)
        line = (f"screens={screens} resources={resources} changes={changes} findings={open_findings} "
                f"human_changes={human_changes}")
        print(("SELFTEST_OK " if ok else "SELFTEST_FAIL ") + line, flush=True)
        return 0 if ok else 1
    finally:
        server.should_exit = True  # 종료 경로에서 서버 스레드를 반드시 정리
        thread.join(10)


# ---- 정적 내보내기 ---------------------------------------------------------------

def run_export(args) -> int:
    """`awsglance export`: 서버 없이 file:// 로 열리는 index.html 한 장을 만든다(읽기 전용 사본)."""
    from .export import HASH_ROUTES, ExportError, export_static

    try:
        if args.demo:
            tmp = Path(tempfile.mkdtemp(prefix="awsglance-export-"))
            try:
                store = prepare_demo(tmp)
                try:
                    target = export_static(store, args.out)
                finally:
                    store.close()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            data_dir = Path(args.data_dir or default_data_dir()).expanduser()
            db = data_dir / "awsglance.db"
            if not db.is_file():
                print(f"No collected data at {db}. Run awsglance --profile <name> first and let it collect, "
                      "or try: awsglance export --demo", file=sys.stderr)
                return 2
            with _data_folder_errors(data_dir):
                store = Store(db)
            try:
                target = export_static(store, args.out)
            finally:
                store.close()
    except ExportError as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 2
    base = target.resolve().as_uri()
    print(f"Exported a read-only copy: {target}")
    print("Open it in a browser (no server needed). Screens:")
    for route in HASH_ROUTES:
        print(f"  {base}{route}")
    return 0


# ---- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "policy":
        from .aws.policy import policy_json

        sys.stdout.write(policy_json())
        return 0

    if args.command == "export":
        return run_export(args)

    from .web.app import create_app, is_loopback

    temp_dir = None
    if args.selftest and args.data_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="awsglance-selftest-")  # 자체 점검은 사용자 데이터 폴더를 건드리지 않는다
    data_dir = Path(temp_dir or args.data_dir or default_data_dir()).expanduser()
    with _data_folder_errors(data_dir):
        data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(data_dir, 0o700)
    settings = load(data_dir)

    scheduler = session = None
    if args.demo:
        store = prepare_demo(data_dir)
    else:
        if args.selftest:
            print("--selftest needs --demo (it never calls AWS)", file=sys.stderr)
            return 2
        store, scheduler, session = prepare_live(args, data_dir, settings)

    token = None if is_loopback(args.host) else _token_for(data_dir)
    app = create_app(store, bind_host=args.host, token=token, allowed_hosts=args.allow_host, scheduler=scheduler)
    try:
        if args.selftest:
            return selftest(app)
        import uvicorn

        if not port_is_free(args.host, args.port):
            print(f"Port {args.port} is in use — pick another with --port (for example --port {args.port + 1}).",
                  file=sys.stderr)
            return 2
        shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
        url = f"http://{shown}:{args.port}/" + (f"?token={token}" if token else "")
        print(f"awsglance {__version__} — open {url}  (Ctrl+C to stop)", flush=True)
        if scheduler:
            scheduler.start()
        timer = None
        if not args.no_browser:
            timer = threading.Timer(1.0, webbrowser.open, args=(url,))
            timer.daemon = True
            timer.start()
        try:
            uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        finally:
            if timer:
                timer.cancel()
        return 0
    finally:
        # 종료 경로: 스케줄러 스레드 → AWS 연결 풀 → DB 순서로 정리
        if scheduler:
            scheduler.stop()
        if session:
            session.close()
        store.close()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
