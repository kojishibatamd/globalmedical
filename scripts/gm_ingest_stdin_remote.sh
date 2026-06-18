#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_ROOT="$ROOT_DIR/outputs/thread_analysis"
REVISION_ROOT="$ROOT_DIR/outputs/project_context_revision"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

log() {
  printf '%s\n' "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

suggest_base_topic() {
  local text="$1"

  if printf "%s" "$text" | grep -Eiq "KARTE|PHR|VNEXT|患者向け"; then
    echo "karte"
  elif printf "%s" "$text" | grep -Eiq "医療鑑定|鑑定|FAXDM|弁護士"; then
    echo "kantei"
  elif printf "%s" "$text" | grep -Eiq "遠隔化|遠隔読影|RDP|VMware|TeamViewer"; then
    echo "enkakuka"
  elif printf "%s" "$text" | grep -Eiq "特許|弁理士|出願"; then
    echo "patent"
  elif printf "%s" "$text" | grep -Eiq "AI業務|Mac|pipeline|コンテキスト|プロジェクト指示|要約|SSH"; then
    echo "ai_workflow"
  elif printf "%s" "$text" | grep -Eiq "Web|LP|サイト|WordPress|アクセス解析"; then
    echo "website"
  elif printf "%s" "$text" | grep -Eiq "資金調達|投資家|ANGEL|ピッチ"; then
    echo "fundraising"
  else
    echo "general"
  fi
}

THREAD_TEXT="$(cat)"

if [ -z "$(printf "%s" "$THREAD_TEXT" | tr -d '[:space:]')" ]; then
  fail "stdin is empty."
fi

BASE_TOPIC="$(suggest_base_topic "$THREAD_TEXT")"
TOPIC="${BASE_TOPIC}_$(date +%Y%m%d_%H%M%S)"
TOPIC="$(printf "%s" "$TOPIC" | sed -E 's/[^A-Za-z0-9_-]+/_/g; s/^_+//; s/_+$//')"

if [ -z "$TOPIC" ]; then
  TOPIC="general_$(date +%Y%m%d_%H%M%S)"
fi

INBOX_DIR="$ROOT_DIR/inbox/$TOPIC"
DISCUSSION_FILE="$INBOX_DIR/discussion.md"

mkdir -p "$INBOX_DIR" "$OUTPUT_ROOT" "$REVISION_ROOT"
printf "%s\n" "$THREAD_TEXT" > "$DISCUSSION_FILE"

log "Auto topic: $TOPIC"
log "Saved stdin to: $DISCUSSION_FILE"

if [ -f "$HOME/.env_globalmedical" ]; then
  # shellcheck source=/dev/null
  if ! source "$HOME/.env_globalmedical" >/dev/null 2>&1; then
    fail "Failed to source ~/.env_globalmedical."
  fi
else
  log "WARNING: ~/.env_globalmedical not found."
fi

export GM_NO_UI=1

log "Running analyze_thread_api.py..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/analyze_thread_api.py" "$TOPIC" >&2

log "Running gm_prepare_context_update.sh..."
"$ROOT_DIR/scripts/gm_prepare_context_update.sh" "$TOPIC" >&2

log "Running gm_revise_project_context.sh..."
"$ROOT_DIR/scripts/gm_revise_project_context.sh" >&2

LATEST_DIR="$(ls -td "$REVISION_ROOT"/*/ 2>/dev/null | head -n 1 || true)"
REVISED_FILE="${LATEST_DIR%/}/project_instruction_revised.md"

if [ -z "$LATEST_DIR" ] || [ ! -f "$REVISED_FILE" ]; then
  fail "Latest project_instruction_revised.md not found."
fi

if grep -E -q 'sk-ant-|sk-proj-|ghp_|GITHUB_TOKEN=.*ghp|OPENAI_API_KEY=.*sk|ANTHROPIC_API_KEY=.*sk' "$REVISED_FILE"; then
  fail "Dangerous token-like pattern found in project_instruction_revised.md."
fi

log "Latest revised instruction: $REVISED_FILE"
cat "$REVISED_FILE"
