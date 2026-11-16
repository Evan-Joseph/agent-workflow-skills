#!/usr/bin/env python3
"""Read-only, zero-dependency workstation baseline probe for AI coding agents."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys

TOOLS = ("git", "gh", "python3", "uv", "node", "npm", "pnpm", "cargo", "go", "docker", "ffmpeg")


def collect_baseline() -> dict[str, object]:
    found_tools = {name: shutil.which(name) for name in TOOLS if shutil.which(name)}
    proxy_vars = {
        k: bool(os.environ.get(k))
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
        if os.environ.get(k)
    }
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "proxy_env_present": proxy_vars,
        "available_tools": found_tools,
    }


if __name__ == "__main__":
    print(json.dumps(collect_baseline(), ensure_ascii=False, indent=2))
