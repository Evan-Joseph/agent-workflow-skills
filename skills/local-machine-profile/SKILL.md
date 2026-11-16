---
name: local-machine-profile
description: "Structured workstation environment & project-boundary SSOT pattern for AI coding agents. Separates static verified baselines, live read-only runtime probes, and domain ledger pointers without storing plaintext secrets."
metadata:
  short-description: Workstation environment baseline & three-tier SSOT pattern
---

# Workstation Environment & SSOT Profile (`local-machine-profile`)

Defines a reusable **Single Source of Truth (SSOT)** layout for developer workstations so AI coding agents stop re-probing static OS/toolchain facts on every turn and never hallucinate stale counters after context compaction.

## Three-Tier Profile Architecture

See [`references/three-tier-ssot-protocol.md`](./references/three-tier-ssot-protocol.md) for the full specification:

1. **Tier 1 — Static Verified Baselines**: OS architecture, managed language runtimes, workspace directory conventions, and explicit boundaries between personal open-source projects and client/commissioned work. Every entry records its verification source and date.
2. **Tier 2 — Live Read-Only Runtime Probes**: Volatile values (active proxy ports, daemon health, container status, remaining API quotas) are never hardcoded as static numbers; query them on demand with read-only commands (`scripts/collect_env_baseline.py`).
3. **Tier 3 — Domain Ledger Pointers**: High-churn project state stays in each project's own `NOTES.md` or ledger file; the profile stores file pointers rather than duplicating snapshots.

## Secret & Credential Boundary

- Never write plaintext API keys, passwords, cookies, tokens, or payment numbers into `SKILL.md` or `references/*.md`.
- Store secrets in the OS keychain (`security` on macOS, `secret-tool` on Linux), a local password vault, or `0600` config files outside version control, and document only environment variable names in skill docs.

## Read-Only Workstation Probe

```bash
python3 $HOME/.agents/skills/local-machine-profile/scripts/collect_env_baseline.py
```
