#!/usr/bin/env python3
"""Semantic Scholar 论文搜索。通过 Semantic Scholar Graph API。"""
from __future__ import annotations

import os
import sys
import time

import httpx

from search_utils import build_parser, get_client, get_key, load_config_env, make_item, make_result, print_json

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

FIELDS = ",".join([
    "title", "abstract", "tldr", "year", "venue", "publicationVenue", "publicationDate",
    "authors", "citationCount", "influentialCitationCount",
    "referenceCount", "isOpenAccess", "openAccessPdf",
    "externalIds", "fieldsOfStudy", "publicationTypes", "journal",
])


def semantic_scholar_get(client, url: str, params: dict, api_key: str | None):
    """Conservative request helper for S2's shared unauthenticated pool."""
    if not api_key:
        time.sleep(0.5)
    max_attempts = 3 if api_key else 1
    for attempt in range(max_attempts):
        resp = client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()
        if attempt == max_attempts - 1:
            raise httpx.HTTPStatusError("Semantic Scholar 429 (Rate Limited)", request=resp.request, response=resp)
        retry_after = resp.headers.get("retry-after")
        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0
        time.sleep(delay)
    raise httpx.HTTPError("Semantic Scholar response was empty after retries")


def search(query: str, limit: int, api_key: str | None = None) -> tuple[list[dict], str]:
    """执行 Semantic Scholar 搜索，遇 429 自动优雅降级到 OpenAlex。"""
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": FIELDS,
    }

    try:
        with get_client(timeout=15, headers=headers) as client:
            data = semantic_scholar_get(client, API_URL, params, api_key)
    except (httpx.HTTPStatusError, httpx.HTTPError) as err:
        # 遇 429 速率限制或连接失败时，自动无缝降级到 OpenAlex (免 Key、100k次/天、高可用)
        sys.stderr.write(f"[semantic_scholar] Upstream unavailable ({err}), falling back to OpenAlex...\n")
        from openalex_search import search as openalex_fallback
        return openalex_fallback(query, limit), "openalex_fallback"

    items = []
    for paper in data.get("data", [])[:limit]:
        authors = [a.get("name", "") for a in paper.get("authors", [])]

        open_access_pdf = None
        if paper.get("openAccessPdf"):
            open_access_pdf = paper["openAccessPdf"].get("url")

        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")

        paper_id = paper.get("paperId", "")
        url = f"https://www.semanticscholar.org/paper/{paper_id}"

        # 摘要：优先用 abstract，缺失时降级用 tldr
        abstract = paper.get("abstract") or ""
        tldr = (paper.get("tldr") or {}).get("text")
        snippet = abstract or tldr or ""

        # 期刊/会议：venue（脏字符串）+ publicationVenue（结构化）
        venue = paper.get("venue") or (paper.get("journal") or {}).get("name")
        pub_venue = paper.get("publicationVenue") or {}
        publication_venue = {
            k: pub_venue[k]
            for k in ("id", "name", "type", "url")
            if pub_venue.get(k)
        } or None

        items.append(make_item(
            title=paper.get("title") or "",
            url=url,
            snippet=snippet,
            tldr=tldr,
            authors=authors,
            year=paper.get("year"),
            venue=venue if venue else None,
            publication_venue=publication_venue,
            publication_date=paper.get("publicationDate"),
            citation_count=paper.get("citationCount"),
            influential_citation_count=paper.get("influentialCitationCount"),
            reference_count=paper.get("referenceCount"),
            is_open_access=paper.get("isOpenAccess"),
            open_access_pdf=open_access_pdf,
            fields_of_study=paper.get("fieldsOfStudy") or None,
            publication_types=paper.get("publicationTypes") or None,
            doi=doi,
            arxiv_id=arxiv_id,
            paper_id=paper_id,
        ))

    return items, "semantic_scholar"


def main():
    parser = build_parser("搜索 Semantic Scholar 学术论文 (带 OpenAlex 自动故障转移)")
    parser.add_argument("--api-key", help="Semantic Scholar API Key（可选，提高限额；默认读取 S2_API_KEY）")
    args = parser.parse_args()

    try:
        load_config_env()
        api_key = get_key("S2_API_KEY", getattr(args, "api_key", None))
        items, provider = search(args.query, args.limit, api_key)
        print_json(make_result(True, args.query, provider, items))
    except Exception as e:
        print_json(make_result(False, args.query, "semantic_scholar", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
