#!/usr/bin/env python3
"""Small Grsai native generation helper.

Reads GRSAI_API_KEY env first, then ~/.config/grsai/grsai.env (GRSAI_API_KEY),
then OPENAI_API_KEY env/config fallback so ambient gateway OPENAI_API_KEY never
overrides a saved Grsai key. Does not print credentials.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


DEFAULT_BASE_URL = "https://grsai.dakka.com.cn"
CONFIG_FILE = Path.home() / ".config" / "grsai" / "grsai.env"
TIMEOUT = 600
MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504, 524}


def load_config_file(path: Path = CONFIG_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    config: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key in {"GRSAI_API_KEY", "GRSAI_BASE_URL", "OPENAI_API_KEY"}:
            config[key] = value
    return config


def write_config_file(key: str | None = None, base_url: str | None = None, path: Path = CONFIG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_config_file(path)
    if key is not None:
        existing["GRSAI_API_KEY"] = key.strip()
    if base_url is not None:
        existing["GRSAI_BASE_URL"] = base_url.strip().rstrip("/")
    lines = [
        "# Private local config for Grsai. Do not commit or paste this file.",
        "# Used by ~/.agents/skills/image-generation/scripts/grsai_generate.py",
    ]
    for env_key in ("GRSAI_BASE_URL", "GRSAI_API_KEY"):
        if existing.get(env_key):
            lines.append(f"{env_key}={existing[env_key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def api_key() -> str:
    config = load_config_file()
    key = (
        os.getenv("GRSAI_API_KEY")
        or config.get("GRSAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or config.get("OPENAI_API_KEY")
        or ""
    )
    if not key:
        raise SystemExit(f"Missing GRSAI_API_KEY or OPENAI_API_KEY. Save one in {CONFIG_FILE} or export it.")
    return key


def default_base_url() -> str:
    config = load_config_file()
    return os.getenv("GRSAI_BASE_URL") or config.get("GRSAI_BASE_URL") or DEFAULT_BASE_URL


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    }


def image_arg(value: str) -> str:
    if value.startswith(("http://", "https://", "data:")):
        return value
    path = Path(value).expanduser()
    if not path.exists():
        raise SystemExit(f"Reference image not found: {value}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def extract_urls(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    urls: list[str] = []
    results = payload.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
    if payload.get("url") and isinstance(payload.get("url"), str):
        urls.append(payload["url"])
    data = payload.get("data")
    if isinstance(data, dict):
        urls.extend(extract_urls(data))
    return list(dict.fromkeys(urls))


def resolve_quality(model: str, quality: str) -> str:
    if quality:
        return quality
    m = (model or "").strip().lower()
    if "sunburst" in m:
        return "max"
    if m.startswith("gpt-image-2"):
        return "high"
    return ""


def _unwrap_envelope(obj: dict[str, Any]) -> dict[str, Any]:
    code = obj.get("code")
    if code not in (0, "0", None):
        raise SystemExit(f"Grsai API error (code={code}): {obj.get('msg') or obj.get('error') or obj}")
    cur = dict(obj)
    while isinstance(cur.get("data"), dict):
        inner = cur.pop("data")
        merged = dict(cur)
        merged.update(inner)
        cur = merged
    return cur


def _parse_json_or_sse(text: str, method: str, url: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise SystemExit(f"{method} {url} returned empty response")
    try:
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise SystemExit(f"{method} {url} returned non-object JSON: {str(parsed)[:500]}")
        return _unwrap_envelope(parsed)
    except json.JSONDecodeError:
        pass

    last_obj: dict[str, Any] | None = None
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload_str = line[5:].strip()
        if not payload_str or payload_str == "[DONE]":
            continue
        try:
            obj = json.loads(payload_str)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            unwrapped = _unwrap_envelope(obj)
            last_obj = unwrapped
            if extract_urls(unwrapped) or str(unwrapped.get("status") or "").lower() in {"succeeded", "failed", "violation"}:
                return unwrapped
    if last_obj is not None:
        return last_obj
    raise SystemExit(f"{method} {url} returned non-JSON/SSE: {stripped[:500]}")


def request_json(method: str, url: str, max_retries: int = MAX_RETRIES, **kwargs: Any) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, headers=headers(), timeout=TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"{method} {url} request failed after {max_retries} retries: {exc}") from exc

        if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code >= 400:
            raise SystemExit(f"{method} {url} failed: {resp.status_code} {resp.text[:500]}")
        return _parse_json_or_sse(resp.text, method, url)
    raise SystemExit(f"{method} {url} failed after {max_retries} retries: {last_exc}")


def poll(base_url: str, task_id: str, interval: float, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/api/result"
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        data = request_json("GET", url, params={"id": task_id})
        last = data
        status = str(data.get("status") or "").lower()
        progress = data.get("progress")
        print(f"task={task_id} status={status} progress={progress}", file=sys.stderr)
        if status in {"succeeded", "failed", "violation"} or extract_urls(data):
            return data
        time.sleep(interval)
    raise SystemExit(f"Timed out waiting for task {task_id}; last={json.dumps(last, ensure_ascii=False)[:500]}")


def download(url: str, out_dir: Path, index: int, prefix: str = "grsai-result", max_retries: int = MAX_RETRIES) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".png"
    safe_prefix = Path(prefix).name or "grsai-result"
    out = out_dir / f"{safe_prefix}-{index:02d}{suffix}"
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
                if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                out_dir.mkdir(parents=True, exist_ok=True)
                with out.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            fh.write(chunk)
            return out
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"Download {url} failed after {max_retries} retries: {exc}") from exc
    raise SystemExit(f"Download {url} failed: {last_exc}")


def cmd_generate(args: argparse.Namespace) -> None:
    base = args.base_url.rstrip("/")
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "images": [image_arg(x) for x in args.image],
        "aspectRatio": args.aspect_ratio,
        "replyType": args.reply_type,
    }
    if args.image_size:
        payload["imageSize"] = args.image_size
    effective_quality = resolve_quality(args.model, getattr(args, "quality", "") or "")
    if effective_quality:
        payload["quality"] = effective_quality

    if args.dry_run:
        safe = dict(payload)
        safe["images"] = [("<data-url>" if x.startswith("data:") else x) for x in safe["images"]]
        print(json.dumps({"url": f"{base}/v1/api/generate", "payload": safe}, ensure_ascii=False, indent=2))
        return

    data = request_json("POST", f"{base}/v1/api/generate", json=payload)
    status = str(data.get("status") or "").lower()
    if (
        status in {"running", "pending", "processing", "queued"}
        or args.reply_type == "async"
        or (data.get("id") and not extract_urls(data) and status not in {"failed", "violation"})
    ):
        task_id = data.get("id")
        if not task_id:
            raise SystemExit(f"Async response missing id: {json.dumps(data, ensure_ascii=False)[:500]}")
        data = poll(base, str(task_id), args.poll_interval, args.timeout)
        status = str(data.get("status") or "").lower()

    print(json.dumps(data, ensure_ascii=False, indent=2))
    if status in {"failed", "violation"}:
        print(
            f"error: Grsai generation {status}: {data.get('error') or data.get('failure_reason') or data.get('msg') or ''}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    urls = extract_urls(data)
    if not urls:
        print("error: Grsai generation produced no image URLs.", file=sys.stderr)
        raise SystemExit(1)

    if args.out_dir:
        out_dir = Path(args.out_dir)
        for i, result_url in enumerate(urls, 1):
            out = download(result_url, out_dir, i, prefix=args.prefix)
            print(f"saved={out}")


def cmd_result(args: argparse.Namespace) -> None:
    data = poll(args.base_url.rstrip("/"), args.id, args.poll_interval, args.timeout)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    status = str(data.get("status") or "").lower()
    if status in {"failed", "violation"} or not extract_urls(data):
        raise SystemExit(1)


def cmd_config(_args: argparse.Namespace) -> None:
    config = load_config_file()
    source = "none"
    if os.getenv("GRSAI_API_KEY"):
        source = "env:GRSAI_API_KEY"
    elif config.get("GRSAI_API_KEY"):
        source = str(CONFIG_FILE)
    elif os.getenv("OPENAI_API_KEY"):
        source = "env:OPENAI_API_KEY"
    elif config.get("OPENAI_API_KEY"):
        source = f"{CONFIG_FILE}:OPENAI_API_KEY"
    print(json.dumps({
        "base_url": default_base_url(),
        "config_file": str(CONFIG_FILE),
        "config_file_exists": CONFIG_FILE.exists(),
        "key_present": source != "none",
        "key_source": source,
    }, ensure_ascii=False, indent=2))


def cmd_save_key(args: argparse.Namespace) -> None:
    key = args.key
    if args.stdin:
        key = sys.stdin.read().strip()
    if not key:
        key = getpass.getpass("Grsai API key: ").strip()
    if not key:
        raise SystemExit("Empty key was not saved.")
    if "\n" in key or "\r" in key:
        raise SystemExit("Key must be a single line.")
    write_config_file(key=key, base_url=args.base_url)
    print(json.dumps({
        "saved": True,
        "config_file": str(CONFIG_FILE),
        "permissions": oct(CONFIG_FILE.stat().st_mode & 0o777),
        "key_present": True,
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Grsai /v1/api/generate helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--base-url", default=default_base_url())
    gen.add_argument("--model", default="gpt-image-2")
    gen.add_argument("--prompt", required=True)
    gen.add_argument(
        "--image",
        "--ref-image",
        dest="image",
        action="append",
        default=[],
        help="Reference image URL, data URL, or local file path (repeatable for style/character consistency)",
    )
    gen.add_argument("--aspect-ratio", default="1024x1024")
    gen.add_argument("--image-size", default="")
    gen.add_argument("--quality", default="", choices=["", "low", "medium", "high", "xhigh", "max"])
    gen.add_argument("--reply-type", choices=["json", "stream", "async"], default="json")
    gen.add_argument("--out-dir", default="")
    gen.add_argument("--prefix", default="grsai-result", help="Output filename prefix when --out-dir is set (default: grsai-result)")
    gen.add_argument("--poll-interval", type=float, default=3.0)
    gen.add_argument("--timeout", type=float, default=TIMEOUT)
    gen.add_argument("--dry-run", action="store_true")
    gen.set_defaults(func=cmd_generate)

    result = sub.add_parser("result")
    result.add_argument("--base-url", default=default_base_url())
    result.add_argument("--id", required=True)
    result.add_argument("--poll-interval", type=float, default=3.0)
    result.add_argument("--timeout", type=float, default=TIMEOUT)
    result.set_defaults(func=cmd_result)

    config = sub.add_parser("config")
    config.set_defaults(func=cmd_config)

    save_key = sub.add_parser("save-key")
    save_key.add_argument("--key", help="Key value. Prefer interactive prompt or --stdin to avoid shell history.")
    save_key.add_argument("--stdin", action="store_true", help="Read key from standard input.")
    save_key.add_argument("--base-url", help="Optional Grsai base URL.")
    save_key.set_defaults(func=cmd_save_key)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
