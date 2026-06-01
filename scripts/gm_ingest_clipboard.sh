#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_ROOT="$ROOT_DIR/outputs/thread_analysis"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

CLIP_TEXT="$(pbpaste)"

if [ -z "$CLIP_TEXT" ]; then
  echo "ERROR: Clipboard is empty."
  exit 1
fi

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
  elif printf "%s" "$text" | grep -Eiq "AI業務|Mac|pipeline|コンテキスト|プロジェクト指示|要約"; then
    echo "ai_workflow"
  elif printf "%s" "$text" | grep -Eiq "Web|LP|サイト|WordPress|アクセス解析"; then
    echo "website"
  elif printf "%s" "$text" | grep -Eiq "資金調達|投資家|ANGEL|ピッチ"; then
    echo "fundraising"
  else
    echo "general"
  fi
}

if [ $# -ge 1 ] && [ -n "$1" ]; then
  TOPIC="$1"
  TOPIC="$(printf "%s" "$TOPIC" | sed -E 's/[^A-Za-z0-9_-]+/_/g; s/^_+//; s/_+$//')"
  if [ -z "$TOPIC" ]; then
    TOPIC="general_$(date +%Y%m%d_%H%M%S)"
  fi
  echo "Topic specified:"
  echo "$TOPIC"
else
  BASE_TOPIC="$(suggest_base_topic "$CLIP_TEXT")"
  TOPIC="${BASE_TOPIC}_$(date +%Y%m%d_%H%M%S)"
  echo "Auto topic:"
  echo "$TOPIC"
fi

INBOX_DIR="$ROOT_DIR/inbox/$TOPIC"
DISCUSSION_FILE="$INBOX_DIR/discussion.md"

mkdir -p "$INBOX_DIR" "$OUTPUT_ROOT"

printf "%s\n" "$CLIP_TEXT" > "$DISCUSSION_FILE"

echo
echo "Saved clipboard to:"
echo "$DISCUSSION_FILE"
echo

if [ -f "$HOME/.env_globalmedical" ]; then
  source "$HOME/.env_globalmedical"
else
  echo "WARNING: ~/.env_globalmedical not found."
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/analyze_thread_api.py" "$TOPIC"

LATEST_DIR="$(ls -td "$OUTPUT_ROOT/${TOPIC}_"* 2>/dev/null | head -1)"

if [ -z "$LATEST_DIR" ]; then
  echo "ERROR: Output directory not found."
  exit 1
fi

echo
echo "Analysis output:"
echo "$LATEST_DIR"
echo
echo "Key files:"
echo "$LATEST_DIR/summary.md"
echo "$LATEST_DIR/decisions.md"
echo "$LATEST_DIR/context_update_proposal.md"
echo "$LATEST_DIR/risk_check.md"
echo

open "$LATEST_DIR"

if [ -f "$LATEST_DIR/context_update_proposal.md" ]; then
  echo "---- context_update_proposal.md ----"
  sed -n '1,220p' "$LATEST_DIR/context_update_proposal.md"
fi

echo
echo "Preparing context update review..."
"$ROOT_DIR/scripts/gm_prepare_context_update.sh" "$TOPIC"

if [ -x "$ROOT_DIR/scripts/gm_copy_project_instruction_patch.sh" ]; then
  echo
  echo "Copying project instruction patch to clipboard..."
  "$ROOT_DIR/scripts/gm_copy_project_instruction_patch.sh" "$TOPIC"
else
  echo
  echo "WARNING: gm_copy_project_instruction_patch.sh not found or not executable."
fi

echo
echo "Git status:"
git -C "$ROOT_DIR" status --short --branch
