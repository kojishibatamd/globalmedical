#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVIEW_ROOT="$ROOT_DIR/outputs/context_review"

if [ $# -ge 1 ] && [ -n "$1" ]; then
  TOPIC="$1"
  if [[ ! "$TOPIC" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: topic must contain only letters, numbers, underscores, and hyphens."
    exit 1
  fi
  LATEST_DIR="$(ls -td "$REVIEW_ROOT/${TOPIC}_"* 2>/dev/null | head -1)"
else
  LATEST_DIR="$(ls -td "$REVIEW_ROOT"/* 2>/dev/null | head -1)"
fi

if [ -z "${LATEST_DIR:-}" ]; then
  echo "ERROR: context_review output directory not found."
  exit 1
fi

PATCH_FILE="$LATEST_DIR/project_instruction_patch.md"

if [ ! -f "$PATCH_FILE" ]; then
  echo "ERROR: project_instruction_patch.md not found:"
  echo "$PATCH_FILE"
  exit 1
fi

if grep -q "該当セクションなし\|抽出エラー" "$PATCH_FILE"; then
  echo "WARNING: project_instruction_patch.md may contain extraction error text."
  echo "Please review before pasting."
fi

pbcopy < "$PATCH_FILE"

echo "Copied project_instruction_patch.md to clipboard:"
echo "$PATCH_FILE"
echo
echo "Preview:"
echo "----------------------------------------"
sed -n '1,120p' "$PATCH_FILE"
echo "----------------------------------------"
