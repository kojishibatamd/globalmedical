#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY_ROOT="$ROOT_DIR/outputs/today_tasks"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

mkdir -p "$TODAY_ROOT"

if [ -f "$HOME/.env_globalmedical" ]; then
  source "$HOME/.env_globalmedical"
else
  echo "WARNING: ~/.env_globalmedical not found."
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/suggest_today_tasks.py"

LATEST_DIR="$(ls -td "$TODAY_ROOT/"* 2>/dev/null | head -1)"
TODAY_FILE="$LATEST_DIR/today_tasks.md"

if [ -z "$LATEST_DIR" ] || [ ! -f "$TODAY_FILE" ]; then
  echo "ERROR: today_tasks.md not found."
  exit 1
fi

echo
echo "Today tasks output:"
echo "$LATEST_DIR"
echo
echo "---- today_tasks.md ----"
cat "$TODAY_FILE"

pbcopy < "$TODAY_FILE"
echo
echo "Copied today_tasks.md to clipboard."

open "$LATEST_DIR"
