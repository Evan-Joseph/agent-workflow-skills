# Three-Tier Environment & SSOT Governance Protocol

## 1. Tier Separation

| Tier | Scope | Storage Rule |
| :--- | :--- | :--- |
| **Tier 1: Static Baseline** | Hardware architecture, OS family, managed Python/Node toolchains, workspace naming conventions, project ownership boundaries | Versioned Markdown verified against primary artifacts; record positive verified facts only |
| **Tier 2: Dynamic Runtime** | Service health, proxy state, active tasks, rate-limit quotas, database row counts | Never hardcode counts; run deterministic read-only CLI probes when needed |
| **Tier 3: Domain Ledgers** | Project-specific roadmaps, experiment tables, release checklists | Keep in each workspace's `NOTES.md` and link by path |

## 2. Anti-Compaction Read-Back Order

After context compaction or a cold session resume, verify facts on disk before acting:
1. Read workspace `AGENTS.md` and `NOTES.md`;
2. Check Tier-1 baseline files when environment or project-scope rules apply;
3. Run `scripts/collect_env_baseline.py` if toolchain or proxy state is uncertain.

## 3. Secret Hygiene

Store credentials exclusively in OS keychains or `0600` runtime files (`~/.config/<service>/`). Reference credentials in documentation by environment variable name only (e.g., `$OPENAI_API_KEY`, `$GITHUB_TOKEN`).
