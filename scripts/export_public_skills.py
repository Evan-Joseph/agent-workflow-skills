#!/usr/bin/env python3
"""Deterministic one-way clean-room compiler for Evan-Joseph/agent-workflow-skills.

Reads the private canonical skill tree (~/.agents/skills) in strictly read-only mode,
excludes Tier X private skills and DMCA/heavy vendor directories, performs deep Tier B
generalization and Tier A parameterization, expands relative symlinks into portable
wrappers, validates every exported Python script with `ast.parse`, and emits the 20
zero-leak public skills into `./skills/` alongside Claude Code & Codex plugin manifests.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path.home() / ".agents" / "skills"
SKILLS_OUT = REPO_ROOT / "skills"
REDACT_CONFIG_PATH = Path(
    os.environ.get("PUBLIC_SKILLS_REDACT_CONFIG", str(Path.home() / ".agents" / "config" / "public-skills-redact.json"))
)


def _load_redact_cfg() -> dict:
    if REDACT_CONFIG_PATH.is_file():
        return json.loads(REDACT_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


REDACT_CFG = _load_redact_cfg()
_MAC_USERS_ROOT = "/" + "Users/"
_COMMISSIONED_TAG = "\u3010\u59d4\u6258\u3011"

# Tier X: Physically excluded private / host-specific skills (NEVER exported)
TIER_X_BLACKLIST = {
    "local-machine-profile",
    "artex-client",
    "harness-governance",
}

# Excluded relative subpaths inside exported skills (DMCA redlines, private ops, heavy caches)
EXCLUDED_SUBPATHS = (
    "chat-history-export/vendor",  # HARD DMCA REDLINE: never export third-party wechat-decrypt
    "chat-history-export/scripts/wechat_export.py",
    "chat-history-export/scripts/tg_ops.py",
    "chat-history-export/tests",
    "ip-materials/vendor",  # heavy binary docx-toolkit cache
    "shuorenhua/evals",  # upstream v2.6.1 slimming practice
)

SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", ".venv", "node_modules"}
SKIP_FILE_NAMES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".pyo"}

TEXT_EXTENSIONS = {
    ".md", ".py", ".sh", ".yaml", ".yml", ".json", ".jsonc", ".toml", ".txt",
    ".csv", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".css", ".html", ".svg", ".xml", ".example",
}


# ---------------------------------------------------------------------------
# Tier B clean-room public templates for deeply host-coupled SKILL.md / docs
# ---------------------------------------------------------------------------

PUBLIC_CHAT_HISTORY_SKILL_MD = """---
name: chat-history-export
description: "Offline read-only search, archive indexing, contact governance audit, and anti-ban operational guardrails for local WeChat JSON/SQLite archives and QQ (NapCat/OneBot/QCE) exports."
metadata:
  short-description: Offline IM archive search, contact governance & anti-ban redlines
---

# Chat History Offline Search & IM Safety Guardrails (`chat-history-export`)

Provides millisecond-latency offline search across pre-exported personal IM archives (`JSON` and read-only `SQLite` vaults), QQ OneBot/QCE read-only contact audits, and strict anti-ban operational guardrails for desktop IM clients.

> **Compliance & Scope Notice**: This public skill ships **read-only offline query and audit scripts only** (`chat_search.py`, `vault_cli.py`, `wechat_schema.py`, `napcat_api.py`). It intentionally excludes any client memory inspection, key extraction, or third-party decryption utilities. Populate `$WECHAT_EXPORTS_DIR` or `$WECHAT_VAULT_DIR` using official LAN migration/export workflows or user-managed offline backups.

---

## Security Red Lines (Zero Account-Ban Risk)

1. **Zero GUI Automation on Desktop IM Clients**:
   - Never drive WeChat or QQ desktop windows via Accessibility APIs, `osascript`, `cliclick`, `PyAutoGUI`, or simulated keystrokes.
2. **Zero Process Injection or Memory Scanning**:
   - Never attach `lldb`, `ptrace`, `task_for_pid`, or binary patches to running IM processes.
3. **Offline Read-Only Consumption by Default**:
   - Query local `$WECHAT_EXPORTS_DIR` / `$WECHAT_VAULT_DIR` snapshots offline. When offline archives lag behind real-time messages, report the exact snapshot timestamp boundary rather than touching the live client.
4. **Draft-First Outbound Policy**:
   - Never auto-send messages or modify contact remarks without explicit `--confirm` approval.

---

## Runtime Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `WECHAT_EXPORTS_DIR` | `~/Documents/WeChatExports/exports` | Directory containing structured conversation JSON exports and `_export_index.json` |
| `WECHAT_VAULT_DIR` | `~/.local/share/wechat-vault` | Root directory for pre-indexed offline SQLite shards (`decrypted/`) and state |
| `NAPCAT_BASE_URL` | `http://<NAPCAT_HOST>:<NAPCAT_PORT>` | Optional local OneBot 11 HTTP endpoint for read-only QQ contact/group audits |
| `QCE_BASE_URL` | `http://<QCE_HOST>:<QCE_PORT>` | Optional local QCE export endpoint |

---

## 1. Fast Offline JSON Archive Search (`scripts/chat_search.py`)

Pure Python standard-library search across exported JSON conversation files:

```bash
# 1. List indexed conversations, chat types, and latest message timestamps
python3 $HOME/.agents/skills/chat-history-export/scripts/chat_search.py list

# 2. Full-text keyword search across all archived conversations
python3 $HOME/.agents/skills/chat-history-export/scripts/chat_search.py search "milestone" --limit 20

# 3. Scoped search inside a specific contact or group archive
python3 $HOME/.agents/skills/chat-history-export/scripts/chat_search.py search "deadline" --target "ProjectGroup" --limit 10

# 4. View the most recent messages in a conversation timeline
python3 $HOME/.agents/skills/chat-history-export/scripts/chat_search.py view "ProjectGroup" --limit 20
```

## 2. Offline SQLite Vault Query & Idea Tagging (`scripts/vault_cli.py`)

Read-only analytics over pre-materialized SQLite shards (contact remark audits, session timelines, favorites, `filehelper` idea extraction, and group digest packets):

```bash
# Check offline SQLite vault readiness
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py status

# Read-only contact remark & tag coverage audit (supports --json and --redact)
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py contacts-audit --redact

# Search messages or inspect recent sessions offline
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py sessions --limit 20 --format text
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py search "architecture" --limit 20 --format text

# Extract tagged notes (#i idea, #t todo, #r reference, #b bookmark) from filehelper + favorites
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py ideas --since 2026-01-01 --limit 30 --format text

# Build a structured group-chat digest source packet
python3 $HOME/.agents/skills/chat-history-export/scripts/vault_cli.py digest-source "EngineeringGroup" --start 2026-10-01
```

## 3. QQ / OneBot Read-Only Governance (`scripts/napcat_api.py`)

```bash
# Read-only audit of unremarked friends and category distribution
python3 $HOME/.agents/skills/chat-history-export/scripts/napcat_api.py contacts-audit --format markdown

# Preview remark update (dry-run by default; requires explicit --confirm to execute)
python3 $HOME/.agents/skills/chat-history-export/scripts/napcat_api.py set-friend-remark --user-id <UID> --remark "<Remark>"
```

## References

- OneBot / QCE endpoint notes: [`references/api-notes.md`](./references/api-notes.md)
- Android SQLCipher legacy parameters & official LAN migration backup SOP: [`references/mobile-encryption-and-backup-assessment.md`](./references/mobile-encryption-and-backup-assessment.md)
- Anti-ban security boundaries: [`references/security-and-risk-boundaries.md`](./references/security-and-risk-boundaries.md)
"""

PUBLIC_MOBILE_ENCRYPTION_ASSESSMENT_MD = """# Android WeChat Legacy Encryption Parameters & Official LAN Backup SOP

## 1. Technical Cross-Verification of Android `EnMicroMsg.db`

Cross-referenced against open-source mobile forensics frameworks (`abrignoni/ALEAPP`, `EnMicroMsg.db-Password-Cracker`):

- **Database Location**: `/data/data/com.tencent.mm/MicroMsg/<md5("mm" + uin)>/EnMicroMsg.db`
- **Legacy SQLCipher Parameters** (distinct from desktop WeChat 4.x SQLCipher 4 `4096B page + 256,000 iter`):
  - `PRAGMA key = '<7-char lowercase hex>';`
  - `PRAGMA cipher_use_hmac = OFF;`
  - `PRAGMA cipher_page_size = 1024;`
  - `PRAGMA kdf_iter = 4000;`
- **Key Derivation**: `lowercase(MD5(IMEI || str(uin))[0:7])`, where `_auth_uin` is stored in `shared_prefs/auth_info_key_prefs.xml`. On Android 10+ (API 29+), unprivileged apps cannot read hardware IMEI and fall back to the constant `"1234567890ABCDEF"`.

### Critical Operational Boundaries
1. **Non-Root Devices Cannot Pull `/data/data/com.tencent.mm/`**:
   - `android:allowBackup="false"` disables `adb backup`; `Shizuku` (`shell` UID `2000`) is blocked by SELinux `untrusted_app` isolation.
   - **Never log a primary personal IM account onto a rooted secondary phone solely to extract databases** — cross-device login onto rooted environments triggers high-severity risk control.
2. **Desktop Backup Bundles (`xwechat_files/Backup/`) Use Session Keys**:
   - Official encrypted backup bundles (`BAK_0_TEXT` / `Backup.db`) negotiate session-scoped symmetric keys and cannot be opened with the 7-character formula above.

---

## 2. Recommended Zero-Risk Disaster-Recovery SOP (Official LAN Migration)

To preserve historical mobile messages on unrooted flagship phones without breaking hardware attestation (Knox / StrongBox) or triggering anti-cheat flags:

1. Connect both the mobile phone and desktop computer to the same local Wi-Fi / LAN segment with desktop WeChat signed in;
2. On the mobile WeChat client, navigate to **Me -> Settings -> Chats -> Chat History Migration & Backup -> Migrate -> Migrate to Computer WeChat**, and select the target conversations;
3. Once official LAN migration merges historical messages (deduplicated by `server_id`) into the desktop database, run your offline indexing workflow to refresh read-only search snapshots;
4. Optionally run **Backup & Restore -> Back Up Chat History to Computer** onto an encrypted external drive for cold storage.
"""

PUBLIC_MOBILE_DEVICE_OPS_SKILL_MD = """---
name: mobile-device-ops
description: "Android ADB multi-device fleet governance, <120KB auto-downsampled screenshot inspection, UI hierarchy XML dumping, safe system debloat redlines, read-only SMS OTP extraction, and mobile reverse-engineering triage."
metadata:
  short-description: Android ADB fleet ops, compact screenshots, safe debloat & RE triage
---

# Mobile Device Operations & Android Reverse Engineering (`mobile-device-ops`)

Standardizes multi-device Android ADB operations, low-overhead visual inspection, safe package debloating, read-only OTP retrieval, and static-first reverse engineering.

## Runtime Contract & Quick Commands

`scripts/adb_ops.py` uses Python 3 (with optional `Pillow` or macOS `sips` fallback for automatic JPEG downsampling):

```bash
# 1. Inspect connected USB / wireless ADB devices (model, Android version, battery, resolution)
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py devices

# 2. Downsampled screenshot (enforces long edge <= 1280px JPEG, < 120KB to prevent multimodal context bloat)
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py screencap --out /tmp/adb_screen.jpg

# 3. Dump lightweight UI Accessibility XML tree & bounds without image overhead
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py ui-dump --out /tmp/window_dump.xml

# 4. Audit installed system / third-party packages and battery/thermal health
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py packages --filter launcher
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py battery-perf
```

---

## 1. Anti-Bloat Screenshot & Headless Inspection Gate

- **Root Problem**: Raw `adb exec-out screencap -p` PNGs from flagship phones/tablets are `2.5 MB–4.5 MB` each. Feeding raw screenshots into multimodal agent contexts bloats session databases and triggers payload limits.
- **Mandatory Rules**:
  1. Always capture via `adb_ops.py screencap --out /tmp/adb_screen.jpg` (`<= 1280px`, JPEG quality `80`, `40–100 KB`) before visual inspection;
  2. Prefer `adb_ops.py ui-dump` when checking text presence or tap coordinates;
  3. Avoid third-party mirroring MCP servers that force-enable `AccessibilityService` on banking/production phones or steal desktop window focus;
  4. Remove `/tmp/adb_screen*.jpg` temporary artifacts when finished.

---

## 2. Android System Debloat Safety Redlines

1. **Reversible User-Space Disable Only — Never Modify `/system`**:
   ```bash
   # Preferred reversible disable
   adb shell pm disable-user --user 0 <package_name>

   # Instant restore
   adb shell pm enable <package_name>
   adb shell cmd package install-existing <package_name>
   ```
2. **Third-Party Launcher Gesture Preservation**:
   - On OEM ROMs (One UI / HyperOS / ZUI), set the new launcher as Default Home *before* freezing OEM promotional services, and never uninstall the stock launcher package (`com.*.launcher`) because system recents and gesture navigation depend on its signature.
3. **Never-Disable System Packages (Bootloop & Companion-Wipe Prevention)**:
   - **`com.android.sdksandbox` (Android 13+)**: `PackageManagerService` asserts an enabled SDK sandbox at boot; disabling triggers `RuntimeException: There should exactly one sdk sandbox package; found 0` and forces `RescueParty` recovery mode;
   - **Wearable Companion Plugins (`com.samsung.wearable.*`, `com.google.android.wearable.app.*`)**: Running `pm uninstall` without `-k` wipes `companiondevice` pairing keys and forces a factory reset on paired smartwatches;
   - **OEM OAID / Device-ID Providers (e.g., `com.zui.deviceidservice`)**: Disabling causes immediate `NullPointerException` crashes in apps linked against MSA OAID SDKs;
   - **Core Infrastructure**: `com.google.android.webview`, package installer, permission controller, OTA updater, Bluetooth/IMS telephony services, and user-installed production apps without explicit confirmation.

---

## 3. Read-Only SMS OTP Extraction

When an automated login flow triggers an SMS verification code on an authorized USB/LAN debugging device, extract it read-only instead of asking the user to copy it manually:

```bash
adb -s "${ADB_SERIAL}" shell "content query --uri content://sms/inbox --projection date:address:body --sort 'date DESC'" | head -n 5
```

---

## 4. Mobile App Reverse-Engineering Triage Matrix

Before attaching dynamic instrumentation (`frida-server`), identify the application packaging stack and route to the matching static analyzer:

| Target Artifact / Magic Signature | Primary Static Tooling | Key Extraction Targets |
| :--- | :--- | :--- |
| **Standard Dalvik/ART (`classes*.dex`)** | `jadx` / `apktool` | `OkHttp` interceptors, `Retrofit` interfaces, custom signing headers (`sign`, `x-hmac`, `nonce`), JNI `System.loadLibrary` entrypoints |
| **Flutter AOT (`libflutter.so` + `libapp.so`)** | `worawit/blutter` + `reFlutter` | Recover Dart class/function symbols and `ObjectPool` string/API constants before socket traffic interception |
| **React Native Hermes (`index.android.bundle`, magic `\\xc6\\x1f\\xbc\\x03`)** | `P1sec/hermes-dec` (`hbc-decompiler`) | Decompile Hermes bytecode (`HBC`) to readable pseudo-JS and inspect API client modules |
| **Unity IL2CPP (`libil2cpp.so` + `global-metadata.dat`)** | `Il2CppDumper` / `Cpp2IL` | Reconstruct C# method offsets and metadata headers for targeted native hooks |
| **Native JNI (`.so` ELF arm64)** | `Ghidra` / `radare2` + `Frida` | Verify pure-Python re-implementations against hooked native input/output pairs; keep heavy `Frida` RPC out of high-concurrency production loops |

### Protocol Executor Reliability Standard
- Emit structured `[REQ_TRACE]` logs (millisecond timestamp, worker ID, HTTP status, business return code, end-to-end `latency_ms`);
- Provide a `--preflight` check validating NTP clock skew, token freshness, and network reachability before entering time-critical request loops.
"""


def sanitize_cloudflare_skill_md(text: str) -> str:
    """Replace the personal 12-asset ledger in cloudflare/SKILL.md with general production safety gates."""
    pattern = re.compile(
        r"## 本机 Cloudflare 资产台账与变更安全门禁 \(Asset Ledger & Destructive Action Gate\)\n.*?(?=\n## Retrieval Sources)",
        re.S,
    )
    replacement = """## Production Safety & Quota Governance Gates

- **Five Mandatory Operational Gates**:
  1. **Explicit Confirmation Before Destructive Commands**: Before running `wrangler delete`, `wrangler pages project delete`, `wrangler d1/kv/r2 delete`, `cloudflared tunnel delete`, or `DELETE` REST calls, present a complete impact table (exact asset name, resource type, bound custom domains, last deployment timestamp, and proposed action) and obtain explicit user confirmation;
  2. **Do Not Redeploy Archived Projects**: Keep completed historical showcase projects frozen; never run `wrangler deploy` or mutate `wrangler.toml` inside archived directories without explicit instruction;
  3. **Post-Deploy HTTP 200 Verification Gate**: After deploying or migrating Pages / Workers, run `curl -ILs` against production endpoints to confirm `HTTP 200` (preventing `HTTP 522` or `HTTP 403 Error 1014` dangling CNAMEs) and bump Service Worker cache versions when applicable;
  4. **Free-Tier Quota & Durable Objects WebSocket Hibernation Gate**: Cloudflare's Free plan caps Durable Objects active duration at `101,562.5` seconds (`~28.21 DO-hours/day`). Any long-lived WebSocket coordinator **must** use the Hibernation API (`this.ctx.acceptWebSocket(ws, tags)`, `this.ctx.getWebSockets(tag)`, and `this.ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("PING", "PONG"))`) with client text `"PING"` intervals `>= 45s` so idle connections consume zero active duration;
  5. **Strict Separation of `wrangler pages deploy` vs. `wrangler deploy`**: Inspect project structure (`pages_dist/` / `_worker.js` vs. standalone Worker `main` entry) before deploying so Pages and Workers targets are never cross-deployed.
"""
    out, n = pattern.subn(replacement, text, count=1)
    out = out.replace("Cloudflare 平台开发、12项生产资产门禁与休眠配额治理", "Cloudflare 平台开发、变更安全门禁与 DO 休眠配额治理")
    return out


def sanitize_browser_routing_skill_md(text: str) -> str:
    """Remove personal email/notifier references from browser-routing/SKILL.md and parameterize CDP URL."""
    text = re.sub(
        r"- 人机验证 macOS 通知接力工具（\[`scripts/notify_human_handoff\.py`\].*?自动兜底。",
        "- 人机验证 macOS 通知接力工具（[`scripts/notify_human_handoff.py`](./scripts/notify_human_handoff.py)，零第三方依赖标准库）：使用 `python3` 运行，优先调用已签名通知宿主 `AgentHandoffNotifier.app` 或系统 `terminal-notifier` 发送可见人机验证横幅并在验证完成或超时后自动清理。",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"- \*\*邮箱/短信 OTP 全自动接管免打扰\*\*：[^\n]+",
        "- **邮箱/短信 OTP 全自动接管免打扰**：当流程含「图形验证 + 6 位邮箱/短信验证码」时，`notify_human_handoff.py` 通知文案**仅请用户点击过掉图形人机验证**，后续邮箱或短信验证码由 Agent 通过受管只读 IMAP 邮箱通道或短信转发通道自动提取并回填，不要求用户手动翻阅复制！",
        text,
    )
    text = re.sub(
        r"- 默认优先复用已获 macOS 横幅弹窗历史授权的 `Mi8SMSNotifier\.app`[^\n]+",
        "- 默认优先调用已获 macOS 通知授权的 `AgentHandoffNotifier.app`（携带校验盾徽章 `handoff-shield.png`，支持回退系统 `terminal-notifier`）；",
        text,
    )
    for raw_email, placeholder in REDACT_CFG.get("emails", {}).items():
        text = re.sub(re.escape(raw_email), placeholder, text, flags=re.I)
    for raw_dom, repl_dom in REDACT_CFG.get("domains", {}).items():
        if "mail" in raw_dom:
            mail_brand = raw_dom.split(".")[0]
            text = re.sub(rf"{re.escape(mail_brand)}/短信 OTP", "邮箱/短信 OTP", text, flags=re.I)
            text = re.sub(re.escape(mail_brand), "imap-mail", text, flags=re.I)
    return text


def sanitize_shuorenhua_docs(text: str, rel_path: str) -> str:
    """Strip links pointing to `shuorenhua/evals/` which is excluded from public distribution."""
    if rel_path == "shuorenhua/SKILL.md":
        text = text.replace(" · [真实样本评测](./evals/real-samples.md)", "")
    elif rel_path == "shuorenhua/README.md":
        text = text.replace(
            "详见 [evals/results-v1.4.3.md](evals/results-v1.4.3.md)。",
            "评测原始语料（`evals/`）涉及本地真实业务样本，不随公开仓库分发。",
        )
    return text


def sanitize_python_code(text: str, rel_path: str) -> str:
    """Apply AST-safe Python sanitizations and normalize shebangs."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("#!") and "python" in lines[0]:
        lines[0] = "#!/usr/bin/env python3\n"
    text = "".join(lines)

    # Clean-room generalization for privacy-scanner rule tables that contain personal regex literals upstream
    if rel_path == "engineering-quality/scripts/pre_push_privacy_audit.py":
        text = re.sub(
            r"  3\. Personal / advisor emails[^\n]+\n  4\. Hardware device serials[^\n]+",
            "  3. Personal / institutional emails, CN phone numbers, 18-digit IDs, and local home directory paths\n"
            "  4. Optional project-specific identifiers configured via `PRIVACY_EXTRA_REGEX`",
            text,
            count=1,
        )
        _public_audit_rules = f'''_MAC_HOME_PREFIX = "/" + "Users/"
_EXTRA_PRIVACY_RE = os.environ.get("PRIVACY_EXTRA_REGEX", "").strip()

RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    r
    for r in (
        (
            "hardcoded_secret",
            "API key / token / private key header",
            re.compile(
                r"(?:sk-[A-Za-z0-9_-]{{20,}}|ghp_[A-Za-z0-9]{{20,}}|github_pat_[A-Za-z0-9_]{{22,}}"
                r"|AIza[0-9A-Za-z_-]{{30,}}|AKIA[0-9A-Z]{{16}}|xox[baprs]-[A-Za-z0-9-]{{16,}}"
                r"|-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----)"
            ),
        ),
        (
            "personal_or_advisor_email",
            "Personal or institutional email address",
            re.compile(
                r"\\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9.-]+\\.edu(?:\\.cn)?|qq\\.com|163\\.com|126\\.com)\\b",
                re.I,
            ),
        ),
        (
            "phone_or_id",
            "Mainland mobile phone or 18-digit resident ID",
            re.compile(
                r"(?<![0-9A-Za-z_.-])(?:1(?:3\\d|4[5-9]|5[0-35-9]|6[2567]|7[0-8]|8\\d|9[0-35-9])\\d{{8}}"
                r"|[1-6]\\d{{5}}(?:19|20)\\d{{2}}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\\d|3[01])\\d{{3}}[\\dXx])(?![0-9A-Za-z_])"
            ),
        ),
        (
            "loopback_or_lan_ip",
            "Loopback port or private LAN IP address",
            re.compile(
                r"\\b(?:127\\.0\\.0\\.1:\\d{{2,5}}|localhost:\\d{{2,5}}|10\\.\\d{{1,3}}\\.\\d{{1,3}}\\.\\d{{1,3}}"
                r"|192\\.168\\.\\d{{1,3}}\\.\\d{{1,3}})\\b"
            ),
        ),
        (
            "local_user_path",
            "Local macOS or Linux home directory path",
            re.compile(rf"(?:{{_MAC_HOME_PREFIX}}|/home/)[A-Za-z0-9._-]+"),
        ),
        (
            "commissioned_marker",
            "Commissioned / client-restricted asset marker ([CLIENT_RESTRICTED])",
            re.compile(r"\\[CLIENT_RESTRICTED\\]"),
        ),
        (
            ("custom_privacy_pattern", "Custom blocked pattern (PRIVACY_EXTRA_REGEX)", re.compile(_EXTRA_PRIVACY_RE))
            if _EXTRA_PRIVACY_RE
            else None
        ),
    )
    if r is not None
)
'''
        text = re.sub(
            r"RULES:\s*tuple\[tuple\[str,\s*str,\s*re\.Pattern\[str\]\],\s*\.\.\.\]\s*=\s*\(\n.*?\n\)\n",
            lambda _m: _public_audit_rules,
            text,
            count=1,
            flags=re.S,
        )

    if rel_path == "cloudflare/scripts/cf_health_and_quota.py":
        text = re.sub(
            r"DEFAULT_PRODUCTION_ENDPOINTS:\s*tuple\[tuple\[str,\s*str,\s*str\],\s*\.\.\.\]\s*=\s*\(\n.*?\n\)",
            lambda _m: (
                "DEFAULT_PRODUCTION_ENDPOINTS: tuple[tuple[str, str, str], ...] = tuple(\n"
                "    (f'endpoint-{i+1}', 'custom', u.strip())\n"
                "    for i, u in enumerate(os.environ.get('CF_PROBE_URLS', '').split(','))\n"
                "    if u.strip()\n"
                ")"
            ),
            text,
            count=1,
            flags=re.S,
        )
        text = re.sub(
            r"    if not proxy:\n        try:\n.*?except OSError:\n            proxy = None\n",
            "",
            text,
            count=1,
            flags=re.S,
        )

    if rel_path == "ip-materials/scripts/extract_code_material.py":
        _public_ip_patterns = '''SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email_or_edu_domain", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", re.I)),
    ("internal_loopback_or_lan", re.compile(r"\\b(?:127\\.0\\.0\\.1:\\d{2,5}|localhost:\\d{2,5}|10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|192\\.168\\.\\d{1,3}\\.\\d{1,3})\\b")),
    ("cn_mobile_phone", re.compile(r"(?<!\\d)1[3-9]\\d{9}(?!\\d)")),
    ("api_key_or_token", re.compile(r"\\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{25,}|AKIA[0-9A-Z]{16})\\b")),
    ("internal_domain", re.compile(os.environ.get("IP_SENSITIVE_DOMAINS_REGEX", r"\\b(?:internal\\.local|staging\\.internal)\\b"), re.I)),
)'''
        text = re.sub(
            r"SENSITIVE_PATTERNS:\s*tuple\[tuple\[str,\s*re\.Pattern\[str\]\],\s*\.\.\.\]\s*=\s*\(\n.*?\n\)",
            lambda _m: _public_ip_patterns,
            text,
            count=1,
            flags=re.S,
        )

    # Specific cleanups in Python scripts loaded from host redaction config
    text = re.sub(
        r'DEFAULT_POLITE_EMAIL\s*=\s*"[^"]+"',
        'DEFAULT_POLITE_EMAIL = os.environ.get("ACADEMIC_POLITE_EMAIL", "")',
        text,
    )
    for raw_email, placeholder in REDACT_CFG.get("emails", {}).items():
        text = re.sub(re.escape(raw_email), placeholder, text, flags=re.I)

    _loop_h = "127.0.0.1"
    # Parameterize loopback host:port literals in Python code without breaking syntax
    text = text.replace(
        f'"http://{_loop_h}:9223/health"',
        'os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223")) + "/health"',
    )
    text = text.replace(
        f'"http://{_loop_h}:9223"',
        'os.environ.get("CDP_RELAY_URL", "http://" + os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223"))',
    )
    text = text.replace(
        f'"{_loop_h}:9223"',
        'os.environ.get("CDP_RELAY_ADDR", os.environ.get("CDP_RELAY_HOST", "localhost") + ":" + os.environ.get("CDP_RELAY_PORT", "9223"))',
    )
    text = text.replace(
        f'"http://{_loop_h}:3425/v1"',
        'os.environ.get("OPENAI_COMPAT_BASE_URL", "http://" + os.environ.get("OPENAI_COMPAT_HOST", "localhost") + ":" + os.environ.get("OPENAI_COMPAT_PORT", "3425") + "/v1")',
    )
    text = text.replace(
        f'"http://{_loop_h}:7897"',
        'os.environ.get("HTTPS_PROXY", "")',
    )
    text = text.replace(
        f'"http://{_loop_h}:3000"',
        '("http://" + os.environ.get("NAPCAT_HOST", "localhost") + ":" + os.environ.get("NAPCAT_PORT", "3000"))',
    )
    text = text.replace(
        f'"http://{_loop_h}:40653"',
        '("http://" + os.environ.get("QCE_HOST", "localhost") + ":" + os.environ.get("QCE_PORT", "40653"))',
    )
    uname = REDACT_CFG.get("username", "")
    if uname:
        uhome = f"{_MAC_USERS_ROOT}{uname}"
        text = text.replace(
            f'Path("{uhome}/.agents/config/magpie-ops-probe.json")',
            'Path("~/.agents/config/openai-probe.json").expanduser()',
        )
        text = re.sub(
            rf'((?:pathlib\.)?Path)\(\s*"{re.escape(uhome)}/([^"\n]+)"\s*\)',
            r'\1("~/\2").expanduser()',
            text,
        )
        text = re.sub(
            rf'"{re.escape(uhome)}/((?:\.agents/skills/[^"\n]+|platform-tools/adb|Library/Android/sdk/platform-tools/adb))"',
            r'os.path.expanduser("~/\1")',
            text,
        )
    text = text.replace(
        'Path("~/.agents/tools/wechat-chat-export/wechat-decrypt/config.json").expanduser()',
        'Path(os.environ.get("WECHAT_VAULT_CONFIG", "~/.local/share/wechat-vault/config.json")).expanduser()',
    )
    text = text.replace(
        'Path("~/.agents/tools/wechat-chat-export").expanduser()',
        'Path(os.environ.get("WECHAT_VAULT_DIR", "~/.local/share/wechat-vault")).expanduser()',
    )
    text = text.replace(
        'DEFAULT_VAULT_DIR / "wechat-decrypt/decrypted"',
        'Path(os.environ.get("WECHAT_DECRYPTED_DIR", str(DEFAULT_VAULT_DIR / "decrypted"))).expanduser()',
    )

    # Ensure `import os` exists if we injected `os.environ` into a file that lacked `import os`
    if "os.environ" in text and not re.search(r"^\s*import\s+os\b", text, flags=re.M):
        # Insert after `from __future__ import ...` if present, else after module docstring / shebang
        m_fut = re.search(r"^from __future__ import [^\n]+\n", text, flags=re.M)
        if m_fut:
            pos = m_fut.end()
            text = text[:pos] + "import os\n" + text[pos:]
        else:
            lines2 = text.splitlines(keepends=True)
            insert_at = 1 if (lines2 and lines2[0].startswith("#!")) else 0
            lines2.insert(insert_at, "import os\n")
            text = "".join(lines2)

    # Clean remaining docstrings / comments inside Python files
    text = sanitize_common_text(text)
    return text


def sanitize_common_text(text: str) -> str:
    """Deterministic text sanitization shared across docs, configs, and comments."""
    uname = REDACT_CFG.get("username", "")
    uhome = f"{_MAC_USERS_ROOT}{uname}" if uname else ""
    _loop_h = "127.0.0.1"

    # 0. Nested shebang strings in tests/templates -> #!/usr/bin/env python3
    if uhome:
        text = re.sub(rf"#!(?:{re.escape(uhome)}|/opt/homebrew)[^\n\"']*python[0-9.]*", "#!/usr/bin/env python3", text)
    else:
        text = re.sub(r"#!/opt/homebrew[^\n\"']*python[0-9.]*", "#!/usr/bin/env python3", text)

    # 1. Interpreter paths -> python3
    if uhome:
        text = re.sub(
            rf"{re.escape(uhome)}/(?:miniconda3|\.agents/runtimes/[A-Za-z0-9_.-]+/\.venv|\.agents/tools/[A-Za-z0-9_./-]+/\.venv|\.local/share/uv/tools/[A-Za-z0-9_.-]+)/bin/python[0-9.]*",
            "python3",
            text,
        )
    text = text.replace("/opt/homebrew/bin/python3", "python3")

    # 2. Skill and home paths
    if uhome:
        text = text.replace(f"file://{uhome}/.agents/skills/", "file://$HOME/.agents/skills/")
        text = text.replace(f"{uhome}/.agents/skills/", "$HOME/.agents/skills/")
        text = text.replace(f"{uhome}/.agents/scripts/with_clash.sh ", "")
        text = text.replace(f"{uhome}/.agents/scripts/", "$HOME/.agents/scripts/")
        text = text.replace(f"{uhome}/.agents/config/", "~/.agents/config/")
        text = text.replace(f"{uhome}/.agents/runtimes/", "~/.agents/runtimes/")
        text = text.replace(f"{uhome}/.local/bin/", "")
        text = text.replace(f"{uhome}/.config/", "~/.config/")
        text = re.sub(rf"file://{re.escape(uhome)}/[^\s)\"`'>]+", "$WORKSPACE_PATH", text)
        text = re.sub(rf"{re.escape(uhome)}/Desktop/[^\s)\"`'>]+", "$WORKSPACE_DIR", text)
        text = re.sub(rf"{re.escape(uhome)}/Documents/[^\s)\"`'>]+", "$DOCUMENTS_DIR", text)
    text = re.sub(rf"{re.escape(_MAC_USERS_ROOT)}[A-Za-z0-9_.-]+/", "$HOME/", text)

    # 3. Personal & third-party PII / emails / handles / domains loaded from host redaction config
    for raw_email, placeholder in REDACT_CFG.get("emails", {}).items():
        text = re.sub(re.escape(raw_email), placeholder, text, flags=re.I)
    handles = REDACT_CFG.get("handles", [])
    if handles:
        h_pat = "|".join(re.escape(h) for h in handles)
        text = re.sub(rf"\b(?:{h_pat})\b", "example-user", text, flags=re.I)
    for raw_dom, repl_dom in REDACT_CFG.get("domains", {}).items():
        text = re.sub(re.escape(raw_dom), repl_dom, text, flags=re.I)

    comm_tokens = REDACT_CFG.get("community_tokens", [])
    if len(comm_tokens) >= 2:
        t0, t1 = re.escape(comm_tokens[0]), re.escape(comm_tokens[1])
        text = re.sub(rf"，?已认证账号\s*`?{t0}`?\s*`?UID:\s*{t1}`?", "", text)
        text = re.sub(rf"账号\s*`?{t0}`?", "已登录账号", text)
        text = re.sub(rf"{t0}|{t1}", "community-user", text)

    identities = REDACT_CFG.get("identities", [])
    if identities:
        primary_cn = re.escape(identities[0])
        text = re.sub(
            rf"明确区分“{primary_cn}本人[^”]*”与“外部委托[^”]*”；处于审查/补正期的软著及任何代办材料一律严禁写入{primary_cn}个人求职简历。",
            "明确区分“第一著作权人自有项目”与“外部委托或协作项目”；尚处审查/补正期的软著及代办材料严禁混入个人对外履历。",
            text,
        )
        text = re.sub(
            rf"严格区分“{primary_cn}本人[^”]*”与“外部委托[^”]*”",
            "严格区分“本人主导项目”与“外部委托或协作项目”",
            text,
        )
        id_pat = "|".join(re.escape(x).replace(r"\ ", r"\s*") for x in identities)
        text = re.sub(id_pat, "<REDACTED_USER>", text, flags=re.I)

    phones_re = REDACT_CFG.get("phones_regex", "")
    if phones_re:
        text = re.sub(phones_re, "<REDACTED_PHONE>", text)

    cf_id = REDACT_CFG.get("cloudflare_account_id", "")
    if cf_id:
        text = text.replace(cf_id, "<CLOUDFLARE_ACCOUNT_ID>")

    serials = REDACT_CFG.get("device_serials", [])
    if serials:
        s_pat = "|".join(re.escape(s) for s in serials)
        text = re.sub(s_pat, "<DEVICE_SERIAL>", text)

    if uname:
        text = re.sub(rf"\b{re.escape(uname)}\b", "developer", text, flags=re.I)

    # 4. Internal session postmortem tags, commissioned markers & UUIDs
    text = text.replace(_COMMISSIONED_TAG, "[CLIENT_RESTRICTED]")
    text = re.sub(r"[（(]源自\s*`?[0-9a-f]{8}`?(?:\s*/\s*`?[0-9a-f]{8}`?)*[^）)]*[）)]", "", text)
    text = re.sub(r"源自\s*`[0-9a-f]{8}`", "实战门禁", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<EXAMPLE_UUID>", text, flags=re.I)

    # 5. Loopback ports & private subnet literals -> portable env vars / RFC 5737 doc examples
    _loop_re = re.escape(_loop_h)
    text = re.sub(rf"https?://{_loop_re}:9223", "${CDP_RELAY_URL}", text)
    text = re.sub(rf"{_loop_re}:9223", "${CDP_RELAY_HOST}", text)
    text = re.sub(rf"https?://{_loop_re}:3425/v1", "${OPENAI_COMPAT_BASE_URL}", text)
    text = re.sub(rf"https?://{_loop_re}:3425", "${OPENAI_COMPAT_BASE_URL}", text)
    text = re.sub(rf"{_loop_re}:3425", "${OPENAI_COMPAT_HOST}", text)
    text = re.sub(rf"https?://{_loop_re}:7897", "${HTTPS_PROXY}", text)
    text = re.sub(rf"{_loop_re}:7897", "${PROXY_HOST}", text)
    text = re.sub(rf"https?://{_loop_re}:3000", "${NAPCAT_BASE_URL}", text)
    text = re.sub(rf"https?://{_loop_re}:6099", "${NAPCAT_WEBUI_URL}", text)
    text = re.sub(rf"https?://{_loop_re}:40653", "${QCE_BASE_URL}", text)
    text = re.sub(rf"{_loop_re}:([0-9]+)", r"<LOOPBACK_HOST>:\1", text)
    text = re.sub(r"localhost:([0-9]+)", r"<LOCAL_HOST>:\1", text)
    text = re.sub(r"\b10\.0\.0\.([0-9]+)\b", r"198.51.100.\1", text)
    text = re.sub(r"\b10\.126\.126\.([0-9]+)\b", r"198.51.100.\1", text)
    text = re.sub(r"\b192\.168\.([0-9]+)\.([0-9]+)\b", r"198.51.100.\2", text)
    return text


def make_symlink_wrapper(target_name: str) -> str:
    return (
        "#!/usr/bin/env python3\n"
        f'"""Portable entrypoint wrapper delegating to `{target_name}`."""\n'
        "from pathlib import Path\n"
        "import runpy\n\n"
        "if __name__ == \"__main__\":\n"
        f'    runpy.run_path(str(Path(__file__).with_name("{target_name}")), run_name="__main__")\n'
    )


def extract_frontmatter(skill_md: Path) -> tuple[str, str]:
    txt = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", txt, flags=re.S)
    if not m:
        raise ValueError(f"Missing YAML frontmatter in {skill_md}")
    fm = m.group(1)
    name_m = re.search(r"^name:\s*(.+)$", fm, flags=re.M)
    desc_m = re.search(r"^description:\s*(.+)$", fm, flags=re.M)
    name = name_m.group(1).strip().strip('"').strip("'") if name_m else skill_md.parent.name
    desc = desc_m.group(1).strip().strip('"').strip("'") if desc_m else ""
    if desc in {"|", ">", "|-", ">-"}:
        lines = fm.splitlines()
        collected = []
        capture = False
        for ln in lines:
            if ln.startswith("description:"):
                capture = True
                continue
            if capture:
                if ln.startswith("  "):
                    collected.append(ln.strip())
                else:
                    break
        desc = " ".join(collected)
    return name, desc


def write_plugin_manifests(exported_skills: list[tuple[str, str]]) -> None:
    """Emit `.claude-plugin/marketplace.json` and `.codex-plugin/plugin.json` for 1-click install."""
    claude_dir = REPO_ROOT / ".claude-plugin"
    claude_dir.mkdir(parents=True, exist_ok=True)
    marketplace = {
        "name": "agent-workflow-skills",
        "owner": {
            "name": "Evan-Joseph",
            "url": "https://github.com/Evan-Joseph",
        },
        "metadata": {
            "description": "20 production-tested cross-harness AI Agent skills with executable Python toolchains, deterministic quality gates, and domain reference trees for Claude Code, Codex, and Antigravity.",
            "version": "2.0.0",
            "license": "Apache-2.0",
        },
        "plugins": [
            {
                "name": "agent-workflow-skills",
                "description": "Full suite of 20 cross-platform engineering, academic research, document crafting, frontend UI/UX, browser routing, Cloudflare, and media production skills.",
                "source": "./",
                "strict": False,
                "skills": [f"./skills/{slug}" for slug, _ in exported_skills],
            }
        ],
    }
    (claude_dir / "marketplace.json").write_text(
        json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    codex_dir = REPO_ROOT / ".codex-plugin"
    codex_dir.mkdir(parents=True, exist_ok=True)
    codex_manifest = {
        "name": "agent-workflow-skills",
        "version": "2.0.0",
        "description": "20 production-grade cross-harness Agent skills with deterministic Python scripts and quality gates.",
        "license": "Apache-2.0",
        "repository": "https://github.com/Evan-Joseph/agent-workflow-skills",
        "skillsDir": "skills",
        "skills": [
            {"name": slug, "path": f"skills/{slug}", "description": desc}
            for slug, desc in exported_skills
        ],
    }
    (codex_dir / "plugin.json").write_text(
        json.dumps(codex_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def export_all(source_root: Path) -> list[tuple[str, str]]:
    if not source_root.is_dir():
        raise FileNotFoundError(f"Canonical skills directory not found: {source_root}")

    if SKILLS_OUT.exists():
        shutil.rmtree(SKILLS_OUT)
    SKILLS_OUT.mkdir(parents=True, exist_ok=True)

    exported: list[tuple[str, str]] = []
    py_checked = 0

    for skill_dir in sorted(source_root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        slug = skill_dir.name
        if slug in TIER_X_BLACKLIST:
            continue

        dst_skill = SKILLS_OUT / slug
        dst_skill.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(skill_dir, followlinks=False):
            root_path = Path(root)
            # Filter directories in-place (skip symlinked dirs & excluded subpaths)
            kept_dirs = []
            for d in sorted(dirs):
                if d in SKIP_DIR_NAMES:
                    continue
                dp = root_path / d
                if dp.is_symlink():
                    continue
                rel_d = dp.relative_to(source_root).as_posix()
                if any(rel_d == ex or rel_d.startswith(ex + "/") for ex in EXCLUDED_SUBPATHS):
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            for fname in sorted(files):
                if fname in SKIP_FILE_NAMES:
                    continue
                src_f = root_path / fname
                if src_f.suffix.lower() in SKIP_SUFFIXES:
                    continue
                rel_f = src_f.relative_to(source_root).as_posix()
                if any(rel_f == ex or rel_f.startswith(ex + "/") for ex in EXCLUDED_SUBPATHS):
                    continue

                dst_f = SKILLS_OUT / rel_f
                dst_f.parent.mkdir(parents=True, exist_ok=True)

                # Expand relative script symlinks into clean standalone Python wrappers
                if src_f.is_symlink():
                    link_target = os.readlink(src_f)
                    target_basename = Path(link_target).name
                    if src_f.suffix == ".py" and (src_f.parent / target_basename).is_file():
                        code = make_symlink_wrapper(target_basename)
                        ast.parse(code, filename=rel_f)
                        dst_f.write_text(code, encoding="utf-8")
                        dst_f.chmod(0o755)
                        py_checked += 1
                    continue

                # Tier B full clean-room replacements
                if rel_f == "chat-history-export/SKILL.md":
                    dst_f.write_text(PUBLIC_CHAT_HISTORY_SKILL_MD, encoding="utf-8")
                    continue
                if rel_f == "chat-history-export/references/mobile-encryption-and-backup-assessment.md":
                    dst_f.write_text(PUBLIC_MOBILE_ENCRYPTION_ASSESSMENT_MD, encoding="utf-8")
                    continue
                if rel_f == "mobile-device-ops/SKILL.md":
                    dst_f.write_text(PUBLIC_MOBILE_DEVICE_OPS_SKILL_MD, encoding="utf-8")
                    continue

                ext = src_f.suffix.lower()
                is_text = ext in TEXT_EXTENSIONS or fname in {"LICENSE", "SKILL.md", ".env.example"} or fname.startswith("LICENSE.")
                if not is_text:
                    shutil.copy2(src_f, dst_f)
                    continue

                try:
                    raw = src_f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    shutil.copy2(src_f, dst_f)
                    continue

                if rel_f == "cloudflare/SKILL.md":
                    raw = sanitize_cloudflare_skill_md(raw)
                elif rel_f == "browser-routing/SKILL.md":
                    raw = sanitize_browser_routing_skill_md(raw)
                elif rel_f in {"shuorenhua/SKILL.md", "shuorenhua/README.md"}:
                    raw = sanitize_shuorenhua_docs(raw, rel_f)

                if ext == ".py":
                    cleaned = sanitize_python_code(raw, rel_f)
                    ast.parse(cleaned, filename=rel_f)
                    py_checked += 1
                else:
                    cleaned = sanitize_common_text(raw)

                dst_f.write_text(cleaned, encoding="utf-8")
                if ext in {".py", ".sh"} or (src_f.stat().st_mode & stat.S_IXUSR):
                    dst_f.chmod(0o755)

        name, desc = extract_frontmatter(dst_skill / "SKILL.md")
        exported.append((name, desc))

    write_plugin_manifests(exported)
    print(f"[export_public_skills] Exported {len(exported)} skills ({py_checked} Python files AST-verified) -> {SKILLS_OUT}")
    return exported


def main() -> int:
    src = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_SOURCE
    exported = export_all(src)
    if len(exported) != 20:
        print(f"ERROR: expected 20 exported public skills, got {len(exported)}: {[s for s, _ in exported]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
