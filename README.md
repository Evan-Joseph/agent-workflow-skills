# Agent Workflow Skills

Small, reusable Agent Skills for work that tends to get messy in real projects: research figures, frontend refreshes, design competition entries, and model-assisted decision making.

These skills are written for agents that can read a `SKILL.md` file and follow local workflows. They are deliberately plain. A good skill should give the agent the missing procedure, not explain the whole internet back to it.

## What's inside

| Skill | Use it for |
|---|---|
| `academic-figure-design` | Planning AI-assisted academic figures, then rebuilding final labels, charts, and source images in editable form. |
| `frontend-refresh-workflow` | Replacing an old frontend with a new prototype while keeping real backend behavior, tests, and project structure intact. |
| `design-competition-entry` | Turning a design competition brief into a checked workflow: rules, branch, concept, prompts, review, and submission assets. |

More skills may be added later, but this repository is not meant to become a junk drawer. Each skill needs a clear owner task, a short trigger description, and enough process to prevent common failure modes.

## Layout

```text
skills/
  academic-figure-design/
    SKILL.md
    references/
  frontend-refresh-workflow/
    SKILL.md
    references/
    templates/
  design-competition-entry/
    SKILL.md
    references/
```

Each skill folder keeps the agent-facing instructions in `SKILL.md`. Longer material lives in `references/` or `templates/` so the agent can load it only when needed.

## Install

Copy a skill folder into the skill directory used by your agent runtime. Common examples:

```bash
# Codex / agent-style layouts
cp -R skills/academic-figure-design "$HOME/.agents/skills/"

# Or install the whole collection
cp -R skills/* "$HOME/.agents/skills/"
```

If your runtime uses a different skill root, copy the folders there. Do not rename the folder without also updating the `name` field in `SKILL.md`.

## Writing style

The repository uses two rules:

- Keep `SKILL.md` short enough to be read during a real task.
- Keep public documentation readable by humans. Avoid sales copy, inflated claims, and template language.

## Compatibility

The skills follow the common `SKILL.md` pattern used by agent runtimes:

- one folder per skill
- lowercase, hyphenated skill names
- YAML frontmatter with `name` and `description`
- optional `metadata`
- optional `references/`, `templates/`, `scripts/`, and `assets/`

They do not depend on private accounts, local paths, credentials, or paid services. When a workflow needs external facts, the skill asks the agent to verify the current official source instead of relying on stale notes.

## Contributing

Contributions are welcome if they make a skill more useful without making it bulky. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
