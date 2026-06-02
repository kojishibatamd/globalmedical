#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVISION_ROOT="$ROOT_DIR/outputs/project_context_revision"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

mkdir -p "$REVISION_ROOT"

if [ -f "$HOME/.env_globalmedical" ]; then
  source "$HOME/.env_globalmedical"
else
  echo "WARNING: ~/.env_globalmedical not found."
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/revise_project_context.py"

LATEST_DIR="$(ls -td "$REVISION_ROOT/"* 2>/dev/null | head -1)"
REVISED_FILE="$LATEST_DIR/project_instruction_revised.md"

if [ -z "$LATEST_DIR" ] || [ ! -f "$REVISED_FILE" ]; then
  echo "ERROR: Revised project instruction output not found."
  exit 1
fi

echo
echo "Project context revision output:"
echo "$LATEST_DIR"
echo
echo "Project instruction characters:"
wc -m < "$REVISED_FILE" | tr -d ' '
echo
echo "---- project_instruction_revised.md (first 220 lines) ----"
sed -n '1,220p' "$REVISED_FILE"

pbcopy < "$REVISED_FILE"
echo
echo "Copied project_instruction_revised.md to clipboard."

open "$LATEST_DIR"
