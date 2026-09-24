#!/usr/bin/env bash
# Mechanical figure checks. Thin wrapper so the same path works from either install:
#   ~/.claude/skills/figure-audit/scripts/figure_audit.sh   (Claude Code)
#   ~/.codex/skills/figure-audit/scripts/figure_audit.sh    (Codex)
# It resolves its own directory, following symlinks, so the skill can live anywhere and be
# linked into both. All logic is in figure_audit.py; see its docstring for the commands.
set -euo pipefail
src="${BASH_SOURCE[0]}"
while [ -L "$src" ]; do
  dir="$(cd -P "$(dirname "$src")" && pwd)"
  src="$(readlink "$src")"
  [[ "$src" != /* ]] && src="$dir/$src"
done
here="$(cd -P "$(dirname "$src")" && pwd)"
py="${FIGURE_AUDIT_PYTHON:-python3}"
if ! command -v "$py" >/dev/null 2>&1; then
  echo "figure_audit: no $py on PATH (set FIGURE_AUDIT_PYTHON)" >&2
  exit 2
fi
exec "$py" "$here/figure_audit.py" "$@"
