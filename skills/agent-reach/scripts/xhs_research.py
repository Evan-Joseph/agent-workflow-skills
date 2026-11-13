#!/usr/bin/env python3
"""Xiaohongshu research helper backed 100% by Chrome ${CDP_RELAY_HOST} window.__INITIAL_STATE__.

Eliminates legacy external Python signature replay (`xiaohongshu-cli` / `xhs`) and
temporary Camoufox QR login, which previously caused dual-fingerprint session kick-out.
"""

from __future__ import annotations
import os

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import reach_hub  # noqa: E402


def save_json(data: Any, save_dir: str | None, prefix: str) -> None:
    if not save_dir:
        return
    out_dir = Path(save_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")[:80] or "xhs"
    path = out_dir / f"{stamp}-{safe_prefix}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved JSON: {path}", file=sys.stderr)


def runtime_health(_: argparse.Namespace) -> None:
    st = reach_hub.auth_status()
    xhs_st = st.get("platforms", {}).get("xiaohongshu", {})
    payload = {
        "ok": True,
        "engine": "cdp-9223-initial-state",
        "chrome_cdp": os.environ.get("CDP_RELAY_ADDR", os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")),
        "xiaohongshu": xhs_st,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def status(_: argparse.Namespace) -> None:
    st = reach_hub.auth_status()
    xhs_st = st.get("platforms", {}).get("xiaohongshu", {})
    print("runtime_health: OK (engine=cdp-9223-initial-state)")
    print(json.dumps(xhs_st, ensure_ascii=False, indent=2))


def refresh_login(ns: argparse.Namespace) -> None:
    res = reach_hub.xhs_login(timeout_s=getattr(ns, "timeout", 180))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        sys.exit(1)


def ensure_login(ns: argparse.Namespace) -> None:
    st = reach_hub.auth_status()
    if st.get("platforms", {}).get("xiaohongshu", {}).get("authenticated"):
        print("Xiaohongshu login inside Chrome 9223 is valid.")
        return
    refresh_login(ns)


def search(ns: argparse.Namespace) -> None:
    res = reach_hub.xhs_search(ns.keyword, limit=ns.limit)
    save_json(res, ns.save_dir, f"search-{ns.keyword}")
    print(json.dumps(res, ensure_ascii=False, indent=2))


def read(ns: argparse.Namespace) -> None:
    res = reach_hub.xhs_read(ns.url, comment_limit=20)
    save_json(res, ns.save_dir, "read")
    print(json.dumps(res, ensure_ascii=False, indent=2))


def comments(ns: argparse.Namespace) -> None:
    limit = 50 if getattr(ns, "all", False) else 20
    res = reach_hub.xhs_read(ns.url, comment_limit=limit)
    save_json(res, ns.save_dir, "comments")
    print(json.dumps(res, ensure_ascii=False, indent=2))


def feed(ns: argparse.Namespace) -> None:
    res = reach_hub.xhs_feed(limit=ns.limit)
    save_json(res, ns.save_dir, "feed")
    print(json.dumps(res, ensure_ascii=False, indent=2))


def topic(ns: argparse.Namespace) -> None:
    compact = []
    for idx, keyword in enumerate(ns.keywords):
        if idx > 0 and getattr(ns, "delay", 0) > 0:
            time.sleep(ns.delay)
        res = reach_hub.xhs_search(keyword, limit=ns.limit)
        save_json(res, ns.save_dir, f"topic-{keyword}")
        compact.append(
            {
                "keyword": keyword,
                "status": "OK" if res.get("ok") else "ERROR",
                "auth_mode": res.get("auth_mode"),
                "count": res.get("count", 0),
                "top_items": res.get("items", [])[: ns.limit],
            }
        )
    print(json.dumps(compact, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Xiaohongshu research helper backed by Chrome 9223 __INITIAL_STATE__")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("status")
    p.set_defaults(func=status)

    p = sub.add_parser("runtime-health")
    p.add_argument("--canary", action="store_true")
    p.set_defaults(func=runtime_health)

    p = sub.add_parser("refresh-login")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(func=refresh_login)

    p = sub.add_parser("ensure-login")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(func=ensure_login)

    p = sub.add_parser("search")
    p.add_argument("keyword")
    p.add_argument("--sort", choices=["general", "popular", "latest"], default="general")
    p.add_argument("--type", choices=["all", "image", "video"], default="all")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--save-dir")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=search)

    p = sub.add_parser("read")
    p.add_argument("url")
    p.add_argument("--save-dir")
    p.set_defaults(func=read)

    p = sub.add_parser("comments")
    p.add_argument("url")
    p.add_argument("--all", action="store_true")
    p.add_argument("--save-dir")
    p.set_defaults(func=comments)

    p = sub.add_parser("feed")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--save-dir")
    p.set_defaults(func=feed)

    p = sub.add_parser("topic")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--sort", choices=["general", "popular", "latest"], default="popular")
    p.add_argument("--type", choices=["all", "image", "video"], default="all")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--save-dir")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=topic)

    ns = parser.parse_args()
    ns.func(ns)


if __name__ == "__main__":
    main()
