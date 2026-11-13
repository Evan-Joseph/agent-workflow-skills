#!/usr/bin/env python3
"""Read-Only Cloudflare Production Endpoint Health & 24h Free-Tier Quota Auditor (cf_health_and_quota.py).

Features:
  1. Probes HTTP status & latency of configured production Pages / Workers endpoints
     (detecting HTTP 522 timeouts, HTTP 403 Error 1014 CNAME Cross-User Banned, 5xx errors).
  2. Optionally queries Cloudflare GraphQL Analytics API (`https://api.cloudflare.com/client/v4/graphql`)
     for the past 24 hours of Workers requests & Durable Objects active duration against the
     Cloudflare Free Plan daily limits (`100,000` Worker requests/day; `101,562,500,000` us =
     `28.21 DO-hours/day` for Durable Objects).
  3. Reads `CLOUDFLARE_API_TOKEN` or Wrangler's local OAuth config (`oauth_token` in
     `~/Library/Preferences/.wrangler/config/default.toml` or `~/.wrangler/config/default.toml`)
     strictly read-only in memory — NEVER prints or logs tokens. Degrades gracefully to
     endpoint-only report if token is absent or lacks `analytics:read` scope.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CF_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
CF_ACCOUNTS_URL = "https://api.cloudflare.com/client/v4/accounts?per_page=5"

# Free Plan Daily Ceilings
FREE_WORKERS_REQ_LIMIT = 100_000
FREE_DO_DURATION_US_LIMIT = 101_562_500_000  # 101,562.5 sec ~= 28.21 DO-hours/day

DEFAULT_PRODUCTION_ENDPOINTS: tuple[tuple[str, str, str], ...] = tuple(
    (f'endpoint-{i+1}', 'custom', u.strip())
    for i, u in enumerate(os.environ.get('CF_PROBE_URLS', '').split(','))
    if u.strip()
)

WRANGLER_CONFIG_CANDIDATES = (
    Path.home() / "Library" / "Preferences" / ".wrangler" / "config" / "default.toml",
    Path.home() / ".wrangler" / "config" / "default.toml",
    Path.home() / ".config" / ".wrangler" / "config" / "default.toml",
)


def _build_opener() -> urllib.request.OpenerDirector:
    proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
    )
    ctx = ssl.create_default_context()
    handlers: list[Any] = [urllib.request.HTTPSHandler(context=ctx)]
    if proxy:
        handlers.insert(0, urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _load_cf_token_readonly() -> tuple[str, str]:
    """Return `(token, source_label)` without ever exposing secret characters."""
    env_tok = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if env_tok:
        return env_tok, "env:CLOUDFLARE_API_TOKEN"

    token_re = re.compile(r'^\s*oauth_token\s*=\s*"([^"]+)"', re.M)
    exp_re = re.compile(r'^\s*expiration_time\s*=\s*"([^"]+)"', re.M)
    for cfg in WRANGLER_CONFIG_CANDIDATES:
        if not cfg.is_file():
            continue
        try:
            txt = cfg.read_text(encoding="utf-8", errors="replace")
            m = token_re.search(txt)
            if m and m.group(1).strip():
                m_exp = exp_re.search(txt)
                exp_note = f" (expires {m_exp.group(1)})" if m_exp else ""
                return m.group(1).strip(), f"wrangler_oauth:{cfg.name}{exp_note}"
        except OSError:
            continue
    return "", "none"


def probe_endpoint(opener: urllib.request.OpenerDirector, name: str, kind: str, url: str, timeout: float = 10.0) -> dict[str, Any]:
    t0 = time.monotonic()
    headers = {
        "User-Agent": "cf-health-and-quota-probe/1.0",
        "Accept": "text/html,application/json,*/*",
    }
    status_code: int | None = None
    final_url = url
    body_head = ""
    err_msg: str | None = None

    methods = ("OPTIONS", "GET") if kind == "worker-api" else ("HEAD", "GET")
    for method in methods:
        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with opener.open(req, timeout=timeout) as resp:
                status_code = resp.getcode()
                final_url = resp.geturl()
                if method == "GET":
                    body_head = resp.read(1024).decode("utf-8", errors="replace")
                break
        except urllib.error.HTTPError as he:
            status_code = he.code
            final_url = he.geturl() or url
            try:
                body_head = he.read(1024).decode("utf-8", errors="replace")
            except Exception:
                body_head = ""
            # Some Workers reject HEAD/OPTIONS with 405/404 while GET or /health returns 200/401/426 (WebSocket upgrade)
            if method in ("HEAD", "OPTIONS") and status_code in (400, 403, 404, 405, 426):
                continue
            break
        except Exception as exc:
            err_msg = str(exc)
            break

    latency_ms = int(round((time.monotonic() - t0) * 1000))
    cname_1014 = "error 1014" in body_head.lower() or "cname cross-user banned" in body_head.lower()
    cf_unrouted = "error code: 1042" in body_head.lower() or "there is nothing here yet" in body_head.lower()
    # Note: DO WebSocket relay workers (`worker-do`) and route-scoped API workers (`worker-api`)
    # return 200/204 on OPTIONS or JSON 401/403/404/426 on bare root GET when healthy
    if cname_1014 or cf_unrouted or status_code == 522 or (status_code is not None and status_code >= 500) or status_code is None:
        healthy = False
    elif kind in ("worker-do", "worker-api") and status_code in (200, 204, 401, 403, 404, 426):
        healthy = True
    else:
        healthy = status_code is not None and 200 <= status_code < 400

    return {
        "name": name,
        "kind": kind,
        "url": url,
        "status_code": status_code,
        "healthy": healthy,
        "cname_1014_error": cname_1014,
        "latency_ms": latency_ms,
        "final_url": final_url if final_url != url else None,
        "error": err_msg,
    }


def _resolve_account_id(opener: urllib.request.OpenerDirector, token: str, explicit_account_id: str | None) -> str | None:
    if explicit_account_id:
        return explicit_account_id.strip()
    env_acc = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if env_acc:
        return env_acc
    req = urllib.request.Request(
        CF_ACCOUNTS_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with opener.open(req, timeout=10.0) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        res_list = body.get("result") or []
        if res_list and isinstance(res_list[0], dict):
            return str(res_list[0].get("id") or "").strip() or None
    except Exception:
        pass
    return None


def query_24h_quota_graphql(
    opener: urllib.request.OpenerDirector,
    token: str,
    account_id: str | None,
) -> dict[str, Any]:
    acc_id = _resolve_account_id(opener, token, account_id)
    if not acc_id:
        return {
            "available": False,
            "reason": "Could not resolve Cloudflare account_id (pass --account-id or set CLOUDFLARE_ACCOUNT_ID; or Wrangler OAuth token expired).",
        }

    now_utc = dt.datetime.now(dt.timezone.utc)
    since_utc = now_utc - dt.timedelta(hours=24)
    start_iso = since_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    gql_query = """
    query Quota24h($accountTag: string!, $since: Time!, $until: Time!) {
      viewer {
        accounts(filter: { accountTag: $accountTag }) {
          workersInvocationsAdaptive(limit: 1000, filter: { datetime_geq: $since, datetime_leq: $until }) {
            sum { requests errors subrequests }
          }
          durableObjectsInvocationsAdaptiveGroups(limit: 1000, filter: { datetime_geq: $since, datetime_leq: $until }) {
            sum { requests }
          }
          durableObjectsPeriodicGroups(limit: 1000, filter: { datetime_geq: $since, datetime_leq: $until }) {
            sum { activeTime }
          }
        }
      }
    }
    """
    payload = json.dumps({
        "query": gql_query,
        "variables": {"accountTag": acc_id, "since": start_iso, "until": end_iso},
    }).encode("utf-8")

    req = urllib.request.Request(
        CF_GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with opener.open(req, timeout=15.0) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as he:
        return {
            "available": False,
            "reason": f"Cloudflare GraphQL returned HTTP {he.code} (token may be expired or lack analytics:read scope; re-run `wrangler login` or use --endpoints-only).",
        }
    except Exception as exc:
        return {"available": False, "reason": f"GraphQL request failed: {exc}"}

    errors = body.get("errors") or []
    accounts = (((body.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    if not accounts:
        msg = "; ".join(str(e.get("message") or e) for e in errors[:3]) if errors else "empty accounts response"
        return {
            "available": False,
            "reason": f"GraphQL analytics unavailable ({msg}). Token may lack analytics:read scope.",
        }

    acc_data = accounts[0] or {}
    worker_reqs = sum(int((row.get("sum") or {}).get("requests") or 0) for row in (acc_data.get("workersInvocationsAdaptive") or []))
    worker_errs = sum(int((row.get("sum") or {}).get("errors") or 0) for row in (acc_data.get("workersInvocationsAdaptive") or []))
    do_reqs = sum(int((row.get("sum") or {}).get("requests") or 0) for row in (acc_data.get("durableObjectsInvocationsAdaptiveGroups") or []))
    do_active_us = sum(int((row.get("sum") or {}).get("activeTime") or 0) for row in (acc_data.get("durableObjectsPeriodicGroups") or []))
    do_hours = do_active_us / 3_600_000_000.0

    return {
        "available": True,
        "window_utc": {"since": start_iso, "until": end_iso},
        "workers_24h": {
            "requests": worker_reqs,
            "errors": worker_errs,
            "free_daily_limit": FREE_WORKERS_REQ_LIMIT,
            "quota_used_pct": round((worker_reqs / FREE_WORKERS_REQ_LIMIT) * 100.0, 2),
        },
        "durable_objects_24h": {
            "requests": do_reqs,
            "active_duration_us": do_active_us,
            "active_do_hours": round(do_hours, 4),
            "free_daily_limit_do_hours": 28.21,
            "quota_used_pct": round((do_active_us / FREE_DO_DURATION_US_LIMIT) * 100.0, 2),
        },
        "partial_graphql_warnings": [str(e.get("message") or e) for e in errors[:3]] if errors else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Cloudflare production endpoint HTTP health & 24h Workers/Durable Objects free-tier quota probe."
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Custom endpoint URL(s) to probe instead of the default production asset list (repeatable)",
    )
    parser.add_argument(
        "--endpoints-only",
        action="store_true",
        help="Only probe HTTP status of production endpoints; skip Cloudflare GraphQL 24h quota telemetry",
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="Optional Cloudflare Account ID for GraphQL analytics (auto-resolved from API if omitted)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-endpoint HTTP timeout in seconds (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON report")
    args = parser.parse_args()

    opener = _build_opener()
    targets: list[tuple[str, str, str]] = (
        [(f"custom-{i+1}", "custom", u) for i, u in enumerate(args.url)]
        if args.url
        else list(DEFAULT_PRODUCTION_ENDPOINTS)
    )

    endpoint_results = [
        probe_endpoint(opener, name, kind, url, timeout=args.timeout)
        for name, kind, url in targets
    ]
    unhealthy = [r for r in endpoint_results if not r["healthy"]]

    quota_report: dict[str, Any]
    if args.endpoints_only:
        quota_report = {"available": False, "skipped": True, "reason": "--endpoints-only requested"}
    else:
        token, tok_src = _load_cf_token_readonly()
        if not token:
            quota_report = {
                "available": False,
                "auth_source": "none",
                "reason": "No CLOUDFLARE_API_TOKEN or local Wrangler OAuth config found; ran endpoint health checks only.",
            }
        else:
            quota_report = {"auth_source": tok_src, **query_24h_quota_graphql(opener, token, args.account_id)}

    overall_ok = len(unhealthy) == 0
    report = {
        "ok": overall_ok,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "endpoints_total": len(endpoint_results),
        "endpoints_healthy": len(endpoint_results) - len(unhealthy),
        "endpoints": endpoint_results,
        "quota_24h": quota_report,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Cloudflare Health & 24h Quota Probe ({'OK' if overall_ok else 'DEGRADED'})")
        print(f"- Endpoints healthy: {report['endpoints_healthy']}/{report['endpoints_total']}")
        for ep in endpoint_results:
            flag = "OK" if ep["healthy"] else "FAIL"
            extra = " [CNAME-1014]" if ep.get("cname_1014_error") else (f" [{ep['error']}]" if ep.get("error") else "")
            print(f"  - [{flag}] {ep['name']} ({ep['kind']}): HTTP {ep['status_code']} ({ep['latency_ms']} ms) -> {ep['url']}{extra}")
        if quota_report.get("available"):
            w = quota_report["workers_24h"]
            d = quota_report["durable_objects_24h"]
            print(f"- Workers 24h: {w['requests']:,} / {w['free_daily_limit']:,} req ({w['quota_used_pct']}%) | errors={w['errors']}")
            print(f"- Durable Objects 24h: {d['active_do_hours']} / {d['free_daily_limit_do_hours']} DO-h ({d['quota_used_pct']}%) | req={d['requests']:,}")
        else:
            print(f"- Quota 24h telemetry: skipped/unavailable ({quota_report.get('reason')})")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
