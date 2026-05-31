#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/gm_ingest_clipboard.sh <topic>"
  exit 1
fi

TOPIC="$1"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INBOX_DIR="$ROOT_DIR/inbox/$TOPIC"
DISCUSSION_FILE="$INBOX_DIR/discussion.md"
OUTPUT_ROOT="$ROOT_DIR/outputs/thread_analysis"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

mkdir -p "$INBOX_DIR" "$OUTPUT_ROOT"

CLIP_TEXT="$(pbpaste)"
if [ -z "$CLIP_TEXT" ]; then
  echo "ERROR: Clipboard is empty."
  exit 1
fi

printf "%s\n" "$CLIP_TEXT" > "$DISCUSSION_FILE"

echo "Saved clipboard to:"
echo "$DISCUSSION_FILE"
echo

if [ -f "$HOME/.env_globalmedical" ]; then
  set +x
  source "$HOME/.env_globalmedical"
  set +x
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




