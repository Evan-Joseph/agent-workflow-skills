#!/usr/bin/env python3
"""Deterministic :9223 Chrome CDP Relay Controller & DevToolsActivePort Syncer (`cdp_ctl.py`).

Bridges macOS `com.apple.macl` app-data isolation between GUI-parented Agent shells
(which can read `~/Library/Application Support/Google/Chrome/DevToolsActivePort`) and
`launchd`-spawned `com.agents.chrome-cdp-daemon` (`${CDP_RELAY_HOST}`), atomically syncing
`0600` `~/.local/state/chrome-cdp-daemon/DevToolsActivePort` and `POST /endpoint` before
issuing `:9223` relay commands.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

DEFAULT_CDP_URL = os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223"))
CHROME_ACTIVE_PORT_FILE = (
    pathlib.Path.home() / "Library/Application Support/Google/Chrome/DevToolsActivePort"
)
DAEMON_STATE_DIR = pathlib.Path.home() / ".local/state/chrome-cdp-daemon"
MIRROR_ACTIVE_PORT_FILE = DAEMON_STATE_DIR / "DevToolsActivePort"


def read_chrome_active_port(
    src_path: pathlib.Path = CHROME_ACTIVE_PORT_FILE,
) -> dict[str, Any] | None:
    try:
        st = src_path.stat()
        lines = [ln.strip() for ln in src_path.read_text("utf-8").splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        port = int(lines[0])
        ws_path = lines[1] if lines[1].startswith("/") else f"/{lines[1]}"
        if not ws_path.startswith("/devtools/browser/"):
            return None
        mtime_ms = int(st.st_mtime * 1000)
        return {
            "port": port,
            "wsPath": ws_path,
            "mtimeMs": mtime_ms,
            "fingerprint": f"{port}:{ws_path}:{mtime_ms}",
        }
    except Exception:
        return None


def write_mirror_active_port(
    info: dict[str, Any],
    mirror_path: pathlib.Path = MIRROR_ACTIVE_PORT_FILE,
) -> bool:
    try:
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"{info['port']}\n{info['wsPath']}\n{info['mtimeMs']}\n"
        if mirror_path.is_file():
            try:
                if mirror_path.read_text("utf-8") == content:
                    os.chmod(mirror_path, 0o600)
                    return False
            except Exception:
                pass
        tmp = mirror_path.with_name(f".DevToolsActivePort.tmp.{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, mirror_path)
        return True
    except Exception:
        return False


def cdp_http_json(
    cdp_url: str,
    route: str,
    payload: dict[str, Any] | None = None,
    *,
    method: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any]]:
    actual_method = method or ("POST" if payload is not None else "GET")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"{cdp_url.rstrip('/')}{route}",
        data=body,
        headers=headers,
        method=actual_method,
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {"ok": False, "error": f"http_{exc.code}"}
        except Exception:
            parsed = {"ok": False, "error": raw.strip() or f"http_{exc.code}"}
        return exc.code, parsed


def sync_devtools_endpoint(
    cdp_url: str = DEFAULT_CDP_URL,
    *,
    notify_daemon: bool = True,
    connect: bool = False,
) -> dict[str, Any]:
    info = read_chrome_active_port()
    if not info:
        return {
            "ok": False,
            "synced": False,
            "reason": "chrome_active_port_unreadable_or_absent",
        }
    file_updated = write_mirror_active_port(info)
    daemon_resp: dict[str, Any] = {}
    if notify_daemon:
        try:
            _, daemon_resp = cdp_http_json(
                cdp_url,
                "/endpoint",
                {
                    "port": info["port"],
                    "wsPath": info["wsPath"],
                    "mtimeMs": info["mtimeMs"],
                    "connect": bool(connect),
                },
                timeout=8.0,
            )
        except Exception as exc:
            daemon_resp = {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "synced": True,
        "mirrorUpdated": file_updated,
        "mirrorFile": str(MIRROR_ACTIVE_PORT_FILE),
        "endpoint": info,
        "daemon": daemon_resp,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage :9223 Chrome CDP relay & sync DevToolsActivePort")
    p.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Relay base URL (default: ${CDP_RELAY_URL})")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync-endpoint", help="Sync Chrome DevToolsActivePort UUID into 0600 mirror & :9223")
    p_sync.add_argument("--connect", action="store_true", help="Also trigger single-flight connectWS() on :9223")

    sub.add_parser("health", help="Sync endpoint (if readable) and query GET /health")
    sub.add_parser("tabs", help="Sync endpoint (if readable) and query GET /tabs")
    sub.add_parser("reconnect", help="Sync endpoint and trigger POST /reconnect")

    p_new = sub.add_parser("new", help="Create or reuse background [Agent] tab via POST /new")
    p_new.add_argument("--url", required=True)
    p_new.add_argument("--task", default="default")
    p_new.add_argument("--group", default="")
    p_new.add_argument("--reuse", action="store_true")
    p_new.add_argument("--ttl-ms", type=int, default=0)

    p_nav = sub.add_parser("navigate", help="Navigate an [Agent] tab via POST /navigate")
    p_nav.add_argument("--url", required=True)
    p_nav.add_argument("--target-id", default="")
    p_nav.add_argument("--url-sub", default="")
    p_nav.add_argument("--task", default="default")

    p_eval = sub.add_parser("eval", help="Evaluate JS expression via POST /eval")
    p_eval.add_argument("--expression", required=True)
    p_eval.add_argument("--target-id", default="")
    p_eval.add_argument("--url-sub", default="")
    p_eval.add_argument("--task", default="")

    p_txt = sub.add_parser("text", help="Extract innerText via POST /text")
    p_txt.add_argument("--target-id", default="")
    p_txt.add_argument("--url-sub", default="")
    p_txt.add_argument("--task", default="")

    p_clean = sub.add_parser("cleanup", help="Close ephemeral [Agent] tabs via POST /cleanup")
    p_clean.add_argument("--task", default="")
    p_clean.add_argument("--target-id", default="")
    p_clean.add_argument("--all-agents", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "sync-endpoint":
        res = sync_devtools_endpoint(args.cdp_url, notify_daemon=True, connect=args.connect)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    # Auto-sync DevToolsActivePort transparently before any :9223 command
    sync_devtools_endpoint(args.cdp_url, notify_daemon=True, connect=False)

    if args.cmd == "health":
        code, data = cdp_http_json(args.cdp_url, "/health", method="GET")
    elif args.cmd == "tabs":
        code, data = cdp_http_json(args.cdp_url, "/tabs", method="GET")
    elif args.cmd == "reconnect":
        code, data = cdp_http_json(args.cdp_url, "/reconnect", {})
    elif args.cmd == "new":
        pl: dict[str, Any] = {"url": args.url, "task": args.task, "reuse": bool(args.reuse)}
        if args.group:
            pl["group"] = args.group
        if args.ttl_ms > 0:
            pl["ttlMs"] = args.ttl_ms
        code, data = cdp_http_json(args.cdp_url, "/new", pl)
    elif args.cmd == "navigate":
        pl = {"url": args.url, "task": args.task}
        if args.target_id:
            pl["targetId"] = args.target_id
        if args.url_sub:
            pl["urlSub"] = args.url_sub
        code, data = cdp_http_json(args.cdp_url, "/navigate", pl)
    elif args.cmd == "eval":
        pl = {"expression": args.expression}
        if args.target_id:
            pl["targetId"] = args.target_id
        if args.url_sub:
            pl["urlSub"] = args.url_sub
        if args.task:
            pl["task"] = args.task
        code, data = cdp_http_json(args.cdp_url, "/eval", pl, timeout=25.0)
    elif args.cmd == "text":
        pl = {}
        if args.target_id:
            pl["targetId"] = args.target_id
        if args.url_sub:
            pl["urlSub"] = args.url_sub
        if args.task:
            pl["task"] = args.task
        code, data = cdp_http_json(args.cdp_url, "/text", pl, timeout=25.0)
    elif args.cmd == "cleanup":
        pl = {"allAgents": bool(args.all_agents)}
        if args.task:
            pl["task"] = args.task
        if args.target_id:
            pl["targetId"] = args.target_id
        code, data = cdp_http_json(args.cdp_url, "/cleanup", pl)
    else:
        return 2

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if 200 <= code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
