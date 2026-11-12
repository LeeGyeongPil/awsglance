"""Static export: a single self-contained ``index.html`` that opens from ``file://`` with no server.

The page embeds a snapshot of every screen's API response (``window.__AWSGLANCE_SNAPSHOT__``)
and the front-end reads from it instead of calling ``fetch``. Screens are chosen with a hash
route (``index.html#/changes?tab=human``). Writing actions (suppress / close / reopen) are
disabled in the exported copy. The snapshot is produced by calling the real web app in-process
through ASGI (no network, no extra dependency), so it shows exactly what the server would.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlencode

from .i18n import msg
from .store import Store, iso, now_utc
from .web.app import STATIC_DIR, create_app

HASH_ROUTES = ["#/", "#/resources", "#/changes?tab=human", "#/changes?tab=all", "#/findings", "#/setup"]
_CHANGE_TABS = ["human", "automated", "unknown", "all"]
_FINDING_TABS = ["open", "suppressed", "resolved", "closed", "all"]


class ExportError(RuntimeError):
    """Raised with a message that tells the user how to fix the problem."""


def _asgi_get(app, path: str) -> object:
    """Call ``app`` once with a GET request and return the decoded JSON body (no sockets)."""
    raw_path, _, query = path.partition("?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": unquote(raw_path), "raw_path": raw_path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": [(b"host", b"127.0.0.1")],
             "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80)}
    status, chunks = 0, []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    if status != 200:
        raise ExportError(f"GET {path} returned {status} while exporting")
    return json.loads(b"".join(chunks))


def _qs(**params: str) -> str:
    # the front-end builds keys with URLSearchParams, so keep the same parameter order
    return urlencode(params)


def collect_snapshot(store: Store) -> dict:
    """Gather every response the five screens ask for (default filters plus each tab)."""
    app = create_app(store, bind_host="127.0.0.1")
    api: dict[str, object] = {}

    def fetch(path: str) -> dict:
        api[path] = _asgi_get(app, path)
        return api[path]  # type: ignore[return-value]

    fetch("/api/status")
    fetch("/api/setup")
    fetch("/api/overview")
    fetch("/api/rules")
    resources = fetch(f"/api/resources?{_qs(type='', region='', q='')}")
    for t in resources["facets"]["types"]:
        fetch(f"/api/resources?{_qs(type=t, region='', q='')}")
    for r in resources["facets"]["regions"]:
        fetch(f"/api/resources?{_qs(type='', region=r, q='')}")
    for item in resources["items"]:
        fetch("/api/resources/" + quote(item["key"], safe="!'()*~-_."))  # same escaping as encodeURIComponent
    for tab in _CHANGE_TABS:
        fetch(f"/api/changes?{_qs(tab=tab, q='', days='14', noise='false')}")
    fetch(f"/api/changes?{_qs(tab='all', q='', days='14', noise='true')}")
    for status in _FINDING_TABS:
        listing = fetch(f"/api/findings?{_qs(status=status, severity='', rule='')}")
        if status in ("open", "all"):
            for f in listing["items"]:
                fetch(f"/api/findings/{f['id']}")
    return {"exported_at": iso(now_utc()), "api": api}


def render_html(snapshot: dict, static_dir: Path = STATIC_DIR) -> str:
    """Inline the built CSS and JS plus the snapshot into one HTML file (module scripts do not load from file://)."""
    index = static_dir / "index.html"
    if not index.is_file():
        raise ExportError(msg("err.export_no_front_end"))
    html = index.read_text(encoding="utf-8")
    css = js = ""
    for m in re.finditer(r'<link rel="stylesheet"[^>]*href="/(assets/[^"]+)"[^>]*>', html):
        css += (static_dir / m.group(1)).read_text(encoding="utf-8")
    html = re.sub(r'<link rel="stylesheet"[^>]*>\s*', "", html)
    for m in re.finditer(r'<script type="module"[^>]*src="/(assets/[^"]+)"[^>]*></script>', html):
        js += (static_dir / m.group(1)).read_text(encoding="utf-8")
    html = re.sub(r'<script type="module"[^>]*></script>\s*', "", html)
    if not js:
        raise ExportError(msg("err.export_no_front_end"))
    # "<" is escaped so no value inside the data can close the script tag early
    data = (json.dumps(snapshot, ensure_ascii=False).replace("<", "\\u003c")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    js = js.replace("</script", "<\\/script")
    head_add = f"<style>{css}</style>\n"
    body_add = f"<script>window.__AWSGLANCE_SNAPSHOT__={data};</script>\n<script>{js}</script>\n"
    return html.replace("</head>", head_add + "</head>", 1).replace("</body>", body_add + "</body>", 1)


def export_static(store: Store, out_dir: Path) -> Path:
    """Write ``<out_dir>/index.html`` and return its path."""
    out_dir = Path(out_dir).expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise ExportError(msg("err.export_not_dir", path=out_dir))
    html = render_html(collect_snapshot(store))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "index.html"
    target.write_text(html, encoding="utf-8")
    return target
