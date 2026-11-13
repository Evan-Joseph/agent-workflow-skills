#!/usr/bin/env python3
"""Managed OpenCLI Bridge (`opencli`) backed by ${CDP_RELAY_HOST} & reach_hub.py.

Provides full CLI compatibility for both:
- `omnireach` browser adapters (`douyin`, `xiaohongshu`, `twitter`, `reddit`, `google`, `weixin`)
- `agent-reach` social/video workflows (`opencli bilibili subtitle/search`, `opencli xiaohongshu search/feed`, `opencli reddit read`)
All browser interactions strictly obey `browser-routing` (background:true, zero focus stealing, automatic /cleanup).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import reach_hub  # noqa: E402


def _emit(data: Any, fmt: str = "json", exit_code: int = 0) -> int:
    if fmt in ("yaml", "yml"):
        print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return exit_code


def _emit_list_result(res: dict[str, Any], key: str, fmt: str = "json") -> int:
    if not res.get("ok"):
        print(json.dumps(res, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    return _emit(res.get(key, []), fmt, exit_code=0)


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-v", "--version", "version"):
        print("opencli, version 2.0.3-cdp9223 (agent-reach managed bridge)")
        return 0
    if args[0] in ("-h", "--help", "help"):
        print("Usage: opencli <source> <command> [args...] [--limit N] [--format json|yaml]")
        return 0

    # Parse flags and positional tokens flexibly
    fmt = "json"
    limit = 10
    url_arg = ""
    view_arg = ""
    pos: list[str] = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in ("-f", "--format") and i + 1 < len(args):
            fmt = args[i + 1].lower()
            i += 2
        elif tok in ("-n", "--limit") and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif tok == "--url" and i + 1 < len(args):
            url_arg = args[i + 1]
            i += 2
        elif tok == "--view" and i + 1 < len(args):
            view_arg = args[i + 1]
            i += 2
        elif tok in ("--window", "--site-session", "--keep-tab") and i + 1 < len(args):
            i += 2
        elif tok in ("--stdout",):
            i += 1
        elif tok.startswith("-"):
            i += 1
        else:
            pos.append(tok)
            i += 1

    if len(pos) < 2:
        print(json.dumps({"ok": False, "error": f"Insufficient arguments: {args}"}))
        return 1

    source = pos[0].lower()
    cmd = pos[1].lower()
    target = " ".join(pos[2:]).strip() or url_arg

    if source == "weixin" and cmd in ("download", "read"):
        res = reach_hub.wechat_read(target)
        if res.get("ok") and res.get("content_markdown"):
            print(res["content_markdown"])
            return 0
        print(json.dumps([{"status": res.get("message") or res.get("error") or "failed"}]))
        return 0

    if source == "douyin":
        if cmd == "search":
            res = reach_hub.douyin_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("author", "user-videos"):
            res = reach_hub.douyin_author(target, limit=limit)
            return _emit_list_result(res, "works", fmt)
        if cmd == "comments":
            res = reach_hub.douyin_comments(target, limit=limit)
            return _emit_list_result(res, "comments", fmt)

    if source in ("xiaohongshu", "xhs"):
        if cmd == "search":
            res = reach_hub.xhs_search(target, limit=limit)
            if not res.get("ok"):
                print(json.dumps(res, ensure_ascii=False, indent=2), file=sys.stderr)
                return 1
            items = [
                {
                    "title": x.get("title", ""),
                    "url": x.get("url", ""),
                    "content": x.get("snippet", ""),
                    "author": x.get("author", ""),
                    "likes": str(x.get("likes", "0")),
                }
                for x in res.get("items", [])
            ]
            return _emit(items, fmt)
        if cmd == "feed":
            res = reach_hub.xhs_feed(limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("note", "read", "comments"):
            res = reach_hub.xhs_read(target, comment_limit=limit)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source in ("bilibili", "bili"):
        if cmd == "subtitle":
            res = reach_hub.bilibili_subtitle(target)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)
        if cmd == "search":
            res = reach_hub.bilibili_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("video", "comments"):
            res = reach_hub.bilibili_comments(target, limit=limit)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source == "zhihu":
        if cmd == "search":
            res = reach_hub.zhihu_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd == "read":
            res = reach_hub.zhihu_read(target)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)
        if cmd == "comments":
            res = reach_hub.zhihu_comments(target, limit=limit)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source in ("twitter", "x"):
        if cmd == "search":
            res = reach_hub.twitter_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("tweet", "article", "read"):
            res = reach_hub.twitter_read(target)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source == "reddit":
        if cmd == "search":
            res = reach_hub.reddit_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd == "read":
            res = reach_hub.reddit_read(target, limit=limit)
            if fmt in ("md", "markdown") and res.get("ok"):
                lines = [f"# {res.get('title')}", f"Subreddit: {res.get('subreddit')} | Score: {res.get('score')}", "", res.get("selftext") or "", "", "## Top Comments"]
                for c in res.get("comments", []):
                    lines.append(f"- **{c.get('author')}** ({c.get('score')} pts): {c.get('body')}")
                print("\n".join(lines))
                return 0
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source in ("youtube", "yt"):
        if cmd == "search":
            res = reach_hub.youtube_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("read", "subtitle"):
            res = reach_hub.youtube_read(target)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source == "52pojie":
        if cmd == "rss":
            res = reach_hub.pojie52_rss(limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("guide", "hot", "digest", "newthread"):
            v = view_arg or (target if cmd == "guide" and target else (cmd if cmd != "guide" else "hot"))
            res = reach_hub.pojie52_guide(view=v, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd == "search":
            res = reach_hub.pojie52_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("read", "thread"):
            res = reach_hub.pojie52_read(target, reply_limit=limit)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    if source == "v2ex":
        if cmd in ("hot", "latest"):
            res = reach_hub.v2ex_topics(cmd, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd == "search":
            res = reach_hub.v2ex_search(target, limit=limit)
            return _emit_list_result(res, "items", fmt)
        if cmd in ("read", "topic"):
            res = reach_hub.v2ex_read(target, reply_limit=limit)
            return _emit(res, fmt, exit_code=0 if res.get("ok") else 1)

    print(json.dumps({"ok": False, "error": f"Unsupported opencli command: {source} {cmd}"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
