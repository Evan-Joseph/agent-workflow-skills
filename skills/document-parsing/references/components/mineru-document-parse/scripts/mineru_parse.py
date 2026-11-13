#!/usr/bin/env python3
"""MinerU API CLI for document-to-Markdown parsing and result organization."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import getpass


DEFAULT_BASE_URL = "https://mineru.net"
DEFAULT_CONFIG_FILE = Path.home() / ".config" / "mineru" / "mineru.env"
SUPPORTED_PRECISION_EXTS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
    ".html", ".htm",
}
SUPPORTED_AGENT_EXTS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
}
TERMINAL_STATES = {"done", "failed"}
RUNNING_STATES = {"waiting-file", "uploading", "pending", "running", "converting"}
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
MAX_HTTP_RETRIES = 3
MAX_PRECISION_BATCH_FILES = 200
MAX_PRECISION_FILE_BYTES = 200 * 1024 * 1024
MAX_AGENT_FILE_BYTES = 10 * 1024 * 1024
ERROR_HINTS = {
    "A0202": "Token error. Check the token and Bearer prefix.",
    "A0211": "Token expired. Create or provide a fresh token.",
    "-30001": "Agent lightweight API file size limit exceeded.",
    "-30002": "Agent lightweight API unsupported file type.",
    "-30003": "Agent lightweight API page limit exceeded.",
    "-30004": "Agent lightweight API request parameter error.",
    "-60002": "File type detection failed. Check extension and source file.",
    "-60005": "File exceeds the 200 MB precision API limit.",
    "-60006": "File exceeds the 200 page precision API limit.",
    "-60009": "Submission queue is full. Retry later.",
    "-60012": "Task not found.",
    "-60018": "Daily parsing task limit reached.",
    "-60019": "HTML parsing quota exhausted.",
    "-60022": "Web page read failed.",
}


class MinerUError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def base_url() -> str:
    config = load_config_file()
    return (os.environ.get("MINERU_API_BASE") or config.get("MINERU_API_BASE", DEFAULT_BASE_URL)).rstrip("/")


def require_token() -> str:
    config = load_config_file()
    token = os.environ.get("MINERU_API_TOKEN", "").strip() or config.get("MINERU_API_TOKEN", "").strip()
    if not token:
        raise MinerUError(
            "MINERU_API_TOKEN is required for the precision API. "
            f"Export it for one command or save it in {DEFAULT_CONFIG_FILE}."
        )
    return token


def load_config_file(path: Path = DEFAULT_CONFIG_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    config: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MinerUError(f"Could not read config file {path}: {exc}") from exc
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key in {"MINERU_API_TOKEN", "MINERU_API_BASE"}:
            config[key] = value
    return config


def write_config_file(token: str | None = None, api_base: str | None = None, path: Path = DEFAULT_CONFIG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_config_file(path)
    if token is not None:
        existing["MINERU_API_TOKEN"] = token.strip()
    if api_base is not None:
        existing["MINERU_API_BASE"] = api_base.strip().rstrip("/")
    lines = [
        "# MinerU private local config. Do not commit or paste this file.",
        "# Used by ~/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py",
    ]
    for key in ("MINERU_API_BASE", "MINERU_API_TOKEN"):
        if existing.get(key):
            lines.append(f"{key}={existing[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def safe_name(value: str, fallback: str = "document", limit: int = 90) -> str:
    value = Path(value).name or value
    value = urllib.parse.unquote(value)
    value = re.sub(r"[^\w.\-()\u4e00-\u9fff]+", "_", value, flags=re.UNICODE)
    value = value.strip("._- ")
    if not value:
        value = fallback
    if len(value) > limit:
        stem = Path(value).stem[: limit - 12]
        suffix = Path(value).suffix[:10]
        value = f"{stem}{suffix}"
    return value


def source_stem(value: str, fallback: str = "document") -> str:
    parsed = urllib.parse.urlparse(value)
    name = Path(parsed.path).name if parsed.scheme else Path(value).name
    return Path(safe_name(name or fallback)).stem or fallback


def source_ext(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    path = parsed.path if parsed.scheme else value
    return Path(path).suffix.lower()


def validate_data_id(data_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", data_id):
        raise MinerUError("data_id must match [A-Za-z0-9_.-] and be at most 128 characters.")


def validate_seed(seed: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", seed):
        raise MinerUError("seed must match [A-Za-z0-9_] and be at most 64 characters.")


def resolve_model_version(model_version: str, sources: list[str]) -> str:
    if model_version != "auto":
        return model_version
    is_html = [source_ext(s) in {".html", ".htm"} for s in sources]
    if all(is_html):
        return "MinerU-HTML"
    if any(is_html):
        raise MinerUError("Mixed HTML and non-HTML sources require separate MinerU batches.")
    return "vlm"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request_json(
    method: str,
    path: str,
    payload: dict | None = None,
    auth: bool = False,
    timeout: int = 60,
    max_retries: int = MAX_HTTP_RETRIES,
) -> dict:
    url = path if path.startswith("http") else f"{base_url()}{path}"
    headers = {"Accept": "*/*"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth:
        headers["Authorization"] = f"Bearer {require_token()}"
    last_exc: Exception | None = None
    body = b""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with _DIRECT_OPENER.open(req, timeout=timeout) as resp:
                body = resp.read()
            break
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            if exc.code in RETRYABLE_HTTP_CODES and attempt < max_retries:
                time.sleep(2 ** attempt)
                last_exc = exc
                continue
            raise MinerUError(f"HTTP {exc.code} from MinerU: {body_text[:1000]}") from exc
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                last_exc = exc
                continue
            raise MinerUError(f"MinerU request failed: {exc}") from exc
    else:
        raise MinerUError(f"MinerU request failed after {max_retries} retries: {last_exc}") from last_exc
    try:
        result = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise MinerUError(f"MinerU returned non-JSON response: {body[:500]!r}") from exc
    code = result.get("code")
    if code not in (0, "0", None):
        code_str = str(code)
        hint = ERROR_HINTS.get(code_str)
        msg = result.get("msg", "")
        detail = f"MinerU API error {code_str}: {msg}"
        if hint:
            detail += f" ({hint})"
        if result.get("trace_id"):
            detail += f" trace_id={result['trace_id']}"
        raise MinerUError(detail)
    return result


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def put_file(url: str, path: Path, timeout: int = 300, max_retries: int = MAX_HTTP_RETRIES) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise MinerUError("Upload URL must be http or https.")
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        conn = conn_cls(parsed.netloc, timeout=timeout)
        try:
            conn.putrequest("PUT", target)
            conn.putheader("Content-Length", str(path.stat().st_size))
            conn.endheaders()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    conn.send(chunk)
            resp = conn.getresponse()
            body = resp.read()
            if resp.status in {200, 201, 204}:
                return
            if resp.status in RETRYABLE_HTTP_CODES and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise MinerUError(f"Upload failed for {path.name}: HTTP {resp.status} {body[:500]!r}")
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as exc:
            if isinstance(exc, MinerUError):
                raise
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                last_exc = exc
                continue
            raise MinerUError(f"Upload failed for {path.name}: {exc}") from exc
        finally:
            conn.close()
    raise MinerUError(f"Upload failed for {path.name} after {max_retries} retries: {last_exc}") from last_exc


def download_file(url: str, dest: Path, timeout: int = 300, max_retries: int = MAX_HTTP_RETRIES) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers={"Accept": "*/*"})
        try:
            with _DIRECT_OPENER.open(req, timeout=timeout) as resp, dest.open("wb") as f:
                shutil.copyfileobj(resp, f, length=1024 * 1024)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_CODES and attempt < max_retries:
                time.sleep(2 ** attempt)
                last_exc = exc
                continue
            raise MinerUError(f"Download failed (HTTP {exc.code}): {exc}") from exc
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                last_exc = exc
                continue
            raise MinerUError(f"Download failed: {exc}") from exc
    raise MinerUError(f"Download failed after {max_retries} retries: {last_exc}") from last_exc


def safe_extract_zip(zip_path: Path, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    root = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = dest / member.filename
            resolved = member_path.resolve()
            if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
                raise MinerUError(f"Unsafe zip path: {member.filename}")
            zf.extract(member, dest)
            if not member.is_dir():
                extracted.append(resolved)
    return extracted


def copy_unique(src: Path, dest_dir: Path, name: str | None = None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / safe_name(name or src.name)
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        i = 2
        while True:
            candidate = dest_dir / f"{stem}-{i}{suffix}"
            if not candidate.exists():
                target = candidate
                break
            i += 1
    shutil.copy2(src, target)
    return target


def copy_tree_merge(src_dir: Path, dest_dir: Path) -> None:
    if not src_dir.exists():
        return
    for path in src_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src_dir)
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def inventory(root: Path) -> list[dict]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        rows.append({"path": rel, "size": path.stat().st_size, "sha256": sha256_file(path)})
    return rows


def classify_extracted_files(run_dir: Path, source_name: str | None = None) -> dict:
    extracted = run_dir / "raw" / "extracted"
    markdown_dir = run_dir / "markdown"
    json_dir = run_dir / "json"
    assets_dir = run_dir / "assets"
    html_dir = run_dir / "html"
    exports_dir = run_dir / "exports"
    debug_dir = run_dir / "debug"
    copied = {"markdown": [], "json": [], "assets": [], "html": [], "exports": [], "debug": []}

    image_roots = [p for p in extracted.rglob("images") if p.is_dir()]
    for image_root in image_roots:
        copy_tree_merge(image_root, assets_dir / "images")
        copy_tree_merge(image_root, markdown_dir / "images")

    for path in sorted(p for p in extracted.rglob("*") if p.is_file()):
        rel = path.relative_to(extracted).as_posix()
        lower = path.name.lower()
        suffix = path.suffix.lower()
        if suffix == ".md":
            target = copy_unique(path, markdown_dir, "full.md" if lower == "full.md" else None)
            copied["markdown"].append(target.relative_to(run_dir).as_posix())
            if lower == "full.md" and source_name:
                named = markdown_dir / f"{Path(safe_name(source_name)).stem}.md"
                if named != target:
                    shutil.copy2(path, named)
                    copied["markdown"].append(named.relative_to(run_dir).as_posix())
        elif suffix == ".json":
            target = copy_unique(path, json_dir)
            copied["json"].append(target.relative_to(run_dir).as_posix())
        elif rel.startswith("images/") or "/images/" in rel:
            continue
        elif suffix == ".html" and lower == "main.html":
            target = copy_unique(path, html_dir)
            copied["html"].append(target.relative_to(run_dir).as_posix())
        elif suffix == ".pdf" and ("layout" in lower or "span" in lower):
            target = copy_unique(path, debug_dir)
            copied["debug"].append(target.relative_to(run_dir).as_posix())
        elif suffix in {".docx", ".doc", ".html", ".htm", ".tex", ".latex", ".pdf"}:
            subdir = {
                ".docx": "docx", ".doc": "docx", ".html": "html", ".htm": "html",
                ".tex": "latex", ".latex": "latex", ".pdf": "pdf",
            }.get(suffix, "other")
            target = copy_unique(path, exports_dir / subdir)
            copied["exports"].append(target.relative_to(run_dir).as_posix())
        else:
            if "layout" in lower or "span" in lower:
                target = copy_unique(path, debug_dir)
                copied["debug"].append(target.relative_to(run_dir).as_posix())

    if (assets_dir / "images").exists():
        copied["assets"].extend(
            p.relative_to(run_dir).as_posix()
            for p in sorted((assets_dir / "images").rglob("*"))
            if p.is_file()
        )
    return copied


def organize_zip(zip_path: Path, output_dir: Path, source_name: str | None = None, meta: dict | None = None) -> Path:
    if not zip_path.exists():
        raise MinerUError(f"Zip not found: {zip_path}")
    stem = source_stem(source_name or zip_path.name)
    ident = ""
    if meta:
        resp = meta.get("response") if isinstance(meta.get("response"), dict) else {}
        data_id = meta.get("data_id") or resp.get("data_id") or ""
        task_or_batch = meta.get("task_id") or resp.get("task_id") or meta.get("batch_id") or ""
        if data_id and task_or_batch:
            ident = f"{task_or_batch}-{data_id}"
        else:
            ident = data_id or task_or_batch or ""
    suffix = safe_name(str(ident), "result", 64) if ident else dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = output_dir / f"{safe_name(stem)}__{suffix}"
    raw_dir = run_dir / "raw"
    extracted_dir = raw_dir / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_zip = raw_dir / "result.zip"
    if zip_path.resolve() != raw_zip.resolve():
        shutil.copy2(zip_path, raw_zip)
    extracted_files = safe_extract_zip(raw_zip, extracted_dir)
    copied = classify_extracted_files(run_dir, source_name)
    manifest = {
        "created_at": now_iso(),
        "source_name": source_name,
        "zip_sha256": sha256_file(raw_zip),
        "zip_size": raw_zip.stat().st_size,
        "meta": meta or {},
        "extracted_file_count": len(extracted_files),
        "normalized_outputs": copied,
        "inventory": inventory(run_dir),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def write_agent_markdown(markdown_url: str, output_dir: Path, source_name: str, meta: dict, timeout: int) -> Path:
    stem = source_stem(source_name)
    ident = meta.get("task_id", "agent")
    run_dir = output_dir / f"{safe_name(stem)}__agent-{safe_name(str(ident), 'task', 32)}"
    markdown_dir = run_dir / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    md_path = markdown_dir / "full.md"
    download_file(markdown_url, md_path, timeout=timeout)
    manifest = {
        "created_at": now_iso(),
        "source_name": source_name,
        "mode": "agent",
        "markdown_url": markdown_url,
        "meta": meta,
        "inventory": inventory(run_dir),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def build_precision_payload(args: argparse.Namespace, sources: list[str], local: bool = False, url_batch: bool = False) -> dict:
    model = resolve_model_version(args.model_version, sources)
    payload: dict = {
        "model_version": model,
    }
    if model != "MinerU-HTML":
        payload.update({
            "enable_formula": not args.disable_formula,
            "enable_table": not args.disable_table,
            "language": args.language,
        })
    if getattr(args, "callback", None):
        payload["callback"] = args.callback
        if not args.seed:
            raise MinerUError("--seed is required when --callback is used.")
    if getattr(args, "seed", None):
        validate_seed(args.seed)
        payload["seed"] = args.seed
    if getattr(args, "extra_format", None):
        payload["extra_formats"] = args.extra_format
    if hasattr(args, "no_cache") and args.no_cache:
        payload["no_cache"] = True
    if getattr(args, "cache_tolerance", None) is not None:
        payload["cache_tolerance"] = args.cache_tolerance

    data_ids = getattr(args, "data_id", None) or []
    if isinstance(data_ids, str):
        data_ids = [data_ids]
    for data_id in data_ids:
        validate_data_id(data_id)

    if local:
        files = []
        for i, src in enumerate(sources):
            item = {"name": Path(src).name}
            if i < len(data_ids):
                item["data_id"] = data_ids[i]
            elif not data_ids and len(sources) > 1:
                clean_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(src).stem).strip("_.-") or "doc"
                auto_id = f"{i:03d}-{clean_stem}"[:128]
                validate_data_id(auto_id)
                item["data_id"] = auto_id
            if args.is_ocr:
                item["is_ocr"] = True
            if args.page_ranges:
                item["page_ranges"] = args.page_ranges
            files.append(item)
        payload["files"] = files
    elif url_batch:
        files = []
        for i, src in enumerate(sources):
            item = {"url": src}
            if i < len(data_ids):
                item["data_id"] = data_ids[i]
            elif not data_ids and len(sources) > 1:
                clean_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_stem(src)).strip("_.-") or "doc"
                auto_id = f"{i:03d}-{clean_stem}"[:128]
                validate_data_id(auto_id)
                item["data_id"] = auto_id
            if args.is_ocr:
                item["is_ocr"] = True
            if args.page_ranges:
                item["page_ranges"] = args.page_ranges
            files.append(item)
        payload["files"] = files
    else:
        payload["url"] = sources[0]
        if data_ids:
            payload["data_id"] = data_ids[0]
        if args.is_ocr:
            payload["is_ocr"] = True
        if args.page_ranges:
            payload["page_ranges"] = args.page_ranges
    return payload


def build_agent_payload(args: argparse.Namespace, source_name: str | None = None, url: str | None = None) -> dict:
    payload = {
        "language": args.language,
        "enable_table": not args.disable_table,
        "is_ocr": args.is_ocr,
        "enable_formula": not args.disable_formula,
    }
    if args.page_range:
        payload["page_range"] = args.page_range
    if source_name:
        payload["file_name"] = source_name
    if url:
        payload["url"] = url
        if args.file_name:
            payload["file_name"] = args.file_name
    return payload


def poll_precision_task(task_id: str, timeout: int, interval: int) -> dict:
    start = time.time()
    while True:
        result = request_json("GET", f"/api/v4/extract/task/{task_id}", auth=True, timeout=60)
        data = result.get("data", {})
        state = data.get("state")
        if state == "done":
            return data
        if state == "failed":
            raise MinerUError(f"MinerU task failed: {data.get('err_msg', '')} task_id={task_id}")
        if time.time() - start > timeout:
            raise MinerUError(f"Polling timed out. Check later with: status {task_id}")
        progress = data.get("extract_progress") or {}
        progress_text = ""
        if progress:
            progress_text = f" pages={progress.get('extracted_pages')}/{progress.get('total_pages')}"
        print(f"[{int(time.time() - start)}s] task {task_id} state={state}{progress_text}", file=sys.stderr)
        time.sleep(interval)


def poll_precision_batch(batch_id: str, timeout: int, interval: int) -> dict:
    start = time.time()
    while True:
        result = request_json("GET", f"/api/v4/extract-results/batch/{batch_id}", auth=True, timeout=60)
        data = result.get("data", {})
        items = data.get("extract_result") or []
        if items and all((item.get("state") in TERMINAL_STATES) for item in items):
            return data
        if time.time() - start > timeout:
            raise MinerUError(f"Polling timed out. Check later with: batch-status {batch_id}")
        states = {}
        for item in items:
            states[item.get("state", "unknown")] = states.get(item.get("state", "unknown"), 0) + 1
        print(f"[{int(time.time() - start)}s] batch {batch_id} states={states or 'waiting'}", file=sys.stderr)
        time.sleep(interval)


def poll_agent_task(task_id: str, timeout: int, interval: int) -> dict:
    start = time.time()
    while True:
        result = request_json("GET", f"/api/v1/agent/parse/{task_id}", auth=False, timeout=60)
        data = result.get("data", {})
        state = data.get("state")
        if state == "done":
            return data
        if state == "failed":
            err_code = data.get("err_code")
            hint = ERROR_HINTS.get(str(err_code), "")
            raise MinerUError(f"MinerU agent task failed: {data.get('err_msg', '')} {hint} task_id={task_id}")
        if time.time() - start > timeout:
            raise MinerUError(f"Polling timed out. Check later with: agent-status {task_id}")
        print(f"[{int(time.time() - start)}s] agent task {task_id} state={state}", file=sys.stderr)
        time.sleep(interval)


def handle_done_zip(full_zip_url: str, output_dir: Path, source_name: str, meta: dict, timeout: int) -> Path:
    tmp_dir = output_dir / ".downloads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    resp = meta.get("response") if isinstance(meta.get("response"), dict) else {}
    uniq = meta.get("data_id") or resp.get("data_id") or meta.get("task_id") or resp.get("task_id") or meta.get("batch_id") or "result"
    tmp_zip = tmp_dir / f"{safe_name(source_stem(source_name))}-{safe_name(str(uniq), 'result', 48)}.zip"
    download_file(full_zip_url, tmp_zip, timeout=timeout)
    run_dir = organize_zip(tmp_zip, output_dir, source_name=source_name, meta=meta)
    try:
        tmp_zip.unlink()
        if not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()
    except OSError:
        pass
    return run_dir


def cmd_url(args: argparse.Namespace) -> None:
    payload = build_precision_payload(args, [args.url])
    if args.dry_run:
        print_json({"method": "POST", "path": "/api/v4/extract/task", "payload": payload})
        return
    result = request_json("POST", "/api/v4/extract/task", payload, auth=True, timeout=args.http_timeout)
    data = result["data"]
    task_id = data["task_id"]
    print(f"submitted task_id={task_id}", file=sys.stderr)
    if args.no_wait:
        print_json(result)
        return
    done = poll_precision_task(task_id, args.timeout, args.interval)
    meta = {"mode": "precision-url", "task_id": task_id, "request": payload, "response": done}
    run_dir = handle_done_zip(done["full_zip_url"], args.output_dir, args.url, meta, args.http_timeout)
    print(run_dir)


def cmd_file(args: argparse.Namespace) -> None:
    paths = [Path(p).expanduser().resolve() for p in args.files]
    if len(paths) > MAX_PRECISION_BATCH_FILES:
        raise MinerUError(f"Batch exceeds {MAX_PRECISION_BATCH_FILES} files limit ({len(paths)} provided).")
    for path in paths:
        if not path.exists() or not path.is_file():
            raise MinerUError(f"File not found: {path}")
        size = path.stat().st_size
        if size <= 0:
            raise MinerUError(f"File is empty (0 bytes): {path}")
        if size > MAX_PRECISION_FILE_BYTES:
            raise MinerUError(
                f"File exceeds 200 MB precision API limit ({size / (1024 * 1024):.1f} MB): {path}"
            )
        if source_ext(str(path)) not in SUPPORTED_PRECISION_EXTS:
            raise MinerUError(f"Unsupported precision file extension: {path.suffix}")
    payload = build_precision_payload(args, [str(p) for p in paths], local=True)
    if args.dry_run:
        print_json({"method": "POST", "path": "/api/v4/file-urls/batch", "payload": payload})
        return
    result = request_json("POST", "/api/v4/file-urls/batch", payload, auth=True, timeout=args.http_timeout)
    data = result["data"]
    batch_id = data["batch_id"]
    urls = data["file_urls"]
    if len(urls) != len(paths):
        raise MinerUError("MinerU returned a different number of upload URLs than requested files.")
    for path, upload_url in zip(paths, urls):
        print(f"uploading {path.name}", file=sys.stderr)
        put_file(upload_url, path, timeout=args.http_timeout)
    print(f"submitted batch_id={batch_id}", file=sys.stderr)
    if args.no_wait:
        print_json({"batch_id": batch_id, "file_count": len(paths)})
        return
    done = poll_precision_batch(batch_id, args.timeout, args.interval)
    run_dirs = []
    req_files = payload.get("files") if isinstance(payload.get("files"), list) else []
    for idx, item in enumerate(done.get("extract_result", [])):
        if item.get("state") == "done" and item.get("full_zip_url"):
            source_name = item.get("file_name") or "document"
            req_data_id = req_files[idx].get("data_id") if idx < len(req_files) and isinstance(req_files[idx], dict) else None
            data_id = item.get("data_id") or req_data_id or (f"{idx:03d}" if len(paths) > 1 else "")
            meta = {"mode": "precision-file", "batch_id": batch_id, "data_id": data_id, "request": payload, "response": item}
            run_dirs.append(str(handle_done_zip(item["full_zip_url"], args.output_dir, source_name, meta, args.http_timeout)))
        elif item.get("state") == "failed":
            print(f"failed {item.get('file_name')}: {item.get('err_msg')}", file=sys.stderr)
    print_json({"batch_id": batch_id, "outputs": run_dirs})


def cmd_batch_url(args: argparse.Namespace) -> None:
    payload = build_precision_payload(args, args.urls, url_batch=True)
    if args.dry_run:
        print_json({"method": "POST", "path": "/api/v4/extract/task/batch", "payload": payload})
        return
    result = request_json("POST", "/api/v4/extract/task/batch", payload, auth=True, timeout=args.http_timeout)
    batch_id = result["data"]["batch_id"]
    print(f"submitted batch_id={batch_id}", file=sys.stderr)
    if args.no_wait:
        print_json(result)
        return
    done = poll_precision_batch(batch_id, args.timeout, args.interval)
    run_dirs = []
    req_files = payload.get("files") if isinstance(payload.get("files"), list) else []
    for idx, item in enumerate(done.get("extract_result", [])):
        if item.get("state") == "done" and item.get("full_zip_url"):
            source_name = item.get("file_name") or item.get("data_id") or "document"
            req_data_id = req_files[idx].get("data_id") if idx < len(req_files) and isinstance(req_files[idx], dict) else None
            data_id = item.get("data_id") or req_data_id or (f"{idx:03d}" if len(args.urls) > 1 else "")
            meta = {"mode": "precision-batch-url", "batch_id": batch_id, "data_id": data_id, "request": payload, "response": item}
            run_dirs.append(str(handle_done_zip(item["full_zip_url"], args.output_dir, source_name, meta, args.http_timeout)))
        elif item.get("state") == "failed":
            print(f"failed {item.get('file_name')}: {item.get('err_msg')}", file=sys.stderr)
    print_json({"batch_id": batch_id, "outputs": run_dirs})


def cmd_status(args: argparse.Namespace) -> None:
    result = request_json("GET", f"/api/v4/extract/task/{args.task_id}", auth=True, timeout=args.http_timeout)
    if args.download:
        data = result.get("data", {})
        if data.get("state") != "done" or not data.get("full_zip_url"):
            raise MinerUError("Task is not done or has no full_zip_url.")
        meta = {"mode": "precision-status", "task_id": args.task_id, "response": data}
        run_dir = handle_done_zip(data["full_zip_url"], args.output_dir, args.source_name or args.task_id, meta, args.http_timeout)
        print(run_dir)
    else:
        print_json(result)


def cmd_batch_status(args: argparse.Namespace) -> None:
    result = request_json("GET", f"/api/v4/extract-results/batch/{args.batch_id}", auth=True, timeout=args.http_timeout)
    if args.download:
        outputs = []
        data = result.get("data", {})
        items = data.get("extract_result", [])
        for idx, item in enumerate(items):
            if item.get("state") == "done" and item.get("full_zip_url"):
                data_id = item.get("data_id") or (f"{idx:03d}" if len(items) > 1 else "")
                meta = {"mode": "precision-batch-status", "batch_id": args.batch_id, "data_id": data_id, "response": item}
                outputs.append(str(handle_done_zip(item["full_zip_url"], args.output_dir, item.get("file_name") or args.batch_id, meta, args.http_timeout)))
        print_json({"batch_id": args.batch_id, "outputs": outputs})
    else:
        print_json(result)


def cmd_agent_url(args: argparse.Namespace) -> None:
    payload = build_agent_payload(args, url=args.url)
    if args.dry_run:
        print_json({"method": "POST", "path": "/api/v1/agent/parse/url", "payload": payload})
        return
    result = request_json("POST", "/api/v1/agent/parse/url", payload, auth=False, timeout=args.http_timeout)
    task_id = result["data"]["task_id"]
    print(f"submitted agent task_id={task_id}", file=sys.stderr)
    if args.no_wait:
        print_json(result)
        return
    done = poll_agent_task(task_id, args.timeout, args.interval)
    run_dir = write_agent_markdown(done["markdown_url"], args.output_dir, args.file_name or args.url, {"task_id": task_id, "request": payload, "response": done}, args.http_timeout)
    print(run_dir)


def cmd_agent_file(args: argparse.Namespace) -> None:
    path = Path(args.file).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise MinerUError(f"File not found: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise MinerUError(f"File is empty (0 bytes): {path}")
    if size > MAX_AGENT_FILE_BYTES:
        raise MinerUError(
            f"File exceeds 10 MB agent lightweight API limit ({size / (1024 * 1024):.1f} MB): {path}"
        )
    if source_ext(str(path)) not in SUPPORTED_AGENT_EXTS:
        raise MinerUError(f"Unsupported agent file extension: {path.suffix}")
    payload = build_agent_payload(args, source_name=path.name)
    if args.dry_run:
        print_json({"method": "POST", "path": "/api/v1/agent/parse/file", "payload": payload})
        return
    result = request_json("POST", "/api/v1/agent/parse/file", payload, auth=False, timeout=args.http_timeout)
    data = result["data"]
    task_id = data["task_id"]
    print(f"uploading {path.name}", file=sys.stderr)
    put_file(data["file_url"], path, timeout=args.http_timeout)
    if args.no_wait:
        print_json({"task_id": task_id})
        return
    done = poll_agent_task(task_id, args.timeout, args.interval)
    run_dir = write_agent_markdown(done["markdown_url"], args.output_dir, path.name, {"task_id": task_id, "request": payload, "response": done}, args.http_timeout)
    print(run_dir)


def cmd_agent_status(args: argparse.Namespace) -> None:
    result = request_json("GET", f"/api/v1/agent/parse/{args.task_id}", auth=False, timeout=args.http_timeout)
    if args.download:
        data = result.get("data", {})
        if data.get("state") != "done" or not data.get("markdown_url"):
            raise MinerUError("Agent task is not done or has no markdown_url.")
        run_dir = write_agent_markdown(data["markdown_url"], args.output_dir, args.source_name or args.task_id, {"task_id": args.task_id, "response": data}, args.http_timeout)
        print(run_dir)
    else:
        print_json(result)


def cmd_organize(args: argparse.Namespace) -> None:
    meta = {"mode": "organize", "source_zip": str(Path(args.zip).expanduser().resolve())}
    run_dir = organize_zip(Path(args.zip).expanduser().resolve(), args.output_dir, source_name=args.source_name, meta=meta)
    print(run_dir)


def cmd_languages(_args: argparse.Namespace) -> None:
    print_json({
        "standalone": ["ch", "ch_server", "en", "japan", "korean", "chinese_cht", "ta", "te", "ka", "el", "th"],
        "families": ["latin", "arabic", "cyrillic", "east_slavic", "devanagari"],
    })


def cmd_config(_args: argparse.Namespace) -> None:
    config = load_config_file()
    token_source = "none"
    raw_tok = ""
    if os.environ.get("MINERU_API_TOKEN"):
        token_source = "env:MINERU_API_TOKEN"
        raw_tok = os.environ.get("MINERU_API_TOKEN", "")
    elif config.get("MINERU_API_TOKEN"):
        token_source = str(DEFAULT_CONFIG_FILE)
        raw_tok = str(config.get("MINERU_API_TOKEN") or "")
    token_expired = False
    expires_at_iso = None
    if raw_tok and raw_tok.count(".") == 2:
        try:
            import base64
            from datetime import datetime, timezone
            b64 = raw_tok.split(".")[1]
            b64 += "=" * (-len(b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(b64).decode("utf-8"))
            exp = payload.get("exp")
            if isinstance(exp, (int, float)):
                token_expired = time.time() >= float(exp)
                expires_at_iso = datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat()
        except Exception:
            pass
    print_json({
        "base_url": base_url(),
        "config_file": str(DEFAULT_CONFIG_FILE),
        "config_file_exists": DEFAULT_CONFIG_FILE.exists(),
        "token_present": token_source != "none",
        "token_valid": (token_source != "none") and not token_expired,
        "token_expired": token_expired,
        "token_expires_at": expires_at_iso,
        "token_source": token_source,
        "hint": "Token expired; refresh at https://mineru.net/apiManage/token and run `mineru_parse.py save-token`" if token_expired else None,
    })


def cmd_save_token(args: argparse.Namespace) -> None:
    token = args.token
    if args.stdin:
        token = sys.stdin.read().strip()
    if not token:
        token = getpass.getpass("MinerU API token: ").strip()
    if not token:
        raise MinerUError("Empty token was not saved.")
    if "\n" in token or "\r" in token:
        raise MinerUError("Token must be a single line.")
    write_config_file(token=token, api_base=args.api_base)
    print_json({
        "saved": True,
        "config_file": str(DEFAULT_CONFIG_FILE),
        "permissions": oct(DEFAULT_CONFIG_FILE.stat().st_mode & 0o777),
        "token_present": True,
    })


def add_common_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", "--out-dir", "-o", dest="output_dir", type=Path, default=Path.cwd() / "mineru-output", help="Output root directory.")
    parser.add_argument("--timeout", type=int, default=1800, help="Polling timeout in seconds.")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds.")
    parser.add_argument("--http-timeout", type=int, default=300, help="HTTP request/upload/download timeout in seconds.")
    parser.add_argument("--no-wait", action="store_true", help="Submit/upload only; do not poll or download.")
    parser.add_argument("--dry-run", action="store_true", help="Print request plan without calling MinerU.")


def add_precision_opts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-version", choices=["auto", "pipeline", "vlm", "MinerU-HTML"], default="auto")
    parser.add_argument("--language", default="ch")
    parser.add_argument("--is-ocr", action="store_true")
    parser.add_argument("--disable-formula", action="store_true")
    parser.add_argument("--disable-table", action="store_true")
    parser.add_argument("--extra-format", choices=["docx", "html", "latex"], action="append")
    parser.add_argument("--page-ranges")
    parser.add_argument("--data-id", action="append")
    parser.add_argument("--callback")
    parser.add_argument("--seed")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-tolerance", type=int)


def add_agent_opts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language", default="ch")
    parser.add_argument("--is-ocr", action="store_true")
    parser.add_argument("--disable-formula", action="store_true")
    parser.add_argument("--disable-table", action="store_true")
    parser.add_argument("--page-range")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse documents with MinerU and organize Markdown outputs.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("url", help="Precision API: parse one remote URL and download result zip.")
    p.add_argument("url")
    add_common_io(p)
    add_precision_opts(p)
    p.set_defaults(func=cmd_url)

    p = sub.add_parser("file", aliases=["parse"], help="Precision API: upload one or more local files and download result zips.")
    p.add_argument("files", nargs="+")
    add_common_io(p)
    add_precision_opts(p)
    p.set_defaults(func=cmd_file)

    p = sub.add_parser("batch-url", help="Precision API: parse multiple remote URLs and download result zips.")
    p.add_argument("urls", nargs="+")
    add_common_io(p)
    add_precision_opts(p)
    p.set_defaults(func=cmd_batch_url)

    p = sub.add_parser("status", help="Precision API: query task status by task_id.")
    p.add_argument("task_id")
    p.add_argument("--download", action="store_true")
    p.add_argument("--source-name")
    p.add_argument("--output-dir", type=Path, default=Path.cwd() / "mineru-output")
    p.add_argument("--http-timeout", type=int, default=300)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("batch-status", help="Precision API: query batch status by batch_id.")
    p.add_argument("batch_id")
    p.add_argument("--download", action="store_true")
    p.add_argument("--output-dir", type=Path, default=Path.cwd() / "mineru-output")
    p.add_argument("--http-timeout", type=int, default=300)
    p.set_defaults(func=cmd_batch_status)

    p = sub.add_parser("agent-url", help="Agent lightweight API: parse one remote URL to Markdown.")
    p.add_argument("url")
    p.add_argument("--file-name")
    add_common_io(p)
    add_agent_opts(p)
    p.set_defaults(func=cmd_agent_url)

    p = sub.add_parser("agent-file", help="Agent lightweight API: upload one local file to Markdown.")
    p.add_argument("file")
    add_common_io(p)
    add_agent_opts(p)
    p.set_defaults(func=cmd_agent_file)

    p = sub.add_parser("agent-status", help="Agent lightweight API: query task status by task_id.")
    p.add_argument("task_id")
    p.add_argument("--download", action="store_true")
    p.add_argument("--source-name")
    p.add_argument("--output-dir", type=Path, default=Path.cwd() / "mineru-output")
    p.add_argument("--http-timeout", type=int, default=300)
    p.set_defaults(func=cmd_agent_status)

    p = sub.add_parser("organize", help="Organize an existing MinerU result zip without calling the API.")
    p.add_argument("zip")
    p.add_argument("--source-name")
    p.add_argument("--output-dir", type=Path, default=Path.cwd() / "mineru-output")
    p.set_defaults(func=cmd_organize)

    p = sub.add_parser("languages", help="List known MinerU language values.")
    p.set_defaults(func=cmd_languages)

    p = sub.add_parser("config", help="Show MinerU local config status without printing secrets.")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("save-token", help="Save MinerU token to the private local config file.")
    p.add_argument("--token", help="Token value. Prefer interactive prompt or --stdin to avoid shell history.")
    p.add_argument("--stdin", action="store_true", help="Read token from standard input.")
    p.add_argument("--api-base", help="Optional MinerU API base URL.")
    p.set_defaults(func=cmd_save_token)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "output_dir"):
            args.output_dir = args.output_dir.expanduser().resolve()
        args.func(args)
        return 0
    except MinerUError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
