#!/usr/bin/env python3
"""OpenAlex 学术文献搜索。

OpenAlex 涵盖超过 2.5 亿篇学术文献及完整引用网络，
免费开放，无需 API Key，单日提供 100,000 次请求配额，
无 Cloudflare 阻断或严苛 429 速率限制，作为 Semantic Scholar 的高可用替代与补充。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from search_utils import build_parser, get_client, get_key, load_config_env, make_item, make_result, print_json

OPENALEX_API_URL = "https://api.openalex.org/works"
CREDENTIALS_JSON_PATH = Path.home() / ".config" / "ai-relays" / "credentials.json"


def _load_config_polite_email() -> str:
    """Read optional `polite_email` from ~/.config/ai-relays/credentials.json without hardcoding PII."""
    try:
        if CREDENTIALS_JSON_PATH.is_file():
            data = json.loads(CREDENTIALS_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                direct = str(data.get("polite_email") or "").strip()
                if direct:
                    return direct
                tool_apis = data.get("tool_apis")
                if isinstance(tool_apis, dict):
                    nested = str(
                        tool_apis.get("polite_email")
                        or (tool_apis.get("openalex") or {}).get("polite_email")
                        or ""
                    ).strip()
                    if nested:
                        return nested
    except Exception:
        pass
    return ""


def resolve_polite_email(mailto: str | None = None) -> str:
    """Resolve OpenAlex/Crossref polite-pool email, falling back cleanly to anonymous pool ('')."""
    return (
        (mailto or "").strip()
        or os.environ.get("ACADEMIC_POLITE_EMAIL", "").strip()
        or os.environ.get("OPENALEX_MAILTO", "").strip()
        or os.environ.get("CROSSREF_MAILTO", "").strip()
        or _load_config_polite_email()
    )

HIJACK_DOI_PREFIXES = ("10.65215/",)
HIJACK_DOMAINS = ("langtaosha.org.cn",)
ARXIV_ID_RE = re.compile(r"(?:arxiv[:./])(\d{2})(\d{2})\.(\d{4,5})(?:v\d+)?", re.I)


def is_predatory_hijack(value: str | None) -> bool:
    """检测是否为已知劫持经典论文的掠夺性预印本 DOI/域名（如 10.65215 / langtaosha.org.cn）。"""
    if not value:
        return False
    low = value.lower()
    return any(p in low for p in HIJACK_DOI_PREFIXES) or any(d in low for d in HIJACK_DOMAINS)


def _location_is_hijacked(loc: dict[str, Any] | None) -> bool:
    if not loc or not isinstance(loc, dict):
        return False
    for k in ("doi", "id", "landing_page_url", "pdf_url"):
        if is_predatory_hijack(loc.get(k)):
            return True
    return False


def sanitize_openalex_work(work: dict[str, Any]) -> dict[str, Any] | None:
    """清洗 OpenAlex work 条目中的掠夺性劫持 DOI（10.65215/），优先恢复真实 arXiv/出版商位置与年份；
    若整个条目纯粹由掠夺性 DOI 构成且无合法来源，则返回 None 予以剔除。
    """
    if not work or not isinstance(work, dict):
        return None

    work = dict(work)
    raw_doi = work.get("doi")
    primary_loc = work.get("primary_location") or {}
    best_oa = work.get("best_oa_location") or {}
    locations = work.get("locations") or []

    has_hijack = (
        is_predatory_hijack(raw_doi)
        or _location_is_hijacked(primary_loc)
        or _location_is_hijacked(best_oa)
        or any(_location_is_hijacked(loc) for loc in locations)
    )
    if not has_hijack:
        return work

    clean_locations = [loc for loc in locations if isinstance(loc, dict) and not _location_is_hijacked(loc)]
    if not clean_locations and (is_predatory_hijack(raw_doi) or _location_is_hijacked(primary_loc)):
        # 纯劫持条目，无任何合法来源
        return None

    if is_predatory_hijack(raw_doi):
        clean_doi = next((loc.get("doi") for loc in clean_locations if loc.get("doi")), None)
        work["doi"] = clean_doi

    if _location_is_hijacked(primary_loc) and clean_locations:
        # 优先选择有 source 名称或有合法 doi 的 location
        chosen_primary = next(
            (loc for loc in clean_locations if (loc.get("source") or {}).get("display_name") or loc.get("doi")),
            clean_locations[0],
        )
        work["primary_location"] = chosen_primary

    if _location_is_hijacked(best_oa):
        chosen_oa = next(
            (loc for loc in clean_locations if loc.get("pdf_url") or loc.get("is_oa")),
            {},
        )
        work["best_oa_location"] = chosen_oa

    # 若原年份被 2025+ 劫持预印本污染，尝试从合法 arXiv ID (YYMM.NNNNN) 恢复真实年份
    pub_year = work.get("publication_year")
    for loc in clean_locations:
        for field_val in (loc.get("id"), loc.get("doi"), loc.get("landing_page_url"), loc.get("pdf_url")):
            if not field_val:
                continue
            m = ARXIV_ID_RE.search(str(field_val))
            if m:
                yy, mm = int(m.group(1)), int(m.group(2))
                inferred_year = (2000 + yy) if yy < 90 else (1900 + yy)
                if not pub_year or (pub_year >= 2024 and inferred_year < pub_year):
                    work["publication_year"] = inferred_year
                    if str(work.get("publication_date") or "").startswith(str(pub_year)):
                        work["publication_date"] = f"{inferred_year}-{mm:02d}-01"
                break
        else:
            continue
        break

    return work


def extract_abstract(work: dict[str, Any]) -> str:
    """从 OpenAlex inverted index 还原摘要。"""
    inv_index = work.get("abstract_inverted_index")
    if not inv_index or not isinstance(inv_index, dict):
        return ""
    word_positions: list[tuple[int, str]] = []
    for word, positions in inv_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in word_positions)


def work_to_item(work: dict[str, Any]) -> dict[str, Any]:
    """将清洗后的 OpenAlex work 转换为标准搜索结果项。"""
    title = work.get("title") or ""
    openalex_id = work.get("id") or ""
    doi = work.get("doi")
    primary_loc = work.get("primary_location") or {}
    best_oa = work.get("best_oa_location") or {}
    url = doi or primary_loc.get("landing_page_url") or openalex_id or ""

    authorships = work.get("authorships") or []
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    ]

    abstract = extract_abstract(work)
    source = primary_loc.get("source") or {}
    venue = source.get("display_name")

    oa_pdf = None
    if best_oa.get("pdf_url"):
        oa_pdf = best_oa["pdf_url"]
    elif primary_loc.get("pdf_url"):
        oa_pdf = primary_loc["pdf_url"]

    return make_item(
        title=title,
        url=url,
        snippet=abstract[:500] if abstract else "",
        abstract=abstract or None,
        authors=authors,
        year=work.get("publication_year"),
        publication_date=work.get("publication_date"),
        venue=venue,
        citation_count=work.get("cited_by_count", 0),
        is_open_access=(work.get("open_access") or {}).get("is_oa", False),
        open_access_pdf=oa_pdf,
        doi=doi,
        openalex_id=openalex_id,
        work_type=work.get("type"),
        is_retracted=work.get("is_retracted") or None,
    )


def search(
    query: str,
    limit: int = 10,
    mailto: str | None = None,
    api_key: str | None = None,
    rerank: bool = False,
) -> list[dict[str, Any]]:
    """执行 OpenAlex 文献搜索（可选通过本地 MagPie moark/Qwen3-Reranker-4B 对摘要重排）。"""
    load_config_env()
    resolved_key = get_key("OPENALEX_API_KEY", api_key)
    resolved_mailto = resolve_polite_email(mailto)

    fetch_count = min(max(limit * 3 if rerank else limit * 2, 10), 50)
    params: dict[str, Any] = {
        "search": query,
        "per_page": fetch_count,
    }
    if resolved_mailto:
        params["mailto"] = resolved_mailto
    if resolved_key:
        params["api_key"] = resolved_key

    ua = (
        f"academic-literature-search/1.0 (mailto:{resolved_mailto})"
        if resolved_mailto
        else "academic-literature-search/1.0"
    )
    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
    }

    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(OPENALEX_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items: list[dict[str, Any]] = []
    cap = fetch_count if rerank else limit
    for raw_work in data.get("results", []):
        work = sanitize_openalex_work(raw_work)
        if work is None:
            continue
        items.append(work_to_item(work))
        if len(items) >= cap:
            break

    if rerank and items:
        from rerank_abstracts import rerank_items
        items = rerank_items(query, items, top_n=limit)

    return items[:limit]


def main():
    parser = build_parser("搜索 OpenAlex 学术文献库 (开放免费、高限额、覆盖 2.5 亿篇论文)")
    parser.add_argument(
        "--mailto",
        default=resolve_polite_email(),
        help="联系邮箱（读取 ACADEMIC_POLITE_EMAIL / OPENALEX_MAILTO 或 ~/.config/ai-relays/credentials.json polite_email，未配置时回退匿名公共池）",
    )
    parser.add_argument("--api-key", default=os.environ.get("OPENALEX_API_KEY"), help="OpenAlex API Key（可选，默认读取 OPENALEX_API_KEY）")
    parser.add_argument("--rerank", action="store_true", help="使用本机 MagPie :3425/v1/rerank (moark/Qwen3-Reranker-4B) 免费重排候选摘要")
    args = parser.parse_args()

    try:
        items = search(
            args.query,
            args.limit,
            mailto=getattr(args, "mailto", None),
            api_key=getattr(args, "api_key", None),
            rerank=bool(getattr(args, "rerank", False)),
        )
        print_json(make_result(True, args.query, "openalex", items))
    except Exception as e:
        print_json(make_result(False, args.query, "openalex", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
