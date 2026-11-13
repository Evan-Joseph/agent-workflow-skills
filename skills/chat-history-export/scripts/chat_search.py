#!/usr/bin/env python3
"""Fast, zero-dependency CLI to search, list, and view exported WeChat/QQ chat histories."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

DEFAULT_LIBRARY_ROOT = Path.home() / "Documents/微信聊天记录资料库/exports"

def format_ts(ts: int | float | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def load_index(export_dir: Path) -> dict:
    idx_file = export_dir / "_export_index.json"
    if not idx_file.exists():
        return {}
    try:
        with idx_file.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def format_alias_note(info: dict) -> str:
    cur = info.get("current_chat_name") or ""
    parts = []
    nick = info.get("nick_name") or ""
    if nick and nick != cur:
        parts.append(f"原昵称: {nick}")
    prev = [p for p in (info.get("previous_names") or []) if p and p != cur and p != nick]
    if prev:
        shown = "、".join(prev[:3]) + ("等" if len(prev) > 3 else "")
        parts.append(f"曾用名: {shown}")
    return f" ({' | '.join(parts)})" if parts else ""


def file_meta_map(export_dir: Path) -> dict[str, dict]:
    index = load_index(export_dir)
    out: dict[str, dict] = {}
    for uname, info in (index.get("chats") or {}).items():
        if not isinstance(info, dict):
            continue
        cfile = info.get("current_file")
        if cfile:
            out[cfile] = info
    return out


def matches_chat_target(f: Path, meta: dict | None, target_lower: str) -> bool:
    if target_lower in f.stem.lower():
        return True
    if not meta:
        return False
    candidates = [
        meta.get("username") or "",
        meta.get("current_chat_name") or "",
        meta.get("nick_name") or "",
        meta.get("remark") or "",
        meta.get("alias") or "",
    ]
    candidates.extend(meta.get("previous_names") or [])
    candidates.extend(meta.get("previous_files") or [])
    return any(target_lower in str(c).lower() for c in candidates if c)


def cmd_list(args: argparse.Namespace) -> None:
    export_dir = Path(args.export_dir).expanduser()
    if not export_dir.exists():
        print(f"Error: Export directory does not exist: {export_dir}", file=sys.stderr)
        return

    index = load_index(export_dir)
    chats = index.get("chats", {})
    if chats:
        rows = []
        for uname, info in chats.items():
            name = (info.get("current_chat_name") or uname) + format_alias_note(info)
            cfile = info.get("current_file") or ""
            last_msg = info.get("date_last_msg") or ""
            is_grp = "群聊" if info.get("is_group") else "单聊"
            rows.append((last_msg, name, is_grp, cfile))
        rows.sort(key=lambda x: x[0], reverse=True)
        print(f"Total chats in library: {len(rows)}\n")
        print(f"{'最后消息时间':<20} | {'类型':<4} | {'会话名称 (含原昵称/曾用名)'}")
        print("-" * 76)
        for last_msg, name, is_grp, _ in rows:
            print(f"{last_msg:<20} | {is_grp:<4} | {name}")
    else:
        files = sorted(export_dir.glob("*.json"))
        print(f"Total exported JSON files: {len(files)}\n")
        for f in files:
            if f.name.startswith("_"):
                continue
            print(f.stem)

def cmd_search(args: argparse.Namespace) -> None:
    export_dir = Path(args.export_dir).expanduser()
    keyword = args.keyword.lower()
    target_filter = args.target.lower() if args.target else None
    meta_by_file = file_meta_map(export_dir)

    matches = []
    for f in export_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        meta = meta_by_file.get(f.name)
        if target_filter and not matches_chat_target(f, meta, target_filter):
            continue
        try:
            with f.open(encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            continue

        chat_name = (data.get("chat") or f.stem) + (format_alias_note(meta) if meta else "")
        messages = data.get("messages") or []
        for msg in messages:
            content = msg.get("content") or ""
            if keyword in content.lower():
                matches.append({
                    "chat": chat_name,
                    "sender": msg.get("sender") or "",
                    "time": format_ts(msg.get("timestamp")),
                    "content": content.strip()
                })

    print(f"Found {len(matches)} messages matching '{args.keyword}':\n")
    for m in matches[:args.limit]:
        print(f"[{m['time']}] 【{m['chat']}】 {m['sender']}:")
        for line in m['content'].split("\n"):
            print(f"  {line}")
        print()
    if len(matches) > args.limit:
        print(f"... and {len(matches) - args.limit} more matches (use --limit to show more).")

def cmd_view(args: argparse.Namespace) -> None:
    export_dir = Path(args.export_dir).expanduser()
    target = args.target.lower()
    meta_by_file = file_meta_map(export_dir)
    matched_file = None
    matched_meta = None

    # Exact stem/current_chat_name match first, then substring match across aliases/previous_names
    for f in export_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        meta = meta_by_file.get(f.name)
        if target in f.stem.lower():
            matched_file = f
            matched_meta = meta
            break

    if not matched_file:
        for f in export_dir.glob("*.json"):
            if f.name.startswith("_"):
                continue
            meta = meta_by_file.get(f.name)
            if matches_chat_target(f, meta, target):
                matched_file = f
                matched_meta = meta
                break

    if not matched_file:
        print(f"No chat found matching '{args.target}'.", file=sys.stderr)
        return

    with matched_file.open(encoding="utf-8") as fp:
        data = json.load(fp)

    chat_name = (data.get("chat") or matched_file.stem) + (format_alias_note(matched_meta) if matched_meta else "")
    messages = data.get("messages") or []
    print(f"=== 会话: {chat_name} (共 {len(messages)} 条消息) ===\n")

    display_msgs = messages[-args.limit:] if not args.all else messages
    for msg in display_msgs:
        t_str = format_ts(msg.get("timestamp"))
        sender = msg.get("sender") or ""
        content = msg.get("content") or ""
        print(f"[{t_str}] {sender}: {content}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", default=str(DEFAULT_LIBRARY_ROOT), help="Export directory path")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_list = sub.add_parser("list", help="List all exported chats")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Search keywords across chat messages")
    p_search.add_argument("keyword", help="Keyword to search")
    p_search.add_argument("--target", help="Filter by chat name")
    p_search.add_argument("--limit", type=int, default=20, help="Max results to display")
    p_search.set_defaults(func=cmd_search)

    p_view = sub.add_parser("view", help="View messages in a specific chat")
    p_view.add_argument("target", help="Chat/person name (partial match)")
    p_view.add_argument("--limit", type=int, default=30, help="Number of recent messages to show")
    p_view.add_argument("--all", action="store_true", help="Show all messages")
    p_view.set_defaults(func=cmd_view)

    args = parser.parse_args()
    args.func(args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
