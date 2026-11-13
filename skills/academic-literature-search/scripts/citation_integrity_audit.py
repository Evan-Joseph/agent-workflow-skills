#!/usr/bin/env python3
"""Citation existence and claim-source alignment helper.

Implements a 4-tier bibliographic verification pipeline:
  1. Crossref
  2. OpenAlex (with OPENALEX_API_KEY and predatory hijack DOI sanitization)
  3. ArXiv API (with automatic arXiv ID extraction from 10.48550/arXiv.* or BibTeX eprint)
  4. Semantic Scholar (with 429 retry and graceful fallback to OpenAlex)

Always resolves DOIs via doi.org (including DataCite DOIs like 10.48550/arXiv.*
or 10.5281/zenodo.*) even when Crossref returns 404, parses BibTeX entries passed
to --reference, and checks metadata mismatches & integrity signals (year mismatch,
first-author mismatch, broken DOI, retraction status, generic short title guard).
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from arxiv_search import fetch_by_ids as arxiv_fetch_by_ids, search as arxiv_search
from openalex_search import (
    OPENALEX_API_URL,
    is_predatory_hijack,
    resolve_polite_email,
    sanitize_openalex_work,
    work_to_item as openalex_work_to_item,
)
from search_utils import get_client, get_key, load_config_env, print_json

CROSSREF_BASE = "https://api.crossref.org"
DOI_BASE = "https://doi.org"
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.I)
ARXIV_EXTRACT_RE = re.compile(
    r"(?:10\.48550/arxiv\.|arxiv\s*[:=/]\s*|arxiv\.org/(?:abs|pdf)/)"
    r"([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)
BARE_ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b")
WORD_RE = re.compile(r"[a-z][a-z0-9_-]{1,}|\d+(?:\.\d+)?", re.I)
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

STOPWORDS = {
    "about", "above", "after", "again", "against", "also", "among", "and",
    "are", "as", "because", "been", "before", "being", "between", "both", "but",
    "can", "could", "did", "does", "doing", "due", "each", "from", "had",
    "has", "have", "having", "into", "its", "may", "more", "most", "not",
    "only", "our", "out", "over", "same", "should", "such", "than", "that",
    "the", "their", "them", "then", "there", "these", "this", "those",
    "through", "using", "was", "were", "which", "while", "with", "within",
    "would", "for", "on", "in", "of", "to", "a", "an", "by", "at", "is",
}


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    candidate = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", candidate, flags=re.I)
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.I)
    match = DOI_RE.search(candidate)
    if not match:
        return None
    doi = match.group(1).strip()
    return doi.rstrip(".,;:)]}").lower()


def extract_doi(*values: str | None) -> str | None:
    for value in values:
        doi = normalize_doi(value)
        if doi:
            return doi
    return None


def extract_arxiv_id(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        m = ARXIV_EXTRACT_RE.search(value)
        if m:
            return m.group(1).lower()
    return None


def _clean_Bibtex_val(val: str) -> str:
    val = val.strip()
    if (val.startswith("{") and val.endswith("}")) or (val.startswith('"') and val.endswith('"')):
        val = val[1:-1].strip()
    # 去除 LaTeX 花括号修饰如 {\L}ukasz 或 {Transformer}
    val = re.sub(r"\{\\?[a-zA-Z]+\s*([a-zA-Z])\}", r"\1", val)
    val = val.replace("{", "").replace("}", "")
    return normalize_space(val)


def _extract_first_author_surname(author_str: str | None) -> str | None:
    if not author_str:
        return None
    cleaned = _clean_Bibtex_val(author_str)
    if not cleaned:
        return None
    # 按 BibTeX ' and ' 或分号切分第一作者
    first_author = re.split(r"\s+and\s+|;", cleaned, maxsplit=1, flags=re.I)[0].strip()
    if "," in first_author:
        surname = first_author.split(",", 1)[0].strip()
    else:
        parts = [p for p in first_author.split() if not p.endswith(".")]
        surname = parts[-1] if parts else ""
    surname = re.sub(r"[^a-zA-Z\u4e00-\u9fff'-]", "", surname).strip()
    return surname if len(surname) >= 2 else None


def parse_bibtex_or_reference(reference: str | None) -> dict[str, Any]:
    """解析 BibTeX 条目（@article{...} / @inproceedings{...}）或普通参考文献字符串。"""
    parsed: dict[str, Any] = {
        "is_bibtex": False,
        "title": None,
        "author": None,
        "first_author_surname": None,
        "year": None,
        "doi": None,
        "arxiv_id": None,
    }
    if not reference:
        return parsed

    text = reference.strip()
    if re.search(r"@\w+\s*\{", text):
        parsed["is_bibtex"] = True
        # 提取 key = {value} 或 key = "value" 或 key = 2017
        field_re = re.compile(
            r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|\d+)",
            re.S,
        )
        fields: dict[str, str] = {}
        for m in field_re.finditer(text):
            k = m.group(1).lower()
            v = _clean_Bibtex_val(m.group(2))
            if k not in fields and v:
                fields[k] = v

        if fields.get("title"):
            parsed["title"] = fields["title"]
        if fields.get("author"):
            parsed["author"] = fields["author"]
            parsed["first_author_surname"] = _extract_first_author_surname(fields["author"])
        if fields.get("year") and re.match(r"^(19|20)\d{2}$", fields["year"]):
            parsed["year"] = int(fields["year"])
        if fields.get("doi"):
            parsed["doi"] = normalize_doi(fields["doi"])
        eprint = fields.get("eprint") or fields.get("arxiv") or fields.get("arxivid")
        if eprint:
            m_ax = BARE_ARXIV_RE.search(eprint) or ARXIV_EXTRACT_RE.search(eprint)
            parsed["arxiv_id"] = m_ax.group(1).lower() if m_ax else eprint.lower()
        if not parsed["arxiv_id"]:
            parsed["arxiv_id"] = extract_arxiv_id(fields.get("doi"), fields.get("url"), fields.get("journal"), text)
        if not parsed["doi"] and parsed["arxiv_id"] and re.match(r"^\d{4}\.\d{4,5}$", parsed["arxiv_id"]):
            parsed["doi"] = f"10.48550/arxiv.{parsed['arxiv_id']}"
        return parsed

    # 非 BibTeX 参考文献文本
    parsed["doi"] = normalize_doi(text)
    parsed["arxiv_id"] = extract_arxiv_id(text)
    m_year = re.search(r"\b((?:19|20)\d{2})\b", text)
    if m_year:
        parsed["year"] = int(m_year.group(1))
    # 尝试提取形如 "Vaswani, A. ... (2017)" 的第一作者姓氏
    m_lead_author = re.match(r"^\s*([A-Z][a-zA-Z'-]{1,25})\s*,", text)
    if m_lead_author:
        parsed["first_author_surname"] = m_lead_author.group(1)
    # 尝试提取非 BibTeX 纯文本引文中的论文标题
    if not parsed["title"]:
        m_quoted = re.search(r'["“]([^"”]{8,250})["”]', text)
        m_after_year = re.search(r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)\.\s*([^.?!]{8,250})[.?!]", text)
        if m_quoted:
            parsed["title"] = _clean_Bibtex_val(m_quoted.group(1))
        elif m_after_year:
            parsed["title"] = _clean_Bibtex_val(m_after_year.group(1))
        else:
            segments = [s.strip() for s in re.split(r"\.\s+", text) if len(s.strip()) >= 8]
            if len(segments) >= 2:
                parsed["title"] = _clean_Bibtex_val(segments[1])
    return parsed


def compact_for_similarity(value: str | None) -> str:
    text = normalize_space(value).lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text).strip()


def title_similarity(left: str | None, right: str | None) -> float | None:
    left_norm = compact_for_similarity(left)
    right_norm = compact_for_similarity(right)
    if not left_norm or not right_norm:
        return None
    return round(SequenceMatcher(None, left_norm, right_norm).ratio(), 3)


def is_generic_short_title(title: str | None) -> bool:
    if not title:
        return False
    words = [w.lower() for w in WORD_RE.findall(title) if w.lower() not in STOPWORDS]
    cjk_chars = "".join(CJK_RE.findall(title))
    if cjk_chars:
        return len(cjk_chars) <= 2 and len(words) == 0
    return len(words) <= 2


def date_year(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        date_parts = (message.get(key) or {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
    return None


def author_names(authors: list[dict[str, Any]] | None, limit: int = 10) -> list[str]:
    names = []
    for author in authors or []:
        given = normalize_space(author.get("given"))
        family = normalize_space(author.get("family"))
        literal = normalize_space(author.get("name"))
        name = normalize_space(" ".join(part for part in (given, family) if part)) or literal
        if name:
            names.append(name)
    if len(names) > limit:
        return names[:limit] + [f"... +{len(names) - limit}"]
    return names


def _crossref_is_retracted(message: dict[str, Any]) -> bool:
    title = normalize_space((message.get("title") or [""])[0])
    if re.match(r"^retracted\s*:", title, re.I):
        return True
    for upd in message.get("update-to") or []:
        upd_type = str(upd.get("type") or "").lower()
        if "retract" in upd_type:
            return True
    return False


def crossref_item(message: dict[str, Any], input_title: str | None = None) -> dict[str, Any]:
    title = normalize_space((message.get("title") or [""])[0])
    container = normalize_space((message.get("container-title") or [""])[0])
    doi = normalize_doi(message.get("DOI"))
    cites = message.get("is-referenced-by-count") or 0
    return {
        "title": title,
        "doi": doi,
        "url": message.get("URL") or (f"{DOI_BASE}/{doi}" if doi else None),
        "year": date_year(message),
        "authors": author_names(message.get("author")),
        "venue": container or None,
        "publisher": normalize_space(message.get("publisher")),
        "type": message.get("type"),
        "crossref_score": message.get("score"),
        "is_referenced_by_count": cites,
        "citation_count": cites,
        "is_retracted": _crossref_is_retracted(message),
        "source_provider": "crossref",
        "title_similarity": title_similarity(input_title, title) if input_title else None,
    }


def crossref_headers(mailto: str | None) -> dict[str, str]:
    resolved = resolve_polite_email(mailto)
    ua = (
        f"academic-literature-search/1.0 (mailto:{resolved})"
        if resolved
        else "academic-literature-search/1.0"
    )
    return {
        "Accept": "application/json",
        "User-Agent": ua,
    }


def fetch_crossref_by_doi(doi: str, mailto: str | None) -> tuple[dict[str, Any] | None, str | None]:
    resolved = resolve_polite_email(mailto)
    url = f"{CROSSREF_BASE}/works/{quote(doi, safe='')}"
    params: dict[str, Any] = {}
    if resolved:
        params["mailto"] = resolved
    with get_client(timeout=20, headers=crossref_headers(resolved)) as client:
        resp = client.get(url, params=params)
        if resp.status_code == 404:
            return None, "DOI not found in Crossref"
        resp.raise_for_status()
        data = resp.json()
    return data.get("message") or None, None


def search_crossref(query: str, limit: int, mailto: str | None, title_query: bool = False) -> list[dict[str, Any]]:
    resolved = resolve_polite_email(mailto)
    params: dict[str, Any] = {
        "query.title" if title_query else "query.bibliographic": query,
        "rows": max(1, min(limit * 2, 20)),
    }
    if resolved:
        params["mailto"] = resolved
    with get_client(timeout=25, headers=crossref_headers(resolved)) as client:
        resp = client.get(f"{CROSSREF_BASE}/works", params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("message", {}).get("items", []) or []


def _openalex_request_config(mailto: str | None = None, api_key: str | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    load_config_env()
    resolved_key = get_key("OPENALEX_API_KEY", api_key)
    resolved_mailto = resolve_polite_email(mailto)
    params: dict[str, Any] = {}
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
    return params, headers


def openalex_candidate(work: dict[str, Any], input_title: str | None = None) -> dict[str, Any]:
    item = openalex_work_to_item(work)
    doi = normalize_doi(item.get("doi"))
    title = normalize_space(item.get("title"))
    cites = item.get("citation_count") or 0
    return {
        "title": title,
        "doi": doi,
        "url": item.get("url") or (f"{DOI_BASE}/{doi}" if doi else item.get("openalex_id")),
        "year": item.get("year"),
        "authors": item.get("authors") or [],
        "venue": item.get("venue"),
        "type": item.get("work_type"),
        "citation_count": cites,
        "is_referenced_by_count": cites,
        "is_retracted": bool(work.get("is_retracted")),
        "openalex_id": item.get("openalex_id"),
        "open_access_pdf": item.get("open_access_pdf"),
        "source_provider": "openalex",
        "title_similarity": title_similarity(input_title, title) if input_title else None,
    }


def fetch_openalex_by_doi(
    doi: str,
    input_title: str | None = None,
    mailto: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    params, headers = _openalex_request_config(mailto, api_key)
    url = f"{OPENALEX_API_URL}/https://doi.org/{quote(doi, safe='/')}"
    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(url, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        raw_work = resp.json()
    work = sanitize_openalex_work(raw_work)
    if work is None:
        return None
    return openalex_candidate(work, input_title)


def search_openalex_candidates(
    query: str,
    limit: int,
    input_title: str | None = None,
    mailto: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    params, headers = _openalex_request_config(mailto, api_key)
    params.update({"search": query, "per_page": min(max(limit * 2, 10), 25)})
    with get_client(timeout=20, headers=headers) as client:
        resp = client.get(OPENALEX_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    candidates: list[dict[str, Any]] = []
    filtered_hijacks = 0
    for raw_work in data.get("results") or []:
        if is_predatory_hijack(raw_work.get("doi")):
            filtered_hijacks += 1
        work = sanitize_openalex_work(raw_work)
        if work is None:
            continue
        candidates.append(openalex_candidate(work, input_title or query))
        if len(candidates) >= limit:
            break
    return candidates, filtered_hijacks


def arxiv_item_to_candidate(item: dict[str, Any], input_title: str | None = None) -> dict[str, Any]:
    raw_ax_id = item.get("arxiv_id") or ""
    base_ax_id = re.sub(r"v\d+$", "", raw_ax_id, flags=re.I)
    doi = normalize_doi(item.get("doi")) or (f"10.48550/arxiv.{base_ax_id}" if base_ax_id else None)
    published = item.get("published") or ""
    year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
    title = normalize_space(item.get("title"))
    return {
        "title": title,
        "doi": doi,
        "arxiv_id": raw_ax_id or None,
        "url": item.get("url") or (f"https://arxiv.org/abs/{base_ax_id}" if base_ax_id else None),
        "year": year,
        "authors": item.get("authors") or [],
        "venue": item.get("journal_ref") or "arXiv",
        "type": "preprint",
        "open_access_pdf": item.get("pdf_url"),
        "source_provider": "arxiv",
        "title_similarity": title_similarity(input_title, title) if input_title else None,
    }


def fetch_arxiv_candidates(
    arxiv_id: str | None,
    query: str | None,
    limit: int,
    input_title: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if arxiv_id:
        items = arxiv_fetch_by_ids([arxiv_id], limit=max(1, limit))
    elif query:
        items = arxiv_search(query, limit=min(limit, 5), title_only=bool(input_title))
        if not items and input_title:
            items = arxiv_search(query, limit=min(limit, 5), title_only=False)
    return [arxiv_item_to_candidate(it, input_title or query) for it in items]


def resolve_doi(doi: str) -> dict[str, Any]:
    doi_url = f"{DOI_BASE}/{doi}"
    headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    result = {"url": doi_url, "status_code": None, "final_url": None, "error": None}
    try:
        with get_client(timeout=20, headers=headers) as client:
            try:
                resp = client.head(doi_url)
                if resp.status_code in (405, 403, 404):
                    resp = client.get(doi_url)
            except Exception:
                resp = client.get(doi_url)
        result.update({"status_code": resp.status_code, "final_url": str(resp.url)})
    except Exception as exc:
        result["error"] = str(exc)
    return result


def search_semantic_scholar(
    query: str,
    limit: int,
    api_key: str | None = None,
    input_title: str | None = None,
) -> list[dict[str, Any]]:
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    params = {
        "query": query,
        "limit": max(1, min(limit, 10)),
        "fields": "title,year,venue,authors,externalIds,url,citationCount,abstract,openAccessPdf",
    }
    max_attempts = 2 if api_key else 1
    data: dict[str, Any] = {}
    with get_client(timeout=20, headers=headers) as client:
        for attempt in range(max_attempts):
            resp = client.get(S2_SEARCH_URL, params=params)
            if resp.status_code != 429:
                resp.raise_for_status()
                data = resp.json()
                break
            if attempt == max_attempts - 1:
                raise httpx.HTTPStatusError(
                    "Semantic Scholar 429 (Rate Limited)",
                    request=resp.request,
                    response=resp,
                )
            time.sleep(1.5)

    candidates = []
    for paper in data.get("data", [])[:limit]:
        external_ids = paper.get("externalIds") or {}
        open_access_pdf = paper.get("openAccessPdf") or {}
        cites = paper.get("citationCount") or 0
        candidates.append({
            "title": paper.get("title"),
            "doi": normalize_doi(external_ids.get("DOI")),
            "arxiv_id": external_ids.get("ArXiv"),
            "year": paper.get("year"),
            "authors": [a.get("name") for a in paper.get("authors", []) if a.get("name")],
            "venue": paper.get("venue"),
            "url": paper.get("url"),
            "citation_count": cites,
            "is_referenced_by_count": cites,
            "open_access_pdf": open_access_pdf.get("url"),
            "source_provider": "semantic_scholar",
            "title_similarity": title_similarity(input_title or query, paper.get("title")),
        })
    return candidates


def _author_matches_candidate(first_author_surname: str | None, candidate_authors: list[str] | None) -> bool | None:
    if not first_author_surname:
        return None
    if not candidate_authors:
        return None
    target = first_author_surname.lower()
    for a in candidate_authors:
        if target in (a or "").lower():
            return True
    return False


def evaluate_metadata_and_signals(
    input_title: str | None,
    input_year: int | None,
    input_first_author: str | None,
    input_doi: str | None,
    item: dict[str, Any] | None,
    doi_resolution: dict[str, Any] | None,
    filtered_hijacks: int = 0,
) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    signals: dict[str, Any] = {
        "year_mismatch": False,
        "year_lag_1yr": False,
        "first_author_mismatch": False,
        "broken_doi": False,
        "retracted": False,
        "generic_short_title": False,
        "predatory_hijack_filtered": filtered_hijacks,
    }

    if input_title and not input_doi and not input_first_author and is_generic_short_title(input_title):
        signals["generic_short_title"] = True
        mismatches.append(
            f"generic short title '{input_title}' (<= 2 significant words) without DOI or author; high risk of ambiguous match"
        )

    if item:
        similarity = item.get("title_similarity")
        if input_title and similarity is not None and similarity < 0.82:
            mismatches.append(
                f"title similarity {similarity} is below 0.82; check that the reference points to this work"
            )

        cand_year = item.get("year")
        if input_year and isinstance(cand_year, int):
            diff = abs(input_year - cand_year)
            if diff > 1:
                signals["year_mismatch"] = True
                mismatches.append(
                    f"publication year mismatch: input year {input_year} vs matched work year {cand_year} (diff={diff} years)"
                )
            elif diff == 1:
                signals["year_lag_1yr"] = True

        author_ok = _author_matches_candidate(input_first_author, item.get("authors"))
        if author_ok is False:
            signals["first_author_mismatch"] = True
            mismatches.append(
                f"first-author surname '{input_first_author}' not found in matched work authors {item.get('authors')[:3]}"
            )

        if item.get("is_retracted"):
            signals["retracted"] = True
            mismatches.append("matched work is marked as RETRACTED in bibliographic database")

        if is_predatory_hijack(item.get("doi")) or is_predatory_hijack(item.get("url")):
            mismatches.append(
                f"DOI '{item.get('doi')}' belongs to a known predatory preprint hijack prefix (10.65215 / langtaosha.org.cn)"
            )

    if doi_resolution:
        status_code = doi_resolution.get("status_code")
        err = doi_resolution.get("error")
        if (isinstance(status_code, int) and status_code >= 400) or err:
            signals["broken_doi"] = True
            detail = f"HTTP {status_code}" if status_code else str(err)
            mismatches.append(f"DOI resolution failed for {doi_resolution.get('url')} ({detail})")

    return mismatches, signals


def sort_candidates(
    candidates: list[dict[str, Any]],
    prefer_title: bool,
    input_year: int | None = None,
    input_first_author: str | None = None,
) -> list[dict[str, Any]]:
    def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
        hijack_penalty = 0 if not is_predatory_hijack(item.get("doi")) else -1
        sim = item.get("title_similarity")
        sim_val = sim if sim is not None else -1.0
        # High similarity bucket (treat >= 0.96 as exact-title tie so citation count & author/year win)
        exact_title_bucket = 1 if sim_val >= 0.96 else 0
        author_match = 1 if _author_matches_candidate(input_first_author, item.get("authors")) else 0
        year_match = 0
        if input_year and isinstance(item.get("year"), int):
            if abs(input_year - item["year"]) == 0:
                year_match = 2
            elif abs(input_year - item["year"]) == 1:
                year_match = 1
        cites = item.get("citation_count") or item.get("is_referenced_by_count") or 0
        cites_log = round(math.log10(max(1, cites)), 2)
        return (
            hijack_penalty,
            exact_title_bucket if prefer_title else 0,
            author_match,
            year_match,
            cites_log if exact_title_bucket else round(sim_val, 2),
            round(sim_val, 3),
            cites,
            item.get("crossref_score") or 0,
        )

    return sorted(candidates, key=_rank_key, reverse=True)


def tokenize(text: str) -> set[str]:
    tokens = {m.group(0).lower() for m in WORD_RE.finditer(text)}
    tokens = {token for token in tokens if token not in STOPWORDS and len(token) > 1}
    for segment_match in CJK_RE.finditer(text):
        segment = segment_match.group(0)
        if len(segment) == 1:
            tokens.add(segment)
        else:
            for n in (2, 3):
                for idx in range(0, max(0, len(segment) - n + 1)):
                    tokens.add(segment[idx:idx + n])
    return tokens


def split_passages(text: str) -> list[str]:
    raw_parts = re.split(r"\n\s*\n|(?<=[。！？.!?])\s+", text)
    parts = [normalize_space(part) for part in raw_parts if normalize_space(part)]
    passages = []
    for part in parts:
        words = part.split()
        if len(words) <= 140:
            passages.append(part)
            continue
        for idx in range(0, len(words), 90):
            passages.append(" ".join(words[idx:idx + 120]))
    return passages


def trim_snippet(text: str, max_chars: int = 500) -> str:
    text = normalize_space(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def rank_passages(claim: str, source_text: str, limit: int = 6) -> list[dict[str, Any]]:
    claim_tokens = tokenize(claim)
    if not claim_tokens:
        return []

    ranked = []
    for idx, passage in enumerate(split_passages(source_text), start=1):
        passage_tokens = tokenize(passage)
        if not passage_tokens:
            continue
        overlap = sorted(claim_tokens & passage_tokens)
        if not overlap:
            continue
        coverage = len(overlap) / len(claim_tokens)
        density = len(overlap) / math.sqrt(max(len(passage_tokens), 1))
        score = round((coverage * 0.7) + (density * 0.3), 3)
        ranked.append({
            "passage_index": idx,
            "score": score,
            "claim_token_coverage": round(coverage, 3),
            "matched_terms": overlap[:24],
            "snippet": trim_snippet(passage),
        })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def build_claim_audit(claim: str | None, source_text_path: str | None) -> dict[str, Any]:
    if not claim:
        return {
            "status": "NO_CLAIM_PROVIDED",
            "method": None,
            "note": "Reference metadata can be checked, but claim support needs the exact cited claim.",
            "candidate_passages": [],
        }
    if not source_text_path:
        return {
            "status": "METADATA_ONLY",
            "method": None,
            "note": "No source text was supplied; do not infer claim support from metadata or abstract alone.",
            "candidate_passages": [],
        }

    path = Path(source_text_path).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {
            "status": "SOURCE_TEXT_UNREADABLE",
            "method": None,
            "note": f"Could not read source text: {exc}",
            "candidate_passages": [],
        }

    candidates = rank_passages(claim, text)
    return {
        "status": "CLAIM_REVIEW_NEEDED",
        "method": "lexical_overlap_passage_ranking",
        "note": (
            "Candidate passages are lexical evidence for manual inspection only; "
            "the script does not decide SUPPORTED/PARTIAL/UNSUPPORTED."
        ),
        "source_text": str(path),
        "candidate_passages": candidates,
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    ref_parsed = parse_bibtex_or_reference(args.reference)
    input_doi = extract_doi(args.doi) or ref_parsed.get("doi")
    input_title = normalize_space(args.title) or normalize_space(ref_parsed.get("title"))
    input_year = args.year or ref_parsed.get("year")
    input_first_author = _extract_first_author_surname(args.author) or ref_parsed.get("first_author_surname")
    input_arxiv_id = extract_arxiv_id(args.doi, args.reference) or ref_parsed.get("arxiv_id")
    reference = normalize_space(args.reference)
    query = input_title or (reference if not ref_parsed.get("is_bibtex") else "")

    if not input_doi and not query and not input_arxiv_id:
        return {
            "success": False,
            "provider": "crossref",
            "error": "Provide at least one of --doi, --title, or --reference.",
        }

    result: dict[str, Any] = {
        "success": True,
        "provider": ["crossref", "openalex", "arxiv", "doi.org"],
        "input": {
            "doi": input_doi,
            "title": input_title or None,
            "author": args.author or ref_parsed.get("author"),
            "first_author_surname": input_first_author,
            "year": input_year,
            "arxiv_id": input_arxiv_id,
            "reference": reference or None,
            "is_bibtex": ref_parsed.get("is_bibtex", False),
            "claim": args.claim,
            "source_text": args.source_text,
        },
        "reference_existence": None,
        "metadata": None,
        "metadata_mismatches": [],
        "signals": {},
        "doi_resolution": None,
        "crossref_candidates": [],
        "openalex_candidates": [],
        "arxiv_candidates": [],
        "semantic_scholar_candidates": [],
        "claim_support": None,
        "next_steps": [],
        "errors": [],
    }

    filtered_hijacks = 0
    explicit_hijack_doi = bool(input_doi and is_predatory_hijack(input_doi))

    # --- Tier 1: Crossref ---
    crossref_messages: list[dict[str, Any]] = []
    crossref_error = None
    verified_by_doi = False
    if input_doi:
        try:
            message, error = fetch_crossref_by_doi(input_doi, args.mailto)
            if message:
                crossref_messages = [message]
                verified_by_doi = True
            else:
                crossref_error = error
        except Exception as exc:
            crossref_error = str(exc)

    if query and not crossref_messages:
        try:
            crossref_messages = search_crossref(
                query,
                args.limit,
                args.mailto,
                title_query=bool(input_title),
            )
        except Exception as exc:
            crossref_error = str(exc)

    if crossref_error and not crossref_messages:
        result["errors"].append({"provider": "crossref", "error": crossref_error})

    raw_cr_candidates = [crossref_item(item, input_title or query) for item in crossref_messages]
    crossref_candidates: list[dict[str, Any]] = []
    for cand in raw_cr_candidates:
        if not explicit_hijack_doi and (is_predatory_hijack(cand.get("doi")) or is_predatory_hijack(cand.get("url"))):
            filtered_hijacks += 1
            continue
        crossref_candidates.append(cand)

    crossref_candidates = sort_candidates(
        crossref_candidates,
        prefer_title=bool(input_title or query),
        input_year=input_year,
        input_first_author=input_first_author,
    )
    result["crossref_candidates"] = crossref_candidates[: args.limit]

    # --- Tier 2: OpenAlex ---
    openalex_candidates: list[dict[str, Any]] = []
    if input_doi:
        try:
            oa_by_doi = fetch_openalex_by_doi(
                input_doi,
                input_title=input_title or query,
                mailto=args.mailto,
                api_key=args.openalex_api_key,
            )
            if oa_by_doi:
                openalex_candidates.append(oa_by_doi)
                verified_by_doi = True
        except Exception as exc:
            result["errors"].append({"provider": "openalex", "error": str(exc)})

    if query:
        try:
            oa_search_cands, oa_hijacks = search_openalex_candidates(
                query,
                args.limit,
                input_title=input_title or query,
                mailto=args.mailto,
                api_key=args.openalex_api_key,
            )
            filtered_hijacks += oa_hijacks
            seen_oa = {c.get("openalex_id") or c.get("doi") for c in openalex_candidates}
            for c in oa_search_cands:
                key = c.get("openalex_id") or c.get("doi")
                if key not in seen_oa:
                    openalex_candidates.append(c)
                    seen_oa.add(key)
        except Exception as exc:
            result["errors"].append({"provider": "openalex", "error": str(exc)})

    openalex_candidates = sort_candidates(
        openalex_candidates,
        prefer_title=bool(input_title or query),
        input_year=input_year,
        input_first_author=input_first_author,
    )
    result["openalex_candidates"] = openalex_candidates[: args.limit]

    # Discover arXiv ID from OpenAlex/Crossref candidates if not in input
    if not input_arxiv_id:
        for cand in openalex_candidates + crossref_candidates:
            ax = extract_arxiv_id(cand.get("doi"), cand.get("url"), cand.get("open_access_pdf"))
            if ax:
                input_arxiv_id = ax
                break

    # --- Tier 3: ArXiv API ---
    arxiv_candidates: list[dict[str, Any]] = []
    has_strong_pre_match = any(
        float(c.get("title_similarity") or 0.0) >= 0.85
        and c.get("year_match") is not False
        and c.get("author_match") is not False
        for c in (crossref_candidates + openalex_candidates)
    )
    need_arxiv = bool(input_arxiv_id) or not has_strong_pre_match
    if need_arxiv:
        try:
            arxiv_candidates = fetch_arxiv_candidates(
                input_arxiv_id,
                query,
                args.limit,
                input_title=input_title or query,
            )
            if input_arxiv_id and arxiv_candidates:
                verified_by_doi = True
        except Exception as exc:
            result["errors"].append({"provider": "arxiv", "error": str(exc)})
    arxiv_candidates = sort_candidates(
        arxiv_candidates,
        prefer_title=bool(input_title or query),
        input_year=input_year,
        input_first_author=input_first_author,
    )
    result["arxiv_candidates"] = arxiv_candidates[: args.limit]

    # --- Tier 4: Semantic Scholar (with 429 fallback to OpenAlex) ---
    s2_candidates: list[dict[str, Any]] = []
    if (args.semantic_scholar or (not crossref_candidates and not openalex_candidates and not arxiv_candidates)) and query:
        if "semantic_scholar" not in result["provider"]:
            result["provider"].append("semantic_scholar")
        try:
            s2_candidates = search_semantic_scholar(
                query,
                min(args.limit, 5),
                args.semantic_scholar_api_key or get_key("S2_API_KEY"),
                input_title=input_title or query,
            )
        except Exception as exc:
            result["errors"].append({
                "provider": "semantic_scholar",
                "error": f"{exc} (gracefully handled via OpenAlex tier)",
            })
            if not openalex_candidates:
                try:
                    oa_fallback, _ = search_openalex_candidates(
                        query,
                        min(args.limit, 5),
                        input_title=input_title or query,
                        mailto=args.mailto,
                        api_key=args.openalex_api_key,
                    )
                    s2_candidates = oa_fallback
                except Exception:
                    pass
    result["semantic_scholar_candidates"] = s2_candidates[: args.limit]

    # Combine & select best metadata across all 4 tiers
    all_candidates = sort_candidates(
        crossref_candidates + openalex_candidates + arxiv_candidates + s2_candidates,
        prefer_title=bool(input_title or query),
        input_year=input_year,
        input_first_author=input_first_author,
    )

    if all_candidates:
        best = dict(all_candidates[0])
        # Enrich best metadata with OpenAlex/ArXiv fields (e.g. open_access_pdf, citation_count, retraction)
        for alt in all_candidates[1:]:
            if (alt.get("title_similarity") or 0) >= 0.92 or (best.get("doi") and alt.get("doi") == best.get("doi")):
                if not best.get("open_access_pdf") and alt.get("open_access_pdf"):
                    best["open_access_pdf"] = alt["open_access_pdf"]
                if not best.get("doi") and alt.get("doi"):
                    best["doi"] = alt["doi"]
                if not best.get("arxiv_id") and alt.get("arxiv_id"):
                    best["arxiv_id"] = alt["arxiv_id"]
                if alt.get("is_retracted"):
                    best["is_retracted"] = True
                if (alt.get("citation_count") or 0) > (best.get("citation_count") or 0):
                    best["citation_count"] = alt["citation_count"]
                    best["is_referenced_by_count"] = alt["citation_count"]
        result["metadata"] = best

    # Always resolve DOI when input_doi or discovered best_doi is present
    best_doi = (result["metadata"] or {}).get("doi") or input_doi
    if best_doi:
        result["doi_resolution"] = resolve_doi(best_doi)

    # Determine reference_existence
    if result["metadata"]:
        sim = result["metadata"].get("title_similarity")
        doi_ok = bool(
            result["doi_resolution"]
            and isinstance(result["doi_resolution"].get("status_code"), int)
            and 200 <= result["doi_resolution"]["status_code"] < 400
        )
        if verified_by_doi or (sim is not None and sim >= 0.92 and doi_ok):
            result["reference_existence"] = "VERIFIED"
        else:
            result["reference_existence"] = "CANDIDATE_FOUND"
    else:
        if result["errors"] and not (crossref_candidates or openalex_candidates or arxiv_candidates):
            result["reference_existence"] = "RETRIEVAL_FAILED"
        else:
            result["reference_existence"] = "NOT_FOUND"

    mismatches, signals = evaluate_metadata_and_signals(
        input_title=input_title or None,
        input_year=input_year,
        input_first_author=input_first_author,
        input_doi=input_doi,
        item=result["metadata"],
        doi_resolution=result["doi_resolution"],
        filtered_hijacks=filtered_hijacks,
    )
    result["metadata_mismatches"] = mismatches
    result["signals"] = signals

    result["claim_support"] = build_claim_audit(args.claim, args.source_text)

    if result["reference_existence"] in ("NOT_FOUND", "RETRIEVAL_FAILED"):
        result["next_steps"].append("Verify the citation through publisher, arXiv, PubMed/PMC, OpenAlex, or the venue website.")
    if result["metadata_mismatches"]:
        result["next_steps"].append("Resolve metadata mismatch before using the citation as evidence.")
    if result["claim_support"]["status"] == "METADATA_ONLY":
        result["next_steps"].append("Retrieve full text or a reliable excerpt before judging claim support.")
    if result["claim_support"]["status"] == "CLAIM_REVIEW_NEEDED":
        result["next_steps"].append("Inspect candidate passages and assign SUPPORTED, PARTIAL, AMBIGUOUS, UNSUPPORTED, or CONTRADICTED manually.")

    return result


def as_markdown(result: dict[str, Any]) -> str:
    lines = ["# Citation Integrity Audit", ""]
    if not result.get("success"):
        return "\n".join(lines + [f"Error: {result.get('error')}"])

    metadata = result.get("metadata") or {}
    claim_support = result.get("claim_support") or {}
    lines.extend([
        "## Reference Existence",
        f"- Status: `{result.get('reference_existence')}`",
        f"- Source Tier: `{metadata.get('source_provider') or 'n/a'}`",
        f"- Title: {metadata.get('title') or 'n/a'}",
        f"- DOI: {metadata.get('doi') or 'n/a'}",
        f"- Year: {metadata.get('year') or 'n/a'}",
        f"- Venue: {metadata.get('venue') or 'n/a'}",
        f"- Citations: {metadata.get('citation_count') if metadata.get('citation_count') is not None else 'n/a'}",
        "",
    ])

    if result.get("metadata_mismatches"):
        lines.append("## Metadata Mismatches & Signals")
        for mismatch in result["metadata_mismatches"]:
            lines.append(f"- {mismatch}")
        lines.append("")

    resolver = result.get("doi_resolution") or {}
    if resolver:
        lines.extend([
            "## DOI Resolution",
            f"- DOI URL: {resolver.get('url')}",
            f"- HTTP status: {resolver.get('status_code') or 'n/a'}",
            f"- Final URL: {resolver.get('final_url') or 'n/a'}",
            "",
        ])

    lines.extend([
        "## Claim Support",
        f"- Status: `{claim_support.get('status')}`",
        f"- Method: {claim_support.get('method') or 'n/a'}",
        f"- Note: {claim_support.get('note') or 'n/a'}",
        "",
    ])

    passages = claim_support.get("candidate_passages") or []
    if passages:
        lines.append("## Candidate Passages")
        for passage in passages:
            terms = ", ".join(passage.get("matched_terms") or [])
            lines.extend([
                f"### Passage {passage.get('passage_index')}  score={passage.get('score')}",
                f"- Claim token coverage: {passage.get('claim_token_coverage')}",
                f"- Matched terms: {terms or 'n/a'}",
                "",
                passage.get("snippet") or "",
                "",
            ])

    if result.get("next_steps"):
        lines.append("## Next Steps")
        for step in result["next_steps"]:
            lines.append(f"- {step}")
        lines.append("")

    if result.get("errors"):
        lines.append("## Retrieval Warnings")
        for error in result["errors"]:
            lines.append(f"- {error.get('provider')}: {error.get('error')}")

    return "\n".join(lines).rstrip() + "\n"


def split_bibtex_entries(bib_text: str) -> list[dict[str, str]]:
    """Parse a .bib file into balanced `@type{citekey, ...}` blocks (skipping @comment/@string/@preamble)."""
    entries: list[dict[str, str]] = []
    header_re = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s{}]+)\s*,", re.M)
    pos = 0
    n = len(bib_text)
    while pos < n:
        m = header_re.search(bib_text, pos)
        if not m:
            break
        entry_type = m.group(1).lower()
        citekey = m.group(2).strip()
        brace_open = bib_text.find("{", m.start())
        depth = 0
        i = brace_open
        while i < n:
            ch = bib_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        raw_block = bib_text[m.start() : min(i + 1, n)]
        pos = max(i + 1, m.end())
        if entry_type in ("comment", "string", "preamble"):
            continue
        entries.append({
            "entry_type": entry_type,
            "citekey": citekey,
            "raw_block": raw_block,
        })
    return entries


def _is_preprint_bib_block(entry_type: str, raw_block: str) -> bool:
    low = raw_block.lower()
    if entry_type in ("misc", "unpublished"):
        return True
    if re.search(r"\b(arxiv|corr|10\.48550/arxiv\.|biorxiv|medrxiv|ssrn)\b", low):
        if not re.search(r"\bbooktitle\s*=\s*\{[^}]+\}", low):
            return True
    return False


def _is_formal_published_venue(cand: dict[str, Any]) -> bool:
    venue = str(cand.get("venue") or "").strip()
    doi = str(cand.get("doi") or "").strip().lower()
    if not venue:
        return False
    low_v = venue.lower()
    if any(p in low_v for p in ("arxiv", "corr", "biorxiv", "medrxiv", "research square", "ssrn")):
        return False
    if doi.startswith("10.48550/arxiv."):
        return False
    return True


def _detect_published_upgrade(entry_audit: dict[str, Any], input_title: str | None) -> dict[str, Any] | None:
    """Check if a preprint BibTeX entry has a formal peer-reviewed conference/journal publication."""
    candidates: list[dict[str, Any]] = []
    for key in ("crossref_candidates", "openalex_candidates", "semantic_scholar_candidates"):
        candidates.extend(entry_audit.get(key) or [])
    for cand in candidates:
        sim = cand.get("title_similarity")
        if sim is None and input_title and cand.get("title"):
            sim = title_similarity(input_title, cand.get("title"))
        if (sim or 0.0) >= 0.90 and _is_formal_published_venue(cand) and not is_predatory_hijack(cand.get("doi")):
            return {
                "venue": cand.get("venue"),
                "year": cand.get("year"),
                "doi": cand.get("doi"),
                "source_provider": cand.get("source_provider"),
                "title_similarity": sim,
            }
    if input_title:
        try:
            from dblp_search import search as dblp_search_fn
            dblp_hits = dblp_search_fn(input_title, limit=5, exclude_corr=True)
            for dh in dblp_hits:
                sim = title_similarity(input_title, dh.get("title"))
                if (sim or 0.0) >= 0.90 and dh.get("venue"):
                    return {
                        "venue": dh.get("venue"),
                        "year": dh.get("year"),
                        "doi": dh.get("doi"),
                        "pages": dh.get("pages"),
                        "is_workshop": dh.get("is_workshop"),
                        "source_provider": "dblp",
                        "title_similarity": sim,
                    }
        except Exception:
            pass
    return None


def audit_bib_file(args: argparse.Namespace) -> dict[str, Any]:
    bib_path = Path(args.bib_file).expanduser().resolve()
    if not bib_path.is_file():
        return {"success": False, "mode": "bib_file", "error": f"BibTeX file not found: {bib_path}"}

    bib_text = bib_path.read_text(encoding="utf-8", errors="replace")
    raw_entries = split_bibtex_entries(bib_text)
    if not raw_entries:
        return {"success": False, "mode": "bib_file", "bib_file": str(bib_path), "error": "No BibTeX entries found in file"}

    entry_results: list[dict[str, Any]] = []
    counts = {
        "verified": 0,
        "candidate_found": 0,
        "not_found": 0,
        "retrieval_failed": 0,
        "with_mismatches": 0,
        "arxiv_upgrades_available": 0,
    }

    for item in raw_entries:
        sub_ns = argparse.Namespace(
            doi=None,
            title=None,
            author=None,
            year=None,
            reference=item["raw_block"],
            claim=None,
            source_text=None,
            limit=max(3, min(args.limit, 5)),
            format="json",
            mailto=args.mailto,
            openalex_api_key=args.openalex_api_key,
            semantic_scholar=args.semantic_scholar,
            semantic_scholar_api_key=args.semantic_scholar_api_key,
        )
        single = audit(sub_ns)
        status = single.get("reference_existence") or "NOT_FOUND"
        if status == "VERIFIED":
            counts["verified"] += 1
        elif status == "CANDIDATE_FOUND":
            counts["candidate_found"] += 1
        elif status == "RETRIEVAL_FAILED":
            counts["retrieval_failed"] += 1
        else:
            counts["not_found"] += 1

        mismatches = single.get("metadata_mismatches") or []
        if mismatches:
            counts["with_mismatches"] += 1

        parsed_title = (single.get("input") or {}).get("title")
        upgrade = None
        if _is_preprint_bib_block(item["entry_type"], item["raw_block"]):
            upgrade = _detect_published_upgrade(single, parsed_title)
            if upgrade:
                counts["arxiv_upgrades_available"] += 1

        meta = single.get("metadata") or {}
        entry_results.append({
            "citekey": item["citekey"],
            "entry_type": item["entry_type"],
            "reference_existence": status,
            "input_title": parsed_title,
            "input_year": (single.get("input") or {}).get("year"),
            "input_doi": (single.get("input") or {}).get("doi"),
            "matched_title": meta.get("title"),
            "matched_venue": meta.get("venue"),
            "matched_year": meta.get("year"),
            "matched_doi": meta.get("doi"),
            "source_provider": meta.get("source_provider"),
            "metadata_mismatches": mismatches,
            "arxiv_upgrade_available": upgrade,
        })

    return {
        "success": True,
        "mode": "bib_file",
        "bib_file": str(bib_path),
        "total_entries": len(entry_results),
        "summary": counts,
        "entries": entry_results,
    }


def bib_audit_as_markdown(batch: dict[str, Any]) -> str:
    if not batch.get("success"):
        return f"# BibTeX Batch Integrity Audit\n\nError: {batch.get('error')}\n"
    s = batch.get("summary") or {}
    lines = [
        "# BibTeX Batch Integrity Audit",
        "",
        f"- File: `{batch.get('bib_file')}`",
        f"- Total entries: `{batch.get('total_entries')}`",
        f"- Verified: `{s.get('verified', 0)}` | Candidate Found: `{s.get('candidate_found', 0)}` | Not Found: `{s.get('not_found', 0)}` | Retrieval Failed: `{s.get('retrieval_failed', 0)}`",
        f"- Entries with metadata mismatches: `{s.get('with_mismatches', 0)}`",
        f"- Preprints with formal venue upgrades available: `{s.get('arxiv_upgrades_available', 0)}`",
        "",
        "| Citekey | Type | Status | Matched Venue / Year | DOI | Notes / Upgrades |",
        "|---|---|---|---|---|---|",
    ]
    for e in batch.get("entries") or []:
        notes: list[str] = list(e.get("metadata_mismatches") or [])
        upg = e.get("arxiv_upgrade_available")
        if upg:
            notes.append(f"Upgrade -> {upg.get('venue')} ({upg.get('year')}) {upg.get('doi') or ''}".strip())
        venue_yr = " ".join(str(x) for x in (e.get("matched_venue") or "-", e.get("matched_year") or "") if x).strip()
        note_str = "; ".join(notes).replace("|", "/") if notes else "OK"
        lines.append(
            f"| `{e['citekey']}` | `@{e['entry_type']}` | `{e['reference_existence']}` | {venue_yr} | `{e.get('matched_doi') or '-'}` | {note_str} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify citation metadata across Crossref -> OpenAlex -> ArXiv -> Semantic Scholar (+ DBLP venue upgrade check) and prepare claim-source alignment evidence."
    )
    parser.add_argument("--doi", help="DOI to verify, e.g. 10.1038/nature14236 or 10.48550/arXiv.1706.03762")
    parser.add_argument("--title", help="Cited work title, used for Crossref/OpenAlex/ArXiv/Semantic Scholar search")
    parser.add_argument("--author", help="Expected author name or first-author surname for verification")
    parser.add_argument("--year", type=int, help="Expected publication year for mismatch detection")
    parser.add_argument("--reference", help="Raw reference entry or BibTeX block (@article{...} / @inproceedings{...})")
    parser.add_argument("--bib-file", help="Path to a .bib file for batch verification and arXiv-to-published-venue upgrade audit")
    parser.add_argument("--claim", help="Exact cited claim sentence or paragraph")
    parser.add_argument("--source-text", help="UTF-8 text file extracted from the cited source")
    parser.add_argument("--limit", type=int, default=5, help="Candidate count for metadata search")
    parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format")
    parser.add_argument(
        "--mailto",
        default=resolve_polite_email(),
        help="Email for Crossref/OpenAlex polite pool (reads ACADEMIC_POLITE_EMAIL / CROSSREF_MAILTO / OPENALEX_MAILTO or credentials.json polite_email; defaults to anonymous pool)",
    )
    parser.add_argument("--openalex-api-key", default=os.environ.get("OPENALEX_API_KEY"), help="OpenAlex API key; defaults to OPENALEX_API_KEY")
    parser.add_argument("--semantic-scholar", action="store_true", help="Also query Semantic Scholar candidates")
    parser.add_argument("--semantic-scholar-api-key", help="Semantic Scholar API key; defaults to S2_API_KEY")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.bib_file:
        batch_res = audit_bib_file(args)
        if args.format == "markdown":
            sys.stdout.write(bib_audit_as_markdown(batch_res))
        else:
            print_json(batch_res)
        if not batch_res.get("success"):
            sys.exit(1)
        return
    result = audit(args)
    if args.format == "markdown":
        sys.stdout.write(as_markdown(result))
    else:
        print_json(result)
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
