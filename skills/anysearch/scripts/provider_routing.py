#!/usr/bin/env python3
"""Multi-source tiered search and fetch router for AnySearch.

Architecture:
Tier 1: DeepSeek Official Search & Fetch REST API (300ms, dense markdown, authority)
        Brave Search Official API (global web search, HTTP 200 verified)
Tier 2: AnySearch Aggregation API
Tier 3: Bing RSS XML (zero-auth lightweight emergency fallback)
Note: Bocha AI Search (HTTP 403 quota exhausted as of 2026-11-12) is demoted out of auto chain and only invoked on explicit --provider bocha.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import requests

CONFIG_ENV = os.path.expanduser("~/.config/anysearch/anysearch.env")
AI_RELAYS_CREDS = os.path.expanduser("~/.config/ai-relays/credentials.json")


def _get_keychain_secret(service_name: str, account: str | None = None) -> str | None:
    """Retrieve secret from macOS Keychain safely."""
    try:
        cmd = ["security", "find-generic-password", "-s", service_name]
        if account:
            cmd.extend(["-a", account])
        cmd.append("-w")
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        val = res.stdout.strip()
        return val or None
    except Exception:
        return None


def _get_ai_relays_provider_key(provider_id: str) -> str | None:
    """Read verified provider key from ~/.config/ai-relays/credentials.json without logging secrets."""
    try:
        if not os.path.exists(AI_RELAYS_CREDS):
            return None
        with open(AI_RELAYS_CREDS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        prov = (data.get("providers") or {}).get(provider_id) or {}
        val = (prov.get("api_key") or "").strip()
        return val or None
    except Exception:
        return None


def get_deepseek_key() -> str | None:
    return (
        os.environ.get("DEEPSEEK_API_KEY")
        or _get_keychain_secret("deepseek-api-key")
        or _get_ai_relays_provider_key("deepseek_official")
    )


def get_brave_key() -> str | None:
    return (
        os.environ.get("BRAVE_API_KEY")
        or os.environ.get("BRAVE_SEARCH_API_KEY")
        or _get_keychain_secret("cc-web-mcp-brave-search-api-key", "default")
        or _get_keychain_secret("cc-web-mcp-brave-search-api-key")
    )


def get_bocha_key() -> str | None:
    return (
        os.environ.get("BOCHA_API_KEY")
        or _get_keychain_secret("bocha-api-key")
    )


def search_deepseek(query: str, count: int = 10, api_key: str | None = None) -> dict:
    """Query DeepSeek Official Search REST API."""
    key = api_key or get_deepseek_key()
    if not key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    url = "https://api.deepseek.com/v1/tools/search"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query[:128],
        "count": max(1, min(count, 50)),
        "need_content": True,
    }

    start = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    elapsed_ms = int((time.time() - start) * 1000)
    raw_results = []
    if isinstance(body.get("data"), dict):
        raw_results = body["data"].get("results") or []
    elif isinstance(body.get("data"), list):
        raw_results = body["data"]
    elif isinstance(body.get("results"), list):
        raw_results = body["results"]

    results = []
    for item in raw_results:
        title = item.get("title") or item.get("name") or "(Untitled)"
        link = item.get("url") or item.get("link") or ""
        snippet = item.get("summary") or item.get("snippet") or item.get("content") or ""
        extra = {}
        if "authority" in item:
            extra["authority"] = item["authority"]
        if "rerank_score" in item:
            extra["rerank_score"] = item["rerank_score"]

        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "content": snippet,
            **extra,
        })

    return {
        "code": 0,
        "message": "success",
        "provider": "deepseek",
        "data": {
            "results": results,
            "metadata": {
                "total_results": len(results),
                "search_time_ms": elapsed_ms,
                "provider": "deepseek",
            },
        },
    }


def search_bocha(query: str, count: int = 10, api_key: str | None = None) -> dict:
    """Query Bocha AI Web Search REST API."""
    key = api_key or get_bocha_key()
    if not key:
        raise ValueError("BOCHA_API_KEY is not configured")

    url = "https://api.bochaai.com/v1/web-search"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "count": max(1, min(count, 50)),
        "summary": True,
    }

    start = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    elapsed_ms = int((time.time() - start) * 1000)
    web_pages = body.get("data", {}).get("webPages", {}).get("value", [])

    results = []
    for page in web_pages:
        title = page.get("name") or "(Untitled)"
        link = page.get("url") or ""
        snippet = page.get("summary") or page.get("snippet") or ""
        date = page.get("datePublished")
        site_name = page.get("siteName")
        desc = snippet
        if date or site_name:
            prefix_parts = []
            if site_name:
                prefix_parts.append(f"[{site_name}]")
            if date:
                prefix_parts.append(f"({date[:10]})")
            desc = f"{' '.join(prefix_parts)} {desc}".strip()

        results.append({
            "title": title,
            "url": link,
            "snippet": desc,
            "content": desc,
            "siteName": site_name,
            "datePublished": date,
        })

    return {
        "code": 0,
        "message": "success",
        "provider": "bocha",
        "data": {
            "results": results,
            "metadata": {
                "total_results": len(results),
                "search_time_ms": elapsed_ms,
                "provider": "bocha",
            },
        },
    }


def search_bing_rss(query: str, count: int = 10) -> dict:
    """Zero-auth fallback using Bing RSS XML."""
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={encoded_query}&format=rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }

    start = time.time()
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    elapsed_ms = int((time.time() - start) * 1000)

    root = ET.fromstring(resp.content)
    results = []
    for item in root.findall(".//item")[:count]:
        title = item.findtext("title") or "(Untitled)"
        link = item.findtext("link") or ""
        snippet = item.findtext("description") or ""
        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "content": snippet,
        })

    return {
        "code": 0,
        "message": "success",
        "provider": "bing_rss",
        "data": {
            "results": results,
            "metadata": {
                "total_results": len(results),
                "search_time_ms": elapsed_ms,
                "provider": "bing_rss",
            },
        },
    }


def fetch_deepseek(url: str, api_key: str | None = None) -> dict:
    """Fetch and extract markdown content via DeepSeek Official Fetch REST API."""
    key = api_key or get_deepseek_key()
    if not key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    fetch_url = "https://api.deepseek.com/v1/tools/fetch"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {"url": url}

    resp = requests.post(fetch_url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    body = resp.json()

    data = body.get("data") or {}
    title = data.get("title") or ""
    content = data.get("content") or data.get("markdown") or ""

    return {
        "code": 0,
        "message": "success",
        "provider": "deepseek_fetch",
        "data": {
            "title": title,
            "url": url,
            "content": content,
        },
    }


def search_brave(query: str, count: int = 10, api_key: str | None = None) -> dict:
    """Query Brave Search Official Web Search REST API."""
    key = api_key or get_brave_key()
    if not key:
        raise ValueError("BRAVE_API_KEY is not configured")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": key,
    }
    params = {
        "q": query[:400],
        "count": max(1, min(count, 20)),
    }
    proxies = None
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("HTTPS_PROXY", "")
    )
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    start = time.time()
    resp = requests.get(url, headers=headers, params=params, proxies=proxies, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    elapsed_ms = int((time.time() - start) * 1000)

    web_items = (body.get("web") or {}).get("results") or []
    results = []
    for item in web_items:
        title = item.get("title") or "(Untitled)"
        link = item.get("url") or ""
        snippet = item.get("description") or ""
        age = item.get("page_age") or item.get("age")
        results.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "content": snippet,
            **({"age": age} if age else {}),
        })

    return {
        "code": 0,
        "message": "success",
        "provider": "brave",
        "data": {
            "results": results,
            "metadata": {
                "total_results": len(results),
                "search_time_ms": elapsed_ms,
                "provider": "brave",
            },
        },
    }


def tiered_search(
    query: str,
    count: int = 10,
    preferred_provider: str = "auto",
    fallback_fn=None,  # AnySearch REST fallback callback
) -> tuple[dict, str]:
    """Execute tiered multi-source search with automatic failover.

    Hierarchy:
    1. DeepSeek Official Search (if key configured in env / Keychain / credentials.json)
    2. Brave Search Official API (if key configured in env / Keychain)
    3. AnySearch API (if fallback_fn provided)
    4. Bing RSS XML
    (Bocha is demoted out of auto chain due to 403 quota exhaustion; callable explicitly via preferred_provider='bocha'.)
    """
    prov = preferred_provider.lower().strip()
    errors = []

    # Explicit provider selection (with automatic failover if quota/auth/network fails)
    if prov == "deepseek":
        try:
            return search_deepseek(query, count), "deepseek"
        except Exception as e:
            errors.append(f"DeepSeek(explicit): {e}")
    elif prov in ("brave", "brave_search"):
        try:
            return search_brave(query, count), "brave"
        except Exception as e:
            errors.append(f"Brave(explicit): {e}")
    elif prov == "bocha":
        try:
            return search_bocha(query, count), "bocha"
        except Exception as e:
            errors.append(f"Bocha(explicit): {e}")
    elif prov in ("bing", "bing_rss"):
        try:
            return search_bing_rss(query, count), "bing_rss"
        except Exception as e:
            errors.append(f"BingRSS(explicit): {e}")
    elif prov == "anysearch" and fallback_fn:
        try:
            return fallback_fn(), "anysearch"
        except Exception as e:
            errors.append(f"AnySearch(explicit): {e}")

    # Auto tiered routing
    # Tier 1a: DeepSeek Official Search
    if get_deepseek_key():
        try:
            res = search_deepseek(query, count)
            if (res.get("data") or {}).get("results"):
                return res, "deepseek"
        except Exception as e:
            errors.append(f"DeepSeek: {e}")

    # Tier 1b: Brave Search Official API
    if get_brave_key():
        try:
            res = search_brave(query, count)
            if (res.get("data") or {}).get("results"):
                return res, "brave"
        except Exception as e:
            errors.append(f"Brave: {e}")

    # Tier 2: AnySearch API
    if fallback_fn:
        try:
            return fallback_fn(), "anysearch"
        except Exception as e:
            errors.append(f"AnySearch: {e}")

    # Tier 3: Bing RSS
    try:
        return search_bing_rss(query, count), "bing_rss"
    except Exception as e:
        errors.append(f"BingRSS: {e}")

    raise RuntimeError(f"All search tiers failed for '{query}': {'; '.join(errors)}")
