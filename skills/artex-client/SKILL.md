---
name: artex-client
description: "Managed zero-leak REST CLI and four-element finding verification gate for authorized local security evaluation services (ARTEX)."
metadata:
  short-description: Authorized security evaluation CLI & finding verification gate
---

# Authorized Security Evaluation Client (`artex-client`)

Provides a zero-dependency Python CLI ([`scripts/artex_cli.py`](./scripts/artex_cli.py)) for interacting with a local authorized security evaluation backend (`$ARTEX_BASE_URL`) alongside a strict four-element vulnerability verification gate ([`references/finding-verification-gate.md`](./references/finding-verification-gate.md)).

## Compliance & Authorization Red Lines

1. **Explicit Scope Authorization First**: Never initiate scanning or probing against any target outside an explicitly authorized asset scope.
2. **Zero Credential Leakage**: `artex_cli.py` reads local state from `$ARTEX_STATE_DIR` (default `~/.local/state/artex`) and caches short-lived JWTs in `0600` files; never pass plaintext passwords or bearer tokens on command lines or print them to `stdout`.
3. **Mandatory Four-Element Gate Before Reporting**: Every candidate finding must satisfy all four checks in [`references/finding-verification-gate.md`](./references/finding-verification-gate.md):
   `Trust Boundary -> Affected Principal -> Concrete Reproduction -> Minimal Fix`.

## CLI Usage (`scripts/artex_cli.py`)

```bash
# 1. Check service health, authentication status, and task/asset counts
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py status

# 2. Preview or sync an authorized target scope
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py scope-sync \
  --company "ExampleOrg" --root example.com --endpoint https://api.example.com/v1 --dry-run

# 3. Create or control an evaluation task (pause / resume / cancel)
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py task-create \
  --name "Authorized API Audit" --target "example.com" --dry-run
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py task-ctl --list

# 4. Inspect findings and statistics
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py findings --limit 20
python3 $HOME/.agents/skills/artex-client/scripts/artex_cli.py findings --stats
```
