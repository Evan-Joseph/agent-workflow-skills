---
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
