#!/usr/bin/env python3
"""Read-only recursive share-tree size & file-count preflight for Quark Cloud Drive.

Zero write side effects and zero Cookie/Token stdout echo. Used prior to `save` or
`download` to enforce the 300 MiB single-file / 1 GiB share-tree confirmation gate.
"""
from __future__ import annotations

import collections
import json
import os
import sys
from quark_client import QuarkClient


def preflight_share(url: str) -> dict:
    client = QuarkClient()
    share_id, pwd = client.shares.parse_share_url(url)
    stoken = client.shares.get_share_token(share_id, pwd)
    files, dirs, total_bytes = 0, 0, 0
    exts: collections.Counter[str] = collections.Counter()
    max_single_bytes = 0
    stack = ["0"]

    while stack:
        pdir = stack.pop()
        page = 1
        while True:
            resp = client.api_client.get(
                "share/sharepage/detail",
                params={
                    "pwd_id": share_id,
                    "stoken": stoken,
                    "pdir_fid": pdir,
                    "force": "0",
                    "_page": page,
                    "_size": 100,
                    "_fetch_total": "1",
                },
                base_url=client.config.SHARE_BASE_URL,
            )
            items = (resp.get("data") or {}).get("list") or []
            for it in items:
                if it.get("dir") or it.get("file_type") == 0:
                    dirs += 1
                    stack.append(str(it["fid"]))
                else:
                    sz = int(it.get("size") or 0)
                    files += 1
                    total_bytes += sz
                    if sz > max_single_bytes:
                        max_single_bytes = sz
                    ext = os.path.splitext(it.get("file_name") or "")[1].lower() or "<noext>"
                    exts[ext] += 1
            if len(items) < 100:
                break
            page += 1

    return {
        "share_id": share_id,
        "dirs": dirs,
        "files": files,
        "total_bytes": total_bytes,
        "total_mib": round(total_bytes / 1048576, 2),
        "total_gib": round(total_bytes / 1073741824, 3),
        "max_single_mib": round(max_single_bytes / 1048576, 2),
        "over_300mib_single_gate": max_single_bytes >= 300 * 1048576,
        "over_1gib_gate": total_bytes >= 1073741824,
        "top_exts": dict(exts.most_common(8)),
    }


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: preflight_share_tree.py 'https://pan.quark.cn/s/<id>?pwd=<code>'")
        return 0 if len(sys.argv) == 2 else 2
    summary = preflight_share(sys.argv[1])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
