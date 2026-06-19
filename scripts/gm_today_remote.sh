#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY_ROOT="$ROOT_DIR/outputs/today_tasks"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

log() {
  printf '%s\n' "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

mkdir -p "$TODAY_ROOT"

if [ -f "$HOME/.env_globalmedical" ]; then
  # shellcheck source=/dev/null
  if ! source "$HOME/.env_globalmedical" >/dev/null 2>&1; then
    fail "Failed to source ~/.env_globalmedical."
  fi
else
  log "WARNING: ~/.env_globalmedical not found."
fi

log "Running suggest_today_tasks.py..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/suggest_today_tasks.py" >&2

LATEST_DIR="$(ls -td "$TODAY_ROOT/"* 2>/dev/null | head -1)"
TODAY_FILE="$LATEST_DIR/today_tasks.md"

if [ -z "$LATEST_DIR" ] || [ ! -f "$TODAY_FILE" ]; then
  fail "today_tasks.md not found."
fi

if grep -E -q 'sk-ant-|sk-proj-|ghp_|GITHUB_TOKEN=.*ghp|OPENAI_API_KEY=.*sk|ANTHROPIC_API_KEY=.*sk' "$TODAY_FILE"; then
  fail "Dangerous token-like pattern found in today_tasks.md."
fi

log "Latest today tasks: $TODAY_FILE"
cat "$TODAY_FILE"
