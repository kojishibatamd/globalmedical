#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY_ROOT="$ROOT_DIR/outputs/today_tasks"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"
TODAY_DIR="$TODAY_ROOT/$(date +%F)"

mkdir -p "$TODAY_ROOT"

if [ -f "$HOME/.env_globalmedical" ]; then
  source "$HOME/.env_globalmedical"
else
  echo "WARNING: ~/.env_globalmedical not found."
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/suggest_today_tasks.py" "$@"

TODAY_FILE="$TODAY_DIR/today_tasks.md"

if [ ! -f "$TODAY_FILE" ]; then
  echo "ERROR: today_tasks.md not found."
  exit 1
fi

echo
echo "Today tasks output:"
echo "$TODAY_DIR"
echo
echo "---- today_tasks.md ----"
cat "$TODAY_FILE"

pbcopy < "$TODAY_FILE"
echo
echo "Copied today_tasks.md to clipboard."

open "$TODAY_DIR"
