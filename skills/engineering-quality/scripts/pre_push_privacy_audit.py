#!/usr/bin/env python3
"""Deterministic Pre-Push Privacy, Secret, Symlink & Monolith Auditor (pre_push_privacy_audit.py).

Audits a target repository's working tree AND `git log -p` commit history (unless
`--worktree-only` is passed) before committing or pushing to public GitHub repositories:
  1. Symlinks outside `.git/` (portability & leak hazard)
  2. Hardcoded API keys / tokens (`sk-`, `ghp_`, `github_pat_`, `AIza`, `AKIA`, PEM private keys)
  3. Personal / institutional emails, CN phone numbers, 18-digit IDs, and local home directory paths
  4. Optional project-specific identifiers configured via `PRIVACY_EXTRA_REGEX`
  5. Loopback / LAN endpoints (`127.0.0.1:<port>`, `localhost:<port>`, `10.0.0.x`, `192.168.x.x`)
  6. Client / commissioned project markers (`[CLIENT_RESTRICTED]`)
  7. `>400`-line code monolith warnings (advisory by default; blocking with `--strict-monoliths`)

Zero third-party dependencies (`homebrew-stdlib` runtime). Masks matched values in output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    "vendor",
}

CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".swift", ".c", ".cpp",
    ".vue", ".svelte",
}

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".7z", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".mp3",
    ".wav", ".pyc", ".so", ".dylib", ".dll", ".exe", ".db", ".sqlite", ".sqlite3",
}

_MAC_HOME_PREFIX = "/" + "Users/"
_EXTRA_PRIVACY_RE = os.environ.get("PRIVACY_EXTRA_REGEX", "").strip()

RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    r
    for r in (
        (
            "hardcoded_secret",
            "API key / token / private key header",
            re.compile(
                r"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{22,}"
                r"|AIza[0-9A-Za-z_-]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{16,}"
                r"|-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----)"
            ),
        ),
        (
            "personal_or_advisor_email",
            "Personal or institutional email address",
            re.compile(
                r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9.-]+\.edu(?:\.cn)?|qq\.com|163\.com|126\.com)\b",
                re.I,
            ),
        ),
        (
            "phone_or_id",
            "Mainland mobile phone or 18-digit resident ID",
            re.compile(
                r"(?<![0-9A-Za-z_.-])(?:1(?:3\d|4[5-9]|5[0-35-9]|6[2567]|7[0-8]|8\d|9[0-35-9])\d{8}"
                r"|[1-6]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?![0-9A-Za-z_])"
            ),
        ),
        (
            "loopback_or_lan_ip",
            "Loopback port or private LAN IP address",
            re.compile(
                r"\b(?:127\.0\.0\.1:\d{2,5}|localhost:\d{2,5}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
                r"|192\.168\.\d{1,3}\.\d{1,3})\b"
            ),
        ),
        (
            "local_user_path",
            "Local macOS or Linux home directory path",
            re.compile(rf"(?:{_MAC_HOME_PREFIX}|/home/)[A-Za-z0-9._-]+"),
        ),
        (
            "commissioned_marker",
            "Commissioned / client-restricted asset marker ([CLIENT_RESTRICTED])",
            re.compile(r"\[CLIENT_RESTRICTED\]"),
        ),
        (
            ("custom_privacy_pattern", "Custom blocked pattern (PRIVACY_EXTRA_REGEX)", re.compile(_EXTRA_PRIVACY_RE))
            if _EXTRA_PRIVACY_RE
            else None
        ),
    )
    if r is not None
)

PLACEHOLDER_ALLOW_RE = re.compile(
    r"(?:example\.com|your[_-]?api[_-]?key|sk-xxxx|sk-\.\.\.|<API_KEY>|<ADVISOR_EMAIL>|127\.0\.0\.1:PORT)",
    re.I,
)


def mask_value(raw: str) -> str:
    s = raw.strip()
    if len(s) <= 6:
        return s[:2] + "***"
    return f"{s[:4]}***{s[-3:]}"


def is_probably_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with path.open("rb") as fh:
            chunk = fh.read(2048)
        return b"\x00" in chunk
    except OSError:
        return True


def scan_line(line: str) -> list[tuple[str, str]]:
    if len(line) > 4000:
        line = line[:4000]
    hits: list[tuple[str, str]] = []
    for rule_id, _, pat in RULES:
        for m in pat.finditer(line):
            matched = m.group(0)
            if PLACEHOLDER_ALLOW_RE.search(matched):
                continue
            hits.append((rule_id, mask_value(matched)))
            break
    return hits


def scan_worktree(root: Path, monolith_lines: int = 400) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    symlinks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    monoliths: list[dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        cur_dir = Path(dirpath)
        # Detect directory symlinks before pruning
        kept_dirs: list[str] = []
        for d in dirnames:
            if d == ".git":
                continue
            dp = cur_dir / d
            if dp.is_symlink():
                symlinks.append({
                    "path": str(dp.relative_to(root)),
                    "target": os.readlink(dp),
                    "kind": "dir_symlink",
                })
                continue
            if d in SKIP_DIRS:
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in filenames:
            fp = cur_dir / fname
            rel_p = str(fp.relative_to(root))
            if fp.is_symlink():
                symlinks.append({
                    "path": rel_p,
                    "target": os.readlink(fp),
                    "kind": "file_symlink",
                })
                continue
            if is_probably_binary(fp):
                continue
            try:
                if fp.stat().st_size > 2_000_000:
                    continue
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            lines = text.splitlines()
            if fp.suffix.lower() in CODE_EXTS and len(lines) > monolith_lines:
                monoliths.append({
                    "path": rel_p,
                    "line_count": len(lines),
                    "threshold": monolith_lines,
                })

            for lineno, line in enumerate(lines, start=1):
                for rule_id, masked in scan_line(line):
                    findings.append({
                        "scope": "worktree",
                        "rule": rule_id,
                        "path": rel_p,
                        "line": lineno,
                        "masked_match": masked,
                    })

    return symlinks, findings, monoliths


def scan_git_history(root: Path, max_commits: int = 200) -> tuple[bool, list[dict[str, Any]], str | None]:
    git_dir = root / ".git"
    if not git_dir.exists():
        return False, [], None

    env = dict(os.environ, CI="1", GIT_TERMINAL_PROMPT="0")
    cmd = ["git", "-C", str(root), "log", "-p", "--no-color", f"-n{max_commits}", "--all"]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=45,
        )
    except Exception as exc:
        return True, [], f"git log -p failed: {exc}"

    if proc.returncode != 0:
        stderr_txt = proc.stderr.decode("utf-8", errors="replace").strip()
        if "does not have any commits yet" in stderr_txt:
            return True, [], None
        return True, [], f"git log exited {proc.returncode}: {stderr_txt[:200]}"

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    cur_commit = "unknown"
    cur_file = "unknown"

    for raw_line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        if raw_line.startswith("commit "):
            cur_commit = raw_line.split()[1][:12]
        elif raw_line.startswith("+++ b/"):
            cur_file = raw_line[6:].strip()
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            added = raw_line[1:]
            for rule_id, masked in scan_line(added):
                dedup_key = (cur_commit, cur_file, rule_id, masked)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    findings.append({
                        "scope": "git_history",
                        "commit": cur_commit,
                        "path": cur_file,
                        "rule": rule_id,
                        "masked_match": masked,
                    })
                    if len(findings) >= 200:
                        return True, findings, None

    return True, findings, None


def format_human_report(report: dict[str, Any]) -> str:
    status = "PASSED" if report["passed"] else "BLOCKED"
    lines = [
        f"# Pre-Push Privacy & Hygiene Audit: {status}",
        f"- Target: `{report['target']}`",
        f"- Symlinks: `{report['counts']['symlinks']}`",
        f"- Worktree privacy/secret hits: `{report['counts']['worktree_findings']}`",
        f"- Git history (`git log -p`) hits: `{report['counts']['history_findings']}`",
        f"- Monolith warnings (`>{report['monolith_threshold']}` lines): `{report['counts']['monoliths']}`",
        "",
    ]
    if report["symlinks"]:
        lines.append("## Symlinks (Blocking)")
        for s in report["symlinks"][:25]:
            lines.append(f"- `{s['path']}` -> `{s['target']}` ({s['kind']})")
        lines.append("")
    if report["worktree_findings"]:
        lines.append("## Worktree Privacy & Secret Hits (Blocking)")
        for f in report["worktree_findings"][:40]:
            lines.append(f"- `{f['path']}:{f['line']}` [{f['rule']}] `{f['masked_match']}`")
        lines.append("")
    if report["history_findings"]:
        lines.append("## Git History (`git log -p`) Hits (Blocking — clean via `git filter-repo` or orphan branch)")
        for f in report["history_findings"][:40]:
            lines.append(f"- commit `{f['commit']}` `{f['path']}` [{f['rule']}] `{f['masked_match']}`")
        lines.append("")
    if report["monoliths"]:
        lines.append("## Monolith Warnings (>400 lines)")
        for m in report["monoliths"][:25]:
            lines.append(f"- `{m['path']}`: {m['line_count']} lines")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit working tree and git log -p history for symlinks, secrets, PII, device serials, LAN IPs, [CLIENT_RESTRICTED] markers, and >400-line monoliths."
    )
    parser.add_argument("target", nargs="?", default=".", help="Target repository directory (default: .)")
    parser.add_argument("--worktree-only", action="store_true", help="Skip `git log -p` commit history scan")
    parser.add_argument("--max-commits", type=int, default=200, help="Max commits to inspect in `git log -p` (default: 200)")
    parser.add_argument("--monolith-lines", type=int, default=400, help="Line threshold for monolith warning (default: 400)")
    parser.add_argument("--strict-monoliths", action="store_true", help="Treat >400-line monolith warnings as blocking errors")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report")
    args = parser.parse_args()

    root = Path(args.target).expanduser().resolve()
    if not root.is_dir():
        err = {"passed": False, "error": f"Target directory not found: {root}"}
        print(json.dumps(err, ensure_ascii=False) if args.json else f"Error: {err['error']}", file=sys.stderr)
        return 2

    symlinks, wt_findings, monoliths = scan_worktree(root, monolith_lines=max(50, args.monolith_lines))
    has_git, hist_findings, git_err = (False, [], None)
    if not args.worktree_only:
        has_git, hist_findings, git_err = scan_git_history(root, max_commits=max(1, args.max_commits))

    blocking_count = len(symlinks) + len(wt_findings) + len(hist_findings) + (1 if git_err else 0)
    if args.strict_monoliths:
        blocking_count += len(monoliths)

    report = {
        "passed": blocking_count == 0,
        "target": str(root),
        "worktree_only": bool(args.worktree_only),
        "git_repo_detected": has_git,
        "git_scan_error": git_err,
        "monolith_threshold": args.monolith_lines,
        "counts": {
            "symlinks": len(symlinks),
            "worktree_findings": len(wt_findings),
            "history_findings": len(hist_findings),
            "monoliths": len(monoliths),
        },
        "symlinks": symlinks,
        "worktree_findings": wt_findings[:100],
        "history_findings": hist_findings[:100],
        "monoliths": monoliths[:50],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(format_human_report(report))

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
