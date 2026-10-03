#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/globalmedical/work/globalmedical"
ENV_FILE="$HOME/.env_globalmedical"

if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE" >/dev/null 2>&1
fi

export GLMED_PROGRESS_CHANNEL_ID="${GLMED_PROGRESS_CHANNEL_ID:-${GLMED_DAILY_SYNC_CHANNEL_ID:-C0BQATZK29K}}"

exec /usr/bin/python3 "$ROOT/scripts/gm_daily_memory_fetch_slack.py" "$@"
