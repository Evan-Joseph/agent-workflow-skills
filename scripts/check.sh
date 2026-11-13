#!/usr/bin/env bash
# Zero-Leak CI Gate v2.1 for Evan-Joseph/agent-workflow-skills
# Contains zero hardcoded personal tokens; loads private local redaction rules from
# ~/.agents/config/public-skills-redact.json when running on the maintainer host.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "[1/6] Checking for symlinks (must be 0)..."
if find . -type l -not -path './.git/*' -print | grep -q .; then
  echo "FAIL: Symlinks found in repository:" >&2
  find . -type l -not -path './.git/*' -print >&2
  exit 1
fi

echo "[2/6] Checking forbidden Tier-X & DMCA paths..."
for forbidden in \
  "skills/local-machine-profile" \
  "skills/artex-client" \
  "skills/harness-governance" \
  "skills/chat-history-export/vendor/wechat-decrypt" \
  "skills/chat-history-export/vendor" \
  "skills/ip-materials/vendor/docx-toolkit"; do
  if [ -e "$forbidden" ]; then
    echo "FAIL: FORBIDDEN PATH PRESENT: $forbidden" >&2
    exit 1
  fi
done

echo "[3/6] Checking zero local home paths, PII, emails, and internal domains..."
mac_home_prefix="/""Users/"
if rg -n "$mac_home_prefix" skills/ scripts/ README.md THIRD_PARTY_NOTICES.md .claude-plugin/ .codex-plugin/; then
  echo "FAIL: macOS local home path leak detected!" >&2
  exit 1
fi

redact_cfg="${PUBLIC_SKILLS_REDACT_CONFIG:-$HOME/.agents/config/public-skills-redact.json}"
if [ -f "$redact_cfg" ]; then
  python3 - "$redact_cfg" <<'PY'
import json, pathlib, re, subprocess, sys

cfg = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
uname = cfg.get("username", "")
if uname:
    r1 = subprocess.run(["rg", "-n", "-i", uname, "skills/"], capture_output=True, text=True)
    if r1.returncode == 0:
        print(r1.stdout, file=sys.stderr)
        sys.exit("FAIL: Maintainer username leak detected in skills/!")
    r2 = subprocess.run(["rg", "-P", "-n", "-i", f"(?<!Evan-){re.escape(uname)}", "scripts/", "README.md", "THIRD_PARTY_NOTICES.md", ".claude-plugin/", ".codex-plugin/"], capture_output=True, text=True)
    if r2.returncode == 0:
        print(r2.stdout, file=sys.stderr)
        sys.exit("FAIL: Bare maintainer username leak detected in scripts/ or root metadata!")

pat = cfg.get("check_block_regex", "")
if pat:
    r3 = subprocess.run(["rg", "-n", "-i", pat, "skills/", "scripts/", "README.md", "THIRD_PARTY_NOTICES.md", ".claude-plugin/", ".codex-plugin/"], capture_output=True, text=True)
    if r3.returncode == 0:
        print(r3.stdout, file=sys.stderr)
        sys.exit("FAIL: Personal identity / email / phone / serial / internal domain leak detected!")
print("  Host private redaction dictionary verified clean across entire repository (including scripts/).")
PY
fi

echo "[4/6] Checking zero hardcoded loopback/LAN ports and internal session UUIDs..."
loopback_re="127\\.0\\.0\\.1:[0-9]+|localhost:[0-9]+|10\\.0\\.0\\.[0-9]+|10\\.126\\.126\\.[0-9]+|192\\.168\\.[0-9]+\\.[0-9]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
if rg -n "$loopback_re" skills/; then
  echo "FAIL: Hardcoded port / LAN IP / UUID leak detected in skills/!" >&2
  exit 1
fi

echo "[5/6] Validating SKILL.md frontmatter & Python AST across all exported skills..."
count=0
for skill in skills/*; do
  [ -d "$skill" ] || continue
  file="$skill/SKILL.md"
  test -f "$file"
  head -n 1 "$file" | grep -qx -- "---"
  sed -n '1,25p' "$file" | grep -q '^name: '
  sed -n '1,25p' "$file" | grep -q '^description: '
  basename "$skill" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'
  count=$((count + 1))
done

if [ "$count" -ne 20 ]; then
  echo "FAIL: Expected exactly 20 skills under skills/, found $count" >&2
  exit 1
fi

python3 - <<'PY'
import ast, pathlib
py_files = list(pathlib.Path("skills").rglob("*.py")) + list(pathlib.Path("scripts").rglob("*.py"))
for p in py_files:
    ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
print(f"  Verified {len(py_files) - 1} skill Python scripts (+1 compiler) with ast.parse() across 20 skills.")
PY

echo "[6/6] Checking Markdown relative links across all .md files..."
python3 - <<'PY'
import pathlib, re, sys

root = pathlib.Path(".").resolve()
md_files = [p for p in root.rglob("*.md") if ".git" not in p.parts]
link_re = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
broken = []
for md in sorted(md_files):
    txt = md.read_text(encoding="utf-8")
    txt_no_code = re.sub(r"```.*?```", "", txt, flags=re.S)
    txt_no_code = re.sub(r"`[^`\n]+`", "", txt_no_code)
    for m in link_re.finditer(txt_no_code):
        raw_target = m.group(1).strip().strip("<>")
        if not raw_target or raw_target.startswith(("#", "http://", "https://", "mailto:", "file://", "conversation://", "data:", "javascript:")):
            continue
        target_path = raw_target.split("#", 1)[0].split("?", 1)[0]
        if not target_path or "$" in target_path or target_path in {"path", "url", "URL", "PATH"}:
            continue
        if not (md.parent / target_path).resolve().exists():
            broken.append((md.relative_to(root).as_posix(), raw_target))

if broken:
    for f, t in broken:
        print(f"  BROKEN LINK: {f} -> {t}", file=sys.stderr)
    sys.exit(f"FAIL: {len(broken)} broken Markdown relative link(s) detected!")
print(f"  Verified 0 broken relative links across {len(md_files)} Markdown files.")
PY

echo "ALL CHECKS PASSED (exit 0) — 20 clean public skills ready."
