#!/usr/bin/env python3
"""Unit and mock-relay tests for notify_human_handoff.py.

Guarantees zero focus stealing and zero interaction with live Chrome (:9223) during tests.
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import threading
import unittest

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "notify_human_handoff.py"
SPEC = importlib.util.spec_from_file_location("notify_human_handoff", SCRIPT_PATH)
MOD = importlib.util.module_from_spec(SPEC)  # type: ignore[arg-type]
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class _MockCDPState:
    def __init__(self) -> None:
        self.tabs = [
            {
                "targetId": "TAB_MOCK_1234567890",
                "title": "Just a moment...",
                "url": "https://verify.example.com/challenge",
                "isAgentTab": True,
                "task": "unit-handoff",
            }
        ]
        self.challenge_present = True
        self.activated_targets: list[str] = []
        self.cdp_calls: list[dict] = []
        self.closed_targets: list[str] = []
        self.cleaned_tasks: list[str] = []


class HumanHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log_file = pathlib.Path(self.tmp.name) / "notifier_calls.jsonl"
        self.fake_notifier = pathlib.Path(self.tmp.name) / "fake-notifier"
        self.fake_notifier.write_text(
            f"""#!/usr/bin/env python3
import json, sys
with open({json.dumps(str(self.log_file))}, "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")
""",
            encoding="utf-8",
        )
        self.fake_notifier.chmod(self.fake_notifier.stat().st_mode | stat.S_IXUSR)

        self.state = _MockCDPState()
        state = self.state

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):  # noqa: D401
                return

            def _send(self, obj: dict) -> None:
                raw = json.dumps(obj).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/tabs":
                    self._send({"ok": True, "tabs": list(state.tabs)})
                else:
                    self._send({"ok": True})

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                if self.path == "/eval":
                    expr = body.get("expression", "")
                    if "challenges.cloudflare.com" in expr or "just a moment" in expr:
                        val = state.challenge_present
                    elif "=== null" in expr:
                        val = not state.challenge_present
                    else:
                        val = not state.challenge_present
                    self._send({"result": {"result": {"value": val}}})
                elif self.path == "/cdp":
                    state.cdp_calls.append(body)
                    if body.get("method") == "Target.activateTarget":
                        state.activated_targets.append(body["params"]["targetId"])
                        self._send({"result": {}})
                    elif body.get("method") == "Target.attachToTarget":
                        self._send({"result": {"sessionId": "MOCK_SESSION_1"}})
                    elif body.get("method") == "Page.bringToFront":
                        self._send({"result": {}})
                    else:
                        self._send({"result": {"targetInfos": []}})
                elif self.path == "/close":
                    tid = body.get("targetId")
                    state.closed_targets.append(tid)
                    state.tabs = [t for t in state.tabs if t["targetId"] != tid]
                    self._send({"ok": True})
                elif self.path == "/cleanup":
                    tsk = body.get("task")
                    state.cleaned_tasks.append(tsk)
                    state.tabs = [t for t in state.tabs if t.get("task") != tsk]
                    self._send({"ok": True})
                else:
                    self._send({"ok": True})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.cdp_url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def _read_notifier_calls(self) -> list[list[str]]:
        if not self.log_file.exists():
            return []
        return [json.loads(line) for line in self.log_file.read_text("utf-8").splitlines() if line.strip()]

    def test_escape_leading_bracket(self) -> None:
        self.assertEqual(MOD.escape_notifier_text("[Agent] 请验证"), "\\[Agent] 请验证")
        self.assertEqual(MOD.escape_notifier_text("普通标题"), "普通标题")

    def test_notifier_host_prefers_dedicated_handoff_bundle_as_priority_one(self) -> None:
        if MOD.DEDICATED_HANDOFF_NOTIFIER_BIN.is_file():
            self.assertEqual(MOD.pick_notifier_binary(None, "auto"), MOD.DEDICATED_HANDOFF_NOTIFIER_BIN)
            self.assertEqual(MOD.pick_notifier_binary(None, "handoff"), MOD.DEDICATED_HANDOFF_NOTIFIER_BIN)
        if MOD.AUTHORIZED_BANNER_NOTIFIER_BIN.is_file():
            self.assertEqual(MOD.pick_notifier_binary(None, "sms"), MOD.AUTHORIZED_BANNER_NOTIFIER_BIN)
            self.assertEqual(MOD.pick_notifier_binary(None, "mi8-sms"), MOD.AUTHORIZED_BANNER_NOTIFIER_BIN)

    def test_dedicated_handoff_notifier_omits_duplicate_content_image(self) -> None:
        app_dir = pathlib.Path(self.tmp.name) / "AgentHandoffNotifier.app" / "Contents" / "MacOS"
        app_dir.mkdir(parents=True, exist_ok=True)
        fake_handoff_bin = app_dir / "terminal-notifier"
        fake_handoff_bin.write_text(self.fake_notifier.read_text("utf-8"), encoding="utf-8")
        fake_handoff_bin.chmod(fake_handoff_bin.stat().st_mode | stat.S_IXUSR)

        MOD.send_notification(
            fake_handoff_bin,
            group_id="grp-1",
            title="验证",
            subtitle="副标题",
            message="正文",
            execute_cmd="/usr/bin/true",
            sound="none",
        )
        calls = self._read_notifier_calls()
        self.assertEqual(len(calls), 1)
        self.assertNotIn("-contentImage", calls[0])

        # Non-AgentHandoffNotifier still includes shield contentImage when file exists
        self.log_file.unlink(missing_ok=True)
        MOD.send_notification(
            self.fake_notifier,
            group_id="grp-2",
            title="验证",
            subtitle="副标题",
            message="正文",
            execute_cmd="/usr/bin/true",
            sound="none",
        )
        calls2 = self._read_notifier_calls()
        if MOD.DEFAULT_SHIELD_IMAGE.is_file():
            self.assertIn("-contentImage", calls2[0])

    def test_completion_clears_notification_and_never_steals_focus(self) -> None:
        def clear_soon() -> None:
            threading.Event().wait(0.35)
            self.state.challenge_present = False
            self.state.tabs[0]["title"] = "Dashboard"
            self.state.tabs[0]["url"] = "https://verify.example.com/dashboard"

        threading.Thread(target=clear_soon, daemon=True).start()
        args = MOD.build_arg_parser().parse_args(
            [
                "--cdp-url",
                self.cdp_url,
                "--url-sub",
                "verify.example.com",
                "--wait-selector-gone",
                ".cf-turnstile",
                "--timeout",
                "3",
                "--poll-interval",
                "0.2",
                "--no-sound",
                "--notifier-bin",
                str(self.fake_notifier),
            ]
        )
        rc, res = MOD.run_handoff(args)
        self.assertEqual(rc, 0)
        self.assertEqual(res["status"], "completed")
        # Must NOT have activated target during background poll!
        self.assertEqual(self.state.activated_targets, [])
        calls = self._read_notifier_calls()
        self.assertEqual(len(calls), 2)
        self.assertIn("-execute", calls[0])
        exec_idx = calls[0].index("-execute") + 1
        self.assertIn("--focus-target TAB_MOCK_1234567890", calls[0][exec_idx])
        self.assertEqual(calls[1], ["-remove", "agent-handoff-TAB_MOCK_123"])

    def test_timeout_removes_notification_and_applies_close_policy(self) -> None:
        args = MOD.build_arg_parser().parse_args(
            [
                "--cdp-url",
                self.cdp_url,
                "--target-id",
                "TAB_MOCK_1234567890",
                "--wait-selector-gone",
                ".cf-turnstile",
                "--timeout",
                "0.5",
                "--poll-interval",
                "0.2",
                "--on-timeout",
                "close",
                "--no-sound",
                "--notifier-bin",
                str(self.fake_notifier),
            ]
        )
        rc, res = MOD.run_handoff(args)
        self.assertEqual(rc, 0)
        self.assertEqual(res["status"], "timeout")
        self.assertEqual(res["actionTaken"], "closed_tab")
        self.assertEqual(self.state.closed_targets, ["TAB_MOCK_1234567890"])
        calls = self._read_notifier_calls()
        self.assertEqual(calls[-1], ["-remove", "agent-handoff-TAB_MOCK_123"])

    def test_focus_callback_passes_allow_focus_and_removes_banner_immediately(self) -> None:
        opened_cmds: list[list[str]] = []
        orig_open = MOD.focus_target_and_open_chrome
        try:
            MOD.focus_target_and_open_chrome = lambda cdp_url, tid, url="": orig_open(  # type: ignore[assignment]
                cdp_url, tid, url, open_runner=opened_cmds.append
            )
            args = MOD.build_arg_parser().parse_args(
                [
                    "--cdp-url",
                    self.cdp_url,
                    "--focus-target",
                    "TAB_MOCK_1234567890",
                    "--group",
                    "agent-handoff-click-test",
                    "--url",
                    "https://verify.example.com/challenge",
                    "--notifier-bin",
                    str(self.fake_notifier),
                ]
            )
            rc, res = MOD.run_handoff(args)
        finally:
            MOD.focus_target_and_open_chrome = orig_open  # type: ignore[assignment]

        self.assertEqual(rc, 0)
        self.assertTrue(res["ok"])
        self.assertEqual(res["removedGroup"], "agent-handoff-click-test")
        # Immediate banner removal on click
        self.assertEqual(self._read_notifier_calls(), [["-remove", "agent-handoff-click-test"]])
        # Explicit allowFocus: True sent on both Target.activateTarget and Page.bringToFront
        act_calls = [c for c in self.state.cdp_calls if c.get("method") == "Target.activateTarget"]
        front_calls = [c for c in self.state.cdp_calls if c.get("method") == "Page.bringToFront"]
        self.assertEqual(len(act_calls), 1)
        self.assertTrue(act_calls[0].get("allowFocus"))
        self.assertTrue(act_calls[0]["params"].get("allowFocus"))
        self.assertEqual(len(front_calls), 1)
        self.assertTrue(front_calls[0].get("allowFocus"))
        self.assertEqual(opened_cmds, [["/usr/bin/open", "-a", "Google Chrome"]])

        # Fallback when tab was closed: still explicitly binds Google Chrome
        opened_cmds.clear()
        res2 = MOD.focus_target_and_open_chrome(
            self.cdp_url,
            "MISSING_TAB",
            "https://verify.example.com/challenge",
            open_runner=opened_cmds.append,
        )
        self.assertTrue(res2["openedFallbackUrl"])
        self.assertEqual(
            opened_cmds,
            [["/usr/bin/open", "-a", "Google Chrome", "https://verify.example.com/challenge"]],
        )

    def test_remove_only_clears_banner_immediately(self) -> None:
        args = MOD.build_arg_parser().parse_args(
            [
                "--remove-only",
                "--group",
                "agent-handoff-manual-01",
                "--notifier-bin",
                str(self.fake_notifier),
            ]
        )
        rc, res = MOD.run_handoff(args)
        self.assertEqual(rc, 0)
        self.assertEqual(res["status"], "removed")
        self.assertEqual(self._read_notifier_calls(), [["-remove", "agent-handoff-manual-01"]])

    def test_tab_closed_mid_poll_clears_notification_cleanly(self) -> None:
        def close_soon() -> None:
            threading.Event().wait(0.25)
            self.state.tabs.clear()

        threading.Thread(target=close_soon, daemon=True).start()
        args = MOD.build_arg_parser().parse_args(
            [
                "--cdp-url",
                self.cdp_url,
                "--task",
                "unit-handoff",
                "--timeout",
                "2",
                "--poll-interval",
                "0.2",
                "--no-sound",
                "--notifier-bin",
                str(self.fake_notifier),
            ]
        )
        rc, res = MOD.run_handoff(args)
        self.assertEqual(rc, 0)
        self.assertEqual(res["status"], "tab_closed")
        calls = self._read_notifier_calls()
        self.assertEqual(calls[-1], ["-remove", "agent-handoff-TAB_MOCK_123"])

    def test_timeout_cleanup_task_policy(self) -> None:
        args = MOD.build_arg_parser().parse_args(
            [
                "--cdp-url",
                self.cdp_url,
                "--task",
                "unit-handoff",
                "--wait-url-contains",
                "/verified-ok",
                "--timeout",
                "0.4",
                "--poll-interval",
                "0.2",
                "--on-timeout",
                "cleanup-task",
                "--exit-nonzero-on-timeout",
                "--no-sound",
                "--notifier-bin",
                str(self.fake_notifier),
            ]
        )
        rc, res = MOD.run_handoff(args)
        self.assertEqual(rc, 124)
        self.assertEqual(res["status"], "timeout")
        self.assertEqual(res["actionTaken"], "cleaned_task:unit-handoff")
        self.assertEqual(self.state.cleaned_tasks, ["unit-handoff"])
        calls = self._read_notifier_calls()
        self.assertEqual(calls[-1], ["-remove", "agent-handoff-TAB_MOCK_123"])


if __name__ == "__main__":
    unittest.main()
