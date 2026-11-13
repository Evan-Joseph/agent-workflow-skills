#!/usr/bin/env python3
"""Unified ADB operations helper for the 5-device mobile ecosystem.

Features:
- devices: List connected ADB devices with model, Android version, screen size, and battery level.
- screencap: Capture screen via `adb exec-out screencap -p` and automatically downsample
  to a compact JPEG (<=1280px max dimension, quality 80, <120KB) so reading screenshots
  never bloats Antigravity conversation SQLite databases.
- ui-dump: Dump UI hierarchy XML via uiautomator and extract clickable/text nodes with bounds.
- packages: List or filter installed packages (enabled, disabled, third-party, system).
- battery-perf: Snapshot battery level, temperature, charging state, and memory info.
- top-app: Read-only inspection of the foreground package, top Activity, and APK path(s).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from PIL import Image


def find_adb() -> str:
    for candidate in [
        shutil.which("adb"),
        os.path.expanduser("~/platform-tools/adb"),
        "/opt/homebrew/bin/adb",
        os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
    ]:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("adb binary not found in PATH or standard locations")


def run_adb(args: List[str], serial: Optional[str] = None, binary: bool = False, timeout: int = 20):
    adb = find_adb()
    cmd = [adb]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"adb {' '.join(args)} failed (code {res.returncode}): {err}")
    return res.stdout if binary else res.stdout.decode("utf-8", errors="replace")


def list_serials() -> List[str]:
    out = run_adb(["devices"])
    serials = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def cmd_devices(args: argparse.Namespace) -> int:
    out = run_adb(["devices"])
    online_serials: List[str] = []
    other_states: List[dict] = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            if parts[1] == "device":
                online_serials.append(parts[0])
            else:
                other_states.append({"serial": parts[0], "state": parts[1]})
    serials = [args.serial] if getattr(args, "serial", None) else online_serials
    devices = []
    for s in serials:
        try:
            model = run_adb(["shell", "getprop", "ro.product.model"], serial=s).strip()
            brand = run_adb(["shell", "getprop", "ro.product.brand"], serial=s).strip()
            sdk = run_adb(["shell", "getprop", "ro.build.version.sdk"], serial=s).strip()
            rel = run_adb(["shell", "getprop", "ro.build.version.release"], serial=s).strip()
            wm = run_adb(["shell", "wm", "size"], serial=s).strip()
            devices.append(
                {
                    "serial": s,
                    "brand": brand,
                    "model": model,
                    "android_release": rel,
                    "sdk": sdk,
                    "wm_size": wm.replace("\n", "; "),
                }
            )
        except Exception as exc:
            devices.append({"serial": s, "error": str(exc)})
    payload = {"adb_binary": find_adb(), "count": len(devices), "devices": devices}
    if other_states:
        payload["non_online_transports"] = other_states
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_screencap(args: argparse.Namespace) -> int:
    raw_png = run_adb(["exec-out", "screencap", "-p"], serial=args.serial, binary=True, timeout=25)
    if not raw_png:
        raise RuntimeError("Empty output from adb exec-out screencap -p")
    img = Image.open(io.BytesIO(raw_png))
    orig_w, orig_h = img.size
    max_dim = args.max_dim
    if max(orig_w, orig_h) > max_dim:
        scale = max_dim / float(max(orig_w, orig_h))
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    else:
        new_w, new_h = orig_w, orig_h

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        img.convert("RGB").save(out_path, format="JPEG", quality=args.quality, optimize=True)
    else:
        img.save(out_path, optimize=True)

    size_kb = round(out_path.stat().st_size / 1024.0, 1)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(out_path),
                "original_size": f"{orig_w}x{orig_h}",
                "downsampled_size": f"{new_w}x{new_h}",
                "file_size_kb": size_kb,
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_ui_dump(args: argparse.Namespace) -> int:
    run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], serial=args.serial, timeout=25)
    xml_text = run_adb(["shell", "cat", "/sdcard/window_dump.xml"], serial=args.serial, timeout=15)
    root = ET.fromstring(xml_text)
    items = []
    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        res_id = (node.attrib.get("resource-id") or "").strip()
        bounds = (node.attrib.get("bounds") or "").strip()
        clickable = node.attrib.get("clickable") == "true"
        if text or desc or (clickable and res_id):
            items.append(
                {
                    "text": text,
                    "content_desc": desc,
                    "resource_id": res_id,
                    "clickable": clickable,
                    "bounds": bounds,
                }
            )
    print(json.dumps({"count": len(items), "nodes": items[: args.limit]}, ensure_ascii=False, indent=2))
    return 0


def cmd_packages(args: argparse.Namespace) -> int:
    pm_args = ["shell", "pm", "list", "packages"]
    if args.state == "disabled":
        pm_args.append("-d")
    elif args.state == "enabled":
        pm_args.append("-e")
    elif args.state == "third-party":
        pm_args.append("-3")
    elif args.state == "system":
        pm_args.append("-s")

    out = run_adb(pm_args, serial=args.serial)
    pkgs = [line.replace("package:", "").strip() for line in out.splitlines() if line.strip()]
    if args.filter:
        pat = re.compile(args.filter, re.IGNORECASE)
        pkgs = [p for p in pkgs if pat.search(p)]
    pkgs.sort()
    print(json.dumps({"count": len(pkgs), "packages": pkgs}, ensure_ascii=False, indent=2))
    return 0


def cmd_battery_perf(args: argparse.Namespace) -> int:
    bat = run_adb(["shell", "dumpsys", "battery"], serial=args.serial)
    mem = run_adb(["shell", "cat", "/proc/meminfo"], serial=args.serial)
    bat_info = {}
    for line in bat.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            if k in ("level", "status", "health", "temperature", "voltage", "AC powered", "USB powered"):
                bat_info[k] = v.strip()
    mem_info = {}
    for line in mem.splitlines()[:6]:
        if ":" in line:
            k, v = line.split(":", 1)
            mem_info[k.strip()] = v.strip()
    print(json.dumps({"battery": bat_info, "memory": mem_info}, ensure_ascii=False, indent=2))
    return 0


def cmd_top_app(args: argparse.Namespace) -> int:
    """Read-only probe of foreground package, resumed Activity, and APK installation paths."""
    comp_re = re.compile(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$]+)")
    package_name: Optional[str] = None
    activity_name: Optional[str] = None
    source_used = ""

    # 1. Try dumpsys activity activities for topResumedActivity / mResumedActivity
    act_out = run_adb(["shell", "dumpsys", "activity", "activities"], serial=args.serial, timeout=20)
    for marker in ("topResumedActivity", "mResumedActivity", "ResumedActivity"):
        for line in act_out.splitlines():
            if marker in line:
                m = comp_re.search(line)
                if m:
                    package_name, raw_cls = m.group(1), m.group(2)
                    activity_name = f"{package_name}{raw_cls}" if raw_cls.startswith(".") else raw_cls
                    source_used = f"dumpsys activity activities ({marker})"
                    break
        if package_name:
            break

    # 2. Fallback to dumpsys window (mCurrentFocus / mFocusedApp) for older ROMs (e.g. Android 5.1 502SH)
    if not package_name:
        win_out = run_adb(["shell", "dumpsys", "window", "windows"], serial=args.serial, timeout=20)
        for marker in ("mCurrentFocus", "mFocusedApp"):
            for line in win_out.splitlines():
                if marker in line:
                    m = comp_re.search(line)
                    if m:
                        package_name, raw_cls = m.group(1), m.group(2)
                        activity_name = f"{package_name}{raw_cls}" if raw_cls.startswith(".") else raw_cls
                        source_used = f"dumpsys window ({marker})"
                        break
            if package_name:
                break

    apk_paths: List[str] = []
    if package_name:
        try:
            pm_out = run_adb(["shell", "pm", "path", package_name], serial=args.serial, timeout=15)
            apk_paths = [
                ln.replace("package:", "", 1).strip()
                for ln in pm_out.splitlines()
                if ln.strip().startswith("package:")
            ]
        except Exception:
            apk_paths = []

    print(
        json.dumps(
            {
                "status": "ok" if package_name else "unknown",
                "package": package_name,
                "activity": activity_name,
                "component": f"{package_name}/{activity_name}" if package_name and activity_name else None,
                "apk_paths": apk_paths,
                "detected_via": source_used or None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified ADB helper for mobile-device-ops")
    parser.add_argument("-s", "--serial", help="Target ADB device serial (optional if only 1 connected)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dev = sub.add_parser("devices", aliases=["status"], help="List connected ADB devices and basic metadata")
    p_dev.set_defaults(func=cmd_devices)

    p_cap = sub.add_parser("screencap", help="Capture and downsample screenshot to prevent DB bloat")
    p_cap.add_argument("--out", "-o", default="/tmp/adb_screen.jpg", help="Output image path (.jpg recommended)")
    p_cap.add_argument("--max-dim", type=int, default=1280, help="Max width/height in pixels (default: 1280)")
    p_cap.add_argument("--quality", type=int, default=80, help="JPEG quality (default: 80)")
    p_cap.set_defaults(func=cmd_screencap)

    p_ui = sub.add_parser("ui-dump", help="Dump clickable/text UI nodes via uiautomator")
    p_ui.add_argument("--limit", "-n", type=int, default=120, help="Max nodes to print")
    p_ui.set_defaults(func=cmd_ui_dump)

    p_pkg = sub.add_parser("packages", help="List or filter packages")
    p_pkg.add_argument(
        "--state",
        choices=["all", "enabled", "disabled", "third-party", "system"],
        default="all",
        help="Package state filter",
    )
    p_pkg.add_argument("--filter", "-f", help="Regex substring filter")
    p_pkg.set_defaults(func=cmd_packages)

    p_bat = sub.add_parser("battery-perf", help="Snapshot battery and memory status")
    p_bat.set_defaults(func=cmd_battery_perf)

    p_top = sub.add_parser("top-app", help="Read-only foreground package, Activity, and APK path(s)")
    p_top.set_defaults(func=cmd_top_app)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
