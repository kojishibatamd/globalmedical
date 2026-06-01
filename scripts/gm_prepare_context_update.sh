#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/gm_prepare_context_update.sh <topic>"
  echo "Example: scripts/gm_prepare_context_update.sh ai_workflow_20260531_120000"
  exit 1
fi

TOPIC="$1"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVIEW_ROOT="$ROOT_DIR/outputs/context_review"
PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"

if [[ ! "$TOPIC" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "ERROR: topic must contain only letters, numbers, underscores, and hyphens."
  exit 1
fi

mkdir -p "$REVIEW_ROOT"

if [ -f "$HOME/.env_globalmedical" ]; then
  source "$HOME/.env_globalmedical"
else
  echo "WARNING: ~/.env_globalmedical not found."
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/prepare_context_update.py" "$TOPIC"

LATEST_DIR="$(ls -td "$REVIEW_ROOT/${TOPIC}_"* 2>/dev/null | head -1)"

if [ -z "$LATEST_DIR" ]; then
  echo "ERROR: Context review output directory not found."
  exit 1
fi

echo
echo "Context review output:"
echo "$LATEST_DIR"
echo
echo "Key files:"
echo "$LATEST_DIR/project_instruction_patch.md"
echo "$LATEST_DIR/company_context_update_plan.md"
echo "$LATEST_DIR/decisions_log_append.md"
echo "$LATEST_DIR/open_questions_update.md"
echo "$LATEST_DIR/review_notes.md"
echo "$LATEST_DIR/risk_check.md"
echo

open "$LATEST_DIR"

if [ -f "$LATEST_DIR/project_instruction_patch.md" ]; then
  echo "---- project_instruction_patch.md ----"
  sed -n '1,220p' "$LATEST_DIR/project_instruction_patch.md"
fi

if [ -f "$LATEST_DIR/review_notes.md" ]; then
  echo
  echo "---- review_notes.md ----"
  sed -n '1,220p' "$LATEST_DIR/review_notes.md"
fi
