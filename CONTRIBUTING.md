# Contributing

This repository is for practical skills that an agent can use during real work. Keep contributions small and testable.

## What makes a good skill

- It has one clear job.
- The `description` says when to use it, not just what it is.
- The body gives procedure, checks, and handoff rules.
- Long examples or background notes live in `references/` or `templates/`.
- It does not include secrets, private paths, account names, cookies, tokens, or local machine assumptions.
- It does not wrap generic advice in a new folder.

## Structure

Use this shape:

```text
skills/<skill-name>/
  SKILL.md
  references/
  templates/
  scripts/
  assets/
```

Only create directories that the skill actually uses.

## Naming

- Use lowercase words separated by hyphens.
- Prefer the task over the tool name.
- Avoid personal names, company internals, temporary project names, and vague labels such as `ai-helper` or `workflow-tool`.

Good:

```text
academic-figure-design
frontend-refresh-workflow
design-competition-entry
```

Weak:

```text
my-skill
ai-design-helper
project-tools
```

## Before opening a pull request

Run a basic leak check:

```bash
rg -n "/Users/|password|passwd|token|cookie|api[_-]?key|secret|private_key|BEGIN .*KEY|localhost:[0-9]+|127\\.0\\.0\\.1:[0-9]+" .
find . -type l -print
```

If a match is intentional, explain it in the pull request.

## Style

Write like a working note for a competent agent. Short sentences, concrete steps, no filler. If a sentence does not change what the agent will do, cut it.

