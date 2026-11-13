#!/usr/bin/env python3
"""Scan a repository for intentional complexity-pruning debt markers."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    "target",
    "vendor",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "site-packages",
    ".nuxt",
    ".svelte-kit",
    ".astro",
    "coverage",
    ".cache",
    "out",
}

MARKER_RE = re.compile(r"(?:\{/\*|/\*|<!--|//|--|#|\*)\s*complexity-" r"pruning:\s*(.*)", re.I)
COMMENT_CONTINUATION_RE = re.compile(r"^\s*(?://|--|#|\*)\s*(.*)")
TRAILING_CLOSE_RE = re.compile(r"\s*(?:\*/\}?|--!?>)\s*$")
TRIGGER_RE = re.compile(
    r"\b(if|when|until|unless|trigger|switch to|replace with|revisit)\b|(升级|改成|触发|出现|需要|再)",
    re.I,
)


def iter_text_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if path.is_symlink() or path.stat().st_size > 2_000_000:
                    continue
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            yield path, content.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a repository for complexity-pruning debt markers.")
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    args = parser.parse_args()

    root = Path(args.repo).expanduser().resolve()
    hits = []
    for path, lines in iter_text_files(root):
        for idx, line in enumerate(lines):
            lineno = idx + 1
            m = MARKER_RE.search(line)
            if not m:
                continue
            body = TRAILING_CLOSE_RE.sub("", m.group(1).strip())
            combined = body
            if idx + 1 < len(lines) and not MARKER_RE.search(lines[idx + 1]):
                next_m = COMMENT_CONTINUATION_RE.match(lines[idx + 1])
                if next_m:
                    next_body = TRAILING_CLOSE_RE.sub("", next_m.group(1).strip())
                    if next_body:
                        combined = f"{body} {next_body}".strip()
            has_trigger = bool(TRIGGER_RE.search(combined))
            hits.append((path.relative_to(root), lineno, body, has_trigger))

    if args.json:
        missing = sum(1 for _, _, _, has_trigger in hits if not has_trigger)
        payload = {
            "repo": str(root),
            "total": len(hits),
            "missing_trigger": missing,
            "markers": [
                {
                    "file": str(rel),
                    "line": lineno,
                    "body": body,
                    "has_trigger": has_trigger,
                }
                for rel, lineno, body, has_trigger in hits
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not hits:
        print("No complexity-pruning debt markers.")
        return 0

    missing = 0
    current = None
    for rel, lineno, body, has_trigger in hits:
        if rel != current:
            current = rel
            print(f"\n{rel}")
        tag = "" if has_trigger else " [no-trigger]"
        if not has_trigger:
            missing += 1
        print(f"  L{lineno}: {body}{tag}")

    print(f"\n{len(hits)} markers, {missing} with no trigger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
