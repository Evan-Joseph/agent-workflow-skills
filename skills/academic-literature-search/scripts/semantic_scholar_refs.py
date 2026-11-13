#!/usr/bin/env python3
"""Semantic Scholar 引用追溯：查询论文的参考文献（backward）和被引论文（forward）。"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Any
from urllib.parse import quote

import httpx

from openalex_search import OPENALEX_API_URL, sanitize_openalex_work, work_to_item
from search_utils import get_client, get_key, load_config_env, make_item, print_json

API_BASE = "https://api.semanticscholar.org/graph/v1/paper"

DIRECTION_ALIASES = {
    "references": "references",
    "backward": "references",
    "citations": "citations",
    "forward": "citations",
}

# paper-level fields（嵌套在 citedPaper/citingPaper 下）
# 注意: tldr 在 nested 请求中容易触发 rate limit，不请求
PAPER_FIELDS = [
    "title", "abstract", "year", "venue", "publicationDate",
    "authors", "citationCount", "influentialCitationCount",
    "isOpenAccess", "openAccessPdf", "externalIds", "fieldsOfStudy",
]

# edge-level fields（引用关系本身的属性）
EDGE_FIELDS = ["contexts", "intents"]


def normalize_direction(value: str | None) -> str:
    if not value:
        raise ValueError("必须指定查询方向：references/backward 或 citations/forward")
    norm = DIRECTION_ALIASES.get(value.strip().lower())
    if not norm:
        raise ValueError(f"不支持的查询方向 '{value}'，可选值：references, backward, citations, forward")
    return norm


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


def resolve_paper_id(identifier: str) -> str:
    """将各种论文标识符转为 Semantic Scholar 可接受的格式。

    支持:
      - Semantic Scholar paper ID (40-char hex)
      - DOI: 10.xxxx/... → DOI:10.xxxx/...
      - ArXiv ID: 2301.07041 → ARXIV:2301.07041
      - PubMed ID: PMID:12345678
      - URL: https://www.semanticscholar.org/paper/... → 提取 ID
    """
    identifier = identifier.strip()

    # S2 URL
    if "semanticscholar.org/paper/" in identifier:
        # URL 末尾的 40-char hex
        parts = identifier.rstrip("/").split("/")
        return parts[-1]

    # ArXiv DataCite DOI: 10.48550/arXiv.1706.03762 -> ARXIV:1706.03762
    m_arxiv_doi = re.search(r"10\.48550/arxiv\.([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", identifier, re.I)
    if m_arxiv_doi:
        return f"ARXIV:{m_arxiv_doi.group(1)}"

    # DOI
    if identifier.startswith("10."):
        return f"DOI:{identifier}"
    if identifier.lower().startswith("doi:"):
        return identifier

    # ArXiv
    if identifier.lower().startswith("arxiv:"):
        return identifier.upper()
    # 形如 2301.07041 或 2301.07041v2
    if "." in identifier and identifier.replace(".", "").replace("v", "").isdigit():
        return f"ARXIV:{identifier}"

    # PMID
    if identifier.lower().startswith("pmid:"):
        return identifier.upper()

    # 假设是 S2 paper ID
    return identifier


def _openalex_params_and_headers() -> tuple[dict[str, Any], dict[str, str]]:
    load_config_env()
    params: dict[str, Any] = {}
    oa_key = get_key("OPENALEX_API_KEY")
    mailto = os.environ.get("OPENALEX_MAILTO") or os.environ.get("CROSSREF_MAILTO")
    if oa_key:
        params["api_key"] = oa_key
    if mailto:
        params["mailto"] = mailto
    headers = {
        "User-Agent": f"academic-literature-search/1.0 (mailto:{mailto or 'agent-research@local.agents'})",
        "Accept": "application/json",
    }
    return params, headers


def resolve_openalex_work(identifier: str, client: httpx.Client, base_params: dict[str, Any]) -> dict[str, Any]:
    """将 DOI / ArXiv ID / PMID / OpenAlex ID / 标题 解析为 OpenAlex work 对象。"""
    raw = identifier.strip()

    # 1. OpenAlex W-ID
    m_oa = re.search(r"\b(W\d{4,})\b", raw, re.I)
    if m_oa:
        wid = m_oa.group(1).upper()
        resp = client.get(f"{OPENALEX_API_URL}/{wid}", params=base_params)
        if resp.status_code == 200:
            return sanitize_openalex_work(resp.json()) or resp.json()

    # 2. DOI (含 10.48550/arXiv.*)
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", raw, flags=re.I).strip()
    if doi.startswith("10."):
        resp = client.get(f"{OPENALEX_API_URL}/https://doi.org/{quote(doi, safe='/')}", params=base_params)
        if resp.status_code == 200:
            return sanitize_openalex_work(resp.json()) or resp.json()

    # 3. ArXiv ID -> 10.48550/arxiv.{id}
    arxiv_raw = re.sub(r"^arxiv:", "", raw, flags=re.I).strip()
    m_ax = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?$", arxiv_raw)
    if m_ax:
        ax_id = m_ax.group(1)
        resp = client.get(f"{OPENALEX_API_URL}/https://doi.org/10.48550/arxiv.{ax_id}", params=base_params)
        if resp.status_code == 200:
            return sanitize_openalex_work(resp.json()) or resp.json()

    # 4. PMID
    if raw.lower().startswith("pmid:"):
        pmid = raw.split(":", 1)[1].strip()
        resp = client.get(f"{OPENALEX_API_URL}/pmid:{pmid}", params=base_params)
        if resp.status_code == 200:
            return sanitize_openalex_work(resp.json()) or resp.json()

    # 5. 搜索回退
    resp = client.get(OPENALEX_API_URL, params={**base_params, "search": raw, "per_page": 5})
    resp.raise_for_status()
    results = resp.json().get("results") or []
    for cand in results:
        cleaned = sanitize_openalex_work(cand)
        if cleaned is not None:
            return cleaned
    if results:
        return results[0]
    raise ValueError(f"OpenAlex 未找到与 '{identifier}' 匹配的论文")


def fetch_openalex_refs_fallback(
    paper_id: str,
    direction: str,
    limit: int,
    min_citations: int,
    year_min: int | None,
    year_max: int | None,
) -> dict[str, Any]:
    """当 Semantic Scholar 遇到 429 或不可用时，使用 OpenAlex 引用图谱执行前向/后向追溯。"""
    base_params, headers = _openalex_params_and_headers()
    with get_client(timeout=25, headers=headers) as client:
        source_work = resolve_openalex_work(paper_id, client, base_params)
        oa_id_url = source_work.get("id") or ""
        short_wid = oa_id_url.rstrip("/").split("/")[-1]
        if not short_wid.startswith("W"):
            raise ValueError(f"无法提取有效的 OpenAlex Work ID: {oa_id_url}")

        raw_works: list[dict[str, Any]] = []
        total_available = 0

        if direction == "citations":
            filters = [f"cites:{short_wid}"]
            if min_citations > 0:
                filters.append(f"cited_by_count:>{min_citations - 1}")
            if year_min and year_max:
                filters.append(f"publication_year:{year_min}-{year_max}")
            elif year_min:
                filters.append(f"publication_year:>{year_min - 1}")
            elif year_max:
                filters.append(f"publication_year:<{year_max + 1}")

            params = {
                **base_params,
                "filter": ",".join(filters),
                "sort": "cited_by_count:desc",
                "per_page": min(max(limit * 2, 25), 100),
            }
            resp = client.get(OPENALEX_API_URL, params=params)
            resp.raise_for_status()
            body = resp.json()
            raw_works = body.get("results") or []
            total_available = (body.get("meta") or {}).get("count", len(raw_works))
        else:
            ref_urls = source_work.get("referenced_works") or []
            ref_ids = [r.rstrip("/").split("/")[-1] for r in ref_urls if r]
            total_available = len(ref_ids)
            for idx in range(0, min(len(ref_ids), 100), 50):
                batch = ref_ids[idx:idx + 50]
                params = {
                    **base_params,
                    "filter": f"openalex_id:{'|'.join(batch)}",
                    "per_page": len(batch),
                }
                resp = client.get(OPENALEX_API_URL, params=params)
                resp.raise_for_status()
                raw_works.extend(resp.json().get("results") or [])

    items: list[dict[str, Any]] = []
    for raw_w in raw_works:
        w = sanitize_openalex_work(raw_w)
        if w is None:
            continue
        year = w.get("publication_year")
        cites = w.get("cited_by_count") or 0
        if cites < min_citations:
            continue
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue
        items.append(work_to_item(w))

    items.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    items = items[:limit]

    return {
        "success": True,
        "paper_id": short_wid,
        "direction": direction,
        "provider": "openalex_fallback",
        "items": items,
        "total_available": total_available,
        "returned": len(items),
        "source_paper": {
            "title": source_work.get("title"),
            "year": source_work.get("publication_year"),
            "citation_count": source_work.get("cited_by_count"),
            "openalex_id": oa_id_url,
            "doi": source_work.get("doi"),
        },
        "error": None,
    }


def fetch_refs(
    paper_id: str,
    direction: str,
    limit: int,
    min_citations: int,
    year_min: int | None,
    year_max: int | None,
    api_key: str | None = None,
) -> dict:
    """获取论文的 references 或 citations，遇 S2 429 或异常时自动回退 OpenAlex。"""
    direction = normalize_direction(direction)
    resolved = resolve_paper_id(paper_id)
    endpoint = f"{API_BASE}/{resolved}/{direction}"

    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    paper_key_prefix = "citedPaper" if direction == "references" else "citingPaper"
    prefixed_fields = [f"{paper_key_prefix}.{f}" for f in PAPER_FIELDS]
    all_fields = ",".join(EDGE_FIELDS + prefixed_fields)

    params = {
        "fields": all_fields,
        "limit": 1000,
    }

    try:
        with get_client(timeout=20, headers=headers) as client:
            data = semantic_scholar_get(client, endpoint, params, api_key)
    except (httpx.HTTPStatusError, httpx.HTTPError) as err:
        sys.stderr.write(f"[semantic_scholar_refs] Upstream unavailable ({err}), falling back to OpenAlex citation graph...\n")
        return fetch_openalex_refs_fallback(
            paper_id=paper_id,
            direction=direction,
            limit=limit,
            min_citations=min_citations,
            year_min=year_min,
            year_max=year_max,
        )

    # 获取论文本体信息（用于输出上下文）
    paper_resp = None
    with get_client(timeout=15, headers=headers) as client:
        try:
            r = client.get(f"{API_BASE}/{resolved}", params={"fields": "title,year,citationCount"})
            r.raise_for_status()
            paper_resp = r.json()
        except Exception:
            pass

    # direction=references 时结构是 {"data": [{"citedPaper": {...}, "contexts": [...], "intents": [...]}]}
    # direction=citations 时结构是 {"data": [{"citingPaper": {...}, "contexts": [...], "intents": [...]}]}
    paper_key = "citedPaper" if direction == "references" else "citingPaper"

    items = []
    for entry in data.get("data", []):
        paper = entry.get(paper_key, {})
        if not paper or not paper.get("title"):
            continue

        year = paper.get("year")
        citation_count = paper.get("citationCount") or 0

        # 过滤
        if citation_count < min_citations:
            continue
        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue

        authors = [a.get("name", "") for a in paper.get("authors", [])]
        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        s2_id = paper.get("paperId", "")

        url = f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else ""

        abstract = paper.get("abstract") or ""
        snippet = abstract

        open_access_pdf = None
        if paper.get("openAccessPdf"):
            open_access_pdf = paper["openAccessPdf"].get("url")

        # contexts: 引用该论文时的上下文句子（仅 citations 方向有意义）
        contexts = entry.get("contexts") or []
        intents = entry.get("intents") or []

        item = make_item(
            title=paper.get("title", ""),
            url=url,
            snippet=snippet,
            authors=authors,
            year=year,
            venue=paper.get("venue") or None,
            publication_date=paper.get("publicationDate"),
            citation_count=citation_count,
            influential_citation_count=paper.get("influentialCitationCount"),
            is_open_access=paper.get("isOpenAccess"),
            open_access_pdf=open_access_pdf,
            fields_of_study=paper.get("fieldsOfStudy") or None,
            doi=doi,
            arxiv_id=arxiv_id,
            paper_id=s2_id,
            citation_contexts=contexts[:3] if contexts else None,  # 最多 3 条上下文
            citation_intents=intents if intents else None,
        )
        items.append(item)

    # 按引用数排序，取 top-N
    items.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    items = items[:limit]

    result = {
        "success": True,
        "paper_id": resolved,
        "direction": direction,
        "provider": "semantic_scholar",
        "items": items,
        "total_available": len(data.get("data", [])),
        "returned": len(items),
        "error": None,
    }
    if paper_resp:
        result["source_paper"] = {
            "title": paper_resp.get("title"),
            "year": paper_resp.get("year"),
            "citation_count": paper_resp.get("citationCount"),
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="查询论文的参考文献（backward/references）或被引论文（forward/citations）"
    )
    parser.add_argument(
        "paper_id",
        help="论文标识符：S2 ID、DOI（如 10.1234/...）、ArXiv ID（如 2301.07041）、PMID（如 PMID:12345678）",
    )
    parser.add_argument(
        "direction_pos",
        nargs="?",
        choices=["references", "citations", "backward", "forward"],
        help="位置参数：references/backward（参考文献）或 citations/forward（被引论文）",
    )
    parser.add_argument(
        "--direction", "-d",
        dest="direction_opt",
        choices=["references", "citations", "backward", "forward"],
        help="选项参数：references/backward（参考文献）或 citations/forward（被引论文）",
    )
    parser.add_argument("--limit", "-n", type=int, default=20, help="返回结果数量（默认 20）")
    parser.add_argument("--min-citations", type=int, default=0, help="最低引用数过滤（默认 0）")
    parser.add_argument("--year-min", type=int, default=None, help="最早年份过滤")
    parser.add_argument("--year-max", type=int, default=None, help="最晚年份过滤")
    parser.add_argument("--api-key", help="Semantic Scholar API Key（可选；默认读取 S2_API_KEY）")
    args = parser.parse_args()

    raw_dir = args.direction_opt or args.direction_pos
    if not raw_dir:
        parser.error("请提供查询方向（位置参数 references/citations 或 --direction forward/backward）")

    try:
        norm_dir = normalize_direction(raw_dir)
        result = fetch_refs(
            args.paper_id,
            norm_dir,
            args.limit,
            args.min_citations,
            args.year_min,
            args.year_max,
            getattr(args, "api_key", None) or os.environ.get("S2_API_KEY"),
        )
        print_json(result)
    except Exception as e:
        print_json({
            "success": False,
            "paper_id": args.paper_id,
            "direction": raw_dir,
            "provider": "semantic_scholar",
            "items": [],
            "error": str(e),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
