#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY_ROOT="$ROOT_DIR/outputs/today_tasks"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"
TODAY_DIR="$TODAY_ROOT/$(date +%F)"

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

ANTHROPIC_PREFIX="sk-""ant-"
OPENAI_PREFIX="sk-""proj-"
GITHUB_PREFIX="ghp""_"

if [ -n "${ANTHROPIC_API_KEY:-}" ] &&
  [[ "$ANTHROPIC_API_KEY" != "$ANTHROPIC_PREFIX"* && "$ANTHROPIC_API_KEY" != "$OPENAI_PREFIX"* ]]; then
  fail "ANTHROPIC_API_KEY has an unexpected format."
fi

log "Running suggest_today_tasks.py..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/suggest_today_tasks.py" "$@" >&2

TODAY_FILE="$TODAY_DIR/today_tasks.md"

if [ ! -f "$TODAY_FILE" ]; then
  fail "today_tasks.md not found."
fi

if grep -E -q "$ANTHROPIC_PREFIX|$OPENAI_PREFIX|$GITHUB_PREFIX|GITHUB_TOKEN=.*ghp|OPENAI_API_KEY=.*sk|ANTHROPIC_API_KEY=.*sk" "$TODAY_FILE"; then
  fail "Dangerous token-like pattern found in today_tasks.md."
fi

log "Latest today tasks: $TODAY_FILE"
cat "$TODAY_FILE"
