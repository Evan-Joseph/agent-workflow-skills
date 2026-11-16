# Empirical Multi-Family Model Routing Guide

When orchestrating multiple frontier model families across coding harnesses, assign roles by empirical strengths and enforce clear scope contracts:

## 1. Role Specialization Matrix

| Primary Task Type | Recommended Model Profile | Scope & Guardrail Contract |
| :--- | :--- | :--- |
| **Long-Context Synthesis, Multimodal QA & Natural Technical Writing** | Long-context multimodal coordinator (e.g., Gemini frontier tier; Flash tier for fast read-only codebase scouting) | Verify screenshots/PDFs directly; search proven upstream implementations before writing glue scripts; avoid ad-hoc CSS overrides on existing design systems |
| **Cross-Module Architecture & Product-Grade Frontend UI/UX** | Architecture & UI specialist (e.g., Claude Opus / Sonnet tier) | Pass explicit `file:line` scope boundaries and design tokens to prevent over-abstraction |
| **Backend Concurrency, Protocols, Formal Solvers & Diff Review** | Systems & adversarial auditor (e.g., GPT reasoning tier via CLI/reviewer role) | Focus on state machines, file locks, subprocess timeouts, SQL/transaction safety, and edge-case regression review |

## 2. Anti-Context-Rot Practices

- **Zero Trust on Compacted Summaries**: Always re-verify line numbers, git status, and config state on disk after context compaction.
- **Output Diet (`< 2 KB`)**: Filter large JSON/log outputs inside `jq` or short Python one-liners instead of dumping raw megabytes into the context window.
- **Anti-Tunnel-Vision Diff Check**: Before patching section `B` of a configuration or specification, inspect `A + B + C` and run `git diff` afterward to ensure `A` and `C` were not accidentally dropped.
