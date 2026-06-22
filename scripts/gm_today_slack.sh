#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$HOME/.env_globalmedical"
FORCE_ARGS=()
LABEL_UPDATE=0

log() {
  printf '%s\n' "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE_ARGS+=("--force")
      ;;
    --label-update)
      LABEL_UPDATE=1
      ;;
    *)
      fail "Unknown option: $arg"
      ;;
  esac
done

if [ ! -f "$ENV_FILE" ]; then
  fail "~/.env_globalmedical not found."
fi

# shellcheck source=/dev/null
if ! source "$ENV_FILE" >/dev/null 2>&1; then
  fail "Failed to source ~/.env_globalmedical."
fi

if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
  fail "SLACK_WEBHOOK_URL is not set."
fi

log "Loading GM Today text..."
if [ "${#FORCE_ARGS[@]}" -gt 0 ]; then
  TODAY_TEXT="$("$ROOT_DIR/scripts/gm_today_remote.sh" "${FORCE_ARGS[@]}")"
else
  TODAY_TEXT="$("$ROOT_DIR/scripts/gm_today_remote.sh")"
fi

if [ "$LABEL_UPDATE" -eq 1 ]; then
  TODAY_TEXT="【更新版】
$TODAY_TEXT"
fi

PAYLOAD="$(
  GM_TODAY_TEXT="$TODAY_TEXT" python3 -c 'import json, os; print(json.dumps({"text": os.environ["GM_TODAY_TEXT"]}, ensure_ascii=False))'
)"

log "Posting GM Today to Slack..."
curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  --data "$PAYLOAD" \
  "$SLACK_WEBHOOK_URL" >/dev/null

log "Slack post completed."
