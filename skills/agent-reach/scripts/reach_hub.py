#!/usr/bin/env python3
"""Unified Multi-Platform Community Research & Hotlist Radar Hub (reach_hub.py).

Supports read-only, zero-focus-stealing search, content extraction, author catalogs,
subtitles, high-like comments, and hotlist radar across:
- 微信公众号 (WeChat Official Accounts: so.qq.com HTTP/SSE + Sogou/Yuanbao :9223 + full Markdown)
- 抖音 (Douyin: native :9223 search, creator catalog sorted by likes/recent, top comments, iesdouyin hotlist)
- 小红书 (Xiaohongshu: :9223 __INITIAL_STATE__ search when logged in, explore feed + xsec_token read; honest AUTH_REQUIRED when unauthenticated)
- B站 (Bilibili: official API search, video detail, top comments + sub-replies, CC/AI subtitles)
- 知乎 (Zhihu: :9223 api/v4/search_v3 & native DOM search, article/question read via Jina + :9223, high-vote comments)
- Twitter/X (:9223 authenticated X DOM search + zero-login Syndication @handle timeline & tweet read)
- Reddit (official reddit.com /search/ via :9223 + Arctic Shift API full post & comment tree)
- 吾爱破解 (52pojie: RSS, guide hot/digest/newthread, strict-domain AnySearch site:52pojie.cn, :9223 persistent-tab read)
- V2EX (v2ex: official hot/latest/show JSON API + first-party SOV2EX search API)
- YouTube (yt-dlp ytsearch + VTT subtitle extraction)
- 跨平台热榜雷达 (Hotlist Radar: Weibo, Douyin, Zhihu, Xiaohongshu, Bilibili, Baidu, V2EX, HN)

Strictly obeys browser-routing & zero-hallucination rules:
- Zero fake off-domain Google `site:` fallbacks.
- Every item URL is domain-verified against the target platform.
- Empty or unauthenticated results honestly return `ok: false` (`AUTH_REQUIRED` / `NO_RESULTS`).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

CDP_BASE = os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223"))
LOCAL_PROXY = os.environ.get("HTTPS_PROXY", "")
ANYSEARCH_PYTHON = "python3"
ANYSEARCH_CLI = os.path.expanduser("~/.agents/skills/anysearch/scripts/anysearch_cli.py")
YTDLP_BIN = (
    shutil.which("yt-dlp")
    or ("/opt/homebrew/bin/yt-dlp" if os.path.exists("/opt/homebrew/bin/yt-dlp") else "")
    or ("~/.agents/runtimes/research-search/.venv/bin/yt-dlp" if os.path.exists("~/.agents/runtimes/research-search/.venv/bin/yt-dlp") else "yt-dlp")
)
HANDOFF_NOTIFIER_BIN = Path("~/.local/libexec/notifiers/AgentHandoffNotifier.app/Contents/MacOS/terminal-notifier").expanduser()
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _url_matches_domains(url: Any, allowed_domains: tuple[str, ...]) -> bool:
    """Strictly verify URL scheme and hostname suffix against target platform domains."""
    s = str(url or "").strip()
    if not s.startswith(("http://", "https://")):
        return False
    try:
        host = (urllib.parse.urlparse(s).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def _q(text: str) -> str:
    """Agent-Reach v1.6.1 safe URL encoding: encode '/' and all reserved chars."""
    return urllib.parse.quote(str(text or ""), safe="")


def _is_empty_or_error_body(text: str, min_chars: int = 20) -> bool:
    """Agent-Reach v1.6.1 empty/shell body guard."""
    s = (text or "").strip()
    if len(s) < min_chars:
        return True
    head = s[:500]
    error_markers = (
        "403: Forbidden",
        "Warning: Target URL returned error",
        "环境异常",
        "完成验证后即可继续访问",
        "Just a moment...",
    )
    return any(m in head for m in error_markers)


def cdp_request(path: str, payload: dict[str, Any] | None = None, method: str = "POST", timeout: float = 20.0) -> dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(
        f"{CDP_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


@contextmanager
def cdp_background_tab(initial_url: str, task_name: str = "agent-reach-hub"):
    """Open a background tab via 9223 and guarantee /cleanup on exit."""
    tid = None
    try:
        res = cdp_request("/new", {"url": initial_url, "task": task_name, "reuse": True})
        tid = res.get("targetId")
        yield tid
    finally:
        try:
            cdp_request("/cleanup", {"task": task_name}, timeout=8.0)
        except Exception:
            if tid:
                try:
                    cdp_request("/close", {"targetId": tid}, timeout=5.0)
                except Exception:
                    pass


def cdp_eval(target_id: str, expression: str, timeout: float = 25.0) -> Any:
    res = cdp_request("/eval", {"targetId": target_id, "expression": expression}, timeout=timeout)
    return ((res.get("result") or {}).get("result") or {}).get("value")


def parse_compact_count(val: Any) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val or "").strip().replace(",", "").replace("+", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([万亿kmbKMB])?$", s)
    if not m:
        return 0
    num = float(m.group(1))
    unit = (m.group(2) or "").lower()
    mult = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "万": 10_000, "亿": 100_000_000}.get(unit, 1)
    return int(round(num * mult))


def _clean_vtt_subtitle(vtt_text: str) -> str:
    """Strip WEBVTT/Kind:/Language:/NOTE/STYLE headers, cue timestamps, and inline tags, deduplicating rolling lines."""
    lines: list[str] = []
    skip_block = False
    cue_ts_re = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}")
    header_meta_re = re.compile(r"^(?:WEBVTT(?:\s|$)|Kind\s*:|Language\s*:|X-TIMESTAMP-MAP\b|Region\s*:)", re.I)
    tag_re = re.compile(r"<[^>]+>")

    for raw_ln in (vtt_text or "").splitlines():
        s = raw_ln.strip()
        if not s:
            skip_block = False
            continue
        if skip_block:
            continue
        if s.startswith(("NOTE", "STYLE", "REGION")) and (len(s) in (4, 5, 6) or s[4:5].isspace() or s[5:6].isspace() or s[6:7].isspace()):
            skip_block = True
            continue
        if header_meta_re.match(s) or cue_ts_re.match(s) or s.isdigit():
            continue
        cleaned = html.unescape(tag_re.sub("", s)).strip()
        if not cleaned:
            continue
        if not lines or lines[-1] != cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _rerank_hotlist_items(query: str, items: list[dict[str, Any]], top_n: int | None = None) -> list[dict[str, Any]]:
    """Rerank hotlist items via local MagPie ${OPENAI_COMPAT_BASE_URL}/rerank (moark/Qwen3-Reranker-4B) using ProxyHandler({})."""
    if not items or not query.strip():
        return items
    probe_path = Path("~/.agents/config/openai-probe.json").expanduser()
    api_key = os.environ.get("MAGPIE_API_KEY", "").strip()
    base_url = os.environ.get("MAGPIE_BASE_URL", os.environ.get("OPENAI_COMPAT_BASE_URL", "http://" + os.environ.get("OPENAI_COMPAT_HOST", "localhost") + ":" + os.environ.get("OPENAI_COMPAT_PORT", "3425") + "/v1")).strip().rstrip("/")
    ua = "agent-reach-hotlist-rerank/1.0"
    if not api_key and probe_path.is_file():
        try:
            pdata = json.loads(probe_path.read_text(encoding="utf-8"))
            if isinstance(pdata, dict):
                api_key = str(pdata.get("api_key") or "").strip()
                base_url = str(pdata.get("base_url") or base_url).strip().rstrip("/")
                ua = str(pdata.get("user_agent") or ua).strip()
        except Exception:
            pass
    if not api_key:
        raise RuntimeError("Missing MAGPIE_API_KEY and ~/.agents/config/magpie-ops-probe.json api_key")

    rerank_url = f"{base_url}/rerank" if base_url.endswith("/v1") else f"{base_url}/v1/rerank"
    docs = [
        " | ".join(
            str(x)
            for x in (
                it.get("platform"),
                it.get("title"),
                it.get("excerpt") or it.get("rcmd_reason") or it.get("node") or "",
            )
            if x
        )[:1000]
        or "(empty)"
        for it in items
    ]
    limit = min(len(docs), max(1, top_n)) if top_n else len(docs)
    payload = json.dumps(
        {
            "model": "moark/Qwen3-Reranker-4B",
            "query": query.strip(),
            "documents": docs,
            "top_n": limit,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        rerank_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": ua,
            "X-Magpie-Session": "agent-reach-hotlist-rerank",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=20.0) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))

    rows = body.get("results") or body.get("data") or []
    ranked: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        score = row.get("relevance_score")
        if isinstance(idx, int) and 0 <= idx < len(items) and idx not in seen:
            enriched = dict(items[idx])
            if isinstance(score, (int, float)):
                enriched["rerank_score"] = round(float(score), 6)
            enriched["rerank_model"] = "moark/Qwen3-Reranker-4B"
            ranked.append(enriched)
            seen.add(idx)
    return ranked[:limit] if ranked else items[:limit]


# ---------------------------------------------------------------------------
# 1. Multi-Platform Hotlist Radar (Absorbed from ZJU-REAL/Easel + Official APIs)
# ---------------------------------------------------------------------------
def fetch_hotlist(
    platform: str = "all",
    limit: int = 15,
    keyword: str | None = None,
    rerank_query: str | None = None,
) -> dict[str, Any]:
    targets = (
        ["weibo", "douyin", "zhihu", "rednote", "bilibili", "baidu", "v2ex", "hackernews"]
        if platform == "all"
        else [platform.lower()]
    )
    fetch_cap = max(limit * 2, 30) if (keyword or rerank_query) else limit
    kw_re = re.compile(keyword, re.I) if keyword else None

    def _fetch_one(p: str) -> tuple[str, dict[str, Any]]:
        items: list[dict[str, Any]] = []
        source_used = ""
        try:
            with httpx.Client(headers=DEFAULT_HEADERS, timeout=10.0, follow_redirects=True) as client:
                if p == "weibo":
                    r = client.get("https://v2.xxapi.cn/api/weibohot")
                    d = (r.json().get("data") or []) if r.status_code == 200 else []
                    if d:
                        source_used = "xxapi:weibohot"
                        items = [{"rank": i + 1, "title": x.get("title"), "hot": x.get("hot"), "url": x.get("url")} for i, x in enumerate(d[:fetch_cap])]
                    else:
                        r2 = client.get("https://60s.viki.moe/v2/weibo")
                        d2 = r2.json().get("data") or []
                        source_used = "60s:weibo"
                        items = [{"rank": i + 1, "title": x.get("title"), "hot": x.get("hot_value"), "url": x.get("link") or x.get("url")} for i, x in enumerate(d2[:fetch_cap])]
                elif p == "douyin":
                    r = client.get("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/")
                    wl = (r.json().get("word_list") or []) if r.status_code == 200 else []
                    if wl:
                        source_used = "douyin:iesdouyin-billboard"
                        for i, x in enumerate(wl[:fetch_cap]):
                            word = str(x.get("word") or "").strip()
                            sid = str(x.get("sentence_id") or "").strip()
                            items.append({
                                "rank": i + 1,
                                "title": word,
                                "hot": x.get("hot_value"),
                                "url": f"https://www.douyin.com/hot/{sid}" if sid else f"https://www.douyin.com/search/{_q(word)}",
                            })
                    else:
                        r2 = client.get(
                            "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                            params={"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web"},
                            headers={**DEFAULT_HEADERS, "Referer": "https://www.douyin.com/"},
                        )
                        wl2 = (((r2.json().get("data") or {}).get("word_list")) or []) if r2.status_code == 200 else []
                        source_used = "douyin:aweme-hot-search"
                        for i, x in enumerate(wl2[:fetch_cap]):
                            word = str(x.get("word") or "").strip()
                            sid = str(x.get("sentence_id") or "").strip()
                            items.append({
                                "rank": x.get("position") or (i + 1),
                                "title": word,
                                "hot": x.get("hot_value"),
                                "url": f"https://www.douyin.com/hot/{sid}" if sid else f"https://www.douyin.com/search/{_q(word)}",
                            })
                elif p == "zhihu":
                    r = client.get("https://api.zhihu.com/topstory/hot-lists/total", params={"limit": fetch_cap})
                    d = r.json().get("data") or []
                    source_used = "zhihu:official-topstory"
                    for i, x in enumerate(d[:fetch_cap]):
                        t = x.get("target") or {}
                        qid = t.get("id")
                        items.append({
                            "rank": i + 1,
                            "title": t.get("title"),
                            "excerpt": (t.get("excerpt") or "")[:160],
                            "hot": x.get("detail_text"),
                            "url": f"https://www.zhihu.com/question/{qid}" if qid else "",
                        })
                elif p in ("rednote", "xiaohongshu", "xhs"):
                    d = []
                    try:
                        r = client.get("https://60s.viki.moe/v2/rednote")
                        if r.status_code == 200 and "json" in (r.headers.get("content-type") or "").lower():
                            d = r.json().get("data") or []
                    except Exception:
                        d = []
                    if d:
                        source_used = "60s:rednote"
                        items = [{"rank": x.get("rank") or (i + 1), "title": x.get("title"), "hot": x.get("score"), "url": x.get("link")} for i, x in enumerate(d[:fetch_cap])]
                    else:
                        xf = xhs_feed(max(fetch_cap, 15))
                        xitems = list(xf.get("items") or [])
                        xitems.sort(key=lambda x: parse_compact_count(x.get("likes")), reverse=True)
                        source_used = "xhs:explore-initial-state"
                        items = [
                            {
                                "rank": i + 1,
                                "title": x.get("title"),
                                "author": x.get("author"),
                                "hot": x.get("likes"),
                                "url": x.get("url"),
                            }
                            for i, x in enumerate(xitems[:fetch_cap])
                        ]
                elif p in ("bilibili", "bili"):
                    r = client.get("https://api.bilibili.com/x/web-interface/popular", params={"ps": fetch_cap, "pn": 1}, headers={**DEFAULT_HEADERS, "Referer": "https://www.bilibili.com/"})
                    d = ((r.json().get("data") or {}).get("list")) or []
                    source_used = "bilibili:popular-api"
                    for i, x in enumerate(d[:fetch_cap]):
                        bvid = x.get("bvid")
                        stat = x.get("stat") or {}
                        items.append({
                            "rank": i + 1,
                            "title": x.get("title"),
                            "author": (x.get("owner") or {}).get("name"),
                            "views": stat.get("view"),
                            "likes": stat.get("like"),
                            "rcmd_reason": (x.get("rcmd_reason") or {}).get("content"),
                            "url": f"https://www.bilibili.com/video/{bvid}" if bvid else x.get("short_link_v2"),
                        })
                elif p == "baidu":
                    r = client.get("https://v2.xxapi.cn/api/baiduhot")
                    d = r.json().get("data") or []
                    source_used = "xxapi:baiduhot"
                    items = [{"rank": i + 1, "title": x.get("title") if isinstance(x, dict) else str(x), "hot": x.get("hot") if isinstance(x, dict) else None, "url": x.get("url") if isinstance(x, dict) else None} for i, x in enumerate(d[:fetch_cap])]
                elif p == "v2ex":
                    d = _v2ex_api_get("/api/topics/hot.json")
                    rows = d if isinstance(d, list) else []
                    source_used = "v2ex:hot-api"
                    items = [{"rank": i + 1, "title": x.get("title"), "replies": x.get("replies"), "node": (x.get("node") or {}).get("title"), "url": x.get("url")} for i, x in enumerate(rows[:fetch_cap])]
                elif p in ("hackernews", "hn"):
                    r = client.get("https://hn.algolia.com/api/v1/search", params={"tags": "front_page", "hitsPerPage": fetch_cap})
                    d = r.json().get("hits") or []
                    source_used = "hn:algolia-frontpage"
                    items = [{"rank": i + 1, "title": x.get("title"), "points": x.get("points"), "comments": x.get("num_comments"), "url": x.get("url") or f"https://news.ycombinator.com/item?id={x.get('objectID')}"} for i, x in enumerate(d[:fetch_cap])]

            raw_fetched = len(items)
            if kw_re is not None:
                items = [
                    it for it in items
                    if kw_re.search(" ".join(str(it.get(k) or "") for k in ("title", "excerpt", "rcmd_reason", "node")))
                ]
            plat_ok = raw_fetched > 0
            return p, {
                "ok": plat_ok,
                "source": source_used,
                "count": len(items[:limit]),
                **({"error": "EMPTY_HOTLIST"} if not plat_ok else {}),
                "items": items[:limit],
            }
        except Exception as exc:
            return p, {"ok": False, "error": str(exc), "items": []}

    results_map: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(targets)))) as pool:
        futs = [pool.submit(_fetch_one, p) for p in targets]
        for fut in as_completed(futs):
            pname, pdata = fut.result()
            results_map[pname] = pdata

    ordered_platforms = {p: results_map[p] for p in targets if p in results_map}
    any_ok = any(v.get("ok") for v in ordered_platforms.values())
    out: dict[str, Any] = {
        "ok": any_ok,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "platforms": ordered_platforms,
    }
    if not any_ok:
        out["error"] = "ALL_HOTLIST_SOURCES_FAILED"

    if keyword:
        out["keyword_filter"] = keyword
    if rerank_query:
        pooled: list[dict[str, Any]] = []
        for plat_name, pblock in out["platforms"].items():
            for it in pblock.get("items") or []:
                pooled.append({"platform": plat_name, **it})
        try:
            out["rerank_query"] = rerank_query
            out["reranked_items"] = _rerank_hotlist_items(rerank_query, pooled, top_n=limit)
        except Exception as exc:
            out["rerank_error"] = str(exc)
    return out


# ---------------------------------------------------------------------------
# 2. WeChat Official Accounts (微信公众号: so.qq.com HTTP/SSE + Sogou/Yuanbao :9223 + Migrated Filter)
# ---------------------------------------------------------------------------
def _resolve_sogou_link(client: httpx.Client, href: str, referer: str) -> str | None:
    h = href.replace("&amp;", "&")
    b = 42
    pos = h.find("url=")
    ch = h[pos + 4 + 21 + b] if (pos != -1 and len(h) > pos + 25 + b) else "a"
    sogou_url = f"https://weixin.sogou.com{h}&k={b}&h={ch}" if h.startswith("/") else h
    try:
        lr = client.get(sogou_url, headers={"Referer": referer})
        if "antispider" not in str(lr.url).lower():
            frags = re.findall(r"url\s*\+=\s*'([^']*)'", lr.text)
            if frags:
                return "".join(frags).replace("@", "")
    except Exception:
        pass
    return None


def wechat_read(url: str) -> dict[str, Any]:
    with httpx.Client(headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True) as client:
        target_url = url
        if "weixin.sogou.com/link" in url:
            resolved = _resolve_sogou_link(client, url, "https://weixin.sogou.com/")
            if resolved:
                target_url = resolved
        if "mp.weixin.qq.com" in target_url:
            r = client.get(target_url, headers={"Referer": "https://weixin.sogou.com/"})
            soup = BeautifulSoup(r.text, "html.parser")
            title_el = soup.select_one("#activity-name")
            author_el = soup.select_one("#js_name")
            content_el = soup.select_one("#js_content")
            if title_el and content_el:
                title_txt = title_el.get_text(" ", strip=True)
                author_txt = author_el.get_text(" ", strip=True) if author_el else ""
                body_txt = content_el.get_text("\n", strip=True)
                if not _is_empty_or_error_body(body_txt, min_chars=10):
                    return {
                        "ok": True,
                        "url": target_url,
                        "backend": "http-direct",
                        "title": title_txt,
                        "author": author_txt,
                        "content_length": len(body_txt),
                        "content_markdown": f"# {title_txt}\n\n**公众号**：{author_txt}\n\n{body_txt}",
                    }
            page_msg = soup.get_text(" ", strip=True)[:200]
            if "该公众号已迁移" in r.text:
                return {"ok": False, "url": target_url, "error": "account_migrated_or_closed", "message": "该历史公众号已迁移或注销回收"}
        else:
            page_msg = "sogou_link_requires_cdp_resolution"
    # Fallback to 9223 background tab if Sogou redirect or environment verification wall was served
    with cdp_background_tab(target_url, task_name="wechat-read") as tid:
        time.sleep(3.5)
        val = cdp_eval(tid, """(() => {
            const title = (document.querySelector('#activity-name') || {}).innerText || document.title;
            const author = (document.querySelector('#js_name') || {}).innerText || '';
            const content = (document.querySelector('#js_content') || {}).innerText || '';
            return { url: location.href, title: title.trim(), author: author.trim(), content: content.trim() };
        })()""") or {}
        if val.get("content") and not _is_empty_or_error_body(val["content"], min_chars=10):
            return {
                "ok": True,
                "url": val.get("url") or target_url,
                "backend": "cdp-9223",
                "title": val.get("title"),
                "author": val.get("author"),
                "content_length": len(val["content"]),
                "content_markdown": f"# {val.get('title')}\n\n**公众号**：{val.get('author')}\n\n{val['content']}",
            }
    return {"ok": False, "url": target_url, "error": "empty_or_blocked", "message": page_msg}


SO_QQ_AIMODE_TOKEN = "aimode_token_1739178536"
PUA_HIGHLIGHT_RE = re.compile(r"[\ue40a\ue40b]")


def _so_qq_clean_text(val: Any) -> str:
    return PUA_HIGHLIGHT_RE.sub("", str(val or "")).strip()


def _so_qq_generate_verify(sign_target: str) -> dict[str, Any]:
    salt_hex = os.urandom(16).hex()
    ts = int(time.time())
    plain = f"{hashlib.md5(sign_target.encode('utf-8')).hexdigest()}{salt_hex}{ts}"
    key_hex = hashlib.sha256(SO_QQ_AIMODE_TOKEN.encode("utf-8")).hexdigest()
    proc = subprocess.run(
        ["/usr/bin/openssl", "enc", "-aes-256-cbc", "-K", key_hex, "-iv", salt_hex],
        input=plain.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=3,
        check=True,
    )
    return {"salt": salt_hex, "timestamp": ts, "sign": proc.stdout.hex()}


def so_qq_nextpage_search(
    query: str,
    *,
    tab: str = "weixin_article",
    time_filter: str = "all",
    page: int = 1,
    limit: int = 15,
) -> dict[str, Any]:
    """Zero-login, ~1s HTTP POST to https://so.qq.com/searchweb/api/search/next-page."""
    headers = {**DEFAULT_HEADERS, "Origin": "https://so.qq.com", "Referer": "https://so.qq.com/isearch"}
    sp: dict[str, Any] = {"tab": tab}
    if time_filter and time_filter != "all":
        sp["timeFilter"] = time_filter
    payload = {"query": query, "page": max(1, page), "variant": "pc", "sp": sp}
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        r = client.post("https://so.qq.com/searchweb/api/search/next-page", json=payload)
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "items": []}
        data = r.json()
    if not data.get("ok"):
        return {"ok": False, "error": "so_qq_not_ok", "items": []}

    items: list[dict[str, Any]] = []
    for card in data.get("cards") or []:
        vm = ((card.get("data") or {}).get("vm")) or {}
        raw_url = str(vm.get("jumpUrl") or vm.get("url") or "").strip()
        title = _so_qq_clean_text(vm.get("title"))
        if not raw_url or not title:
            continue
        if tab == "weixin_article" and "mp.weixin.qq.com" not in raw_url:
            continue
        clean_url = re.sub(r"^http://", "https://", raw_url) if "mp.weixin.qq.com" in raw_url else raw_url
        pub_str = _so_qq_clean_text(vm.get("publishTime") or vm.get("time"))
        ts_val = None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", pub_str):
            ts_val = int(datetime.strptime(pub_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        items.append(
            {
                "title": title,
                "author": _so_qq_clean_text(vm.get("authorName") or vm.get("siteName") or vm.get("host")),
                "snippet": _so_qq_clean_text(vm.get("summary") or vm.get("abstract")),
                "ts": ts_val,
                "published_date": pub_str or None,
                "url": clean_url,
                "backend": "so-qq-nextpage-http",
            }
        )
        if len(items) >= limit:
            break
    return {
        "ok": True,
        "platform": "so-qq",
        "tab": tab,
        "time_filter": time_filter,
        "page": page,
        "has_more": bool(data.get("hasMore")),
        "query": query,
        "count": len(items),
        "items": items,
    }


def so_qq_aimode_search(query: str, *, wechat_bias: bool = True, want_summary: bool = False, limit: int = 12) -> dict[str, Any]:
    """Zero-login SSE POST to lizhiassistant.search.qq.com/browser_aimode/aimode/query_get."""
    q_prompt = (
        query
        if (not wechat_bias or "公众号" in query or "微信" in query)
        else f"{query} 微信公众号最新文章"
    )
    payload = {
        "session_id": str(uuid.uuid4()),
        "stream": True,
        "uid": str(uuid.uuid4()),
        "qinfo": "",
        "query": q_prompt,
        "enable_enhancement": True,
        "model": "deepseek-v3",
        "ext": {"regen_query_id": -1, "neo_sphere": "outer"},
        "verify": _so_qq_generate_verify(q_prompt),
    }
    headers = {**DEFAULT_HEADERS, "Origin": "https://so.qq.com", "Referer": "https://so.qq.com/"}
    all_docs: list[dict[str, Any]] = []
    wx_docs: list[dict[str, Any]] = []
    summary_parts: list[str] = []
    with httpx.Client(headers=headers, timeout=25.0) as client:
        with client.stream(
            "POST",
            "https://lizhiassistant.search.qq.com/browser_aimode/aimode/query_get",
            json=payload,
        ) as resp:
            if resp.status_code != 200:
                return {"ok": False, "error": f"HTTP {resp.status_code}", "wxDocs": [], "items": [], "summary": ""}
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("data_type") == "anti_crawl" and (ev.get("data") or {}).get("status") != "pass":
                    return {"ok": False, "error": "so_qq_anti_crawl_blocked", "wxDocs": [], "items": [], "summary": ""}
                if "search_info" in ev:
                    for sr in (ev["search_info"].get("search_results") or []):
                        u = str(sr.get("url") or "").strip()
                        if not u:
                            continue
                        doc = {
                            "title": _so_qq_clean_text(sr.get("title")),
                            "author": _so_qq_clean_text(sr.get("site_name") or sr.get("source")),
                            "snippet": _so_qq_clean_text(sr.get("abstract")),
                            "ts": sr.get("publish_time_ts"),
                            "published_date": sr.get("time") or None,
                            "url": re.sub(r"^http://", "https://", u) if "mp.weixin.qq.com" in u else u,
                            "backend": "so-qq-aimode-sse",
                        }
                        all_docs.append(doc)
                        if "mp.weixin.qq.com" in u:
                            wx_docs.append(doc)
                    if not want_summary:
                        break
                if want_summary and ev.get("choices"):
                    delta = (ev["choices"][0].get("delta") or {}).get("content") or ""
                    if delta:
                        summary_parts.append(delta)
    return {
        "ok": True,
        "platform": "so-qq-ai",
        "query": query,
        "count": len(all_docs[:limit]),
        "items": all_docs[:limit],
        "wxDocs": wx_docs[:limit],
        "summary": "".join(summary_parts).strip(),
    }


def wechat_yuanbao_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Query Tencent Yuanbao (yuanbao.tencent.com) in Chrome 9223 to harvest native WeChat Search (微信搜一搜) citations, then auto-delete the temp conversation."""
    prompt_text = f"请使用微信搜一搜检索微信公众号关于「{query}」的最新文章，列出公众号名称与文章标题"
    with cdp_background_tab("https://yuanbao.tencent.com/chat/naQivTmsDa", task_name="wechat-yuanbao") as tid:
        for _ in range(12):
            time.sleep(0.5)
            if cdp_eval(tid, "!!document.querySelector('.ql-editor')"):
                break
        time.sleep(0.6)
        out = cdp_eval(
            tid,
            f"""(async () => {{
                const delay = ms => new Promise(r => setTimeout(r, ms));
                const ed = document.querySelector('.ql-editor');
                if (!ed) return {{ ok: false, error: 'yuanbao_not_logged_in_or_editor_missing' }};
                ed.focus();
                document.execCommand('insertText', false, {json.dumps(prompt_text)});
                await delay(300);
                const sendBtn = document.querySelector('[class*=SendButton_sendButton], [class*=send-btn], [class*=sendBtn], .yb-input-send-btn, [class*=style__send-btn]');
                if (sendBtn) sendBtn.click();
                let convId = '';
                for (let i = 0; i < 20; i++) {{
                    await delay(400);
                    const m = location.href.match(/\\/chat\\/[^/]+\\/([A-Za-z0-9_-]+)/);
                    if (m && m[1]) {{ convId = m[1]; break; }}
                }}
                if (!convId) return {{ ok: false, error: 'yuanbao_conv_id_timeout' }};
                let detail = null;
                try {{
                    for (let step = 0; step < 22; step++) {{
                        await delay(1200);
                        const r = await fetch('/api/user/agent/conversation/v1/detail', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ conversationId: convId }})
                        }});
                        detail = await r.json();
                        const s = JSON.stringify(detail);
                        if (s.includes('searchGuid') && s.includes('"msg"')) break;
                    }}
                }} finally {{
                    try {{
                        await fetch('/api/user/agent/conversation/v1/clear', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ conversationIds: [convId] }})
                        }});
                    }} catch (e) {{}}
                }}
                return {{ ok: true, convId, detail }};
            }})()""",
            timeout=38.0,
        ) or {}
        if not out.get("ok"):
            return {"ok": False, "error": out.get("error") or "yuanbao_eval_failed"}
        conv_id = str(out.get("convId") or "")
        detail = out.get("detail") or {}

        wx_docs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        def _walk(obj: Any) -> None:
            if isinstance(obj, list):
                for item in obj:
                    _walk(item)
            elif isinstance(obj, dict):
                u = obj.get("url") or obj.get("link") or ""
                if isinstance(u, str) and "mp.weixin.qq.com" in u:
                    clean_u = re.sub(r"^http://", "https://", u.strip())
                    if clean_u not in seen_urls:
                        seen_urls.add(clean_u)
                        wx_docs.append(
                            {
                                "title": str(obj.get("title") or obj.get("text") or "").strip(),
                                "url": clean_u,
                                "author": str(obj.get("sourceName") or obj.get("web_site_name") or "").strip(),
                                "snippet": str(obj.get("quote") or "").strip(),
                                "backend": "yuanbao-cdp-9223",
                            }
                        )
                for v in obj.values():
                    _walk(v)

        _walk(detail)
        summary = ""
        for conv in detail.get("convs") or []:
            if conv.get("speaker") == "ai":
                for sp in conv.get("speechesV2") or []:
                    for blk in sp.get("content") or []:
                        if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("msg"):
                            summary = str(blk.get("msg")).strip()
        return {"ok": True, "convId": conv_id, "wxDocs": wx_docs, "summary": summary}


def wechat_search(query: str, limit: int = 10, with_body: bool = False, deep: bool = False) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    skipped_migrated = 0
    seen_urls: set[str] = set()
    backends_used: list[str] = []
    yuanbao_summary: str | None = None

    raw_candidates: list[dict[str, Any]] = []

    # Stage 1a (Default fast zero-login HTTP, ~1s): Tencent so.qq.com /searchweb/api/search/next-page (100% permanent __biz URLs)
    try:
        sq_np = so_qq_nextpage_search(query, tab="weixin_article", limit=max(limit + 4, 18))
        if sq_np.get("ok") and sq_np.get("items"):
            backends_used.append("so-qq-nextpage-http")
            raw_candidates.extend(sq_np["items"])
    except Exception:
        pass

    # Stage 1b (Zero-login SSE long-tail recall / --deep summary, ~4s early-stop): so.qq.com AI mode
    if deep or len(raw_candidates) < limit:
        try:
            sq_ai = so_qq_aimode_search(query, wechat_bias=True, want_summary=deep, limit=max(limit, 12))
            if sq_ai.get("ok"):
                if sq_ai.get("wxDocs"):
                    backends_used.append("so-qq-aimode-sse")
                    # When --deep is explicitly requested, prioritize fresh long-tail SSE citations alongside permanent links
                    if deep:
                        raw_candidates = list(sq_ai["wxDocs"]) + raw_candidates
                    else:
                        raw_candidates.extend(sq_ai["wxDocs"])
                if sq_ai.get("summary"):
                    yuanbao_summary = sq_ai["summary"]
        except Exception:
            pass

    # Optional Browser Fallback Stage 2a (only if pure-HTTP so.qq.com channels returned < limit and --deep was requested)
    if deep and len(raw_candidates) < limit:
        try:
            yb = wechat_yuanbao_search(query, limit=limit)
            if yb.get("ok") and yb.get("wxDocs"):
                backends_used.append("yuanbao-cdp-9223")
                raw_candidates.extend(yb["wxDocs"])
                if not yuanbao_summary:
                    yuanbao_summary = yb.get("summary") or None
        except Exception:
            pass

    # Browser Fallback Stage 2b: Sogou WeChat Search via ${CDP_RELAY_HOST} CDP background tab (only when needed)
    if len(raw_candidates) < limit:
        sogou_search_url = f"https://weixin.sogou.com/weixin?type=2&query={_q(query)}&ie=utf8"
        try:
            with cdp_background_tab(sogou_search_url, task_name="wechat-search") as tid:
                for _ in range(10):
                    time.sleep(0.45)
                    ready = cdp_eval(
                        tid,
                        "document.querySelectorAll('ul.news-list li').length > 0 || location.href.includes('antispider')",
                    )
                    if ready:
                        break
                sogou_cands = cdp_eval(tid, f"""(async () => {{
                    if (location.href.includes('antispider')) return [];
                    const lis = Array.from(document.querySelectorAll('ul.news-list li')).slice(0, {max(limit + 4, 12)});
                    const tasks = lis.map(async (li) => {{
                        const a = li.querySelector('h3 a');
                        if (!a) return null;
                        const rawHref = a.getAttribute('href') || '';
                        const b = 42;
                        const pos = rawHref.indexOf('url=');
                        const ch = (pos !== -1 && rawHref.length > pos + 25 + b) ? rawHref.charAt(pos + 4 + 21 + b) : 'a';
                        const fullUrl = rawHref.startsWith('/')
                            ? ('https://weixin.sogou.com' + rawHref + '&k=' + b + '&h=' + ch)
                            : rawHref;
                        let mpUrl = null;
                        try {{
                            const resp = await fetch(fullUrl, {{ credentials: 'include' }});
                            const txt = await resp.text();
                            const matches = [...txt.matchAll(/url\\s*\\+=\\s*'([^']*)'/g)];
                            if (matches.length) {{
                                mpUrl = matches.map(m => m[1]).join('').replace(/@/g, '').replace(/&amp;/g, '&');
                            }}
                        }} catch (e) {{}}
                        const authorEl = li.querySelector('.s-p .all-time-y2, a.account');
                        const snippetEl = li.querySelector('p.txt-info');
                        const scripts = Array.from(li.querySelectorAll('script')).map(s => s.textContent).join(' ');
                        const tsMatch = scripts.match(/timeConvert\\('(\\d+)'\\)/);
                        return {{
                            title: a.innerText.trim(),
                            author: authorEl ? authorEl.innerText.trim() : '',
                            snippet: snippetEl ? snippetEl.innerText.trim() : '',
                            ts: tsMatch ? parseInt(tsMatch[1], 10) : null,
                            url: mpUrl || fullUrl,
                            backend: 'sogou-cdp-9223'
                        }};
                    }});
                    const resolved = await Promise.all(tasks);
                    return resolved.filter(x => x && x.url && x.url.includes('mp.weixin.qq.com'));
                }})()""") or []
                if sogou_cands:
                    backends_used.append("sogou-cdp-9223")
                    raw_candidates.extend(sogou_cands)
        except Exception:
            pass

    # Stage 2: If Sogou returned 0 results (e.g., long-tail niche query or CAPTCHA) and Yuanbao wasn't run yet, auto-escalate to Yuanbao!
    if not raw_candidates and not deep:
        try:
            yb = wechat_yuanbao_search(query, limit=limit)
            if yb.get("ok") and yb.get("wxDocs"):
                backends_used.append("yuanbao-cdp-9223")
                raw_candidates.extend(yb["wxDocs"])
                yuanbao_summary = yb.get("summary") or None
        except Exception:
            pass

    # Verify live status & optionally extract full Markdown body via httpx (strictly mp.weixin.qq.com only)
    with httpx.Client(headers=DEFAULT_HEADERS, timeout=12.0, follow_redirects=True) as client:
        for cand in raw_candidates:
            if len(items) >= limit:
                break
            mp_url = str(cand.get("url") or "").strip()
            if not mp_url or mp_url in seen_urls or not _url_matches_domains(mp_url, ("mp.weixin.qq.com",)):
                continue
            seen_urls.add(mp_url)
            title = str(cand.get("title") or "").strip()
            author = str(cand.get("author") or "").strip()
            snippet = str(cand.get("snippet") or "").strip()
            ts_val = cand.get("ts")
            pub_iso = datetime.fromtimestamp(int(ts_val), tz=timezone.utc).isoformat() if ts_val else None
            body_txt = ""
            try:
                ar = client.get(mp_url, headers={"Referer": "https://so.qq.com/"})
                if "该公众号已迁移" in ar.text and 'id="activity-name"' not in ar.text:
                    skipped_migrated += 1
                    continue
                ct_m = re.search(r'\bvar\s+ct\s*=\s*"(\d{10})"', ar.text)
                if ct_m:
                    pub_iso = datetime.fromtimestamp(int(ct_m.group(1)), tz=timezone.utc).isoformat()
                s2 = BeautifulSoup(ar.text, "html.parser")
                c_el = s2.select_one("#js_content")
                body_txt = c_el.get_text("\n", strip=True) if c_el else ""
                a_el = s2.select_one("#js_name")
                if a_el and not author:
                    author = a_el.get_text(" ", strip=True)
                t_el = s2.select_one("#activity-name")
                if t_el and not title:
                    title = t_el.get_text(" ", strip=True)
            except Exception:
                body_txt = ""
            entry: dict[str, Any] = {
                "source": "wechat",
                "backend": cand.get("backend", "so-qq-nextpage-http"),
                "title": title,
                "author": author,
                "published_at": pub_iso,
                "snippet": snippet or (body_txt[:220].replace("\n", " ") if body_txt else ""),
                "url": mp_url,
                "content_length": len(body_txt),
            }
            if with_body and body_txt:
                entry["content_markdown"] = body_txt[:6000]
            items.append(entry)
    out_res: dict[str, Any] = {
        "ok": len(items) > 0,
        "platform": "wechat",
        "backends": backends_used,
        "query": query,
        "count": len(items),
        "skipped_migrated_accounts": skipped_migrated,
        **({"error": "NO_RESULTS"} if not items else {}),
        "items": items,
    }
    if yuanbao_summary:
        out_res["yuanbao_summary"] = yuanbao_summary
    return out_res


# ---------------------------------------------------------------------------
# 3. Douyin (抖音: Native :9223 Search, Creator Catalog, High-Like Comments)
# ---------------------------------------------------------------------------
def douyin_search(query: str, limit: int = 10) -> dict[str, Any]:
    url = f"https://www.douyin.com/search/{_q(query)}?type=video"
    items: list[dict[str, Any]] = []
    blocked_reason = ""
    with cdp_background_tab(url, task_name="douyin-search") as tid:
        time.sleep(3.5)
        probe = cdp_eval(tid, f"""(async () => {{
            const delay = ms => new Promise(r => setTimeout(r, ms));
            const deadline = Date.now() + 5500;
            let prev = 0, stable = 0;
            let blocked = '';
            while (Date.now() < deadline) {{
                if (document.querySelector('#nocaptcha-container, .captcha_verify_container')) {{
                    blocked = 'CAPTCHA_REQUIRED';
                    break;
                }}
                if (document.querySelector('#douyin-login-new-id')) {{
                    blocked = 'AUTH_REQUIRED';
                }}
                const anchors = Array.from(document.querySelectorAll('a[href*="/video/"], a[href*="/note/"]'));
                const unique = new Map();
                for (const a of anchors) {{
                    const href = a.getAttribute("href") || a.href || "";
                    const m = href.match(/\\/(video|note)\\/(\\d+)/);
                    if (!m || unique.has(m[2])) continue;
                    const lines = (a.innerText || a.textContent || "").split(/\\n+/).map(x => x.trim()).filter(Boolean);
                    if (lines.length > 0) {{
                        unique.set(m[2], {{
                            id: m[2],
                            kind: m[1],
                            url: `https://www.douyin.com/${{m[1]}}/${{m[2]}}`,
                            leafTexts: lines
                        }});
                    }}
                }}
                if (unique.size >= {limit} || (unique.size > 0 && stable >= 2)) {{
                    return {{ blocked: '', cards: Array.from(unique.values()).slice(0, {limit}) }};
                }}
                if (blocked && unique.size === 0) break;
                stable = unique.size === prev ? stable + 1 : 0;
                prev = unique.size;
                window.scrollBy(0, 900);
                await delay(450);
            }}
            return {{ blocked: blocked || 'AUTH_REQUIRED', cards: [] }};
        }})()""") or {}
        blocked_reason = str(probe.get("blocked") or "")
        raw_cards = probe.get("cards") or []
        if raw_cards:
            dur_re = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
            cnt_re = re.compile(r"^\d+(?:\.\d+)?[万亿]?$")
            time_re = re.compile(r"^(\d+\s*(?:秒|分钟|小时|天|周|个月|月|年)前|刚刚|今天|昨天|前天|\d{4}[-/.年]\d{1,2}.*)$")
            for idx, c in enumerate(raw_cards[:limit]):
                cand_url = str(c.get("url") or "")
                if not _url_matches_domains(cand_url, ("douyin.com",)):
                    continue
                author, likes, duration, pub_time, desc = "", 0, "", "", ""
                texts = c.get("leafTexts") or []
                for i, t in enumerate(texts):
                    if t.startswith("@") and len(t) > 1 and not author:
                        author = t[1:].strip()
                    elif t == "@" and i + 1 < len(texts) and not author:
                        author = texts[i + 1].strip()
                    elif dur_re.match(t) and not duration:
                        duration = t
                    elif cnt_re.match(t) and not dur_re.match(t) and not likes:
                        likes = parse_compact_count(t)
                    elif time_re.match(t) and not pub_time:
                        pub_time = t
                    elif t not in ("合集", "视频", "图文", "作者", "@", author) and len(t) > len(desc):
                        desc = t
                items.append({
                    "rank": idx + 1,
                    "id": c.get("id"),
                    "url": cand_url,
                    "title": (desc[:80] + "…") if len(desc) > 80 else desc,
                    "desc": desc,
                    "author": author,
                    "likes": likes,
                    "duration": duration,
                    "published_relative": pub_time,
                })
    if not items:
        return {
            "ok": False,
            "platform": "douyin",
            "backend": "douyin-search-dom",
            "query": query,
            "error": blocked_reason or "AUTH_REQUIRED",
            "message": "Douyin keyword search requires active login / slider verification in Chrome :9223 (or use `reach-hub hotlist -p douyin` / `douyin author <sec_uid_or_video_url>`).",
            "count": 0,
            "items": [],
        }
    return {"ok": True, "platform": "douyin", "backend": "douyin-search-dom", "query": query, "count": len(items), "items": items}


def douyin_author(handle: str, limit: int = 20, order: str = "likes") -> dict[str, Any]:
    sec_uid = ""
    aweme_id_from_link = ""
    if "v.douyin.com" in handle:
        try:
            r = httpx.get(handle.strip(), headers=DEFAULT_HEADERS, follow_redirects=True, timeout=10.0)
            redir = str(r.url)
            m_u = re.search(r"/user/([A-Za-z0-9_-]+)", redir)
            m_v = re.search(r"/(?:video|note)/(\d+)", redir)
            if m_u and m_u.group(1) != "self":
                sec_uid = m_u.group(1)
            elif m_v:
                aweme_id_from_link = m_v.group(1)
        except Exception:
            pass
    elif "douyin.com/user/" in handle or "share/user/" in handle:
        m = re.search(r"/user/([A-Za-z0-9_-]+)", handle)
        if m and m.group(1) != "self":
            sec_uid = m.group(1)
    elif "douyin.com/video/" in handle or "douyin.com/note/" in handle:
        m = re.search(r"/(?:video|note)/(\d+)", handle)
        if m:
            aweme_id_from_link = m.group(1)
    elif handle.startswith("MS4wLjABAAAA"):
        sec_uid = handle.strip()
    clean_handle = handle.lstrip("@").strip()
    init_url = (
        f"https://www.douyin.com/user/{sec_uid}"
        if sec_uid
        else (
            f"https://www.douyin.com/video/{aweme_id_from_link}"
            if aweme_id_from_link
            else f"https://www.douyin.com/search/{_q(clean_handle)}?type=user"
        )
    )
    with cdp_background_tab(init_url, task_name="douyin-author") as tid:
        time.sleep(3.0)
        nickname = clean_handle
        if not sec_uid and aweme_id_from_link:
            uinfo = cdp_eval(tid, f"""(async () => {{
                const r = await fetch("https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&aweme_id={aweme_id_from_link}", {{ credentials: "include" }});
                const j = await r.json();
                const a = (j.aweme_detail && j.aweme_detail.author) || {{}};
                return {{ secUid: a.sec_uid || "", nickname: a.nickname || "" }};
            }})()""") or {}
            sec_uid = uinfo.get("secUid") or ""
            nickname = uinfo.get("nickname") or nickname
            if sec_uid:
                cdp_request("/navigate", {"targetId": tid, "task": "douyin-author", "url": f"https://www.douyin.com/user/{sec_uid}"})
                time.sleep(2.5)
        if not sec_uid:
            cand = cdp_eval(tid, """(() => {
                const out = [];
                const seen = new Set();
                for (const a of document.querySelectorAll('a[href*="/user/"]')) {
                    const href = a.getAttribute("href") || a.href || "";
                    const m = href.match(/\\/user\\/([A-Za-z0-9_-]+)/);
                    if (!m || m[1] === "self" || seen.has(m[1])) continue;
                    seen.add(m[1]);
                    const lines = (a.innerText || "").split(/\\n+/).map(x => x.trim()).filter(Boolean);
                    if (lines.length) out.push({ secUid: m[1], nickname: lines[0], raw: lines.join(" ") });
                }
                return out;
            })()""") or []
            if not cand:
                blocked = cdp_eval(tid, "!!document.querySelector('#nocaptcha-container, .captcha_verify_container, #douyin-login-new-id')")
                return {
                    "ok": False,
                    "platform": "douyin",
                    "error": "AUTH_REQUIRED" if blocked else "AUTHOR_NOT_FOUND",
                    "message": f"Unable to resolve Douyin author {handle!r} without login/slider verification (pass a sec_uid MS4wLjABAAAA... or douyin.com/video/<id> URL, or log in to douyin.com in Chrome :9223).",
                    "works": [],
                }
            sec_uid = cand[0]["secUid"]
            nickname = cand[0].get("nickname") or clean_handle
            cdp_request("/navigate", {"targetId": tid, "task": "douyin-author", "url": f"https://www.douyin.com/user/{sec_uid}"})
            time.sleep(3.0)
        batch = cdp_eval(tid, f"""(async () => {{
            const rows = [];
            let cursor = "0";
            for (let page = 0; page < 4; page++) {{
                const r = await fetch("https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&max_cursor=" + cursor + "&count=20&aid=6383", {{
                    credentials: "include",
                    headers: {{ "referer": "https://www.douyin.com/user/{sec_uid}" }}
                }});
                const d = await r.json();
                for (const item of (d.aweme_list || [])) {{
                    const st = item.statistics || {{}};
                    const imgs = (item.images || []).map(img => (img.url_list && img.url_list[0]) || "").filter(Boolean);
                    const isImageNote = item.aweme_type === 68 || imgs.length > 0;
                    const rawPlayUrl = (item.video && item.video.play_addr && item.video.play_addr.url_list && item.video.play_addr.url_list[0]) || "";
                    const musicUrl = (item.music && item.music.play_url && item.music.play_url.url_list && item.music.play_url.url_list[0]) || (isImageNote ? rawPlayUrl : "");
                    rows.push({{
                        aweme_id: item.aweme_id,
                        aweme_type: item.aweme_type || 0,
                        media_type: isImageNote ? "image_note" : "video",
                        duration_ms: isImageNote ? 0 : ((item.video && item.video.duration) || 0),
                        desc: item.desc || "",
                        create_time: item.create_time,
                        is_top: Boolean(item.is_top),
                        author: (item.author && item.author.nickname) || "",
                        likes: st.digg_count || 0,
                        comments: st.comment_count || 0,
                        shares: st.share_count || 0,
                        collects: st.collect_count || 0,
                        plays: st.play_count || 0,
                        play_url: isImageNote ? "" : rawPlayUrl,
                        bgm_url: musicUrl,
                        image_urls: imgs,
                        url: "https://www.douyin.com/video/" + item.aweme_id
                    }});
                }}
                if (!d.has_more || !d.max_cursor) break;
                cursor = String(d.max_cursor);
                if ("{order}" === "recent" && rows.length >= {limit}) break;
            }}
            return rows;
        }})()""") or []
    if order == "likes":
        batch.sort(key=lambda x: int(x.get("likes") or 0), reverse=True)
    works = [w for w in batch[:limit] if _url_matches_domains(w.get("url"), ("douyin.com",))]
    return {
        "ok": len(works) > 0,
        "platform": "douyin",
        "handle": handle,
        "sec_uid": sec_uid,
        "nickname": (works[0].get("author") if works else nickname) or nickname,
        "order": order,
        "scanned": len(batch),
        "count": len(works),
        **({"error": "AUTH_REQUIRED", "message": "Douyin aweme/post returned 0 items (login or slider required in Chrome :9223)."} if not works else {}),
        "works": works,
    }


def douyin_comments(video_url_or_id: str, limit: int = 20) -> dict[str, Any]:
    m = re.search(r"(\d{15,22})", video_url_or_id)
    if not m:
        return {"ok": False, "platform": "douyin", "error": f"Cannot extract aweme_id from {video_url_or_id!r}"}
    aweme_id = m.group(1)
    vurl = f"https://www.douyin.com/video/{aweme_id}"
    with cdp_background_tab(vurl, task_name="douyin-comments") as tid:
        time.sleep(3.0)
        res = cdp_eval(tid, f"""(async () => {{
            const r = await fetch("https://www.douyin.com/aweme/v1/web/comment/list/?aweme_id={aweme_id}&cursor=0&count={min(limit, 50)}&aid=6383", {{
                credentials: "include",
                headers: {{ "referer": "{vurl}" }}
            }});
            const d = await r.json();
            const comments = (d.comments || []).map(c => ({{
                cid: c.cid,
                text: c.text,
                likes: c.digg_count || 0,
                reply_count: c.reply_comment_total || 0,
                user: c.user && c.user.nickname,
                ip_label: c.ip_label || "",
                create_time: c.create_time
            }}));
            return {{ total: d.total || 0, comments }};
        }})()""") or {}
    comments = res.get("comments") or []
    return {
        "ok": True,
        "platform": "douyin",
        "aweme_id": aweme_id,
        "url": vurl,
        "total_comments": res.get("total", 0),
        "count": len(comments[:limit]),
        "comments": comments[:limit],
    }


# ---------------------------------------------------------------------------
# 4. Bilibili (B站: Search, Video Detail, High-Like Comments, Subtitles)
# ---------------------------------------------------------------------------
def _extract_bvid(url_or_id: str) -> str:
    m = re.search(r"(BV[0-9A-Za-z]{10})", url_or_id)
    if m:
        return m.group(1)
    if "b23.tv" in url_or_id:
        r = httpx.get(url_or_id, headers=DEFAULT_HEADERS, follow_redirects=True, timeout=10.0)
        m2 = re.search(r"(BV[0-9A-Za-z]{10})", str(r.url))
        if m2:
            return m2.group(1)
    raise ValueError(f"Could not extract BVID from {url_or_id!r}")


def bilibili_search(query: str, limit: int = 10) -> dict[str, Any]:
    headers = {**DEFAULT_HEADERS, "Referer": "https://www.bilibili.com/"}
    with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
        client.get("https://www.bilibili.com/")
        r = client.get("https://api.bilibili.com/x/web-interface/search/type", params={"search_type": "video", "keyword": query, "page": 1})
        res = ((r.json().get("data") or {}).get("result")) or []
        items = []
        for x in res[:limit]:
            bvid = x.get("bvid")
            cand_url = f"https://www.bilibili.com/video/{bvid}" if bvid else str(x.get("arcurl") or "")
            if not _url_matches_domains(cand_url, ("bilibili.com", "b23.tv")):
                continue
            title = re.sub(r"<[^>]+>", "", x.get("title") or "")
            items.append({
                "bvid": bvid,
                "aid": x.get("aid") or x.get("id"),
                "title": title,
                "author": x.get("author"),
                "description": x.get("description"),
                "views": x.get("play"),
                "likes": x.get("like"),
                "comments": x.get("review"),
                "danmaku": x.get("video_review"),
                "duration": x.get("duration"),
                "url": cand_url,
            })
        return {
            "ok": len(items) > 0,
            "platform": "bilibili",
            "query": query,
            "count": len(items),
            **({"error": "NO_RESULTS"} if not items else {}),
            "items": items,
        }


def bilibili_comments(bvid_or_url: str, limit: int = 20) -> dict[str, Any]:
    bvid = _extract_bvid(bvid_or_url)
    headers = {**DEFAULT_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"}
    with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
        vr = client.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid}).json()
        vdata = vr.get("data") or {}
        aid = vdata.get("aid")
        if not aid:
            return {"ok": False, "platform": "bilibili", "bvid": bvid, "error": "Failed to resolve aid"}
        cr = client.get("https://api.bilibili.com/x/v2/reply", params={"type": 1, "oid": aid, "sort": 2, "ps": min(limit, 20), "pn": 1}).json()
        cdata = cr.get("data") or {}
        replies = (cdata.get("hots") or []) + (cdata.get("replies") or [])
        seen = set()
        items = []
        for rp in replies:
            rpid = rp.get("rpid")
            if not rpid or rpid in seen:
                continue
            seen.add(rpid)
            sub = [
                {"user": (sr.get("member") or {}).get("uname"), "message": (sr.get("content") or {}).get("message"), "likes": sr.get("like")}
                for sr in (rp.get("replies") or [])[:3]
            ]
            items.append({
                "rpid": rpid,
                "user": (rp.get("member") or {}).get("uname"),
                "message": (rp.get("content") or {}).get("message"),
                "likes": rp.get("like"),
                "rcount": rp.get("rcount"),
                "sub_replies": sub,
            })
            if len(items) >= limit:
                break
        return {
            "ok": True,
            "platform": "bilibili",
            "bvid": bvid,
            "aid": aid,
            "title": vdata.get("title"),
            "count": len(items),
            "comments": items,
        }


def bilibili_subtitle(bvid_or_url: str) -> dict[str, Any]:
    bvid = _extract_bvid(bvid_or_url)
    headers = {**DEFAULT_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"}
    with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
        vr = client.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid}).json()
        vdata = vr.get("data") or {}
        cid = vdata.get("cid")
        sub_list = ((vdata.get("subtitle") or {}).get("list")) or []
        if not sub_list and cid:
            pr = client.get("https://api.bilibili.com/x/player/wbi/v2", params={"bvid": bvid, "cid": cid}).json()
            sub_list = (((pr.get("data") or {}).get("subtitle") or {}).get("subtitles")) or []
        # If anonymous API returned no subtitles and Chrome 9223 has SESSDATA, query in-page wbi/v2 with credentials
        if not sub_list and cid:
            try:
                with cdp_background_tab(f"https://www.bilibili.com/video/{bvid}", task_name="bili-sub") as tid:
                    time.sleep(2.5)
                    sub_list = cdp_eval(tid, f"""(async () => {{
                        const r = await fetch(`https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}`, {{ credentials: 'include' }});
                        const j = await r.json();
                        return (((j.data || {{}}).subtitle || {{}}).subtitles) || [];
                    }})()""") or []
            except Exception:
                pass
        tracks = []
        for s in sub_list:
            surl = s.get("subtitle_url") or ""
            if surl.startswith("//"):
                surl = "https:" + surl
            if surl:
                resp_sub = client.get(surl)
                raw_sub_text = resp_sub.text.strip()
                if raw_sub_text.upper().startswith("WEBVTT") or surl.lower().split("?", 1)[0].endswith(".vtt"):
                    cleaned_vtt = _clean_vtt_subtitle(raw_sub_text)
                    vtt_lines = [ln for ln in cleaned_vtt.splitlines() if ln]
                    tracks.append({
                        "lan": s.get("lan"),
                        "lan_doc": s.get("lan_doc"),
                        "segment_count": len(vtt_lines),
                        "text": cleaned_vtt,
                        "segments": [{"content": ln} for ln in vtt_lines[:100]],
                    })
                else:
                    sr = resp_sub.json()
                    body = sr.get("body") or []
                    tracks.append({
                        "lan": s.get("lan"),
                        "lan_doc": s.get("lan_doc"),
                        "segment_count": len(body),
                        "text": "\n".join(str(c.get("content") or "") for c in body),
                        "segments": body[:100],
                    })
        return {
            "ok": True,
            "platform": "bilibili",
            "bvid": bvid,
            "cid": cid,
            "title": vdata.get("title"),
            "description": vdata.get("desc"),
            "has_cc_subtitle": len(tracks) > 0,
            "tracks": tracks,
            "fallback_hint": None if tracks else f"No CC subtitle published; run `bili audio {bvid}` for ASR audio extraction.",
        }


# ---------------------------------------------------------------------------
# 5. Zhihu (知乎: In-Site api/v4/search_v3 & DOM when logged in, Read, Comments)
# ---------------------------------------------------------------------------
def zhihu_search(query: str, limit: int = 10) -> dict[str, Any]:
    st = auth_status()
    is_auth = bool(st.get("platforms", {}).get("zhihu", {}).get("authenticated"))
    if not is_auth:
        return {
            "ok": False,
            "platform": "zhihu",
            "auth_mode": "unauthenticated",
            "error": "AUTH_REQUIRED",
            "message": "Zhihu search requires active `z_c0` session in Chrome :9223 (log in to zhihu.com in Chrome, or use `reach-hub hotlist -p zhihu`).",
            "query": query,
            "count": 0,
            "items": [],
        }

    z_url = f"https://www.zhihu.com/search?type=content&q={_q(query)}"
    with cdp_background_tab(z_url, task_name="zhihu-search") as tid:
        time.sleep(1.8)
        api_rows = cdp_eval(tid, f"""(async () => {{
            const strip = s => (s || '').replace(/<[^>]+>/g, '').replace(/\\s+/g, ' ').trim();
            try {{
                const r = await fetch(
                    'https://www.zhihu.com/api/v4/search_v3?gk_version=gz-gaokao&t=general&q=' + encodeURIComponent({json.dumps(query)}) + '&correction=1&offset=0&limit={min(max(limit * 2, 20), 40)}',
                    {{ credentials: 'include' }}
                );
                if (r.status !== 200) return [];
                const j = await r.json();
                const out = [];
                const seen = new Set();
                for (const row of (j.data || [])) {{
                    const obj = row.object || {{}};
                    const typ = obj.type || row.type || '';
                    let url = '';
                    let title = '';
                    if (typ === 'article' && obj.id) {{
                        url = `https://zhuanlan.zhihu.com/p/${{obj.id}}`;
                        title = strip(obj.title);
                    }} else if (typ === 'answer' && obj.id && obj.question && obj.question.id) {{
                        url = `https://www.zhihu.com/question/${{obj.question.id}}/answer/${{obj.id}}`;
                        title = strip(obj.question.name || obj.question.title || obj.title);
                    }} else if (typ === 'question' && obj.id) {{
                        url = `https://www.zhihu.com/question/${{obj.id}}`;
                        title = strip(obj.name || obj.title);
                    }}
                    if (!url || !title || seen.has(url)) continue;
                    seen.add(url);
                    out.push({{
                        type: typ,
                        title,
                        url,
                        author: (obj.author && obj.author.name) || '',
                        votes: obj.voteup_count ?? 0,
                        comments: obj.comment_count ?? 0,
                        snippet: strip(obj.excerpt || obj.description || '').slice(0, 300),
                    }});
                    if (out.length >= {limit}) break;
                }}
                return out;
            }} catch (e) {{
                return [];
            }}
        }})()""") or []
        valid_api_rows = [r for r in api_rows if _url_matches_domains(r.get("url"), ("zhihu.com",))]
        if valid_api_rows:
            return {
                "ok": True,
                "platform": "zhihu",
                "auth_mode": "logged_in_search_v3_api",
                "query": query,
                "count": len(valid_api_rows[:limit]),
                "items": valid_api_rows[:limit],
            }

        for _ in range(8):
            time.sleep(0.5)
            if cdp_eval(tid, """document.querySelectorAll('a[href*="/question/"], a[href*="zhuanlan.zhihu.com/p/"]').length || 0"""):
                break
        dom_rows = cdp_eval(tid, f"""(() => {{
            const out = [];
            const seen = new Set();
            for (const a of document.querySelectorAll('a[href*="/question/"], a[href*="zhuanlan.zhihu.com/p/"]')) {{
                const title = (a.innerText || '').trim();
                if (!title || title.length < 4 || seen.has(a.href)) continue;
                seen.add(a.href);
                const card = a.closest('.Card, .List-item, .ContentItem, [class*="SearchResult"]') || a.parentElement?.parentElement?.parentElement;
                const rich = card ? card.querySelector('.RichContent-inner, .CopyrightRichText-richText') : null;
                const vote = card ? card.querySelector('.VoteButton--up, [class*="VoteButton"]') : null;
                out.push({{
                    title,
                    url: a.href,
                    votes: vote ? vote.innerText.trim() : "",
                    snippet: rich ? rich.innerText.trim().slice(0, 300) : (card ? card.innerText.trim().slice(0, 300) : "")
                }});
                if (out.length >= {limit}) break;
            }}
            return out;
        }})()""") or []
        valid_dom_rows = [r for r in dom_rows if _url_matches_domains(r.get("url"), ("zhihu.com",))]
        if valid_dom_rows:
            return {
                "ok": True,
                "platform": "zhihu",
                "auth_mode": "logged_in_native_dom",
                "query": query,
                "count": len(valid_dom_rows[:limit]),
                "items": valid_dom_rows[:limit],
            }

    return {
        "ok": False,
        "platform": "zhihu",
        "auth_mode": "logged_in_empty_or_blocked",
        "error": "NO_RESULTS",
        "message": f"Zhihu returned 0 verified zhihu.com results for {query!r} (or session requires re-verification in Chrome :9223).",
        "query": query,
        "count": 0,
        "items": [],
    }


def zhihu_read(url: str) -> dict[str, Any]:
    try:
        rj = httpx.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/markdown", "User-Agent": CHROME_UA}, timeout=15.0)
        if rj.status_code == 200 and not _is_empty_or_error_body(rj.text, min_chars=200):
            return {"ok": True, "platform": "zhihu", "url": url, "backend": "jina-reader", "content_length": len(rj.text), "content_markdown": rj.text}
    except Exception:
        pass
    with cdp_background_tab(url, task_name="zhihu-read") as tid:
        time.sleep(3.5)
        val = cdp_eval(tid, """(() => {
            const title = (document.querySelector('h1.Post-Title, h1.QuestionHeader-title') || {}).innerText || document.title;
            const body = Array.from(document.querySelectorAll('.Post-RichTextContainer, .RichContent-inner')).map(e => e.innerText.trim()).join('\\n\\n---\\n\\n') || (document.body ? document.body.innerText : '');
            return { title: title.trim(), body: body.trim() };
        })()""") or {}
        body_str = (val.get("body") or "").strip()
        is_valid = not _is_empty_or_error_body(body_str, min_chars=20)
        return {
            "ok": is_valid,
            "platform": "zhihu",
            "url": url,
            "backend": "cdp-9223",
            "title": val.get("title"),
            "content_length": len(body_str),
            "content_markdown": body_str,
        }


def zhihu_comments(url: str, limit: int = 15) -> dict[str, Any]:
    with cdp_background_tab(url, task_name="zhihu-comments") as tid:
        time.sleep(3.0)
        val = cdp_eval(tid, f"""(async () => {{
            const stripHtml = s => (s || '').replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
            const mapComment = c => ({{
                id: String(c.id || ''),
                user: (c.author && (c.author.name || (c.author.member && c.author.member.name))) || '',
                likes: c.like_count || 0,
                ip_location: (c.comment_tag && c.comment_tag[0] && c.comment_tag[0].text) || c.address_text || '',
                created_time: c.created_time || null,
                content: stripHtml(c.content),
                sub_comments: (c.child_comments || []).slice(0, 3).map(sc => ({{
                    user: (sc.author && (sc.author.name || (sc.author.member && sc.author.member.name))) || '',
                    likes: sc.like_count || 0,
                    content: stripHtml(sc.content)
                }}))
            }});
            const href = location.href;
            const mP = href.match(/zhuanlan\\.zhihu\\.com\\/p\\/(\\d+)/);
            const mA = href.match(/answer\\/(\\d+)/);
            const mQ = href.match(/question\\/(\\d+)/);
            const endpoints = [];
            if (mP) endpoints.push(`https://www.zhihu.com/api/v4/comment_v5/articles/${{mP[1]}}/root_comment?order_by=score&limit={min(limit, 20)}&offset=`);
            if (mA) endpoints.push(`https://www.zhihu.com/api/v4/comment_v5/answers/${{mA[1]}}/root_comment?order_by=score&limit={min(limit, 20)}&offset=`);
            if (mQ) endpoints.push(`https://www.zhihu.com/api/v4/comment_v5/questions/${{mQ[1]}}/root_comment?order_by=score&limit={min(limit, 20)}&offset=`);
            for (const a of document.querySelectorAll('a[href*="/answer/"]')) {{
                const ma = (a.href || '').match(/\\/answer\\/(\\d+)/);
                if (ma) {{
                    endpoints.push(`https://www.zhihu.com/api/v4/comment_v5/answers/${{ma[1]}}/root_comment?order_by=score&limit={min(limit, 20)}&offset=`);
                    if (endpoints.length >= 4) break;
                }}
            }}
            const out = [];
            let totalCount = 0;
            for (const ep of endpoints) {{
                try {{
                    const r = await fetch(ep, {{ credentials: 'include' }});
                    if (r.status !== 200) continue;
                    const d = await r.json();
                    if (d.counts && d.counts.total_counts) totalCount += d.counts.total_counts;
                    for (const item of (d.data || [])) {{
                        out.push(mapComment(item));
                        if (out.length >= {limit}) break;
                    }}
                    if (out.length >= {limit}) break;
                }} catch (e) {{}}
            }}
            return {{ title: document.title, total_comments: totalCount, count: out.length, comments: out }};
        }})()""") or {}
        return {
            "ok": True,
            "platform": "zhihu",
            "backend": "comment_v5_in_page",
            "url": url,
            "title": val.get("title"),
            "total_comments": val.get("total_comments", 0),
            "count": val.get("count", 0),
            "comments": val.get("comments") or [],
        }


# ---------------------------------------------------------------------------
# 6. Xiaohongshu (小红书: Pure 9223 window.__INITIAL_STATE__ Engine + Guest Fallback)
# ---------------------------------------------------------------------------
def xhs_search(query: str, limit: int = 10) -> dict[str, Any]:
    url = f"https://www.xiaohongshu.com/search_result?keyword={_q(query)}&source=web_explore_feed"
    with cdp_background_tab(url, task_name="xhs-search") as tid:
        for _ in range(10):
            time.sleep(0.6)
            ready = cdp_eval(tid, """(() => {
                const s = window.__INITIAL_STATE__;
                const feeds = s && s.search && s.search.feeds ? (s.search.feeds.value || s.search.feeds._value || []) : [];
                if (feeds.length > 0) return 'state_ready';
                const txt = document.body ? document.body.innerText : '';
                if (/登录后查看搜索结果|扫码登录|验证码登录/.test(txt)) return 'login_wall';
                return '';
            })()""")
            if ready:
                break
        st = cdp_eval(tid, f"""(() => {{
            const s = window.__INITIAL_STATE__;
            const loggedIn = !!(s && s.user && s.user.loggedIn && (s.user.loggedIn.value || s.user.loggedIn._value));
            const rawFeeds = s && s.search && s.search.feeds ? (s.search.feeds.value || s.search.feeds._value || []) : [];
            const rows = [];
            for (const item of rawFeeds) {{
                const card = item.noteCard || item.note_card || {{}};
                if (!item.id || (!card.displayTitle && !card.title)) continue;
                const user = card.user || {{}};
                const interact = card.interactInfo || card.interact_info || {{}};
                const xsec = item.xsecToken || item.xsec_token || '';
                const noteUrl = xsec
                    ? `https://www.xiaohongshu.com/explore/${{item.id}}?xsec_token=${{encodeURIComponent(xsec)}}&xsec_source=pc_search`
                    : `https://www.xiaohongshu.com/explore/${{item.id}}`;
                rows.push({{
                    id: item.id,
                    xsec_token: xsec,
                    title: card.displayTitle || card.title || '',
                    author: user.nickname || user.nickName || '',
                    user_id: user.userId || user.user_id || '',
                    likes: interact.likedCount || interact.liked_count || '0',
                    collects: interact.collectedCount || interact.collected_count || '0',
                    comments: interact.commentCount || interact.comment_count || '0',
                    shares: interact.shareCount || interact.share_count || '0',
                    type: card.type || 'normal',
                    url: noteUrl
                }});
                if (rows.length >= {limit}) break;
            }}
            return {{ loggedIn, rows }};
        }})()""") or {}
        verified_rows = [
            r for r in (st.get("rows") or [])
            if _url_matches_domains(r.get("url"), ("xiaohongshu.com", "xhslink.com"))
        ]
        if verified_rows:
            return {
                "ok": True,
                "platform": "xiaohongshu",
                "auth_mode": "logged_in_initial_state",
                "query": query,
                "count": len(verified_rows),
                "items": verified_rows,
            }
        logged_in = bool(st.get("loggedIn"))
    return {
        "ok": False,
        "platform": "xiaohongshu",
        "auth_mode": "logged_in_initial_state" if logged_in else "guest_unauthenticated",
        "error": "NO_RESULTS" if logged_in else "AUTH_REQUIRED",
        "message": (
            f"Xiaohongshu returned 0 notes for {query!r}."
            if logged_in
            else "Xiaohongshu keyword search requires an authenticated session in Chrome :9223. Run `reach-hub xiaohongshu login` once, or use `reach-hub xiaohongshu feed` + `reach-hub xiaohongshu read <url_with_xsec_token>`."
        ),
        "query": query,
        "count": 0,
        "items": [],
    }


def xhs_feed(limit: int = 15) -> dict[str, Any]:
    with cdp_background_tab("https://www.xiaohongshu.com/explore", task_name="xhs-feed") as tid:
        for _ in range(10):
            time.sleep(0.5)
            if cdp_eval(tid, "(() => { const s = window.__INITIAL_STATE__; return !!(s && s.feed && s.feed.feeds); })()"):
                break
        rows = cdp_eval(tid, f"""(() => {{
            const s = window.__INITIAL_STATE__;
            const rawFeeds = s && s.feed && s.feed.feeds ? (s.feed.feeds.value || s.feed.feeds._value || []) : [];
            const out = [];
            for (const item of rawFeeds) {{
                const card = item.noteCard || item.note_card || {{}};
                if (!item.id) continue;
                const user = card.user || {{}};
                const interact = card.interactInfo || card.interact_info || {{}};
                const xsec = item.xsecToken || item.xsec_token || '';
                const noteUrl = xsec
                    ? `https://www.xiaohongshu.com/explore/${{item.id}}?xsec_token=${{encodeURIComponent(xsec)}}&xsec_source=pc_feed`
                    : `https://www.xiaohongshu.com/explore/${{item.id}}`;
                out.push({{
                    id: item.id,
                    xsec_token: xsec,
                    title: card.displayTitle || card.title || '',
                    author: user.nickname || user.nickName || '',
                    user_id: user.userId || user.user_id || '',
                    likes: interact.likedCount || interact.liked_count || '0',
                    type: card.type || 'normal',
                    url: noteUrl
                }});
                if (out.length >= {limit}) break;
            }}
            return out;
        }})()""") or []
    rows = [r for r in rows if _url_matches_domains(r.get("url"), ("xiaohongshu.com", "xhslink.com"))]
    return {
        "ok": len(rows) > 0,
        "platform": "xiaohongshu",
        "mode": "explore_initial_state",
        "count": len(rows),
        **({"error": "AUTH_REQUIRED", "message": "Xiaohongshu /explore returned 0 feed cards (run `reach-hub xiaohongshu login` in Chrome :9223)."} if not rows else {}),
        "items": rows,
    }


def xhs_read(url_or_id: str, comment_limit: int = 20) -> dict[str, Any]:
    url = url_or_id if url_or_id.startswith("http") else f"https://www.xiaohongshu.com/explore/{url_or_id}"
    with cdp_background_tab(url, task_name="xhs-read") as tid:
        for _ in range(10):
            time.sleep(0.5)
            ready = cdp_eval(tid, """(() => {
                const s = window.__INITIAL_STATE__;
                const map = s && s.note && s.note.noteDetailMap;
                if (!map) return false;
                const k = Object.keys(map)[0];
                if (!k || !map[k] || !map[k].note) return false;
                const clist = map[k].comments && map[k].comments.list;
                return Array.isArray(clist) && clist.length > 0;
            })()""")
            if ready:
                break
        detail = cdp_eval(tid, f"""(() => {{
            const s = window.__INITIAL_STATE__;
            const map = (s && s.note && s.note.noteDetailMap) || {{}};
            const keys = Object.keys(map);
            if (!keys.length) return {{ ok: false, error: "noteDetailMap empty (note requires valid xsec_token in URL)" }};
            const entry = map[keys[0]] || {{}};
            const note = entry.note || {{}};
            const user = note.user || {{}};
            const interact = note.interactInfo || {{}};
            const rawComments = (entry.comments && entry.comments.list) || [];
            const comments = rawComments.slice(0, {comment_limit}).map(c => ({{
                id: c.id,
                content: c.content,
                likes: c.likeCount,
                ip_location: c.ipLocation,
                user: c.userInfo ? c.userInfo.nickname : "",
                sub_comment_count: c.subCommentCount,
                sub_comments: (c.subComments || []).slice(0, 5).map(sc => ({{
                    content: sc.content,
                    likes: sc.likeCount,
                    user: sc.userInfo ? sc.userInfo.nickname : ""
                }}))
            }}));
            return {{
                ok: true,
                platform: "xiaohongshu",
                backend: "cdp-9223-initial-state",
                note_id: note.noteId || keys[0],
                title: note.title || "",
                desc: note.desc || "",
                author: user.nickname || "",
                user_id: user.userId || "",
                ip_location: note.ipLocation || "",
                interact_info: interact,
                tags: (note.tagList || []).map(t => t.name),
                images: (note.imageList || []).map(img => img.urlDefault || img.url),
                comments_count: comments.length,
                comments
            }};
        }})()""") or {"ok": False, "error": "Failed to evaluate __INITIAL_STATE__.note.noteDetailMap"}
    return detail


def xhs_login(timeout_s: int = 180, notify: bool = True) -> dict[str, Any]:
    """Login to Xiaohongshu directly inside Chrome 9223 (zero foreground focus theft, zero external Preview window)."""
    import base64

    qr_file = Path("/tmp/xhs_9223_login_qr.png")
    group_id = "xhs-9223-login-qr"

    def _clear_banner() -> None:
        if notify and HANDOFF_NOTIFIER_BIN.exists():
            subprocess.run(
                [str(HANDOFF_NOTIFIER_BIN), "-remove", group_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    with cdp_background_tab("https://www.xiaohongshu.com/explore", task_name="xhs-login") as tid:
        time.sleep(2.5)
        st = cdp_eval(tid, """(() => {
            const s = window.__INITIAL_STATE__;
            const loggedIn = !!(s && s.user && s.user.loggedIn && (s.user.loggedIn.value || s.user.loggedIn._value));
            const qr = document.querySelector('.login-container .qrcode-img, img[class*="qrcode"]');
            return { loggedIn, qrSrc: qr ? qr.src : '' };
        })()""") or {}
        if st.get("loggedIn"):
            return {"ok": True, "status": "already_logged_in", "message": "Chrome 9223 is already logged in to Xiaohongshu."}
        qr_src = str(st.get("qrSrc") or "")
        if qr_src.startswith("data:image/") and "," in qr_src:
            b64_data = qr_src.split(",", 1)[1]
            qr_file.write_bytes(base64.b64decode(b64_data))
            print(f"[xhs_login] QR code saved to {qr_file} (zero-focus mode; Preview not opened)", file=sys.stderr)
            if notify and HANDOFF_NOTIFIER_BIN.exists() and not os.environ.get("CI"):
                subprocess.run(
                    [
                        str(HANDOFF_NOTIFIER_BIN),
                        "-title",
                        "小红书扫码登录",
                        "-subtitle",
                        "Chrome :9223 后台就绪",
                        "-message",
                        f"二维码已落盘至 {qr_file}，扫码完成后自动关闭提示。",
                        "-group",
                        group_id,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        try:
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                time.sleep(1.5)
                ok = cdp_eval(tid, """(() => {
                    const s = window.__INITIAL_STATE__;
                    if (s && s.user && s.user.loggedIn && (s.user.loggedIn.value || s.user.loggedIn._value)) return true;
                    return !!document.querySelector('.main-container .user .link-wrapper .channel');
                })()""")
                if ok:
                    qr_file.unlink(missing_ok=True)
                    return {"ok": True, "status": "logged_in", "qr_path": str(qr_file), "message": "Xiaohongshu login succeeded inside Chrome 9223."}
        finally:
            _clear_banner()
            qr_file.unlink(missing_ok=True)
        return {"ok": False, "status": "timeout", "qr_path": str(qr_file), "message": f"QR scan timed out after {timeout_s}s."}


def auth_status() -> dict[str, Any]:
    """Check live authentication and session expiry across all platforms inside Chrome 9223."""
    cookies_readable = True
    cookie_error: str | None = None
    cookies: list[dict[str, Any]] = []
    try:
        res = cdp_request("/cookies", {})
        if res.get("ok") is False:
            cookies_readable = False
            cookie_error = str(res.get("error") or "cookies_endpoint_failed")
        else:
            cookies = res.get("cookies") or (res.get("result") or {}).get("cookies") or []
    except Exception as exc:
        cookies_readable = False
        cookie_error = str(exc)

    now = time.time()
    by_dom: dict[str, dict[str, Any]] = {}
    for c in cookies:
        d = (c.get("domain") or "").lstrip(".")
        by_dom.setdefault(d, {})[c.get("name")] = c

    def _find(sub: str, name: str) -> dict[str, Any] | None:
        for d, kv in by_dom.items():
            if sub in d and name in kv:
                return kv[name]
        return None

    def _days(c: dict[str, Any] | None) -> float | None:
        if not c or c.get("expires", -1) <= 0:
            return None
        return round((float(c["expires"]) - now) / 86400, 1)

    xhs_ws = _find("xiaohongshu.com", "web_session")
    xhs_val = str((xhs_ws or {}).get("value") or "")
    xhs_logged_in = bool(xhs_val and not xhs_val.startswith("0300"))

    dy_sid = _find("douyin.com", "sessionid") or _find("douyin.com", "sid_tt")
    yb_tok = _find("yuanbao.tencent.com", "hy_token") or _find("tencent.com", "hy_token") or _find("yuanbao.tencent.com", "hy_user")
    bili_sess = _find("bilibili.com", "SESSDATA")
    zhihu_zc0 = _find("zhihu.com", "z_c0")
    tw_auth = _find("x.com", "auth_token") or _find("twitter.com", "auth_token")
    rd_tok = _find("reddit.com", "reddit_session") or _find("reddit.com", "token_v2")
    pj_auth = _find("52pojie.cn", "htVC_2132_auth")

    return {
        "ok": True,
        "chrome_cdp": os.environ.get("CDP_RELAY_ADDR", os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")),
        "cookies_readable": cookies_readable,
        **({"cookie_error": cookie_error} if cookie_error else {}),
        "platforms": {
            "douyin": {
                "authenticated": bool(dy_sid) if cookies_readable else None,
                "expires_in_days": _days(dy_sid),
                "mode": "native_9223_dom_and_aweme_api (search / author / comments) + iesdouyin_hotlist",
                "need_action": False if not cookies_readable else (not bool(dy_sid)),
            },
            "xiaohongshu": {
                "authenticated": xhs_logged_in if cookies_readable else None,
                "session_type": (
                    "unreadable_cookies"
                    if not cookies_readable
                    else ("authenticated_0400" if xhs_logged_in else ("guest_0300" if xhs_val else "none"))
                ),
                "expires_in_days": _days(xhs_ws),
                "mode": "full_initial_state (search / feed / read / comments)" if xhs_logged_in else "guest_initial_state (feed + read/comments with xsec_token; keyword search returns AUTH_REQUIRED)",
                "need_action": False if not cookies_readable else (not xhs_logged_in),
                "login_hint": "Scan QR once in Chrome xiaohongshu.com or run `reach-hub xiaohongshu login` to unlock native keyword search & sorting",
            },
            "wechat": {
                "authenticated": True,
                "yuanbao_authenticated": bool(yb_tok) if cookies_readable else None,
                "yuanbao_expires_in_days": _days(yb_tok),
                "mode": "so_qq_nextpage_http (zero-login 100% __biz) + so_qq_aimode_sse (--deep long-tail) + sogou/yuanbao 9223 + http_direct_read",
                "need_action": False,
            },
            "bilibili": {
                "authenticated": bool(bili_sess) if cookies_readable else None,
                "expires_in_days": _days(bili_sess),
                "mode": "zero_login_public_api (search / hot / video / comments / subtitle)",
                "need_action": False,
            },
            "zhihu": {
                "authenticated": bool(zhihu_zc0) if cookies_readable else None,
                "expires_in_days": _days(zhihu_zc0),
                "mode": "logged_in_search_v3_api_and_jina (search / read / comments / hotlist)",
                "need_action": False if not cookies_readable else (not bool(zhihu_zc0)),
            },
            "twitter": {
                "authenticated": bool(tw_auth) if cookies_readable else None,
                "expires_in_days": _days(tw_auth),
                "mode": "authenticated_9223_x_search (when logged in) + zero_login_syndication_timeline_and_tweet_read",
                "need_action": False if not cookies_readable else (not bool(tw_auth)),
            },
            "reddit": {
                "authenticated": bool(rd_tok) if cookies_readable else None,
                "expires_in_days": _days(rd_tok),
                "mode": "native_reddit_search_9223 + arctic_shift_api (search + full post & comment tree)",
                "need_action": False,
            },
            "52pojie": {
                "authenticated": bool(pj_auth) if cookies_readable else None,
                "expires_in_days": _days(pj_auth),
                "mode": "rss + guide(hot/digest/newthread) + strict_domain_anysearch(site:52pojie.cn) + cdp-9223-persistent-read",
                "need_action": False,
            },
            "v2ex": {
                "authenticated": True,
                "expires_in_days": None,
                "mode": "official_public_json_api (hot / latest / read) + sov2ex_search_api",
                "need_action": False,
            },
            "youtube": {
                "authenticated": True,
                "expires_in_days": None,
                "mode": "yt_dlp_first_party (ytsearch + vtt_subtitle_extract)",
                "need_action": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# 7. Twitter/X & Reddit (Native First-Party Search + Syndication / Arctic Shift Read)
# ---------------------------------------------------------------------------
def twitter_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search X/Twitter via zero-login Syndication (@handle / from:handle) or authenticated :9223 X DOM."""
    q_str = (query or "").strip()
    handle_m = re.match(r"^(?:@|from:)([A-Za-z0-9_]{1,15})(?:\s+(.*))?$", q_str, re.I)
    if handle_m:
        handle = handle_m.group(1)
        kw_filter = (handle_m.group(2) or "").strip().lower()
        tl_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
        try:
            with httpx.Client(headers=DEFAULT_HEADERS, proxy=LOCAL_PROXY, timeout=12.0, follow_redirects=True, trust_env=False) as client:
                r = client.get(tl_url)
            if r.status_code == 200:
                nd_m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
                if nd_m:
                    nd = json.loads(nd_m.group(1))
                    entries = ((((nd.get("props") or {}).get("pageProps") or {}).get("timeline") or {}).get("entries")) or []
                    rows: list[dict[str, Any]] = []
                    for ent in entries:
                        tw = ((ent.get("content") or {}).get("tweet")) or {}
                        tw_id = str(tw.get("id_str") or tw.get("conversation_id_str") or "").strip()
                        text = str(tw.get("full_text") or tw.get("text") or "").strip()
                        if not tw_id or not text:
                            continue
                        if kw_filter and not all(tok in text.lower() for tok in kw_filter.split()):
                            continue
                        u = tw.get("user") or {}
                        sn = str(u.get("screen_name") or handle)
                        likes = int(tw.get("favorite_count") or 0)
                        retweets = int(tw.get("retweet_count") or tw.get("quote_count") or 0)
                        replies = int(tw.get("reply_count") or tw.get("conversation_count") or 0)
                        cand_url = f"https://x.com/{sn}/status/{tw_id}"
                        if not _url_matches_domains(cand_url, ("x.com", "twitter.com")):
                            continue
                        rows.append({
                            "tweet_id": tw_id,
                            "title": text[:80],
                            "text": text,
                            "author": sn,
                            "created_at": tw.get("created_at"),
                            "likes": likes,
                            "retweets": retweets,
                            "replies": replies,
                            "engagement_score": likes + retweets * 3 + replies * 2,
                            "url": cand_url,
                        })
                        if len(rows) >= limit:
                            break
                    return {
                        "ok": len(rows) > 0,
                        "platform": "twitter",
                        "backend": "syndication-timeline-profile",
                        "query": query,
                        "count": len(rows),
                        **({"error": "NO_RESULTS"} if not rows else {}),
                        "items": rows,
                    }
        except Exception as exc:
            return {"ok": False, "platform": "twitter", "query": query, "error": f"SYNDICATION_FAILED: {exc}", "items": []}

    st = auth_status()
    tw_auth = bool(st.get("platforms", {}).get("twitter", {}).get("authenticated"))
    if not tw_auth:
        return {
            "ok": False,
            "platform": "twitter",
            "error": "AUTH_REQUIRED",
            "message": "X/Twitter general keyword search requires active `x.com` login (`auth_token`) in Chrome :9223. Log in to x.com in Chrome, or query `@<handle> [keywords]` / `reach-hub twitter read <tweet_id_or_url>` for zero-login Syndication access.",
            "query": query,
            "count": 0,
            "items": [],
        }

    x_url = f"https://x.com/search?q={_q(q_str)}&src=typed_query"
    with cdp_background_tab(x_url, task_name="twitter-search") as tid:
        for _ in range(12):
            time.sleep(0.6)
            if cdp_eval(tid, 'document.querySelectorAll(\'article[data-testid="tweet"]\').length || 0'):
                break
        rows = cdp_eval(tid, f"""(() => {{
            const out = [];
            const seen = new Set();
            for (const art of document.querySelectorAll('article[data-testid="tweet"]')) {{
                const statusLink = art.querySelector('a[href*="/status/"]');
                if (!statusLink) continue;
                const href = statusLink.href || '';
                const sm = href.match(/(?:x|twitter)\\.com\\/([^/?#]+)\\/status\\/(\\d+)/);
                if (!sm || seen.has(sm[2])) continue;
                seen.add(sm[2]);
                const textEl = art.querySelector('[data-testid="tweetText"]');
                const text = textEl ? textEl.innerText.trim() : art.innerText.trim().slice(0, 280);
                const timeEl = art.querySelector('time');
                out.push({{
                    tweet_id: sm[2],
                    title: text.slice(0, 80),
                    text,
                    author: sm[1],
                    created_at: timeEl ? timeEl.getAttribute('datetime') : null,
                    url: `https://x.com/${{sm[1]}}/status/${{sm[2]}}`
                }});
                if (out.length >= {limit}) break;
            }}
            return out;
        }})()""") or []

    rows = [r for r in rows if _url_matches_domains(r.get("url"), ("x.com", "twitter.com"))]
    with httpx.Client(headers=DEFAULT_HEADERS, proxy=LOCAL_PROXY, timeout=6.0, follow_redirects=True, trust_env=False) as client:
        for row in rows:
            tw_id = row.get("tweet_id") or ""
            likes = 0
            retweets = 0
            replies = 0
            if tw_id:
                try:
                    sr = client.get(f"https://cdn.syndication.twimg.com/tweet-result?id={tw_id}&token=a")
                    if sr.status_code == 200:
                        d = sr.json()
                        likes = int(d.get("favorite_count") or 0)
                        replies = int(d.get("conversation_count") or 0)
                        retweets = int(d.get("retweet_count") or d.get("quote_count") or 0)
                        if d.get("text"):
                            row["text"] = d["text"]
                except Exception:
                    pass
            row["likes"] = likes
            row["retweets"] = retweets
            row["replies"] = replies
            row["engagement_score"] = likes + retweets * 3 + replies * 2

    return {
        "ok": len(rows) > 0,
        "platform": "twitter",
        "backend": "x-native-dom-9223",
        "query": query,
        "count": len(rows),
        **({"error": "NO_RESULTS"} if not rows else {}),
        "items": rows,
    }


def twitter_read(url_or_id: str) -> dict[str, Any]:
    m = re.search(r"(?:status|statuses)/(\d+)", url_or_id) or re.match(r"^(\d{10,25})$", url_or_id.strip())
    if not m:
        return {"ok": False, "platform": "twitter", "error": f"Cannot extract tweet ID from {url_or_id!r}"}
    tid = m.group(1)
    r = httpx.get(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&token=a", headers=DEFAULT_HEADERS, timeout=10.0)
    if r.status_code != 200:
        return {"ok": False, "platform": "twitter", "tweet_id": tid, "error": f"HTTP {r.status_code}"}
    d = r.json()
    user = d.get("user") or {}
    return {
        "ok": True,
        "platform": "twitter",
        "tweet_id": tid,
        "author": user.get("screen_name"),
        "author_name": user.get("name"),
        "created_at": d.get("created_at"),
        "likes": d.get("favorite_count"),
        "retweets": d.get("retweet_count") or d.get("quote_count") or 0,
        "replies": d.get("conversation_count"),
        "text": d.get("text"),
        "url": f"https://x.com/{user.get('screen_name', 'i')}/status/{tid}",
    }


def reddit_search(query: str, limit: int = 10) -> dict[str, Any]:
    q_str = (query or "").strip()
    sub_m = re.match(r"^(?:r/|subreddit:)([A-Za-z0-9_]+)(?:\s+(.*))?$", q_str, re.I)
    if sub_m:
        sub_name = sub_m.group(1)
        sub_q = (sub_m.group(2) or "").strip()
        try:
            with httpx.Client(headers=DEFAULT_HEADERS, timeout=12.0) as client:
                params: dict[str, Any] = {"subreddit": sub_name, "limit": limit, "sort": "desc"}
                if sub_q:
                    params["query"] = sub_q
                r = client.get("https://arctic-shift.photon-reddit.com/api/posts/search", params=params)
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    items = []
                    for p in data[:limit]:
                        perm = str(p.get("permalink") or "")
                        cand_url = f"https://www.reddit.com{perm}" if perm.startswith("/") else f"https://www.reddit.com/r/{sub_name}/comments/{p.get('id')}/"
                        if not _url_matches_domains(cand_url, ("reddit.com",)):
                            continue
                        items.append({
                            "id": p.get("id"),
                            "subreddit": p.get("subreddit_name_prefixed") or f"r/{sub_name}",
                            "title": p.get("title"),
                            "author": p.get("author"),
                            "score": p.get("score"),
                            "num_comments": p.get("num_comments"),
                            "selftext": str(p.get("selftext") or "")[:320],
                            "url": cand_url,
                        })
                    if items:
                        return {"ok": True, "platform": "reddit", "backend": "arctic-shift-subreddit-api", "query": query, "count": len(items), "items": items}
        except Exception:
            pass

    r_url = f"https://www.reddit.com/search/?q={_q(q_str)}&type=link"
    rows: list[dict[str, Any]] = []
    with cdp_background_tab(r_url, task_name="reddit-search") as tid:
        for _ in range(10):
            time.sleep(0.5)
            if cdp_eval(tid, "document.querySelectorAll('a[data-testid=\"post-title\"], a[href*=\"/r/\"][href*=\"/comments/\"]').length || 0"):
                break
        rows = cdp_eval(tid, f"""(() => {{
            const out = [];
            const seen = new Set();
            for (const a of document.querySelectorAll('a[data-testid="post-title"], a[href*="/r/"][href*="/comments/"]')) {{
                const href = a.href || '';
                const m = href.match(/\\/r\\/([^/]+)\\/comments\\/([a-z0-9]+)/i);
                const title = (a.innerText || a.getAttribute('aria-label') || '').trim();
                if (!m || !title || seen.has(m[2])) continue;
                seen.add(m[2]);
                const cleanUrl = href.split('?')[0];
                out.push({{
                    id: m[2],
                    subreddit: 'r/' + m[1],
                    title,
                    url: cleanUrl
                }});
                if (out.length >= {limit}) break;
            }}
            return out;
        }})()""") or []

    rows = [r for r in rows if _url_matches_domains(r.get("url"), ("reddit.com",))]
    if rows:
        ids_csv = ",".join(r["id"] for r in rows if r.get("id"))
        if ids_csv:
            try:
                with httpx.Client(headers=DEFAULT_HEADERS, timeout=10.0) as client:
                    pr = client.get("https://arctic-shift.photon-reddit.com/api/posts/ids", params={"ids": ids_csv})
                    if pr.status_code == 200:
                        by_id = {str(x.get("id")): x for x in (pr.json().get("data") or []) if isinstance(x, dict)}
                        for r in rows:
                            meta = by_id.get(str(r.get("id"))) or {}
                            r["author"] = meta.get("author")
                            r["score"] = meta.get("score")
                            r["num_comments"] = meta.get("num_comments")
                            r["selftext"] = str(meta.get("selftext") or "")[:320]
            except Exception:
                pass
    return {
        "ok": len(rows) > 0,
        "platform": "reddit",
        "backend": "reddit-native-search-9223",
        "query": query,
        "count": len(rows),
        **({"error": "NO_RESULTS"} if not rows else {}),
        "items": rows,
    }


def reddit_read(url_or_id: str, limit: int = 15) -> dict[str, Any]:
    m = re.search(r"/comments/([a-z0-9]+)", url_or_id, re.I) or re.match(r"^([a-z0-9]{5,10})$", url_or_id.strip(), re.I)
    if not m:
        return {"ok": False, "platform": "reddit", "error": f"Cannot extract Reddit post ID from {url_or_id!r}"}
    pid = m.group(1)
    with httpx.Client(headers=DEFAULT_HEADERS, timeout=12.0) as client:
        pr = client.get("https://arctic-shift.photon-reddit.com/api/posts/ids", params={"ids": pid}).json()
        pdata = (pr.get("data") or [{}])[0] if pr.get("data") else {}
        cr = client.get("https://arctic-shift.photon-reddit.com/api/comments/search", params={"link_id": pid, "limit": limit}).json()
        cdata = cr.get("data") or []
        comments = [
            {"id": c.get("id"), "author": c.get("author"), "score": c.get("score"), "body": c.get("body")}
            for c in cdata
            if c.get("body") not in (None, "[deleted]", "[removed]")
        ]
        return {
            "ok": True,
            "platform": "reddit",
            "id": pid,
            "subreddit": pdata.get("subreddit_name_prefixed") or pdata.get("subreddit"),
            "title": pdata.get("title"),
            "author": pdata.get("author"),
            "score": pdata.get("score"),
            "num_comments": pdata.get("num_comments"),
            "selftext": pdata.get("selftext"),
            "url": f"https://www.reddit.com{pdata.get('permalink')}" if pdata.get("permalink") else url_or_id,
            "comments_count": len(comments),
            "comments": comments,
        }


# ---------------------------------------------------------------------------
# 8. 52pojie (吾爱破解: RSS, Guide hot/digest/newthread, AnySearch, 9223 Read)
# ---------------------------------------------------------------------------
def _run_anysearch(query: str, limit: int = 10) -> tuple[bool, list[dict[str, Any]], str | None]:
    """Invoke local managed AnySearch CLI without scraping target forum search endpoints."""
    cmd = [ANYSEARCH_PYTHON, ANYSEARCH_CLI, "search", query, "-m", str(max(1, min(limit, 30))), "--json"]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            env={**os.environ, "CI": "1"},
            check=False,
        )
        if proc.returncode != 0:
            return False, [], (proc.stderr or proc.stdout or f"anysearch exited {proc.returncode}").strip()[:300]
        payload = json.loads(proc.stdout)
        results = ((payload.get("data") or {}).get("results")) or payload.get("results") or []
        return True, results[:limit], None
    except Exception as exc:
        return False, [], str(exc)


def _decode_52pojie_bytes(raw: bytes, content_type: str = "") -> str:
    ct = (content_type or "").lower()
    if "gbk" in ct or "gb2312" in ct or "gb18030" in ct:
        return raw.decode("gb18030", errors="replace")
    head_ascii = raw[:256].decode("latin1", errors="ignore").lower()
    if 'encoding="gbk"' in head_ascii or "charset=gbk" in head_ascii or "charset=gb2312" in head_ascii:
        return raw.decode("gb18030", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gb18030", errors="replace")


def _is_52pojie_waf(url_str: str, body_text: str) -> bool:
    u = (url_str or "").lower()
    head = (body_text or "")[:1500].lower()
    if "wzws-waf-cgi" in u or "slidercaptcha" in head:
        return True
    if "$_ts" in head and "<rss" not in head and "normalthread_" not in head and "postlist" not in head:
        return True
    return False


def _get_52pojie_headers_and_cookies() -> tuple[dict[str, str], dict[str, str]]:
    ua = CHROME_UA
    jar: dict[str, str] = {}
    try:
        ver = cdp_request("/json/version", method="GET", timeout=3.0)
        if ver.get("User-Agent"):
            ua = str(ver["User-Agent"])
        ck_res = cdp_request("/cookies", {"domain": "52pojie.cn"}, timeout=4.0)
        for c in ck_res.get("cookies") or []:
            if c.get("name") and c.get("value") is not None:
                jar[str(c["name"])] = str(c["value"])
    except Exception:
        pass
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.52pojie.cn/",
    }
    return headers, jar


def _fetch_52pojie_document(url: str) -> tuple[bool, str, str, bool]:
    """Return (ok, final_url, decoded_text, waf_detected) using direct HTTP + Chrome cookies, with :9223 persistent fallback."""
    headers, cookies = _get_52pojie_headers_and_cookies()
    try:
        with httpx.Client(headers=headers, cookies=cookies, follow_redirects=True, timeout=12.0, trust_env=False) as client:
            r = client.get(url)
            txt = _decode_52pojie_bytes(r.content, r.headers.get("content-type", ""))
            if r.status_code == 200 and not _is_52pojie_waf(str(r.url), txt):
                return True, str(r.url), txt, False
    except Exception:
        pass

    # Fallback: fetch inside :9223 persistent 52pojie.cn tab (preserves session & clearance)
    try:
        with cdp_background_tab("https://www.52pojie.cn/", task_name="52pojie-http") as tid:
            time.sleep(1.5)
            fetched = cdp_eval(
                tid,
                f"""(async () => {{
                    const r = await fetch({json.dumps(url)}, {{ credentials: 'include' }});
                    const buf = await r.arrayBuffer();
                    const ct = r.headers.get('content-type') || '';
                    let dec = 'utf-8';
                    const head = new TextDecoder('latin1').decode(buf.slice(0, 256)).toLowerCase();
                    if (ct.toLowerCase().includes('gbk') || head.includes('gbk') || head.includes('gb2312')) dec = 'gb18030';
                    const text = new TextDecoder(dec).decode(buf);
                    return {{ status: r.status, url: r.url, text }};
                }})()""",
                timeout=15.0,
            ) or {}
            txt = str(fetched.get("text") or "")
            f_url = str(fetched.get("url") or url)
            waf = _is_52pojie_waf(f_url, txt)
            return (fetched.get("status") == 200 and not waf and bool(txt)), f_url, txt, waf
    except Exception as exc:
        return False, url, str(exc), False


def pojie52_rss(limit: int = 20) -> dict[str, Any]:
    rss_url = "https://www.52pojie.cn/forum.php?mod=rss"
    ok, final_url, xml_text, waf = _fetch_52pojie_document(rss_url)
    if not ok:
        return {
            "ok": False,
            "platform": "52pojie",
            "action": "rss",
            "url": final_url,
            "waf_detected": waf,
            "error": "waf_challenge_detected" if waf else "rss_fetch_failed",
            "fallback_hint": "Use `reach_hub.py 52pojie search <query>` (AnySearch) or complete WAF verification in Chrome :9223.",
            "items": [],
        }
    clean_xml = re.sub(r'(<\?xml[^>]*encoding=["\'])([^"\']+)(["\'])', r"\1utf-8\3", xml_text, count=1, flags=re.I)
    try:
        root = ET.fromstring(clean_xml.encode("utf-8"))
    except ET.ParseError as exc:
        return {"ok": False, "platform": "52pojie", "action": "rss", "error": f"xml_parse_error: {exc}", "items": []}

    items: list[dict[str, Any]] = []
    for item_el in root.findall("./channel/item")[:limit]:
        link = (item_el.findtext("link") or "").strip()
        tid_m = re.search(r"thread-(\d+)-|tid=(\d+)", link)
        tid = (tid_m.group(1) or tid_m.group(2)) if tid_m else ""
        desc_html = item_el.findtext("description") or ""
        desc_txt = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)[:280]
        items.append(
            {
                "tid": tid,
                "title": (item_el.findtext("title") or "").strip(),
                "category": (item_el.findtext("category") or "").strip(),
                "author": (item_el.findtext("author") or "").strip(),
                "pub_date": (item_el.findtext("pubDate") or "").strip(),
                "snippet": desc_txt,
                "url": link,
            }
        )
    return {
        "ok": True,
        "platform": "52pojie",
        "action": "rss",
        "count": len(items),
        "items": items,
    }


def pojie52_guide(view: str = "hot", limit: int = 20) -> dict[str, Any]:
    norm_view = view.strip().lower() if view else "hot"
    if norm_view not in ("hot", "digest", "newthread", "new", "sofa"):
        norm_view = "hot"
    guide_url = f"https://www.52pojie.cn/forum.php?mod=guide&view={norm_view}"
    ok, final_url, html_text, waf = _fetch_52pojie_document(guide_url)
    if not ok:
        return {
            "ok": False,
            "platform": "52pojie",
            "action": "guide",
            "view": norm_view,
            "url": final_url,
            "waf_detected": waf,
            "error": "ruishu_or_cwap_waf_detected" if waf else "guide_fetch_failed",
            "fallback_hint": "WAF challenge encountered; fallback to `reach_hub.py 52pojie rss` or `reach_hub.py 52pojie search <query>`.",
            "items": [],
        }

    soup = BeautifulSoup(html_text, "html.parser")
    items: list[dict[str, Any]] = []
    for tbody in soup.select('#threadlist tbody[id^="normalthread_"]')[:limit]:
        tbody_id = tbody.get("id") or ""
        tid = tbody_id.replace("normalthread_", "").strip()
        a_xst = tbody.select_one("a.xst")
        if not a_xst:
            continue
        href = (a_xst.get("href") or "").strip()
        full_url = urllib.parse.urljoin("https://www.52pojie.cn/", href) if href else f"https://www.52pojie.cn/thread-{tid}-1-1.html"
        forum_el = tbody.select_one("td.by a")
        author_cells = tbody.select("td.by")
        author_el = author_cells[1].select_one("cite a") if len(author_cells) > 1 else tbody.select_one("td.by cite a")
        date_el = author_cells[1].select_one("em span, em") if len(author_cells) > 1 else None
        num_replies_el = tbody.select_one("td.num a")
        num_views_el = tbody.select_one("td.num em")
        items.append(
            {
                "tid": tid,
                "title": a_xst.get_text(" ", strip=True),
                "forum": forum_el.get_text(" ", strip=True) if forum_el else "",
                "author": author_el.get_text(" ", strip=True) if author_el else "",
                "published": date_el.get_text(" ", strip=True) if date_el else "",
                "replies": parse_compact_count(num_replies_el.get_text(strip=True)) if num_replies_el else 0,
                "views": parse_compact_count(num_views_el.get_text(strip=True)) if num_views_el else 0,
                "url": full_url,
            }
        )
    return {
        "ok": True,
        "platform": "52pojie",
        "action": "guide",
        "view": norm_view,
        "count": len(items),
        "items": items,
    }


def pojie52_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search 52pojie via local AnySearch (`site:52pojie.cn <query>`) with strict 52pojie.cn thread-URL verification."""
    ok, raw_results, err = _run_anysearch(f"site:52pojie.cn {query}".strip(), limit=max(limit * 2, 15))
    if not ok:
        return {"ok": False, "platform": "52pojie", "action": "search", "query": query, "error": err, "items": []}
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for r in raw_results:
        url = str(r.get("url") or "").strip()
        if not _url_matches_domains(url, ("52pojie.cn",)):
            continue
        tid_m = re.search(r"thread-(\d+)-|tid=(\d+)", url)
        if not tid_m and "mod=viewthread" not in url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        tid = (tid_m.group(1) or tid_m.group(2)) if tid_m else ""
        items.append(
            {
                "tid": tid,
                "title": str(r.get("title") or "").strip(),
                "snippet": str(r.get("content") or r.get("snippet") or "")[:300].strip(),
                "url": url,
                "engine": r.get("engine") or "anysearch",
            }
        )
        if len(items) >= limit:
            break
    return {
        "ok": len(items) > 0,
        "platform": "52pojie",
        "action": "search",
        "backend": "anysearch-strict-52pojie",
        "query": query,
        "count": len(items),
        **({"error": "NO_RESULTS"} if not items else {}),
        "items": items,
    }


def pojie52_read(tid_or_url: str, reply_limit: int = 15) -> dict[str, Any]:
    """Read a single 52pojie thread via :9223 persistent reusable tab (logged-in state)."""
    raw = (tid_or_url or "").strip()
    m = re.search(r"thread-(\d+)-|tid=(\d+)", raw) or re.match(r"^(\d+)$", raw)
    if m:
        tid_num = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else "")
        target_url = f"https://www.52pojie.cn/thread-{tid_num}-1-1.html"
    elif raw.startswith("http"):
        tid_num = ""
        target_url = raw
    else:
        return {"ok": False, "platform": "52pojie", "action": "read", "error": f"Invalid 52pojie tid or URL: {tid_or_url!r}"}

    with cdp_background_tab(target_url, task_name="52pojie-read") as tid:
        for _ in range(12):
            time.sleep(0.5)
            if cdp_eval(tid, "document.querySelectorAll('#postlist div[id^=\"post_\"] td.t_f, #thread_subject').length > 0"):
                break
        data = cdp_eval(
            tid,
            f"""(() => {{
                const subjectEl = document.querySelector('#thread_subject');
                const title = subjectEl ? subjectEl.innerText.trim() : document.title.replace(/\\s*-\\s*吾爱破解.*$/, '').trim();
                const posts = [];
                const postDivs = Array.from(document.querySelectorAll('#postlist > div[id^="post_"]'));
                for (const div of postDivs.slice(0, {max(2, reply_limit + 1)})) {{
                    const pid = (div.id || '').replace('post_', '');
                    const authorEl = div.querySelector('.authi a.xw1, .pls .authi a');
                    const timeEl = div.querySelector('em[id^="authorposton"]');
                    const floorEl = div.querySelector('.pi strong a');
                    const bodyEl = div.querySelector('td.t_f');
                    if (!bodyEl) continue;
                    const clone = bodyEl.cloneNode(true);
                    clone.querySelectorAll('i.pstatus, .jammer, span[style*="display:none"]').forEach(n => n.remove());
                    posts.push({{
                        pid,
                        floor: floorEl ? floorEl.innerText.trim() : '',
                        author: authorEl ? authorEl.innerText.trim() : '',
                        posted_at: timeEl ? timeEl.innerText.replace(/^发表于\\s*/, '').trim() : '',
                        content: (clone.innerText || '').trim()
                    }});
                }}
                const hotReplies = Array.from(document.querySelectorAll('#psta, .cm .pstl')).slice(0, 10).map(el => el.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
                return {{ url: location.href, title, posts, hotReplies }};
            }})()""",
            timeout=20.0,
        ) or {}

    posts = data.get("posts") or []
    if not posts:
        return {
            "ok": False,
            "platform": "52pojie",
            "action": "read",
            "tid": tid_num,
            "url": data.get("url") or target_url,
            "error": "empty_thread_or_login_required",
        }
    main_post = posts[0]
    replies = posts[1 : reply_limit + 1]
    return {
        "ok": True,
        "platform": "52pojie",
        "action": "read",
        "backend": "cdp-9223-persistent",
        "tid": tid_num,
        "url": data.get("url") or target_url,
        "title": data.get("title") or "",
        "author": main_post.get("author") or "",
        "posted_at": main_post.get("posted_at") or "",
        "content": main_post.get("content") or "",
        "hot_comments": data.get("hotReplies") or [],
        "replies_count": len(replies),
        "replies": replies,
    }


# ---------------------------------------------------------------------------
# 9. V2EX (Official Public JSON API via :7897 / Direct Adaptive + AnySearch)
# ---------------------------------------------------------------------------
def _v2ex_api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"https://www.v2ex.com{path}"
    last_err: Exception | None = None
    for proxy_url in (LOCAL_PROXY, None):
        try:
            client_kwargs: dict[str, Any] = {
                "headers": DEFAULT_HEADERS,
                "timeout": 10.0,
                "follow_redirects": True,
                "trust_env": False,
            }
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
            with httpx.Client(**client_kwargs) as client:
                r = client.get(url, params=params)
                if r.status_code == 200:
                    return r.json()
                last_err = RuntimeError(f"V2EX HTTP {r.status_code}")
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"V2EX API request failed for {path}: {last_err}")


def v2ex_topics(kind: str = "hot", limit: int = 15) -> dict[str, Any]:
    endpoint = "/api/topics/latest.json" if kind == "latest" else "/api/topics/hot.json"
    try:
        raw = _v2ex_api_get(endpoint)
    except Exception as exc:
        return {"ok": False, "platform": "v2ex", "action": kind, "error": str(exc), "items": []}
    rows = raw if isinstance(raw, list) else []
    items = [
        {
            "id": x.get("id"),
            "title": x.get("title"),
            "url": x.get("url") or (f"https://www.v2ex.com/t/{x.get('id')}" if x.get("id") else ""),
            "replies": x.get("replies"),
            "node": (x.get("node") or {}).get("title"),
            "node_name": (x.get("node") or {}).get("name"),
            "author": (x.get("member") or {}).get("username"),
            "created": x.get("created"),
            "excerpt": str(x.get("content") or "")[:240],
        }
        for x in rows[:limit]
    ]
    return {"ok": True, "platform": "v2ex", "action": kind, "count": len(items), "items": items}


def v2ex_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search V2EX via first-party SOV2EX API (with strict-domain AnySearch fallback)."""
    items: list[dict[str, Any]] = []
    for proxy_url in (LOCAL_PROXY, None):
        try:
            ckw: dict[str, Any] = {"headers": DEFAULT_HEADERS, "timeout": 10.0, "follow_redirects": True, "trust_env": False}
            if proxy_url:
                ckw["proxy"] = proxy_url
            with httpx.Client(**ckw) as client:
                r = client.get("https://www.sov2ex.com/api/search", params={"q": query, "size": min(max(limit, 1), 50), "sort": "sumup"})
                if r.status_code == 200:
                    hits = r.json().get("hits") or []
                    for h in hits[:limit]:
                        tid = h.get("_id") or (h.get("_source") or {}).get("id")
                        if not tid:
                            continue
                        src = h.get("_source") or {}
                        hl = h.get("highlight") or {}
                        hl_frags = (hl.get("content") or []) + (hl.get("postscript_list.content") or [])
                        snippet = re.sub(r"<[^>]+>", "", " ".join(hl_frags))[:300].strip() or str(src.get("content") or "")[:300].strip()
                        cand_url = f"https://www.v2ex.com/t/{tid}"
                        items.append({
                            "id": int(tid),
                            "title": str(src.get("title") or "").strip(),
                            "author": src.get("member"),
                            "replies": src.get("replies"),
                            "created": src.get("created"),
                            "snippet": snippet,
                            "url": cand_url,
                            "engine": "sov2ex",
                        })
                    if items:
                        return {"ok": True, "platform": "v2ex", "action": "search", "backend": "sov2ex-api", "query": query, "count": len(items), "items": items}
                    break
        except Exception:
            continue

    ok, raw_results, err = _run_anysearch(f"site:v2ex.com/t {query}".strip(), limit=max(limit * 2, 15))
    if not ok:
        return {"ok": False, "platform": "v2ex", "action": "search", "query": query, "error": err, "items": []}
    for r in raw_results:
        url = str(r.get("url") or "").strip()
        m = re.search(r"v2ex\.com/t/(\d+)", url)
        if not m or not _url_matches_domains(url, ("v2ex.com",)):
            continue
        items.append(
            {
                "id": int(m.group(1)),
                "title": str(r.get("title") or "").strip(),
                "snippet": str(r.get("content") or r.get("snippet") or "")[:300].strip(),
                "url": f"https://www.v2ex.com/t/{m.group(1)}",
                "engine": r.get("engine") or "anysearch",
            }
        )
        if len(items) >= limit:
            break
    return {
        "ok": len(items) > 0,
        "platform": "v2ex",
        "action": "search",
        "backend": "anysearch-strict-v2ex",
        "query": query,
        "count": len(items),
        **({"error": "NO_RESULTS"} if not items else {}),
        "items": items,
    }


def v2ex_read(id_or_url: str, reply_limit: int = 20) -> dict[str, Any]:
    raw = (id_or_url or "").strip()
    m = re.search(r"v2ex\.com/t/(\d+)", raw) or re.match(r"^(\d+)$", raw)
    if not m:
        return {"ok": False, "platform": "v2ex", "action": "read", "error": f"Cannot extract V2EX topic ID from {id_or_url!r}"}
    topic_id = int(m.group(1))
    try:
        t_list = _v2ex_api_get("/api/topics/show.json", params={"id": topic_id})
        r_list = _v2ex_api_get("/api/replies/show.json", params={"topic_id": topic_id})
    except Exception as exc:
        return {"ok": False, "platform": "v2ex", "action": "read", "id": topic_id, "error": str(exc)}

    topic = (t_list[0] if isinstance(t_list, list) and t_list else None) or {}
    if not topic:
        return {"ok": False, "platform": "v2ex", "action": "read", "id": topic_id, "error": "topic_not_found"}

    raw_replies = r_list if isinstance(r_list, list) else []
    replies = [
        {
            "id": rp.get("id"),
            "author": (rp.get("member") or {}).get("username"),
            "thanks": rp.get("thanks", 0),
            "created": rp.get("created"),
            "content": rp.get("content") or "",
        }
        for rp in raw_replies[:reply_limit]
    ]
    return {
        "ok": True,
        "platform": "v2ex",
        "action": "read",
        "id": topic_id,
        "url": topic.get("url") or f"https://www.v2ex.com/t/{topic_id}",
        "title": topic.get("title") or "",
        "author": (topic.get("member") or {}).get("username"),
        "node": (topic.get("node") or {}).get("title"),
        "created": topic.get("created"),
        "replies_total": topic.get("replies", len(raw_replies)),
        "content": topic.get("content") or "",
        "replies_count": len(replies),
        "replies": replies,
    }


# ---------------------------------------------------------------------------
# 10. YouTube (yt-dlp First-Party Search & VTT Subtitle Extraction)
# ---------------------------------------------------------------------------
def youtube_search(query: str, limit: int = 10) -> dict[str, Any]:
    cmd = [
        YTDLP_BIN,
        "--no-update",
        "--proxy",
        LOCAL_PROXY,
        "--flat-playlist",
        "-J",
        f"ytsearch{max(1, min(limit, 25))}:{query}",
    ]
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "CI": "1"},
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "platform": "youtube", "action": "search", "query": query, "error": (proc.stderr or proc.stdout).strip()[:300], "items": []}
    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        return {"ok": False, "platform": "youtube", "action": "search", "query": query, "error": str(exc), "items": []}
    items: list[dict[str, Any]] = []
    for ent in (data.get("entries") or [])[:limit]:
        vid = str(ent.get("id") or "").strip()
        cand_url = str(ent.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")).strip()
        if vid and not cand_url.startswith("http"):
            cand_url = f"https://www.youtube.com/watch?v={vid}"
        if not _url_matches_domains(cand_url, ("youtube.com", "youtu.be")):
            continue
        items.append({
            "id": vid,
            "title": ent.get("title"),
            "channel": ent.get("channel") or ent.get("uploader"),
            "duration": ent.get("duration"),
            "views": ent.get("view_count"),
            "url": cand_url,
        })
    return {
        "ok": len(items) > 0,
        "platform": "youtube",
        "action": "search",
        "backend": "yt-dlp",
        "query": query,
        "count": len(items),
        **({"error": "NO_RESULTS"} if not items else {}),
        "items": items,
    }


def youtube_read(url_or_id: str) -> dict[str, Any]:
    raw = (url_or_id or "").strip()
    url = raw if raw.startswith("http") else f"https://www.youtube.com/watch?v={raw}"
    if not _url_matches_domains(url, ("youtube.com", "youtu.be")):
        return {"ok": False, "platform": "youtube", "error": f"Invalid YouTube URL or video ID: {url_or_id!r}"}
    with tempfile.TemporaryDirectory(prefix="reach-yt-") as tmp_dir:
        out_tpl = str(Path(tmp_dir) / "%(id)s.%(ext)s")
        cmd = [
            YTDLP_BIN,
            "--no-update",
            "--proxy",
            LOCAL_PROXY,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "zh-Hans,zh-CN,zh,en.*,en",
            "--sub-format",
            "vtt",
            "--print-json",
            "-o",
            out_tpl,
            url,
        ]
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=45,
            env={**os.environ, "CI": "1"},
            check=False,
        )
        meta: dict[str, Any] = {}
        for line in (proc.stdout or "").splitlines():
            if line.strip().startswith("{"):
                try:
                    meta = json.loads(line)
                    break
                except Exception:
                    pass
        vtts = sorted(Path(tmp_dir).glob("*.vtt"))
        tracks = []
        for vf in vtts:
            cleaned = _clean_vtt_subtitle(vf.read_text(encoding="utf-8", errors="replace"))
            if cleaned:
                tracks.append({
                    "file": vf.name,
                    "char_length": len(cleaned),
                    "text": cleaned[:12000],
                })
        if not meta and not tracks:
            return {"ok": False, "platform": "youtube", "url": url, "error": (proc.stderr or "yt-dlp failed").strip()[:300]}
        return {
            "ok": True,
            "platform": "youtube",
            "id": meta.get("id"),
            "url": meta.get("webpage_url") or url,
            "title": meta.get("title"),
            "channel": meta.get("channel") or meta.get("uploader"),
            "duration": meta.get("duration"),
            "views": meta.get("view_count"),
            "description": str(meta.get("description") or "")[:2000],
            "has_subtitle": len(tracks) > 0,
            "tracks": tracks,
        }


def main() -> int:
    parser = argparse.ArgumentParser(prog="reach_hub", description="Multi-Platform Community & Hotlist Hub")
    sub = parser.add_subparsers(dest="platform", required=True)

    sub.add_parser("auth-status", help="Inspect live Chrome 9223 authentication status across all platforms")
    sub.add_parser("status", help="Alias for auth-status")

    p_hot = sub.add_parser("hotlist", help="Fetch multi-platform hotlist radar")
    p_hot.add_argument("--platform", "-p", dest="hot_platform", default="all")
    p_hot.add_argument("--limit", "-n", type=int, default=15)
    p_hot.add_argument("--keyword", "-k", default=None, help="Regex/substring keyword filter across hotlist items")
    p_hot.add_argument(
        "--rerank",
        default=None,
        metavar="QUERY",
        help="Semantic rerank query via local MagPie ${OPENAI_COMPAT_BASE_URL}/rerank (moark/Qwen3-Reranker-4B)",
    )

    p_sq = sub.add_parser("so-qq", help="Tencent Yuanbao Search (so.qq.com) zero-login HTTP/SSE engine")
    p_sq.add_argument("action", choices=["search", "ai"], help="search=structured tab cards; ai=SSE RAG citations & optional summary")
    p_sq.add_argument("target", help="Search query")
    p_sq.add_argument("--tab", choices=["weixin_article", "all", "media", "gov", "xueshu", "weixin_video"], default="all")
    p_sq.add_argument("--time", dest="time_filter", choices=["all", "1h", "1d", "1w", "1m", "1y"], default="all")
    p_sq.add_argument("--page", type=int, default=1)
    p_sq.add_argument("--limit", "-n", type=int, default=10)
    p_sq.add_argument("--summary", action="store_true", help="Wait for full LLM summary in ai mode (default early-stops after citations)")

    p_52 = sub.add_parser("52pojie", help="52pojie (吾爱破解) RSS, guide, strict-domain AnySearch, and :9223 persistent-tab reader")
    p_52.add_argument("action", choices=["rss", "guide", "search", "read"])
    p_52.add_argument("target", nargs="?", default="", help="Query for search, tid/URL for read, or view (hot|digest|newthread) for guide")
    p_52.add_argument("--view", choices=["hot", "digest", "newthread"], default=None, help="Guide view when action=guide")
    p_52.add_argument("--limit", "-n", type=int, default=15)

    p_v2 = sub.add_parser("v2ex", help="V2EX official public API (hot/latest/read) + SOV2EX search")
    p_v2.add_argument("action", choices=["hot", "latest", "search", "read"])
    p_v2.add_argument("target", nargs="?", default="", help="Query for search or topic ID/URL for read")
    p_v2.add_argument("--limit", "-n", type=int, default=15)

    for plat in ("wechat", "douyin", "bilibili", "zhihu", "xiaohongshu", "xhs", "twitter", "reddit", "youtube", "yt"):
        sp = sub.add_parser(plat)
        sp.add_argument("action", choices=["search", "read", "author", "comments", "subtitle", "feed", "hot", "login", "yuanbao", "so-qq"])
        sp.add_argument("target", nargs="?", default="")
        sp.add_argument("--limit", "-n", type=int, default=10)
        sp.add_argument("--order", choices=["likes", "recent"], default="likes")
        sp.add_argument("--with-body", action="store_true")
        sp.add_argument("--deep", action="store_true", help="Include so.qq.com AI SSE long-tail WeChat Search + summary")

    ns = parser.parse_args()
    if ns.platform in ("auth-status", "status"):
        res = auth_status()
    elif ns.platform == "hotlist":
        res = fetch_hotlist(ns.hot_platform, ns.limit, keyword=ns.keyword, rerank_query=ns.rerank)
    elif ns.platform == "so-qq":
        if ns.action == "ai":
            res = so_qq_aimode_search(ns.target, wechat_bias=False, want_summary=ns.summary, limit=ns.limit)
        else:
            res = so_qq_nextpage_search(ns.target, tab=ns.tab, time_filter=ns.time_filter, page=ns.page, limit=ns.limit)
    elif ns.platform == "52pojie":
        if ns.action == "rss":
            res = pojie52_rss(ns.limit)
        elif ns.action == "guide":
            res = pojie52_guide(ns.view or ns.target or "hot", ns.limit)
        elif ns.action == "search":
            res = pojie52_search(ns.target, ns.limit)
        else:
            res = pojie52_read(ns.target, ns.limit)
    elif ns.platform == "v2ex":
        if ns.action in ("hot", "latest"):
            res = v2ex_topics(ns.action, ns.limit)
        elif ns.action == "search":
            res = v2ex_search(ns.target, ns.limit)
        else:
            res = v2ex_read(ns.target, ns.limit)
    elif ns.platform == "wechat":
        if ns.action in ("search", "yuanbao", "so-qq"):
            res = wechat_search(ns.target, ns.limit, ns.with_body, deep=(ns.deep or ns.action == "yuanbao"))
        else:
            res = wechat_read(ns.target)
    elif ns.platform == "douyin":
        if ns.action == "search":
            res = douyin_search(ns.target, ns.limit)
        elif ns.action == "author":
            res = douyin_author(ns.target, ns.limit, ns.order)
        else:
            res = douyin_comments(ns.target, ns.limit)
    elif ns.platform == "bilibili":
        if ns.action == "search":
            res = bilibili_search(ns.target, ns.limit)
        elif ns.action == "comments":
            res = bilibili_comments(ns.target, ns.limit)
        else:
            res = bilibili_subtitle(ns.target)
    elif ns.platform == "zhihu":
        if ns.action == "search":
            res = zhihu_search(ns.target, ns.limit)
        elif ns.action == "comments":
            res = zhihu_comments(ns.target, ns.limit)
        else:
            res = zhihu_read(ns.target)
    elif ns.platform in ("xiaohongshu", "xhs"):
        if ns.action == "search":
            res = xhs_search(ns.target, ns.limit)
        elif ns.action == "feed":
            res = xhs_feed(ns.limit)
        elif ns.action in ("read", "comments"):
            res = xhs_read(ns.target, ns.limit)
        elif ns.action == "login":
            res = xhs_login()
        else:
            res = fetch_hotlist("rednote", ns.limit)
    elif ns.platform == "twitter":
        res = twitter_search(ns.target, ns.limit) if ns.action == "search" else twitter_read(ns.target)
    elif ns.platform == "reddit":
        res = reddit_search(ns.target, ns.limit) if ns.action == "search" else reddit_read(ns.target, ns.limit)
    elif ns.platform in ("youtube", "yt"):
        res = youtube_search(ns.target, ns.limit) if ns.action == "search" else youtube_read(ns.target)
    else:
        res = {"ok": False, "error": f"Unsupported platform {ns.platform}"}

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
