#!/usr/bin/env python3
"""Human-in-the-Loop macOS Notification Handoff for Browser Verification Gates.

Strictly adheres to anti-bot & focus-hygiene boundaries:
1. NEVER attempts to solve, click through, compute, or bypass any CAPTCHA / human challenge.
2. NEVER steals macOS foreground focus before the user explicitly clicks the notification banner.
3. Sends a visually clean macOS notification via `AgentHandoffNotifier.app` (`人机验证接力` custom
   shield `.icns` + `-contentImage`), whose click callback activates the exact `:9223` Chrome
   `targetId` (uncollapsing its `[Agent]` tab group if needed) and brings `Google Chrome.app`
   to the front (never Safari).
4. Silently polls read-only completion predicates via `${CDP_RELAY_URL}`:
   - Completed -> immediately removes the notification (`-remove <group>`) and returns `status="completed"`.
   - Timed out -> immediately removes the expired notification (`-remove <group>`), applies the
     configured `--on-timeout` tab hygiene policy (`collapse` | `close` | `cleanup-task` | `keep`),
     and returns `status="timeout"` so the caller can gracefully record `pending` / fallback.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

DEFAULT_CDP_URL = os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223"))
AUTHORIZED_BANNER_NOTIFIER_BIN = pathlib.Path("~/.local/libexec/notifiers/SMSNotifier.app/Contents/MacOS/terminal-notifier").expanduser()
DEDICATED_HANDOFF_NOTIFIER_BIN = pathlib.Path("~/.local/libexec/notifiers/AgentHandoffNotifier.app/Contents/MacOS/terminal-notifier").expanduser()
FALLBACK_NOTIFIER_BIN = pathlib.Path("/opt/homebrew/bin/terminal-notifier")
DEFAULT_SHIELD_IMAGE = (
    pathlib.Path(__file__).resolve().parent / "assets" / "handoff-shield.png"
)
CHROME_APP = "Google Chrome"

AUTO_CHALLENGE_DETECT_JS = r"""(() => {
  const title = (document.title || '').toLowerCase();
  const url = (location.href || '').toLowerCase();
  const titleHit = (
    title.includes('just a moment') ||
    title.includes('attention required') ||
    title.includes('安全验证') ||
    title.includes('人机验证') ||
    title.includes('verify you are human')
  );
  const urlHit = (
    url.includes('/cdn-cgi/challenge') ||
    url.includes('__cf_chl') ||
    url.includes('/captcha')
  );
  const selectors = [
    'iframe[src*="challenges.cloudflare.com"]',
    'iframe[src*="turnstile"]',
    'iframe[src*="hcaptcha.com"]',
    'iframe[src*="google.com/recaptcha"]',
    '.cf-turnstile',
    '.h-captcha',
    '.g-recaptcha',
    '[class*="geetest_"]',
    '[class*="gocaptcha"]',
    '#challenge-running',
    '#challenge-stage'
  ];
  let domHit = false;
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) {
      const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 1, height: 1 };
      if (rect.width > 0 && rect.height > 0) {
        domHit = true;
        break;
      }
    }
  }
  return Boolean(titleHit || urlHit || domHit);
})()"""


def escape_notifier_text(value: str) -> str:
    """Escape leading '[' or '(' quirks in terminal-notifier argument parsing."""
    text = (value or "").strip()
    if text.startswith(("[", "(")):
        return "\\" + text
    return text


def http_json(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def resolve_target_tab(
    cdp_url: str,
    *,
    target_id: str | None = None,
    url_sub: str | None = None,
    task: str | None = None,
) -> dict[str, Any] | None:
    resp = http_json(cdp_url, "/tabs")
    tabs: list[dict[str, Any]] = resp.get("tabs") or []
    if target_id:
        for tab in tabs:
            if tab.get("targetId") == target_id:
                return tab
        return None
    if url_sub:
        for tab in tabs:
            if tab.get("isAgentTab") and url_sub in str(tab.get("url", "")):
                return tab
        for tab in tabs:
            if url_sub in str(tab.get("url", "")):
                return tab
        return None
    if task:
        matches = [t for t in tabs if t.get("task") == task]
        if matches:
            return matches[-1]
    return None


def eval_on_target(cdp_url: str, target_id: str, expression: str) -> Any:
    resp = http_json(
        cdp_url,
        "/eval",
        {"targetId": target_id, "expression": expression},
        timeout=6.0,
    )
    return ((resp.get("result") or {}).get("result") or {}).get("value")


def set_tab_group_collapsed_via_extension(
    cdp_url: str,
    target_url: str,
    *,
    target_id: str = "",
    collapsed: bool,
    activate_tab: bool,
) -> bool:
    """Use Chrome extension service_worker via :9223 /cdp to uncollapse/collapse group & focus tab."""
    try:
        targets = (
            http_json(cdp_url, "/cdp", {"method": "Target.getTargets", "params": {}})
            .get("result", {})
            .get("targetInfos", [])
        )
        sws = [
            t
            for t in targets
            if t.get("type") == "service_worker"
            and str(t.get("url", "")).startswith("chrome-extension://")
        ]
        sws.sort(
            key=lambda x: (
                0
                if "dpccigpgfdgoljglokjhlokmdnjfpfcl" in str(x.get("url", ""))
                else (1 if "hehggadaopoacecdllhhajmbjkdcmajg" in str(x.get("url", "")) else 2)
            )
        )
        for sw in sws:
            session_id = None
            try:
                att = http_json(
                    cdp_url,
                    "/cdp",
                    {"method": "Target.attachToTarget", "params": {"targetId": sw["targetId"], "flatten": True}},
                )
                session_id = (att.get("result") or {}).get("sessionId")
                if not session_id:
                    continue
                js = f"""(async () => {{
                  if (typeof chrome === 'undefined' || !chrome.tabs) return {{ ok: false }};
                  const tid = {json.dumps(target_id)};
                  const u = {json.dumps(target_url)};
                  let tab = null;
                  if (tid && chrome.debugger && chrome.debugger.getTargets) {{
                    const dbg = await chrome.debugger.getTargets();
                    const hit = dbg.find(t => t.id === tid);
                    if (hit && typeof hit.tabId === 'number') {{
                      tab = await chrome.tabs.get(hit.tabId).catch(() => null);
                    }}
                  }}
                  if (!tab && u) {{
                    const tabs = await chrome.tabs.query({{}});
                    tab = tabs.filter(t => t.url === u || t.pendingUrl === u).pop() || null;
                  }}
                  if (!tab) return {{ ok: false }};
                  if (chrome.tabGroups && typeof tab.groupId === 'number' && tab.groupId > -1) {{
                    await chrome.tabGroups.update(tab.groupId, {{ collapsed: { 'true' if collapsed else 'false' } }});
                  }}
                  if ({ 'true' if activate_tab else 'false' }) {{
                    await chrome.tabs.update(tab.id, {{ active: true }});
                    if (chrome.windows && typeof tab.windowId === 'number') {{
                      await chrome.windows.update(tab.windowId, {{ focused: true }});
                    }}
                  }}
                  return {{ ok: true }};
                }})()"""
                ev = http_json(
                    cdp_url,
                    "/cdp",
                    {
                        "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "awaitPromise": True},
                        "sessionId": session_id,
                    },
                )
                val = (((ev.get("result") or {}).get("result") or {}).get("value")) or {}
                http_json(
                    cdp_url,
                    "/cdp",
                    {"method": "Target.detachFromTarget", "params": {"sessionId": session_id}},
                )
                if val.get("ok"):
                    return True
            except Exception:
                if session_id:
                    try:
                        http_json(
                            cdp_url,
                            "/cdp",
                            {"method": "Target.detachFromTarget", "params": {"sessionId": session_id}},
                        )
                    except Exception:
                        pass
    except Exception:
        pass
    return False


def focus_target_and_open_chrome(
    cdp_url: str,
    target_id: str,
    fallback_url: str = "",
    open_runner: Callable[[list[str]], Any] | None = None,
) -> dict[str, Any]:
    """Executed ONLY when the user clicks the macOS notification banner."""
    runner = open_runner or (
        lambda cmd: subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    )
    tab = None
    try:
        tab = resolve_target_tab(cdp_url, target_id=target_id)
    except Exception:
        tab = None

    if tab:
        tab_url = str(tab.get("url") or fallback_url or "")
        set_tab_group_collapsed_via_extension(
            cdp_url,
            tab_url,
            target_id=target_id,
            collapsed=False,
            activate_tab=True,
        )
        try:
            http_json(
                cdp_url,
                "/cdp",
                {
                    "method": "Target.activateTarget",
                    "allowFocus": True,
                    "params": {"targetId": target_id, "allowFocus": True},
                },
            )
            att = http_json(
                cdp_url,
                "/cdp",
                {"method": "Target.attachToTarget", "params": {"targetId": target_id, "flatten": True}},
            )
            sid = (att.get("result") or {}).get("sessionId")
            if sid:
                http_json(
                    cdp_url,
                    "/cdp",
                    {
                        "method": "Page.bringToFront",
                        "sessionId": sid,
                        "allowFocus": True,
                        "params": {"allowFocus": True},
                    },
                )
        except Exception:
            pass
        runner(["/usr/bin/open", "-a", CHROME_APP])
        return {"ok": True, "focusedTargetId": target_id, "openedFallbackUrl": False}

    if fallback_url:
        runner(["/usr/bin/open", "-a", CHROME_APP, fallback_url])
        return {"ok": True, "focusedTargetId": None, "openedFallbackUrl": True}

    runner(["/usr/bin/open", "-a", CHROME_APP])
    return {"ok": True, "focusedTargetId": None, "openedFallbackUrl": False}


def pick_notifier_binary(explicit: str | None = None, host_mode: str = "auto") -> pathlib.Path:
    """Select notifier host binary.

    `auto` prioritizes `AgentHandoffNotifier.app` (`人机验证接力`, custom shield bundle icon),
    falling back to `SMSNotifier.app` and then `/opt/homebrew/bin/terminal-notifier`.
    """
    if explicit:
        return pathlib.Path(explicit).expanduser()
    if host_mode in ("sms", "mi8-sms"):
        candidates = (AUTHORIZED_BANNER_NOTIFIER_BIN, DEDICATED_HANDOFF_NOTIFIER_BIN)
    else:
        candidates = (DEDICATED_HANDOFF_NOTIFIER_BIN, AUTHORIZED_BANNER_NOTIFIER_BIN)
    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return FALLBACK_NOTIFIER_BIN


def is_dedicated_handoff_notifier(notifier_bin: pathlib.Path) -> bool:
    return "AgentHandoffNotifier.app" in str(notifier_bin)


def send_notification(
    notifier_bin: pathlib.Path,
    *,
    group_id: str,
    title: str,
    subtitle: str,
    message: str,
    execute_cmd: str,
    content_image: pathlib.Path | None = DEFAULT_SHIELD_IMAGE,
    explicit_content_image: bool = False,
    sound: str = "Pop",
) -> None:
    cmd = [
        str(notifier_bin),
        "-title",
        escape_notifier_text(title),
        "-subtitle",
        escape_notifier_text(subtitle),
        "-message",
        escape_notifier_text(message),
        "-group",
        group_id,
        "-execute",
        execute_cmd,
    ]
    # AgentHandoffNotifier.app already displays its custom shield .icns on the left;
    # omit -contentImage unless the caller explicitly passed --content-image.
    use_content_image = content_image and content_image.is_file() and (
        explicit_content_image or not is_dedicated_handoff_notifier(notifier_bin)
    )
    if use_content_image:
        cmd.extend(["-contentImage", str(content_image)])
    if sound and sound.lower() != "none":
        cmd.extend(["-sound", sound])
    subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10, check=True)


def remove_notification(notifier_bin: pathlib.Path, group_id: str) -> None:
    try:
        subprocess.run(
            [str(notifier_bin), "-remove", group_id],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


def build_completion_checker(
    args: argparse.Namespace,
    initial_url: str,
    initial_auto_challenge: bool,
) -> Callable[[str, str], bool]:
    """Return `check(cdp_url, current_url) -> bool` using read-only predicates."""
    has_explicit = bool(
        args.wait_selector_gone
        or args.wait_selector
        or args.wait_url_change
        or args.wait_url_contains
        or args.wait_url_not_contains
        or args.wait_js
    )

    def _norm_url(u: str) -> str:
        p = urllib.parse.urlsplit(u)
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))

    init_norm = _norm_url(initial_url)

    def _check(cdp_url: str, target_id: str, current_url: str) -> bool:
        if not has_explicit:
            url_changed = _norm_url(current_url) != init_norm
            if initial_auto_challenge:
                still_challenged = bool(eval_on_target(cdp_url, target_id, AUTO_CHALLENGE_DETECT_JS))
                return not still_challenged
            return url_changed

        if args.wait_url_change and _norm_url(current_url) == init_norm:
            return False
        if args.wait_url_contains and args.wait_url_contains not in current_url:
            return False
        if args.wait_url_not_contains and args.wait_url_not_contains in current_url:
            return False
        for sel in args.wait_selector_gone or []:
            expr = f"document.querySelector({json.dumps(sel)}) === null"
            if not bool(eval_on_target(cdp_url, target_id, expr)):
                return False
        for sel in args.wait_selector or []:
            expr = f"document.querySelector({json.dumps(sel)}) !== null"
            if not bool(eval_on_target(cdp_url, target_id, expr)):
                return False
        if args.wait_js:
            expr = f"Boolean({args.wait_js})"
            if not bool(eval_on_target(cdp_url, target_id, expr)):
                return False
        return True

    return _check  # type: ignore[return-value]


def apply_timeout_policy(
    cdp_url: str,
    policy: str,
    target_id: str,
    current_url: str,
    task: str | None,
) -> str:
    if policy == "close":
        try:
            http_json(cdp_url, "/close", {"targetId": target_id})
            return "closed_tab"
        except Exception:
            return "close_failed"
    if policy == "cleanup-task" and task:
        try:
            http_json(cdp_url, "/cleanup", {"task": task})
            return f"cleaned_task:{task}"
        except Exception:
            return "cleanup_failed"
    if policy == "collapse":
        collapsed = set_tab_group_collapsed_via_extension(
            cdp_url, current_url, target_id=target_id, collapsed=True, activate_tab=False
        )
        return "collapsed_group" if collapsed else "kept_background_tab"
    return "kept_background_tab"


def run_handoff(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    notifier_bin = pick_notifier_binary(args.notifier_bin, getattr(args, "notifier_host", "auto"))

    if args.remove_only:
        if not args.group:
            return 2, {"ok": False, "status": "error", "error": "--group is required with --remove-only"}
        remove_notification(notifier_bin, args.group)
        return 0, {"ok": True, "status": "removed", "group": args.group}

    if getattr(args, "cdp_approval_alert", False):
        group_id = args.group or "chrome-cdp-remote-debug-approval"
        title = args.title or "Chrome 远程调试需点一次允许"
        subtitle = args.subtitle or "${CDP_RELAY_HOST} 持久中继 · 单连接不叠窗"
        message = (
            args.message
            or "后台任务请求建立唯一 Chrome 远程调试持久连接，点击横幅切至 Chrome 点选一次「允许」后自动恢复。"
        )
        exec_cmd = f'/usr/bin/open -a "{CHROME_APP}"'
        send_notification(
            notifier_bin,
            group_id=group_id,
            title=title,
            subtitle=subtitle,
            message=message,
            execute_cmd=exec_cmd,
            content_image=pathlib.Path(args.content_image) if args.content_image else DEFAULT_SHIELD_IMAGE,
            explicit_content_image=bool(args.content_image),
            sound="none" if args.no_sound else args.sound,
        )
        return 0, {"ok": True, "status": "cdp_approval_notified", "group": group_id}

    if args.focus_target:
        focus_group = args.group or f"agent-handoff-{args.focus_target[:12]}"
        remove_notification(notifier_bin, focus_group)
        res = focus_target_and_open_chrome(args.cdp_url, args.focus_target, args.url or "")
        return 0, {"status": "focused", "removedGroup": focus_group, **res}

    tab = resolve_target_tab(
        args.cdp_url,
        target_id=args.target_id,
        url_sub=args.url_sub,
        task=args.task,
    )
    if not tab:
        return 1, {
            "ok": False,
            "status": "target_not_found",
            "error": "No matching Chrome tab found on :9223 relay",
        }

    target_id = str(tab["targetId"])
    initial_url = str(tab.get("url") or args.url or "")
    resolved_task = str(tab.get("task") or args.task or "")
    host = urllib.parse.urlsplit(initial_url).netloc or "Chrome"
    group_id = args.group or f"agent-handoff-{target_id[:12]}"

    title = args.title or "需要人工完成人机验证"
    subtitle = args.subtitle or f"{host} · 点击直达 Chrome 验证页"
    message = args.message or "检测到自动流程无法代劳的验证码/安全校验，点击横幅切换至对应标签页完成后将自动继续。"

    exec_parts = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "--focus-target",
        target_id,
        "--group",
        group_id,
        "--cdp-url",
        args.cdp_url,
    ]
    if args.notifier_bin:
        exec_parts.extend(["--notifier-bin", args.notifier_bin])
    if initial_url:
        exec_parts.extend(["--url", initial_url])
    execute_cmd = shlex.join(exec_parts)

    # Extend TTL reaper lease on :9223 during active human handoff
    try:
        lease_ms = int(max(60.0, float(args.timeout) + 30.0) * 1000)
        http_json(args.cdp_url, "/handoff", {"targetId": target_id, "leaseMs": lease_ms})
    except Exception:
        pass

    initial_challenge = False
    try:
        initial_challenge = bool(eval_on_target(args.cdp_url, target_id, AUTO_CHALLENGE_DETECT_JS))
    except Exception:
        initial_challenge = False

    checker = build_completion_checker(args, initial_url, initial_challenge)
    start_ts = time.monotonic()

    interrupted = False

    def _handle_sig(_signum: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    old_int = signal.signal(signal.SIGINT, _handle_sig)
    old_term = signal.signal(signal.SIGTERM, _handle_sig)

    try:
        send_notification(
            notifier_bin,
            group_id=group_id,
            title=title,
            subtitle=subtitle,
            message=message,
            execute_cmd=execute_cmd,
            content_image=pathlib.Path(args.content_image) if args.content_image else DEFAULT_SHIELD_IMAGE,
            explicit_content_image=bool(args.content_image),
            sound="none" if args.no_sound else args.sound,
        )

        if args.no_poll:
            return 0, {
                "ok": True,
                "status": "notified",
                "group": group_id,
                "targetId": target_id,
                "url": initial_url,
            }

        deadline = start_ts + max(1.0, float(args.timeout))
        last_url = initial_url
        while time.monotonic() < deadline and not interrupted:
            time.sleep(max(0.2, float(args.poll_interval)))
            if interrupted:
                break
            live_tab = resolve_target_tab(args.cdp_url, target_id=target_id)
            if not live_tab:
                return 0, {
                    "ok": False,
                    "status": "tab_closed",
                    "group": group_id,
                    "targetId": target_id,
                    "url": last_url,
                    "elapsedSec": round(time.monotonic() - start_ts, 2),
                }
            last_url = str(live_tab.get("url") or last_url)
            try:
                if checker(args.cdp_url, target_id, last_url):
                    return 0, {
                        "ok": True,
                        "status": "completed",
                        "group": group_id,
                        "targetId": target_id,
                        "url": last_url,
                        "elapsedSec": round(time.monotonic() - start_ts, 2),
                    }
            except Exception:
                # Transient navigation / execution context destroy during redirect: continue polling
                continue

        if interrupted:
            return 130, {
                "ok": False,
                "status": "interrupted",
                "group": group_id,
                "targetId": target_id,
                "url": last_url,
                "elapsedSec": round(time.monotonic() - start_ts, 2),
            }

        action_taken = apply_timeout_policy(
            args.cdp_url,
            args.on_timeout,
            target_id,
            last_url,
            resolved_task or None,
        )
        rc = 124 if args.exit_nonzero_on_timeout else 0
        return rc, {
            "ok": False,
            "status": "timeout",
            "onTimeout": args.on_timeout,
            "actionTaken": action_taken,
            "group": group_id,
            "targetId": target_id,
            "url": last_url,
            "elapsedSec": round(time.monotonic() - start_ts, 2),
        }
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)
        if not args.no_poll:
            try:
                http_json(args.cdp_url, "/handoff", {"targetId": target_id, "clear": True})
            except Exception:
                pass
            remove_notification(notifier_bin, group_id)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Send macOS human-verification handoff notification bound to :9223 Chrome tab and poll completion."
    )
    p.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Persistent CDP relay base URL (default: ${CDP_RELAY_URL})")
    p.add_argument("--target-id", help="Exact CDP targetId of the tab awaiting human verification")
    p.add_argument("--url-sub", help="Substring to match target tab URL on :9223")
    p.add_argument("--task", help="Agent task name registered on :9223")
    p.add_argument("--url", help="Fallback URL if target tab no longer exists when clicked")
    p.add_argument("--group", help="Custom NotificationCenter group ID (default: agent-handoff-<targetId[:12]>)")
    p.add_argument("--title", default="", help="Notification banner title")
    p.add_argument("--subtitle", default="", help="Notification banner subtitle")
    p.add_argument("--message", default="", help="Notification body text")
    p.add_argument("--sound", default="Pop", help="macOS sound name or 'none' (default: Pop)")
    p.add_argument("--no-sound", action="store_true", help="Send banner silently without sound")
    p.add_argument("--content-image", default="", help="Optional path to right-side badge image")
    p.add_argument(
        "--notifier-host",
        choices=("auto", "sms", "mi8-sms", "handoff"),
        default="auto",
        help="Notifier bundle host: 'auto' defaults to AgentHandoffNotifier.app (3.1.0, Alerts); 'sms' (alias 'mi8-sms') uses SMSNotifier.app (Banners); 'handoff' forces AgentHandoffNotifier.app",
    )
    p.add_argument("--notifier-bin", default="", help="Override terminal-notifier binary path")

    p.add_argument("--wait-selector-gone", action="append", default=[], help="Complete when CSS selector disappears (repeatable)")
    p.add_argument("--wait-selector", action="append", default=[], help="Complete when CSS selector appears (repeatable)")
    p.add_argument("--wait-url-change", action="store_true", help="Complete when tab URL changes from initial challenge URL")
    p.add_argument("--wait-url-contains", default="", help="Complete when tab URL contains substring")
    p.add_argument("--wait-url-not-contains", default="", help="Complete when tab URL no longer contains substring")
    p.add_argument("--wait-js", default="", help="Read-only JS boolean expression that evaluates truthy upon completion")

    p.add_argument("--timeout", type=float, default=180.0, help="Max wait seconds before auto-clearing notification (default: 180)")
    p.add_argument("--poll-interval", type=float, default=2.0, help="Read-only poll interval in seconds (default: 2.0)")
    p.add_argument(
        "--on-timeout",
        choices=("collapse", "close", "cleanup-task", "keep"),
        default="collapse",
        help="Tab hygiene action when user is away and notification times out (default: collapse)",
    )
    p.add_argument("--exit-nonzero-on-timeout", action="store_true", help="Exit with code 124 on timeout instead of 0")
    p.add_argument("--no-poll", action="store_true", help="Send notification only and return immediately without polling")
    p.add_argument("--remove-only", action="store_true", help="Remove an existing notification by --group and exit")
    p.add_argument("--cdp-approval-alert", action="store_true", help="Send single deduplicated Chrome remote-debugging approval notification and exit")
    p.add_argument("--focus-target", help=argparse.SUPPRESS)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    rc, payload = run_handoff(args)
    print(json.dumps(payload, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
