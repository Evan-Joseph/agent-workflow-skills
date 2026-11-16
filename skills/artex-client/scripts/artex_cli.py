#!/usr/bin/env python3
"""Managed zero-dependency CLI for local ARTEX (http://<LOOPBACK_HOST>:8787).

Reads credentials from $ARTEX_STATE_DIR (default $HOME/.local/state/artex)
or local ARTEX runtime state, caches short-lived JWTs in a 0600 file, uses direct
loopback connections (ProxyHandler({})), and NEVER prints tokens, keys, or passwords
to stdout, stderr, or argv.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = os.environ.get("ARTEX_BASE_URL", "http://" + os.environ.get("ARTEX_HOST", "localhost") + ":" + os.environ.get("ARTEX_PORT", "8787"))
DEFAULT_STATE_DIR = Path("~/.local/state/artex").expanduser()
DEFAULT_LIBEXEC_DIR = Path("~/.local/libexec/artex").expanduser()
JWT_TTL_SECONDS = 7 * 24 * 3600


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * ((4 - len(seg) % 4) % 4)
    return base64.urlsafe_b64decode((seg + pad).encode("ascii"))


def _jwt_is_fresh(token: str, min_remaining_sec: int = 300) -> bool:
    parts = token.strip().split(".")
    if len(parts) != 3:
        return False
    try:
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception:
        return False
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return float(exp) > (time.time() + min_remaining_sec)
    return True


def _mint_hs256_jwt(secret_key: bytes, subject: str = "ARTEX") -> str:
    now = int(time.time())
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    claims = _b64url_encode(
        json.dumps({"sub": subject, "iat": now, "exp": now + JWT_TTL_SECONDS}, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header}.{claims}".encode("ascii")
    sig = _b64url_encode(hmac.new(secret_key, signing_input, hashlib.sha256).digest())
    return f"{header}.{claims}.{sig}"


def _write_0600_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _opener_for_url(base_url: str) -> urllib.request.OpenerDirector:
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _http_json(
    base_url: str,
    method: str,
    api_path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 25.0,
) -> tuple[int, Any]:
    url = f"{base_url.rstrip('/')}{api_path}"
    headers = {"Accept": "application/json", "User-Agent": "artex-managed-cli/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    opener = _opener_for_url(base_url)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            pass
        try:
            parsed = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            parsed = {"error": raw[:400] or str(exc.reason)}
        return exc.code, parsed


def _load_admin_password(state_dir: Path) -> tuple[str, str]:
    username = os.environ.get("ARTEX_ADMIN_USER", "ARTEX").strip() or "ARTEX"
    env_pw = os.environ.get("ARTEX_ADMIN_PASS", "").strip()
    if env_pw:
        return username, env_pw

    cred_json = state_dir / "credentials.json"
    if cred_json.is_file():
        try:
            obj = json.loads(cred_json.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                u = str(obj.get("username") or username).strip()
                pw = str(obj.get("password") or obj.get("admin_password") or "").strip()
                if pw:
                    return u, pw
        except Exception:
            pass

    for pw_file in (state_dir / "admin.pass", state_dir / ".admin_pass"):
        if pw_file.is_file():
            try:
                pw = pw_file.read_text(encoding="utf-8").strip()
                if pw:
                    return username, pw
            except Exception:
                pass
    return username, ""


def _resolve_jwt(base_url: str, state_dir: Path, *, force_refresh: bool = False) -> tuple[str, str]:
    """Return (jwt_token, auth_source_label) without ever exposing secret values."""
    env_tok = os.environ.get("ARTEX_TOKEN", "").strip()
    if env_tok and not force_refresh and _jwt_is_fresh(env_tok):
        return env_tok, "env:ARTEX_TOKEN"

    cache_path = state_dir / "cli_jwt_cache.json"
    if not force_refresh and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            tok = str((cached or {}).get("token") or "").strip()
            if tok and _jwt_is_fresh(tok) and cached.get("base_url") == base_url.rstrip("/"):
                return tok, "cache:0600"
        except Exception:
            pass

    username, password = _load_admin_password(state_dir)
    if password:
        code, resp = _http_json(
            base_url,
            "POST",
            "/api/auth/login",
            body={"username": username, "password": password},
            timeout=15.0,
        )
        tok = str((resp or {}).get("token") or "").strip() if isinstance(resp, dict) else ""
        if code == 200 and tok:
            try:
                _write_0600_json(
                    cache_path,
                    {"base_url": base_url.rstrip("/"), "updated_at": int(time.time()), "source": "login", "token": tok},
                )
            except OSError:
                pass
            return tok, "api:/api/auth/login"

    for key_candidate in (
        DEFAULT_LIBEXEC_DIR / "jwt.key",
        state_dir / "jwt.key",
        state_dir / "data" / "jwt.key",
    ):
        if key_candidate.is_file():
            try:
                raw_key = key_candidate.read_text(encoding="utf-8").strip()
                if len(raw_key) >= 32:
                    tok = _mint_hs256_jwt(raw_key.encode("utf-8"), subject=username)
                    try:
                        _write_0600_json(
                            cache_path,
                            {
                                "base_url": base_url.rstrip("/"),
                                "updated_at": int(time.time()),
                                "source": "local_jwt_key",
                                "token": tok,
                            },
                        )
                    except OSError:
                        pass
                    return tok, f"jwt_key:{key_candidate.parent.name}/{key_candidate.name}"
            except OSError:
                continue

    raise RuntimeError(
        f"No valid ARTEX credentials found. Set ARTEX_ADMIN_PASS, create 0600 {state_dir}/credentials.json, "
        f"or ensure local jwt.key exists."
    )


def _authed_request(
    base_url: str,
    state_dir: Path,
    method: str,
    api_path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 25.0,
) -> tuple[int, Any, str]:
    token, source = _resolve_jwt(base_url, state_dir, force_refresh=False)
    code, data = _http_json(base_url, method, api_path, token=token, body=body, timeout=timeout)
    if code == 401:
        token, source = _resolve_jwt(base_url, state_dir, force_refresh=True)
        code, data = _http_json(base_url, method, api_path, token=token, body=body, timeout=timeout)
    return code, data, source


def cmd_status(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    state_dir = Path(args.state_dir).expanduser()
    try:
        h_code, health = _http_json(base, "GET", "/api/health", timeout=6.0)
    except urllib.error.URLError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reachable": False,
                    "base_url": base,
                    "state_dir": str(state_dir),
                    "error": f"ARTEX service unreachable ({exc.reason})",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if args.strict else 0

    version: Any = {}
    auth_ok = False
    auth_source = "none"
    assets_counts: Any = {}
    tasks_count: int | None = None
    try:
        t_code, tasks_resp, auth_source = _authed_request(base, state_dir, "GET", "/api/tasks", timeout=10.0)
        auth_ok = t_code == 200
        if isinstance(tasks_resp, list):
            tasks_count = len(tasks_resp)
        elif isinstance(tasks_resp, dict) and isinstance(tasks_resp.get("tasks"), list):
            tasks_count = len(tasks_resp["tasks"])
        v_code, v_resp, _ = _authed_request(base, state_dir, "GET", "/api/version", timeout=6.0)
        if v_code == 200:
            version = v_resp
        a_code, a_resp, _ = _authed_request(base, state_dir, "GET", "/api/assets/counts", timeout=10.0)
        if a_code == 200:
            assets_counts = a_resp
    except Exception as exc:
        auth_source = f"error:{type(exc).__name__}"

    out = {
        "ok": h_code == 200 and auth_ok,
        "reachable": h_code == 200,
        "base_url": base,
        "state_dir": str(state_dir),
        "auth_authenticated": auth_ok,
        "auth_source": auth_source,
        "health": health,
        "version": version,
        "tasks_count": tasks_count,
        "assets_counts": assets_counts,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


def cmd_scope_sync(args: argparse.Namespace) -> int:
    if args.from_json:
        payload = json.loads(Path(args.from_json).expanduser().read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit("--from-json must contain a JSON object")
    else:
        if not (args.company or args.roots or args.subdomains or args.endpoints):
            raise SystemExit("Provide --from-json or at least one of --company / --root / --subdomain / --endpoint")
        payload = {
            "company": args.company,
            "roots": args.roots,
            "subdomains": args.subdomains,
            "endpoints": args.endpoints,
        }

    api_path = f"/api/tasks/{urllib.parse.quote(args.task_id)}/scope" if args.task_id else "/api/assets"
    if args.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": api_path, "payload": payload}, ensure_ascii=False, indent=2))
        return 0

    code, data, _ = _authed_request(args.base_url, Path(args.state_dir).expanduser(), "POST", api_path, body=payload)
    print(json.dumps({"ok": 200 <= code < 300, "status_code": code, "data": data}, ensure_ascii=False, indent=2))
    return 0 if 200 <= code < 300 else 1


def cmd_task_create(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "name": args.name,
        "target": args.target,
        "description": args.description,
    }
    if args.goals:
        payload["goals"] = args.goals
    if args.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/api/tasks", "payload": payload}, ensure_ascii=False, indent=2))
        return 0

    code, data, _ = _authed_request(args.base_url, Path(args.state_dir).expanduser(), "POST", "/api/tasks", body=payload)
    print(json.dumps({"ok": 200 <= code < 300, "status_code": code, "data": data}, ensure_ascii=False, indent=2))
    return 0 if 200 <= code < 300 else 1


def cmd_task_ctl(args: argparse.Namespace) -> int:
    base = args.base_url
    state_dir = Path(args.state_dir).expanduser()
    if args.list_tasks or not args.task_id:
        code, data, _ = _authed_request(base, state_dir, "GET", "/api/tasks")
        print(json.dumps({"ok": code == 200, "status_code": code, "data": data}, ensure_ascii=False, indent=2))
        return 0 if code == 200 else 1

    tid = urllib.parse.quote(args.task_id)
    if not args.action:
        code, data, _ = _authed_request(base, state_dir, "GET", f"/api/tasks/{tid}")
        print(json.dumps({"ok": code == 200, "status_code": code, "data": data}, ensure_ascii=False, indent=2))
        return 0 if code == 200 else 1

    code, data, _ = _authed_request(base, state_dir, "POST", f"/api/tasks/{tid}/control", body={"action": args.action})
    print(
        json.dumps(
            {"ok": 200 <= code < 300, "status_code": code, "task_id": args.task_id, "action": args.action, "data": data},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if 200 <= code < 300 else 1


def cmd_findings(args: argparse.Namespace) -> int:
    base = args.base_url
    state_dir = Path(args.state_dir).expanduser()
    if args.stats:
        code, data, _ = _authed_request(base, state_dir, "GET", "/api/exploration/findings/stats")
        print(json.dumps({"ok": code == 200, "status_code": code, "stats": data}, ensure_ascii=False, indent=2))
        return 0 if code == 200 else 1

    if args.finding_id:
        fid = urllib.parse.quote(args.finding_id)
        code, data, _ = _authed_request(base, state_dir, "GET", f"/api/exploration/findings/{fid}")
        print(json.dumps({"ok": code == 200, "status_code": code, "finding": data}, ensure_ascii=False, indent=2))
        return 0 if code == 200 else 1

    qs: dict[str, str] = {}
    if args.task_id:
        qs["task_id"] = args.task_id
    if args.severity:
        qs["severity"] = args.severity
    if args.limit:
        qs["limit"] = str(args.limit)
    suffix = f"?{urllib.parse.urlencode(qs)}" if qs else ""
    code, data, _ = _authed_request(base, state_dir, "GET", f"/api/exploration/findings{suffix}")
    if code == 404:
        code, data, _ = _authed_request(base, state_dir, "GET", f"/api/findings{suffix}")

    items: list[Any] | None = None
    if isinstance(data, list):
        items = data[: args.limit] if args.limit else data
    elif isinstance(data, dict) and isinstance(data.get("findings"), list):
        items = data["findings"][: args.limit] if args.limit else data["findings"]
        data = {**data, "findings": items}

    print(
        json.dumps(
            {
                "ok": code == 200,
                "status_code": code,
                "verification_gate": "references/finding-verification-gate.md",
                "count": len(items) if items is not None else None,
                "data": data,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if code == 200 else 1


def build_parser() -> argparse.ArgumentParser:
    default_base = os.environ.get("ARTEX_BASE_URL", DEFAULT_BASE_URL)
    default_state = os.environ.get("ARTEX_STATE_DIR", str(DEFAULT_STATE_DIR))

    p = argparse.ArgumentParser(
        description="Zero-dependency managed CLI for local ARTEX (:8787) with 0600 JWT caching and zero token leakage."
    )
    p.add_argument("--base-url", default=default_base, help=f"ARTEX base URL (default: {DEFAULT_BASE_URL})")
    p.add_argument("--state-dir", default=default_state, help=f"ARTEX state directory (default: {DEFAULT_STATE_DIR})")

    sub = p.add_subparsers(dest="command", required=True)

    p_st = sub.add_parser("status", help="Check ARTEX service health, version, auth status, task count, and asset counts")
    p_st.add_argument("--strict", action="store_true", help="Exit nonzero if ARTEX daemon is currently stopped")
    p_st.set_defaults(func=cmd_status)

    p_sc = sub.add_parser("scope-sync", help="Sync authorized asset scope to ARTEX asset graph or a specific task")
    p_sc.add_argument("--company", default="", help="Target company or program name")
    p_sc.add_argument("--root", dest="roots", action="append", default=[], help="Root domain (repeatable)")
    p_sc.add_argument("--subdomain", dest="subdomains", action="append", default=[], help="Subdomain (repeatable)")
    p_sc.add_argument("--endpoint", dest="endpoints", action="append", default=[], help="Endpoint URL (repeatable)")
    p_sc.add_argument("--task-id", default="", help="Optional task ID to bind scope directly (/api/tasks/<id>/scope)")
    p_sc.add_argument("--from-json", default="", help="Load scope payload from JSON file")
    p_sc.add_argument("--dry-run", action="store_true", help="Print sanitized scope payload without sending")
    p_sc.set_defaults(func=cmd_scope_sync)

    p_tc = sub.add_parser("task-create", help="Create a new authorized security evaluation task")
    p_tc.add_argument("--name", required=True, help="Task name")
    p_tc.add_argument("--target", required=True, help="Authorized primary target")
    p_tc.add_argument("--description", default="", help="Authorization scope & evaluation notes")
    p_tc.add_argument("--goal", dest="goals", action="append", default=[], help="Optional initial goal (repeatable)")
    p_tc.add_argument("--dry-run", action="store_true", help="Validate payload locally without creating task")
    p_tc.set_defaults(func=cmd_task_create)

    p_ctl = sub.add_parser("task-ctl", help="List tasks, inspect task details, or pause/resume/cancel a task")
    p_ctl.add_argument("task_id", nargs="?", default="", help="Target task ID (omit or pass --list to list tasks)")
    p_ctl.add_argument("--list", dest="list_tasks", action="store_true", help="List all active tasks")
    p_ctl.add_argument("--action", choices=("pause", "resume", "cancel", "stop"), help="Lifecycle control action")
    p_ctl.set_defaults(func=cmd_task_ctl)

    p_fd = sub.add_parser("findings", help="Read security findings or finding statistics")
    p_fd.add_argument("--id", dest="finding_id", default="", help="Inspect a single finding by ID")
    p_fd.add_argument("--task-id", default="", help="Filter findings by task ID")
    p_fd.add_argument("--severity", default="", help="Filter by severity (critical/high/medium/low)")
    p_fd.add_argument("--limit", type=int, default=25, help="Max findings to return (default: 25)")
    p_fd.add_argument("--stats", action="store_true", help="Fetch aggregated finding statistics")
    p_fd.set_defaults(func=cmd_findings)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except urllib.error.URLError as exc:
        print(json.dumps({"ok": False, "error": f"Connection failed: {exc.reason}"}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
