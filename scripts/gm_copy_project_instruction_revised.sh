#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVISION_ROOT="$ROOT_DIR/outputs/project_context_revision"

LATEST_DIR="$(ls -td "$REVISION_ROOT"/* 2>/dev/null | head -1)"

if [ -z "${LATEST_DIR:-}" ]; then
  echo "ERROR: project_context_revision output directory not found."
  echo "Run: scripts/gm_revise_project_context.sh"
  exit 1
fi

REVISED_FILE="$LATEST_DIR/project_instruction_revised.md"

if [ ! -f "$REVISED_FILE" ]; then
  echo "ERROR: project_instruction_revised.md not found:"
  echo "$REVISED_FILE"
  exit 1
fi

if grep -q "抽出エラー\|該当セクションなし" "$REVISED_FILE"; then
  echo "WARNING: project_instruction_revised.md may contain extraction error text."
  echo "Please review before pasting."
fi

pbcopy < "$REVISED_FILE"

echo "Copied project_instruction_revised.md to clipboard:"
echo "$REVISED_FILE"
echo
echo "Character count:"
wc -m "$REVISED_FILE"
echo
echo "Preview:"
echo "----------------------------------------"
sed -n '1,160p' "$REVISED_FILE"
echo "----------------------------------------"
