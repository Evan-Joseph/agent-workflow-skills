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
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

ANDROMELD_ADBKEY = Path.home() / "Library" / "Group Containers" / "group.com.catchingnow.andfiles.shared" / ".android" / "adbkey"


class AdbOpsError(RuntimeError):
    """Structured CLI error surfaced as clean JSON without a raw Python traceback."""

    def __init__(self, message: str, *, code: str = "adb_error", hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


def find_adb() -> str:
    env_bin = os.environ.get("ADB_BIN", "").strip()
    for candidate in [
        env_bin,
        "adb",
        os.path.expanduser("~/platform-tools/adb"),
        os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
        "/opt/homebrew/bin/adb",
        shutil.which("adb"),
    ]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise AdbOpsError(
        "未在标准路径或 PATH 中找到可用的 adb 可执行文件",
        code="adb_not_found",
        hint="请确认 adb 或 ~/platform-tools/adb 存在且具备可执行权限。",
    )


def build_adb_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(Path.home())
    env.setdefault("ADB_MDNS", "1")
    env.setdefault("ADB_MDNS_OPENSCREEN", "1")
    env.setdefault("ADB_MDNS_AUTO_CONNECT", "adb-tls-connect,adb")
    if ANDROMELD_ADBKEY.is_file() and not env.get("ADB_VENDOR_KEYS"):
        env["ADB_VENDOR_KEYS"] = str(ANDROMELD_ADBKEY)
    return env


def run_adb(args: List[str], serial: Optional[str] = None, binary: bool = False, timeout: int = 20):
    adb = find_adb()
    cmd = [adb]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        res = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            env=build_adb_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbOpsError(
            f"adb {' '.join(args)} 执行超时（>{timeout}s）",
            code="timeout",
            hint="请检查设备无线调试或 EasyTier Mesh 隧道连通性后重试。",
        ) from exc
    except OSError as exc:
        raise AdbOpsError(
            f"无法拉起 adb 进程: {exc}",
            code="exec_failed",
            hint="请确认 adb 二进制未损坏且权限正常。",
        ) from exc

    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace").strip() or res.stdout.decode("utf-8", errors="replace").strip()
        raise AdbOpsError(
            f"adb {' '.join(args)} failed (code {res.returncode}): {err or 'unknown error'}",
            code="adb_failed",
            hint="请核对目标序列号/端口（如 198.51.100.1:5552）及 USB/无线调试授权状态。",
        )
    return res.stdout if binary else res.stdout.decode("utf-8", errors="replace")


def list_serials() -> List[str]:
    out = run_adb(["devices"])
    serials = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def resolve_serial(explicit_serial: Optional[str]) -> str:
    if explicit_serial:
        return explicit_serial
    serials = list_serials()
    if not serials:
        raise AdbOpsError(
            "当前默认 ADB 池中 0 台设备在线",
            code="no_device",
            hint="请先通过 USB 或按需无线连接目标设备（主力机 S23U: -s 198.51.100.1:5552 / <LOOPBACK_HOST>:15552；小新平板: -s 198.51.100.1:5553；小米8默认隔离需显式传 -s 198.51.100.1:5555 或 <LOOPBACK_HOST>:15554）。",
        )
    if len(serials) > 1:
        raise AdbOpsError(
            f"检测到 {len(serials)} 台在线 ADB 设备: {', '.join(serials)}",
            code="multiple_devices",
            hint="请使用 -s <serial> 指定唯一目标设备后重试。",
        )
    return serials[0]


def _parse_battery_level(bat_out: str) -> Optional[int]:
    for line in bat_out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip() == "level":
                val = v.strip()
                if val.isdigit():
                    return int(val)
    return None


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
            bat_raw = run_adb(["shell", "dumpsys", "battery"], serial=s)
            devices.append(
                {
                    "serial": s,
                    "brand": brand,
                    "model": model,
                    "android_release": rel,
                    "sdk": sdk,
                    "wm_size": wm.replace("\n", "; "),
                    "battery_level": _parse_battery_level(bat_raw),
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
    serial = resolve_serial(args.serial)
    raw_png = run_adb(["exec-out", "screencap", "-p"], serial=serial, binary=True, timeout=25)
    if not raw_png:
        raise AdbOpsError(
            "adb exec-out screencap -p 返回空数据",
            code="screencap_empty",
            hint="设备当前可能拒绝截图（如系统安全界面或 FLAG_SECURE 窗口）。",
        )
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


def _extract_hierarchy_xml(raw_text: str) -> ET.Element:
    if not raw_text or not raw_text.strip():
        raise AdbOpsError(
            "uiautomator 未输出控件树 XML",
            code="ui_dump_empty",
            hint="当前界面可能处于锁屏、视频播放或持续动画状态，请稍候重试或改用 screencap。",
        )
    idx_xml = raw_text.find("<?xml")
    idx_hier = raw_text.find("<hierarchy")
    if idx_xml != -1 and (idx_hier == -1 or idx_xml < idx_hier):
        xml_slice = raw_text[idx_xml:]
    elif idx_hier != -1:
        xml_slice = raw_text[idx_hier:]
    else:
        snippet = raw_text.strip().splitlines()[0][:160]
        raise AdbOpsError(
            f"uiautomator 返回非 XML 内容: {snippet}",
            code="ui_dump_failed",
            hint="若界面存在连续动画/视频（常见 ERROR: could not get idle state），请改用 screencap。",
        )
    try:
        return ET.fromstring(xml_slice)
    except ET.ParseError as exc:
        raise AdbOpsError(
            f"控件树 XML 解析失败: {exc}",
            code="ui_dump_parse_error",
            hint="页面可能在导出中途发生切换，请重试 ui-dump 或改用 screencap。",
        ) from exc


def cmd_ui_dump(args: argparse.Namespace) -> int:
    serial = resolve_serial(args.serial)
    raw_out = run_adb(
        [
            "shell",
            "uiautomator dump /sdcard/window_dump.xml 2>&1; "
            "cat /sdcard/window_dump.xml 2>/dev/null; "
            "rm -f /sdcard/window_dump.xml >/dev/null 2>&1 || true",
        ],
        serial=serial,
        timeout=25,
    )
    root = _extract_hierarchy_xml(raw_out)
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
    serial = resolve_serial(args.serial)
    pm_args = ["shell", "pm", "list", "packages"]
    if args.state == "disabled":
        pm_args.append("-d")
    elif args.state == "enabled":
        pm_args.append("-e")
    elif args.state == "third-party":
        pm_args.append("-3")
    elif args.state == "system":
        pm_args.append("-s")

    out = run_adb(pm_args, serial=serial)
    pkgs = [line.replace("package:", "").strip() for line in out.splitlines() if line.strip()]
    if args.filter:
        pat = re.compile(args.filter, re.IGNORECASE)
        pkgs = [p for p in pkgs if pat.search(p)]
    pkgs.sort()
    print(json.dumps({"count": len(pkgs), "packages": pkgs}, ensure_ascii=False, indent=2))
    return 0


def cmd_battery_perf(args: argparse.Namespace) -> int:
    serial = resolve_serial(args.serial)
    bat = run_adb(["shell", "dumpsys", "battery"], serial=serial)
    mem = run_adb(["shell", "cat", "/proc/meminfo"], serial=serial)
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
    serial = resolve_serial(args.serial)
    comp_re = re.compile(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$]+)")
    package_name: Optional[str] = None
    activity_name: Optional[str] = None
    source_used = ""

    # 1. Try dumpsys activity activities for topResumedActivity / mResumedActivity
    act_out = run_adb(["shell", "dumpsys", "activity", "activities"], serial=serial, timeout=20)
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
        win_out = run_adb(["shell", "dumpsys", "window", "windows"], serial=serial, timeout=20)
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
            pm_out = run_adb(["shell", "pm", "path", package_name], serial=serial, timeout=15)
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
    try:
        return args.func(args)
    except AdbOpsError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": exc.code,
                    "error": str(exc),
                    "hint": exc.hint,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "system_error",
                    "error": str(exc),
                    "hint": "请检查系统命令与 ADB 服务连接状态。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
