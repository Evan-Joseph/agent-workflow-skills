---
name: quick-colleague
description: "Cross-session queued CLI delegation pattern and budget circuit-breaker protocol (`--pure-reply` single-turn code extraction and bounded `<=8` surgical workspace edits) for local desktop coding assistants."
metadata:
  short-description: Cross-session queued CLI delegation & budget circuit-breaker protocol
---

# `quick-colleague` — Serialized Desktop Assistant Queue & Pure-Reply Pattern

Defines a serialized cross-session execution wrapper (`quick-colleague`) over a local desktop AI assistant's loopback DevTools endpoint (`$QUICK_CDP_URL`) and workspace outpost (`$QUICK_OUTPOST_URL`), allowing concurrent coding sessions to share one monthly reasoning quota without window collisions or runaway tool loops.

## 1. Two Calling Modes (Prefer Mode A `--pure-reply`)

### Mode A (Default): Single-Turn Zero-Tool Extraction (`--pure-reply`)
- **Best for**: SVG icons, self-contained HTML/CSS templates or widgets, storyboards, and high-cohesion copy/review output.
- **Mechanism**: Assemble a tight, self-contained specification locally first, constrain the model to **1 turn with 0 tool calls (`--max-steps 0`)**, and extract the fenced code block directly to disk via `--extract-code`. Zero Outpost reverse-tunnel overhead and zero multi-turn prefill inflation.
```bash
quick-colleague send \
  --pure-reply \
  --ephemeral \
  --effort medium \
  --timeout 5m \
  --prompt-file "/path/to/inline_spec.md" \
  --extract-code "/path/to/output.html"
```

### Mode B: Bounded Surgical Multi-File Edits (`<=8` Tool Steps)
- **Best for**: Localized in-place edits across existing files that cannot fit comfortably in a single inline prompt.
- **Pre-flight tunnel health check**: Probes `$QUICK_OUTPOST_URL/health` and workspace mounts before dispatch, automatically recovering dormant local tunnels when needed.
```bash
quick-colleague send \
  --cwd "/path/to/project" \
  --prompt-file "/path/to/surgical_brief.md" \
  --effort medium \
  --max-steps 10 \
  --timeout 5m
```

## 2. Concurrency Lock & Four Budget Circuit Breakers

1. **Cross-Session Mutex Queue (`$QUICK_LOCK_FILE`, default `~/.local/state/quick-colleague/quick.lock`)**: Serializes concurrent calls from separate agent sessions; execution timeout starts only after acquiring the lock.
2. **Cold-Start Singleton Lock Recovery**: Cleanly handles stale desktop profile locks before attaching DevTools.
3. **Four Quota-Protection Circuit Breakers**:
   - **Stop-Before-Archive/Cancel**: Explicitly clicks Stop and waits for streaming to settle (`isStreaming == false`) before closing or deleting ephemeral chats;
   - **Hard Timeout Auto-Stop**: Stops streaming automatically at `--timeout` (default `5m`) unless `--keep-running-on-timeout` is passed;
   - **Step Budget Cap**: Enforces `--max-steps` (`0` for `--pure-reply`, `10` default for surgical edits);
   - **Rolling Window Guard**: Tracks cumulative usage across 5-hour rolling windows and keeps memory/ingestion side-features disabled.

## 3. Lifecycle Subcommands & Local Free Verification

```bash
quick-colleague doctor --ensure-cdp
quick-colleague wait <job_id> --timeout 6m
quick-colleague result <job_id> --extract-fenced > output.svg
quick-colleague stop-all
quick-colleague prune-chats
```

Never burn assistant quota running headless screenshot loops inside `quick-colleague`; verify returned UI artifacts locally afterwards using `sloplint.mjs` (`0 FAIL, 0 REFLEX`) and local Playwright/headless browser inspection:

```bash
node $HOME/.agents/skills/frontend-design/scripts/sloplint.mjs <target> --scope app
```
