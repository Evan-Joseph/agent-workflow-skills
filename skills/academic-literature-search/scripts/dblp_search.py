#!/usr/bin/env python3
"""DBLP Computer Science Bibliography 搜索（免 Key 开放 JSON 接口，含 Crossref 官方开放源透明回退）。

权威检索计算机科学会议（NeurIPS / ICLR / ICML / CVPR / ACL / AAAI / IJCAI 等）与期刊正式出版元数据，
区分主会论文、Workshop 论文与 CoRR (arXiv) 预印本条目。当 DBLP 返回 HTTP 202 反爬验证页时，
绝不绕过或计算挑战，自动回退至 Crossref 官方开放文献 API 并显式标注 provider 来源。
"""
from __future__ import annotations

import html
import re
from typing import Any

from search_utils import build_parser, get_client, make_item, make_result, print_json

DBLP_PUBL_API = "https://dblp.org/search/publ/api"
CROSSREF_WORKS_API = "https://api.crossref.org/works"


def _as_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _clean_dblp_text(val: Any) -> str:
    txt = html.unescape(str(val or "")).strip()
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\s+", " ", txt).strip().rstrip(".")


def _clean_author_name(author_obj: Any) -> str:
    if isinstance(author_obj, dict):
        raw = author_obj.get("text") or author_obj.get("@pid") or ""
    else:
        raw = str(author_obj or "")
    cleaned = _clean_dblp_text(raw)
    return re.sub(r"\s+\d{4}$", "", cleaned).strip()


def hit_to_item(hit: dict[str, Any]) -> dict[str, Any]:
    info = hit.get("info") or {}
    title = _clean_dblp_text(info.get("title"))
    authors_raw = (info.get("authors") or {}).get("author")
    authors = [a for a in (_clean_author_name(x) for x in _as_list(authors_raw)) if a]

    venue_raw = info.get("venue")
    venue = " / ".join(_clean_dblp_text(v) for v in _as_list(venue_raw) if _clean_dblp_text(v)) or None
    year_str = str(info.get("year") or "").strip()
    year = int(year_str) if year_str.isdigit() else None

    doi_raw = str(info.get("doi") or "").strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi_raw, flags=re.I).lower() or None
    ee_list = _as_list(info.get("ee"))
    ee_url = str(ee_list[0]).strip() if ee_list else ""
    dblp_url = str(info.get("url") or "").strip()
    url = ee_url or (f"https://doi.org/{doi}" if doi else dblp_url)

    pub_type = str(info.get("type") or "").strip()
    pages = str(info.get("pages") or "").strip() or None
    volume = str(info.get("volume") or "").strip() or None
    number = str(info.get("number") or "").strip() or None
    dblp_key = str(info.get("key") or "").strip() or None

    is_preprint = bool(
        (venue and venue.lower() in ("corr", "arxiv"))
        or "informal" in pub_type.lower()
        or (dblp_key and dblp_key.lower().startswith("journals/corr/"))
    )
    is_workshop = bool(
        (venue and re.search(r"\b(workshop|workshops|ws|companion|adjunct)\b", venue, re.I))
        or (dblp_key and "workshop" in dblp_key.lower())
    )

    snippet_parts = [p for p in (venue, str(year) if year else None, f"pp. {pages}" if pages else None, pub_type or None) if p]
    return make_item(
        title=title,
        url=url,
        snippet=" | ".join(snippet_parts),
        authors=authors,
        year=year,
        venue=venue,
        pages=pages,
        volume=volume,
        number=number,
        doi=doi,
        dblp_key=dblp_key,
        dblp_url=dblp_url or None,
        work_type=pub_type or None,
        is_preprint=is_preprint,
        is_workshop=is_workshop,
    )


def _crossref_item_to_item(raw: dict[str, Any]) -> dict[str, Any]:
    titles = _as_list(raw.get("title"))
    title = _clean_dblp_text(titles[0] if titles else "")
    authors: list[str] = []
    for au in _as_list(raw.get("author")):
        if not isinstance(au, dict):
            continue
        given = str(au.get("given") or "").strip()
        family = str(au.get("family") or "").strip()
        name = f"{given} {family}".strip() or str(au.get("name") or "").strip()
        if name:
            authors.append(name)

    containers = [_clean_dblp_text(c) for c in _as_list(raw.get("container-title")) if _clean_dblp_text(c)]
    events = (raw.get("event") or {}).get("name") if isinstance(raw.get("event"), dict) else None
    venue = " / ".join(containers) or (_clean_dblp_text(events) if events else None) or (_clean_dblp_text(raw.get("publisher")) or None)

    year: int | None = None
    for date_key in ("published", "published-print", "published-online", "issued", "created"):
        dp = ((raw.get(date_key) or {}).get("date-parts") or [[]])[0]
        if dp and isinstance(dp[0], int):
            year = dp[0]
            break

    doi_raw = str(raw.get("DOI") or "").strip()
    doi = doi_raw.lower() or None
    url = str(raw.get("URL") or (f"https://doi.org/{doi}" if doi else "")).strip()
    pub_type = str(raw.get("type") or "").strip()
    pages = str(raw.get("page") or "").strip() or None
    volume = str(raw.get("volume") or "").strip() or None
    number = str(raw.get("issue") or "").strip() or None

    is_preprint = bool(
        pub_type == "posted-content"
        or (doi and "arxiv" in doi)
        or (venue and venue.lower() in ("corr", "arxiv"))
    )
    is_workshop = bool(venue and re.search(r"\b(workshop|workshops|ws|companion|adjunct)\b", venue, re.I))
    snippet_parts = [p for p in (venue, str(year) if year else None, f"pp. {pages}" if pages else None, pub_type or None) if p]
    return make_item(
        title=title,
        url=url,
        snippet=" | ".join(snippet_parts),
        authors=authors,
        year=year,
        venue=venue,
        pages=pages,
        volume=volume,
        number=number,
        doi=doi,
        dblp_key=None,
        dblp_url=None,
        work_type=pub_type or None,
        is_preprint=is_preprint,
        is_workshop=is_workshop,
    )


def _search_crossref_fallback(
    query: str,
    limit: int,
    exclude_corr: bool,
    year: int | None,
) -> list[dict[str, Any]]:
    rows = min(max(limit * 3 if (exclude_corr or year) else limit * 2, 10), 50)
    headers = {
        "Accept": "application/json",
        "User-Agent": "academic-literature-search/1.1 (Crossref bibliographic fallback)",
    }
    params: dict[str, Any] = {"query.bibliographic": query, "rows": rows}
    if year is not None:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(CROSSREF_WORKS_API, params=params)
        resp.raise_for_status()
        data = resp.json()
    raw_items = ((data.get("message") or {}).get("items")) or []
    items: list[dict[str, Any]] = []
    for raw in _as_list(raw_items):
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        item = _crossref_item_to_item(raw)
        if exclude_corr and item.get("is_preprint"):
            continue
        if year is not None and item.get("year") != year:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items


def search_with_provenance(
    query: str,
    limit: int = 10,
    exclude_corr: bool = False,
    year: int | None = None,
    strict_dblp: bool = False,
) -> tuple[list[dict[str, Any]], str, str | None]:
    """查询 DBLP 出版物 API；若遇 HTTP 202 反爬门禁且未开启 --strict-dblp，则透明回退至 Crossref 开放接口。"""
    fetch_h = min(max(limit * 3 if (exclude_corr or year) else limit, 10), 100)
    params = {"q": query, "format": "json", "h": fetch_h}
    headers = {
        "Accept": "application/json",
        "User-Agent": "academic-literature-search/1.1 (DBLP client)",
    }
    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(DBLP_PUBL_API, params=params)
        resp.raise_for_status()
        ctype = (resp.headers.get("content-type") or "").lower()
        if resp.status_code == 202 or "text/html" in ctype or resp.text.lstrip().startswith("<!doctype"):
            gate_msg = (
                f"DBLP API ({DBLP_PUBL_API}) returned HTTP {resp.status_code} ({ctype or 'html'}) anti-bot challenge page; "
                "stopped without bypassing challenge."
            )
            if strict_dblp:
                raise RuntimeError(f"{gate_msg} Pass without --strict-dblp to allow Crossref fallback, or use openalex_search.py.")
            fallback_items = _search_crossref_fallback(query, limit=limit, exclude_corr=exclude_corr, year=year)
            return (
                fallback_items,
                "crossref (dblp_202_fallback)",
                f"{gate_msg} Served verified bibliographic metadata from Crossref open API.",
            )
        data = resp.json()

    hits_block = (((data.get("result") or {}).get("hits")) or {}).get("hit")
    items: list[dict[str, Any]] = []
    for raw_hit in _as_list(hits_block):
        if not isinstance(raw_hit, dict):
            continue
        item = hit_to_item(raw_hit)
        if exclude_corr and item.get("is_preprint"):
            continue
        if year is not None and item.get("year") != year:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items, "dblp", None


def search(
    query: str,
    limit: int = 10,
    exclude_corr: bool = False,
    year: int | None = None,
) -> list[dict[str, Any]]:
    items, _, _ = search_with_provenance(query, limit=limit, exclude_corr=exclude_corr, year=year, strict_dblp=False)
    return items


def main() -> int:
    parser = build_parser("搜索 DBLP 计算机科学文献库（免 Key 权威核验会议/期刊卷期页码与 Workshop/CoRR 区分）")
    parser.add_argument("--exclude-corr", action="store_true", help="过滤 CoRR / arXiv 预印本，仅保留正式会议或期刊条目")
    parser.add_argument("--year", type=int, default=None, help="按发表年份精确过滤（可选）")
    parser.add_argument("--strict-dblp", action="store_true", help="禁用 DBLP HTTP 202 时的 Crossref 透明回退")
    args = parser.parse_args()

    try:
        items, provider_label, warning = search_with_provenance(
            args.query,
            limit=args.limit,
            exclude_corr=bool(args.exclude_corr),
            year=args.year,
            strict_dblp=bool(args.strict_dblp),
        )
        res = make_result(True, args.query, provider_label, items)
        if warning:
            res["warning"] = warning
        print_json(res)
        return 0
    except Exception as exc:
        print_json(make_result(False, args.query, "dblp", [], str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
