#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic unit tests for adb_ops.py."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import adb_ops


class TestAdbOps(unittest.TestCase):
    def test_build_adb_env_and_find_adb_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake_adb = tmp / "adb"
            fake_adb.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_adb.chmod(fake_adb.stat().st_mode | stat.S_IXUSR)

            fake_key = tmp / "andromeld_adbkey"
            fake_key.write_text("KEY", encoding="utf-8")

            with mock.patch.dict(os.environ, {"ADB_BIN": str(fake_adb)}, clear=False), mock.patch.object(
                adb_ops, "ANDROMELD_ADBKEY", fake_key
            ):
                self.assertEqual(adb_ops.find_adb(), str(fake_adb))
                env = adb_ops.build_adb_env()
                self.assertEqual(env["ADB_MDNS_OPENSCREEN"], "1")
                self.assertEqual(env["ADB_VENDOR_KEYS"], str(fake_key))

    def test_devices_and_zero_or_multi_device_json_errors(self) -> None:
        script_path = Path(__file__).resolve().parent / "adb_ops.py"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            log_file = tmp / "adb_calls.log"
            stub = tmp / "fake_adb"
            stub.write_text(
                f"""#!/bin/sh
echo "$@" >> "{log_file}"
case "$*" in
  "devices")
    if [ "${{FAKE_MODE:-zero}}" = "zero" ]; then
      echo "List of devices attached"
    elif [ "${{FAKE_MODE}}" = "one" ]; then
      echo "List of devices attached"
      echo "<DEVICE_SERIAL>\tdevice"
      echo "<DEVICE_SERIAL>\toffline"
    else
      echo "List of devices attached"
      echo "<DEVICE_SERIAL>\tdevice"
      echo "<DEVICE_SERIAL>\tdevice"
    fi
    ;;
  *"getprop ro.product.model"*) echo "SM-S9180" ;;
  *"getprop ro.product.brand"*) echo "samsung" ;;
  *"getprop ro.build.version.sdk"*) echo "36" ;;
  *"getprop ro.build.version.release"*) echo "16" ;;
  *"wm size"*) echo "Physical size: 1440x3088" ;;
  *"dumpsys battery"*)
    echo "Current Battery Service state:"
    echo "  level: 84"
    echo "  temperature: 295"
    ;;
  *"shell uiautomator dump"*)
    if [ "${{FAKE_UIDUMP:-ok}}" = "idle_err" ]; then
      echo "ERROR: could not get idle state."
    else
      echo "UI hierchary dumped to: /sdcard/window_dump.xml"
      echo '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0"><node text="设置" content-desc="" resource-id="com.android.settings:id/title" clickable="true" bounds="[0,0][100,50]"/></hierarchy>'
    fi
    ;;
esac
exit 0
""",
                encoding="utf-8",
            )
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

            base_env = os.environ.copy()
            base_env["ADB_BIN"] = str(stub)

            # 1) zero devices: devices -> count 0; top-app -> structured error JSON, no Traceback
            p_zero_dev = subprocess.run(
                [sys.executable, str(script_path), "devices"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "zero"},
                timeout=10,
            )
            self.assertEqual(p_zero_dev.returncode, 0)
            self.assertEqual(json.loads(p_zero_dev.stdout)["count"], 0)

            p_zero_top = subprocess.run(
                [sys.executable, str(script_path), "top-app"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "zero"},
                timeout=10,
            )
            self.assertEqual(p_zero_top.returncode, 1)
            self.assertNotIn("Traceback", p_zero_top.stderr)
            err_zero = json.loads(p_zero_top.stdout)
            self.assertEqual(err_zero["status"], "error")
            self.assertEqual(err_zero["code"], "no_device")
            self.assertIn("S23U", err_zero["hint"])

            # 2) one device: devices includes battery_level + non_online_transports
            p_one = subprocess.run(
                [sys.executable, str(script_path), "devices"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "one"},
                timeout=10,
            )
            self.assertEqual(p_one.returncode, 0)
            one_doc = json.loads(p_one.stdout)
            self.assertEqual(one_doc["count"], 1)
            self.assertEqual(one_doc["devices"][0]["battery_level"], 84)
            self.assertEqual(one_doc["non_online_transports"][0]["state"], "offline")

            # 3) multiple devices without -s -> multiple_devices JSON error
            p_multi = subprocess.run(
                [sys.executable, str(script_path), "battery-perf"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "multi"},
                timeout=10,
            )
            self.assertEqual(p_multi.returncode, 1)
            err_multi = json.loads(p_multi.stdout)
            self.assertEqual(err_multi["code"], "multiple_devices")
            self.assertIn("-s", err_multi["hint"])

            # 4) ui-dump strips prefix text and cleans /sdcard/window_dump.xml
            p_ui_ok = subprocess.run(
                [sys.executable, str(script_path), "-s", "<DEVICE_SERIAL>", "ui-dump"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "one", "FAKE_UIDUMP": "ok"},
                timeout=10,
            )
            self.assertEqual(p_ui_ok.returncode, 0)
            ui_doc = json.loads(p_ui_ok.stdout)
            self.assertEqual(ui_doc["count"], 1)
            self.assertEqual(ui_doc["nodes"][0]["text"], "设置")
            self.assertIn("rm -f /sdcard/window_dump.xml", log_file.read_text(encoding="utf-8"))

            # 5) ui-dump non-XML failure -> friendly ui_dump_failed JSON without Traceback
            p_ui_err = subprocess.run(
                [sys.executable, str(script_path), "-s", "<DEVICE_SERIAL>", "ui-dump"],
                capture_output=True,
                text=True,
                env={**base_env, "FAKE_MODE": "one", "FAKE_UIDUMP": "idle_err"},
                timeout=10,
            )
            self.assertEqual(p_ui_err.returncode, 1)
            self.assertNotIn("Traceback", p_ui_err.stderr)
            err_ui = json.loads(p_ui_err.stdout)
            self.assertEqual(err_ui["code"], "ui_dump_failed")
            self.assertIn("screencap", err_ui["hint"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
