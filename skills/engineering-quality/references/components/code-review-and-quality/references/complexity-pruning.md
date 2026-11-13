# Complexity Pruning Pass

Use this pass when a review asks whether code is over-engineered, too large, dependency-heavy, or likely written by an AI agent that overbuilt the task. It complements normal correctness review; do not let it hide correctness, security, data-loss, accessibility, or required behavior risks.

## What To Hunt

- Dead features, speculative switches, unused extension points, or config nobody sets.
- Interfaces, factories, repositories, services, adapters, or providers with one implementation and one caller.
- Wrapper functions that only delegate without adding policy, validation, tracing, retries, or compatibility.
- Hand-written standard-library behavior: parsing, grouping, formatting, debounce, rate limit, deep clone, path handling, retries, CSV/JSON helpers.
- New dependencies for behavior that language stdlib, platform APIs, browser controls, CSS, database constraints, shell tools, or installed dependencies already cover.
- Reimplemented project-local helpers, components, DTOs, hooks, scripts, or middleware.
- Tests that only assert mocks were called and do not protect behavior; keep the smallest behavior check that would fail on regression.

## Tags

- `delete`: remove dead or speculative code.
- `stdlib`: replace hand-written logic with language stdlib.
- `native`: replace custom/dependency code with platform capability.
- `yagni`: remove abstraction, layer, config, or flexibility that has no current second use.
- `shrink`: same behavior, fewer lines.
- `reuse`: use existing project code.

## Finding Shape

```text
path/to/file.ts:L42: yagni: AbstractThing has one implementation and one caller. Inline until a second implementation exists.
path/to/file.ts:L7: native: dependency used only for date input. Use <input type="date"> and remove the package.
```

End a pruning-only review with:

```text
net: -N lines, -M deps possible.
```

If nothing meaningful can be cut:

```text
已经够精简，可以保留。
```

## Do Not Flag

- Trust-boundary validation, permission checks, escaping, schema validation, data-loss protection, migration safeguards, audit logs, rate limits, accessibility basics, and user-requested behavior.
- Clear project conventions that look verbose in isolation but keep the repository consistent.
- A small runnable test, smoke check, or assertion that proves non-trivial logic.

## Debt Markers

When a deliberate simplification has a known ceiling, it may leave a short marker:

```text
// complexity-pruning: global lock; switch to per-account locks if write contention appears
```

The marker must name both the ceiling and the trigger for revisiting it. To audit a repository:

```bash
python3 $HOME/.agents/skills/engineering-quality/references/components/complexity-pruning/scripts/scan_debt.py <repo>
```

Report markers with missing triggers as review findings; do not treat every marker as a bug.
