#!/usr/bin/env python3
"""
搜索 Skill 共享工具库。

提供标准 JSON 输出、CLI 脚手架、httpx helper 和配置读取。
所有搜索脚本通过 sys.path 导入此模块。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from typing import Any


def _ensure_local_proxy() -> None:
    """Auto-detect local Clash proxy at ${PROXY_HOST} when proxy env vars are unset."""
    if any(os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")):
        return
    try:
        with socket.create_connection(("127.0.0.1", 7897), timeout=0.2):
            proxy_url = os.environ.get("HTTPS_PROXY", "")
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            os.environ["ALL_PROXY"] = proxy_url
    except OSError:
        pass


_ensure_local_proxy()

try:
    import httpx
except ImportError:
    json.dump(
        {
            "success": False,
            "error": (
                "搜索运行时不完整，请运行：uv sync --project "
                "~/.agents/runtimes/research-search"
            ),
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 标准输出
# ---------------------------------------------------------------------------

def make_result(
    success: bool,
    query: str,
    provider: str,
    items: list[dict[str, Any]],
    error: str | None = None,
) -> dict[str, Any]:
    """构造标准化的搜索结果。"""
    return {
        "success": success,
        "query": query,
        "provider": provider,
        "items": items,
        "error": error,
    }


def make_item(
    title: str,
    url: str,
    snippet: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """构造标准化的搜索结果条目。"""
    item: dict[str, Any] = {"title": title, "url": url, "snippet": snippet}
    for k, v in extra.items():
        if v not in (None, "", [], {}):
            item[k] = v
    return item


def print_json(data: dict[str, Any]) -> None:
    """将结果 JSON 输出到 stdout。"""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# CLI 脚手架
# ---------------------------------------------------------------------------

def build_parser(description: str) -> argparse.ArgumentParser:
    """创建带有通用参数的 ArgumentParser（同时兼容位置参数 query 与 -q/--query）。"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("pos_query", nargs="?", help="搜索关键词")
    parser.add_argument("-q", "--query", dest="opt_query", help="搜索关键词（同位置参数）")
    parser.add_argument("--limit", "-n", "--num", type=int, default=10, help="返回结果数量（默认 10）")

    orig_parse = parser.parse_args

    def _parse_args(*args, **kwargs):
        ns = orig_parse(*args, **kwargs)
        ns.query = ns.opt_query or ns.pos_query
        if not ns.query:
            parser.error("必须提供 query（位置参数或 -q/--query）")
        return ns

    parser.parse_args = _parse_args  # type: ignore[assignment]
    return parser


# ---------------------------------------------------------------------------
# httpx helper
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 15
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def get_client(
    timeout: int = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> httpx.Client:
    """返回预配置的 httpx.Client。"""
    default_headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)
    return httpx.Client(
        timeout=timeout,
        headers=default_headers,
        follow_redirects=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 配置读取
# ---------------------------------------------------------------------------

def get_key(env_var: str, cli_arg: str | None = None) -> str | None:
    """读取 API key：CLI 参数 > 环境变量。"""
    if cli_arg:
        return cli_arg
    return os.environ.get(env_var)


def get_github_token(cli_arg: str | None = None) -> str | None:
    """读取 GitHub token：CLI 参数 > env > gh auth token。"""
    token = get_key("GITHUB_TOKEN", cli_arg) or os.environ.get("GH_TOKEN")
    if token:
        return token
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    token = result.stdout.strip()
    return token or None


# ---------------------------------------------------------------------------
# 脚本入口辅助
# ---------------------------------------------------------------------------

def run_search(
    provider: str,
    search_fn,  # Callable[[str, int, ...], list[dict]]
    parser: argparse.ArgumentParser | None = None,
    extra_kwargs_fn=None,  # Callable[[Namespace], dict] 从 args 提取额外参数
) -> None:
    """通用脚本入口：解析参数 → 执行搜索 → 输出 JSON。"""
    if parser is None:
        parser = build_parser(f"Search {provider}")
    args = parser.parse_args()

    extra = {}
    if extra_kwargs_fn:
        extra = extra_kwargs_fn(args)

    try:
        items = search_fn(args.query, args.limit, **extra)
        print_json(make_result(True, args.query, provider, items))
    except Exception as e:
        print_json(make_result(False, args.query, provider, [], str(e)))
        sys.exit(1)
