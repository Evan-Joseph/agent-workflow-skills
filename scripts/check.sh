#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "Checking for symlinks..."
if find . -type l -print | grep -q .; then
  find . -type l -print
  exit 1
fi

echo "Checking for common leaks..."
if rg -n "/Users/|gaoshenzhou|foxmail|qdu\\.edu|password|passwd|token|cookie|api[_-]?key|private_key|BEGIN .*KEY|127\\.0\\.0\\.1:[0-9]+|localhost:[0-9]+" . \
  --glob '!CONTRIBUTING.md' \
  --glob '!SECURITY.md' \
  --glob '!README.md' \
  --glob '!scripts/check.sh'; then
  exit 1
fi

echo "Checking skill frontmatter..."
for skill in skills/*; do
  [ -d "$skill" ] || continue
  file="$skill/SKILL.md"
  test -f "$file"
  head -n 1 "$file" | grep -qx -- "---"
  sed -n '1,20p' "$file" | grep -q '^name: '
  sed -n '1,20p' "$file" | grep -q '^description: '
  directory_name="$(basename "$skill")"
  skill_name="$(sed -n '1,20p' "$file" | sed -n 's/^name: *//p' | head -n 1)"
  printf '%s\n' "$directory_name" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'
  test "$skill_name" = "$directory_name"
done

echo "OK"
