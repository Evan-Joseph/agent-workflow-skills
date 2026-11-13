#!/usr/bin/env python3
"""LinuxDO 社区数据检索与交互 CLI 包装脚本。

基于 linuxdo-mcp 的底层会话与过盾机制（curl_cffi + pycookiecheat + discourse:// 授权），
提供快速检索、话题读取、最新榜单以及用户认证状态查询能力。
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterator

try:
    from linuxdo_mcp import auth, client, handler, server, session
except ModuleNotFoundError:
    _LINUXDO_PY = "python3"
    if os.path.exists(_LINUXDO_PY) and os.path.realpath(sys.executable) != os.path.realpath(_LINUXDO_PY):
        os.execv(_LINUXDO_PY, [_LINUXDO_PY, __file__, *sys.argv[1:]])
    raise


CACHE_DIR = Path("~/.cache/linuxdo-mcp").expanduser()
CLI_LOCK_FILE = CACHE_DIR / "cli.lock"
LAST_REQ_TS_FILE = CACHE_DIR / "last_req_ts"
MIN_REQ_INTERVAL_SEC = 0.85


@contextmanager
def _serialized_network_gate() -> Iterator[None]:
    """Serialize concurrent CLI callers and enforce >=0.85s inter-request spacing to prevent Cloudflare 403."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(CLI_LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            if LAST_REQ_TS_FILE.is_file():
                last_ts = float(LAST_REQ_TS_FILE.read_text(encoding="utf-8").strip() or "0")
                elapsed = time.time() - last_ts
                if 0.0 <= elapsed < MIN_REQ_INTERVAL_SEC:
                    time.sleep(MIN_REQ_INTERVAL_SEC - elapsed)
        except (OSError, ValueError):
            pass
        try:
            yield
        finally:
            try:
                tmp_ts = CACHE_DIR / f"last_req_ts.{os.getpid()}"
                tmp_ts.write_text(f"{time.time():.6f}\n", encoding="utf-8")
                os.chmod(tmp_ts, 0o600)
                os.replace(tmp_ts, LAST_REQ_TS_FILE)
            except OSError:
                pass
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def cmd_whoami(args: argparse.Namespace) -> int:
    try:
        user = server._whoami()
        if args.json:
            print(json.dumps(user, ensure_ascii=False, indent=2))
        else:
            print(f"用户名: {user.get('username')}")
            print(f"姓名: {user.get('name') or '—'}")
            print(f"信任等级: Lv{user.get('trust_level', 0)}")
            print(f"管理员: {'是' if user.get('admin') else '否'}")
            print(f"版主: {'是' if user.get('moderator') else '否'}")
        return 0
    except Exception as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1


def cmd_login(args: argparse.Namespace) -> int:
    try:
        user = server._cli_login()
        print("授权成功！当前登录账号：")
        print(json.dumps(user, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"登录失败: {exc}", file=sys.stderr)
        return 1


def cmd_logout(args: argparse.Namespace) -> int:
    try:
        res = server._logout()
        print("已退出登录（本地独立会话已清除）。")
        return 0
    except Exception as exc:
        print(f"退出失败: {exc}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    query = args.query or args.query_opt
    if not query:
        print("错误: 必须提供搜索关键词 (query 或 -q/--query)", file=sys.stderr)
        return 2
    try:
        if args.raw or args.json:
            res = server._search(query, page=args.page, pages=args.pages)
            if args.limit and isinstance(res, dict) and "topics" in res:
                res["topics"] = res["topics"][: args.limit]
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            formatted = server._format_search(query, page=args.page, pages=args.pages)
            if args.limit and args.limit > 0:
                lines = formatted.splitlines()
                header = lines[:2] if len(lines) >= 2 else []
                body = lines[2:]
                blocks: list[list[str]] = []
                for ln in body:
                    if ln.startswith("- **"):
                        blocks.append([ln])
                    elif blocks:
                        blocks[-1].append(ln)
                trimmed = [ln for b in blocks[: args.limit] for ln in b]
                formatted = "\n".join(header + trimmed)
            print(formatted)
        return 0
    except Exception as exc:
        print(f"搜索失败: {exc}", file=sys.stderr)
        return 1


def cmd_topic(args: argparse.Namespace) -> int:
    posts = args.posts
    if args.limit is not None:
        posts = args.limit
    elif args.end is not None and args.end >= args.start:
        posts = args.end - args.start + 1
    try:
        if args.raw or args.json:
            res = server._topic(args.topic_id, posts=posts, start=args.start)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            formatted = server._format_topic(args.topic_id, posts=posts, start=args.start)
            print(formatted)
        return 0
    except Exception as exc:
        print(f"获取话题失败: {exc}", file=sys.stderr)
        return 1


def _print_topics_table(header_line: str, topics: list[dict[str, Any]]) -> None:
    print(f"{header_line}\n")
    print("| 标题 | 分类 | 等级 | 回复 | 点赞 | 链接 |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for t in topics:
        title = (t.get("title") or "").replace("|", "\\|")
        cat = t.get("category") or "—"
        lv = f"Lv{t['min_trust_level']}" if t.get("min_trust_level") is not None else "—"
        replies = t.get("posts_count", 0)
        likes = t.get("like_count", 0)
        url = t.get("url", "")
        print(f"| {title} | {cat} | {lv} | {replies} | {likes} | {url} |")


def _slice_topics_result(res: dict[str, Any], limit: int | None) -> list[dict[str, Any]]:
    topics = list(res.get("topics") or [])
    if limit is not None and limit >= 0:
        topics = topics[:limit]
        res["topics"] = topics
        res["returned"] = len(topics)
    return topics


def cmd_latest(args: argparse.Namespace) -> int:
    try:
        res = server.latest_topics(page=args.page)
        topics = _slice_topics_result(res, args.limit)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_topics_table(f"LinuxDO 最新话题（第 {args.page} 页，共 {len(topics)} 条）：", topics)
        return 0
    except Exception as exc:
        print(f"获取最新话题失败: {exc}", file=sys.stderr)
        return 1


def cmd_top(args: argparse.Namespace) -> int:
    try:
        res = server.top_topics(period=args.period, page=args.page)
        topics = _slice_topics_result(res, args.limit)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_topics_table(f"LinuxDO 热门话题 ({args.period}，第 {args.page} 页，共 {len(topics)} 条）：", topics)
        return 0
    except Exception as exc:
        print(f"获取热门话题失败: {exc}", file=sys.stderr)
        return 1


def cmd_category_topics(args: argparse.Namespace) -> int:
    try:
        res = server.category_topics(category_id=args.category_id, page=args.page)
        topics = _slice_topics_result(res, args.limit)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_topics_table(
                f"LinuxDO 板块 #{args.category_id} 话题（第 {args.page} 页，共 {len(topics)} 条）：",
                topics,
            )
        return 0
    except Exception as exc:
        print(f"获取板块话题失败: {exc}", file=sys.stderr)
        return 1


def cmd_tags(args: argparse.Namespace) -> int:
    try:
        res = server.list_tags()
        tags = list(res.get("tags") or [])
        if args.limit is not None and args.limit >= 0:
            tags = tags[: args.limit]
            res["tags"] = tags
            res["count"] = len(tags)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"LinuxDO 标签列表（共 {len(tags)} 个）：\n")
            print("| 标签名 | 话题数 | 描述 |")
            print("| :--- | :--- | :--- |")
            for t in tags:
                name = str(t.get("name") or "").replace("|", "\\|")
                cnt = t.get("count", 0)
                desc = str(t.get("description") or "—").replace("|", "\\|").replace("\n", " ")
                print(f"| {name} | {cnt} | {desc} |")
        return 0
    except Exception as exc:
        print(f"获取标签列表失败: {exc}", file=sys.stderr)
        return 1


def cmd_tag_topics(args: argparse.Namespace) -> int:
    try:
        res = server.tag_topics(tag=args.tag, page=args.page)
        topics = _slice_topics_result(res, args.limit)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_topics_table(
                f"LinuxDO 标签「{args.tag}」话题（第 {args.page} 页，共 {len(topics)} 条）：",
                topics,
            )
        return 0
    except Exception as exc:
        print(f"获取标签话题失败: {exc}", file=sys.stderr)
        return 1


def cmd_user_actions(args: argparse.Namespace) -> int:
    try:
        res = server.user_actions(username=args.username, limit=args.limit)
        actions = list(res.get("actions") or [])
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"用户 @{args.username} 最近动态（共 {len(actions)} 条）：\n")
            print("| 类型 | 时间 | 话题/楼层 | 摘要 | 链接 |")
            print("| :--- | :--- | :--- | :--- | :--- |")
            for a in actions:
                act_type = "发帖" if a.get("action_type") == 4 else ("回复" if a.get("action_type") == 5 else str(a.get("action_type")))
                created = a.get("created_at") or "—"
                loc = f"{a.get('topic_id')}#{a.get('post_number')}"
                excerpt = str(a.get("excerpt") or "—").replace("|", "\\|").replace("\n", " ")[:120]
                url = a.get("url") or "—"
                print(f"| {act_type} | {created} | {loc} | {excerpt} | {url} |")
        return 0
    except Exception as exc:
        print(f"获取用户动态失败: {exc}", file=sys.stderr)
        return 1


def cmd_user(args: argparse.Namespace) -> int:
    try:
        info = server.user_info(username=args.username)
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"用户资料: {info.get('username')}")
            print(f"姓名: {info.get('name') or '—'}")
            print(f"信任等级: Lv{info.get('trust_level', 0)}")
            print(f"称号: {info.get('title') or '—'}")
            print(f"创建时间: {info.get('created_at')}")
            print(f"最后在线: {info.get('last_seen_at')}")
            print(f"话题数: {info.get('topic_count', 0)}")
            print(f"发帖数: {info.get('post_count', 0)}")
            print(f"给出点赞: {info.get('likes_given', 0)}")
            print(f"收获点赞: {info.get('likes_received', 0)}")
            print(f"解决问题数: {info.get('solved_count', 0)}")
        return 0
    except Exception as exc:
        print(f"查询用户资料失败: {exc}", file=sys.stderr)
        return 1


def cmd_categories(args: argparse.Namespace) -> int:
    try:
        res = server.list_categories()
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            cats = res.get("categories", [])
            print(f"LinuxDO 板块分类（共 {len(cats)} 个）：\n")
            print("| ID | 标识符 | 名称 | 话题数 | 帖子数 |")
            print("| :--- | :--- | :--- | :--- | :--- |")
            for c in cats:
                print(f"| {c.get('id')} | {c.get('slug')} | {c.get('name')} | {c.get('topic_count')} | {c.get('post_count')} |")
        return 0
    except Exception as exc:
        print(f"获取板块列表失败: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LinuxDO 社区数据检索与交互 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # whoami
    p_whoami = subparsers.add_parser("whoami", help="查看当前登录状态与信任等级")
    p_whoami.add_argument("--json", action="store_true", help="输出原始 JSON 数据")
    p_whoami.set_defaults(func=cmd_whoami)

    # login
    p_login = subparsers.add_parser("login", help="授权登录 LinuxDO")
    p_login.set_defaults(func=cmd_login)

    # logout
    p_logout = subparsers.add_parser("logout", help="退出登录并清理本地独立会话")
    p_logout.set_defaults(func=cmd_logout)

    # search
    p_search = subparsers.add_parser("search", help="搜索话题")
    p_search.add_argument("query", nargs="?", default="", help="搜索关键词或高级语法 (order:latest, #分类 等)")
    p_search.add_argument("-q", "--query", dest="query_opt", default="", help="搜索关键词（同位置参数 query）")
    p_search.add_argument("--page", type=int, default=1, help="起始页码（默认 1）")
    p_search.add_argument("--pages", type=int, default=1, help="抓取总页数（默认 1）")
    p_search.add_argument("-n", "--limit", type=int, default=None, help="限制返回条数（兼容别名）")
    p_search.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_search.add_argument("--raw", action="store_true", help="同 --json")
    p_search.set_defaults(func=cmd_search)

    # topic
    p_topic = subparsers.add_parser("topic", aliases=["get_topic", "read", "view"], help="获取指定话题详情与帖子内容")
    p_topic.add_argument("topic_id", help="话题数字 ID 或完整 URL")
    p_topic.add_argument("--posts", type=int, default=20, help="返回楼层数（默认 20）")
    p_topic.add_argument("-n", "--limit", type=int, default=None, help="同 --posts")
    p_topic.add_argument("--start", type=int, default=1, help="起始楼层 (1-based，默认 1)")
    p_topic.add_argument("--end", type=int, default=None, help="结束楼层 (1-based，自动换算为 posts)")
    p_topic.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_topic.add_argument("--raw", action="store_true", help="同 --json")
    p_topic.set_defaults(func=cmd_topic)

    # latest
    p_latest = subparsers.add_parser("latest", aliases=["latest_topics"], help="获取最新话题列表")
    p_latest.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p_latest.add_argument("-n", "--limit", type=int, default=None, help="限制返回条数（兼容别名）")
    p_latest.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_latest.set_defaults(func=cmd_latest)

    # top
    p_top = subparsers.add_parser("top", aliases=["top_topics", "hot"], help="获取热门话题列表")
    p_top.add_argument("--period", choices=server.TOP_PERIODS, default="weekly", help="周期 (daily/weekly/monthly/quarterly/yearly/all)")
    p_top.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p_top.add_argument("-n", "--limit", type=int, default=None, help="限制返回条数（兼容别名）")
    p_top.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_top.set_defaults(func=cmd_top)

    # user
    p_user = subparsers.add_parser("user", aliases=["user_info"], help="查询用户公开资料")
    p_user.add_argument("username", help="目标用户名")
    p_user.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_user.set_defaults(func=cmd_user)

    # categories
    p_cats = subparsers.add_parser("categories", aliases=["list_categories"], help="列出所有板块分类")
    p_cats.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_cats.set_defaults(func=cmd_categories)

    # category-topics
    p_cat_topics = subparsers.add_parser("category-topics", aliases=["category_topics"], help="列出指定板块分类下的话题")
    p_cat_topics.add_argument("category_id", type=int, help="板块数字 ID（可由 categories 查询）")
    p_cat_topics.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p_cat_topics.add_argument("-n", "--limit", type=int, default=None, help="限制返回条数")
    p_cat_topics.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_cat_topics.set_defaults(func=cmd_category_topics)

    # tags
    p_tags = subparsers.add_parser("tags", aliases=["list_tags"], help="列出所有标签及话题数")
    p_tags.add_argument("-n", "--limit", type=int, default=None, help="限制返回标签数")
    p_tags.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_tags.set_defaults(func=cmd_tags)

    # tag-topics
    p_tag_topics = subparsers.add_parser("tag-topics", aliases=["tag_topics"], help="列出指定标签下的话题")
    p_tag_topics.add_argument("tag", help="标签名称（如 人工智能）")
    p_tag_topics.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p_tag_topics.add_argument("-n", "--limit", type=int, default=None, help="限制返回条数")
    p_tag_topics.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_tag_topics.set_defaults(func=cmd_tag_topics)

    # user-actions
    p_uact = subparsers.add_parser("user-actions", aliases=["user_actions"], help="获取指定用户的发帖/回复动态")
    p_uact.add_argument("username", help="目标用户名")
    p_uact.add_argument("-n", "--limit", type=int, default=20, help="返回条数（默认 20）")
    p_uact.add_argument("--json", action="store_true", help="输出 JSON 结构数据")
    p_uact.set_defaults(func=cmd_user_actions)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.func in (cmd_login, cmd_logout):
        return args.func(args)
    with _serialized_network_gate():
        return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
