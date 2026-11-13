#!/usr/bin/env python3
"""Compatibility wrapper delegating to hackernews_search.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))
_TARGET = str(_DIR / 'hackernews_search.py')

if __name__ == "__main__":
    runpy.run_path(_TARGET, run_name="__main__")
else:
    globals().update(runpy.run_path(_TARGET, run_name=__name__))
