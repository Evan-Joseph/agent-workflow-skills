---
name: harness-governance
description: "Cross-harness SKILL.md lifecycle tooling, single-source-of-truth instruction layout (@AGENTS.md), and multi-model role routing conventions across Claude Code, Codex, Gemini CLI, and Antigravity."
metadata:
  short-description: Cross-harness skill lifecycle validation, packaging & routing
---

# Multi-Harness Skill Lifecycle & Governance (`harness-governance`)

Standardizes how `SKILL.md` packages and workspace instructions are authored, validated, and shared across multiple AI coding harnesses (**Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Gemini CLI**, and compatible agents) without configuration drift.

## Core Conventions

1. **Canonical Skill Directory (`~/.agents/skills`)**:
   - Maintain skills in a single canonical directory and project them to `~/.claude/skills` or `~/.codex/skills` via symlinks or plugin manifests rather than maintaining diverging copies.
   - Keep each `SKILL.md` concise (`< 12 KB`) using progressive disclosure: core routing and guardrails in `SKILL.md`, detailed specifications in `references/`, and deterministic tools in `scripts/`.
2. **Single Static Root Instruction (`AGENTS.md`)**:
   - Keep one static `AGENTS.md` per repository root; in harnesses that read `CLAUDE.md`, use a one-line `@AGENTS.md` import so prompt caches remain byte-stable and rules never drift.
   - Store mutable task progress in `NOTES.md` or `task_plan.md` rather than mutating root instruction files.
3. **Empirical Role Routing**:
   - Route architecture/UI design, backend/concurrency auditing, and long-context multimodal synthesis according to [`references/multi-family-model-routing.md`](./references/multi-family-model-routing.md).

## Bundled Skill Lifecycle Scripts

```bash
# 1. Scaffold a new standard SKILL.md directory
python3 $HOME/.agents/skills/harness-governance/scripts/init_skill.py my-new-skill --path ./skills

# 2. Validate SKILL.md YAML frontmatter and naming conventions
python3 $HOME/.agents/skills/harness-governance/scripts/quick_validate.py ./skills/my-new-skill

# 3. Scan an entire skill tree for broken local references and frontmatter health
python3 $HOME/.agents/skills/harness-governance/scripts/scan_skills.py --root ~/.agents/skills

# 4. Package a validated skill folder into a distributable .skill archive
python3 $HOME/.agents/skills/harness-governance/scripts/package_skill.py ./skills/my-new-skill ./dist
```
