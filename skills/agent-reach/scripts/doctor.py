#!/usr/bin/env python3
"""Agent Reach channel health doctor CLI (`agent-reach doctor [--json]`)."""
from __future__ import annotations
import os

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

CHANNELS = [
    ("omnireach", "omnireach", ["--version"]),
    ("opencli", "opencli", ["--version"]),
    ("reach-hub", "reach-hub", ["--help"]),
    ("xhs-research", os.path.expanduser("~/.agents/skills/agent-reach/scripts/xhs_research.py"), ["runtime-health"]),
    ("bili", "bili", ["--version"]),
    ("yt-dlp", shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp", ["--version"]),
    ("gh", shutil.which("gh") or "/opt/homebrew/bin/gh", ["--version"]),
    ("curl-jina", "/usr/bin/curl", ["--version"]),
]


def probe_cdp_9223() -> dict[str, object]:
    try:
        with urllib.request.urlopen(os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")) + "/health", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        ok = bool(data.get("ok") and data.get("connected"))
        return {
            "channel": "cdp-9223",
            "binary": os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")) + "/health",
            "ok": ok,
            "version": f"{data.get('service', 'cdp-persistent-daemon')} (connected={data.get('connected')})",
        }
    except Exception as exc:
        return {"channel": "cdp-9223", "binary": os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")) + "/health", "ok": False, "detail": str(exc)}


def probe_channel(name: str, binary: str, args: list[str]) -> dict[str, object]:
    path = Path(binary)
    if not path.exists():
        return {"channel": name, "binary": binary, "ok": False, "detail": "binary_missing"}
    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        first_line = (proc.stdout or proc.stderr or "").strip().splitlines()
        return {
            "channel": name,
            "binary": binary,
            "ok": proc.returncode == 0,
            "version": first_line[0] if first_line else "",
        }
    except Exception as exc:
        return {"channel": name, "binary": binary, "ok": False, "detail": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-reach", description="Agent Reach local channel doctor")
    sub = parser.add_subparsers(dest="cmd")
    doc_p = sub.add_parser("doctor", help="Check channel availability")
    doc_p.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    ns = parser.parse_args()

    results = [probe_channel(name, binary, args) for name, binary, args in CHANNELS]
    results.append(probe_cdp_9223())
    report = {
        "status": "ok" if all(r["ok"] for r in results) else "degraded",
        "runtime": sys.executable,
        "channels": results,
    }
    if getattr(ns, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={report['status']} runtime={report['runtime']}")
        for item in results:
            state = "OK" if item["ok"] else "FAIL"
            print(f"  [{state}] {item['channel']:10s} -> {item['binary']} ({item.get('version') or item.get('detail', '')})")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
