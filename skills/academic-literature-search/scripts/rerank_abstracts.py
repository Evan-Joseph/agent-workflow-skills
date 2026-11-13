#!/usr/bin/env python3
"""Local MagPie (:3425) academic abstract & candidate reranker.

Calls `POST ${OPENAI_COMPAT_BASE_URL}/rerank` (`model="moark/Qwen3-Reranker-4B"`,
free serverless rerank route on MagPie) to re-score candidate papers returned by
`openalex_search.py`, `arxiv_search.py`, `semantic_scholar_search.py`, or
`pubmed_search.py`.

Reads credentials from `MAGPIE_API_KEY` env or `~/.agents/config/magpie-ops-probe.json`
without ever printing secrets, and uses `trust_env=False` on loopback so local
Clash proxy variables never intercept `${OPENAI_COMPAT_HOST}`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_MAGPIE_BASE = os.environ.get("OPENAI_COMPAT_BASE_URL", "http://" + os.environ.get("OPENAI_COMPAT_HOST", "localhost") + ":" + os.environ.get("OPENAI_COMPAT_PORT", "3425") + "/v1")
DEFAULT_RERANK_MODEL = "moark/Qwen3-Reranker-4B"
MAGPIE_PROBE_PATH = Path("~/.agents/config/openai-probe.json").expanduser()


def _load_magpie_auth() -> tuple[str, str, str]:
    probe: dict[str, str] = {}
    if MAGPIE_PROBE_PATH.is_file():
        try:
            raw = json.loads(MAGPIE_PROBE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                probe = {k: str(v).strip() for k, v in raw.items() if isinstance(v, str) and v.strip()}
        except Exception:
            pass

    base_url = (
        os.environ.get("MAGPIE_BASE_URL")
        or probe.get("base_url")
        or DEFAULT_MAGPIE_BASE
    ).rstrip("/")
    api_key = (os.environ.get("MAGPIE_API_KEY") or probe.get("api_key") or "").strip()
    user_agent = probe.get("user_agent") or "magpie-academic-rerank/1.0"
    if not api_key:
        raise RuntimeError(
            "Missing MAGPIE_API_KEY and ~/.agents/config/magpie-ops-probe.json api_key"
        )
    rerank_url = f"{base_url}/rerank" if base_url.endswith("/v1") else f"{base_url}/v1/rerank"
    return rerank_url, api_key, user_agent


def _item_to_doc_text(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    abstract = str(item.get("abstract") or item.get("snippet") or "").strip()
    venue = str(item.get("venue") or "").strip()
    year = item.get("year")
    meta = " | ".join(str(x) for x in (venue, year) if x)
    parts = [p for p in (title, meta, abstract) if p]
    return "\n".join(parts)[:4000] or "(empty candidate)"


def rerank_items(
    query: str,
    items: list[dict[str, Any]],
    top_n: int | None = None,
    model: str = DEFAULT_RERANK_MODEL,
    timeout: float = 25.0,
) -> list[dict[str, Any]]:
    """Rerank standard academic search `items` against `query` via MagPie `/v1/rerank`."""
    if not items or not query.strip():
        return list(items)

    rerank_url, api_key, user_agent = _load_magpie_auth()
    documents = [_item_to_doc_text(it) for it in items]
    limit = min(len(documents), max(1, top_n)) if top_n else len(documents)

    payload: dict[str, Any] = {
        "model": model,
        "query": query.strip(),
        "documents": documents,
        "top_n": limit,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
        "X-Magpie-Session": "academic-literature-rerank",
    }
    is_loopback = any(h in rerank_url for h in ("127.0.0.1", "localhost", "[::1]"))
    with httpx.Client(timeout=timeout, trust_env=not is_loopback) as client:
        resp = client.post(rerank_url, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()

    ranked_rows = body.get("results") or body.get("data") or []
    reranked: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    for row in ranked_rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        score = row.get("relevance_score")
        if isinstance(idx, int) and 0 <= idx < len(items) and idx not in seen_indices:
            enriched = dict(items[idx])
            if isinstance(score, (int, float)):
                enriched["rerank_score"] = round(float(score), 6)
            enriched["rerank_model"] = model
            reranked.append(enriched)
            seen_indices.add(idx)

    if not reranked:
        return list(items[:limit])
    return reranked[:limit]


def run_self_test(model: str = DEFAULT_RERANK_MODEL) -> int:
    sample_items = [
        {
            "title": "Deep Reinforcement Learning for Quadrupedal Locomotion in Rough Terrain",
            "year": 2024,
            "venue": "ICRA",
            "abstract": "Policy gradient methods for legged robot locomotion over uneven rocks.",
        },
        {
            "title": "Equivariant Message Passing Neural Networks for 3D Molecular Property Prediction",
            "year": 2024,
            "venue": "NeurIPS",
            "abstract": "SE(3)-equivariant graph neural networks improve quantum chemical energy and QSAR property prediction.",
        },
        {
            "title": "Compiler Register Allocation via Graph Coloring Heuristics",
            "year": 2021,
            "venue": "PLDI",
            "abstract": "Chaitin-Briggs register allocation for optimizing ahead-of-time native code generation.",
        },
    ]
    query = "3D graph neural network for molecular property and QSAR prediction"
    ranked = rerank_items(query, sample_items, top_n=3, model=model)
    assert len(ranked) == 3, f"Expected 3 ranked items, got {len(ranked)}"
    assert "Molecular Property" in ranked[0]["title"], f"Unexpected top-1 title: {ranked[0]['title']}"
    assert ranked[0]["rerank_score"] > ranked[-1]["rerank_score"], "Top-1 score must exceed last score"
    print(
        json.dumps(
            {
                "ok": True,
                "self_test": "passed",
                "model": model,
                "top1_title": ranked[0]["title"],
                "top1_score": ranked[0]["rerank_score"],
                "bottom_score": ranked[-1]["rerank_score"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rerank candidate papers/abstracts via local MagPie (:3425/v1/rerank, moark/Qwen3-Reranker-4B)."
    )
    parser.add_argument("--query", "-q", default="", help="Query string (defaults to input JSON's 'query' field)")
    parser.add_argument("--input", "-i", default="", help="Input search JSON file (reads stdin if omitted and --doc not set)")
    parser.add_argument("--doc", action="append", default=[], help="Inline candidate text (repeatable)")
    parser.add_argument("--top-n", "-n", type=int, default=0, help="Keep top N results (0 = keep all)")
    parser.add_argument("--model", default=DEFAULT_RERANK_MODEL, help=f"Rerank model (default: {DEFAULT_RERANK_MODEL})")
    parser.add_argument("--self-test", action="store_true", help="Run live self-test against ${OPENAI_COMPAT_HOST}/v1/rerank")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test(model=args.model)

    envelope: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    if args.doc:
        items = [{"title": f"doc-{i+1}", "snippet": text} for i, text in enumerate(args.doc)]
    else:
        raw_text = (
            Path(args.input).expanduser().read_text(encoding="utf-8")
            if args.input
            else sys.stdin.read()
        )
        if not raw_text.strip():
            parser.error("Provide --input <search.json>, pipe search JSON via stdin, or pass --doc / --self-test")
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            envelope = dict(parsed)
            items = list(parsed.get("items") or [])
        elif isinstance(parsed, list):
            items = list(parsed)
        else:
            raise ValueError("Input JSON must be a search result object {'items': [...]} or a list of item dicts")

    query = args.query.strip() or (str(envelope.get("query") or "").strip() if envelope else "")
    if not query:
        parser.error("--query is required when input JSON does not carry a 'query' field")

    ranked = rerank_items(query, items, top_n=(args.top_n or None), model=args.model)
    out_obj: dict[str, Any] = (
        {**envelope, "query": query, "reranked": True, "rerank_model": args.model, "items": ranked}
        if envelope is not None
        else {"success": True, "query": query, "provider": "magpie-rerank", "rerank_model": args.model, "items": ranked}
    )
    json.dump(out_obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
