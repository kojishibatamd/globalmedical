#!/usr/bin/env bash
set -euo pipefail

TOPIC=""
INPUT_MODE="auto"
INPUT_FILE=""
FROM_ISSUE=""
SYNC_GITHUB="false"

usage() {
  echo "Usage:"
  echo "  ./scripts/ai_pipeline.sh <topic> [--sync-github]"
  echo "  ./scripts/ai_pipeline.sh <topic> --from-file <path> [--sync-github]"
  echo "  ./scripts/ai_pipeline.sh <topic> --stdin [--sync-github]"
  echo "  ./scripts/ai_pipeline.sh <topic> --from-issue <issue-number> [--sync-github]"
  exit 1
}

if [ $# -lt 1 ]; then
  usage
fi

TOPIC="$1"
shift || true

while [ $# -gt 0 ]; do
  case "$1" in
    --stdin)
      INPUT_MODE="stdin"
      shift
      ;;
    --from-file)
      INPUT_MODE="file"
      INPUT_FILE="${2:-}"
      shift 2
      ;;
    --from-issue)
      INPUT_MODE="issue"
      FROM_ISSUE="${2:-}"
      shift 2
      ;;
    --sync-github)
      SYNC_GITHUB="true"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

ROOT_DIR="$(git rev-parse --show-toplevel)"
INBOX_DIR="$ROOT_DIR/inbox/$TOPIC"
TMP_DIR="$ROOT_DIR/tmp/$TOPIC"
DISCUSSION_FILE="$INBOX_DIR/discussion.md"
RAW_FILE="$INBOX_DIR/raw.md"
TXT_FILE="$INBOX_DIR/discussion.txt"
CANONICAL_INPUT="$TMP_DIR/input.md"

mkdir -p "$INBOX_DIR" "$TMP_DIR"

# -------------------------------
# Step 0: 入力解決
# -------------------------------
resolve_input() {
  case "$INPUT_MODE" in
    auto)
      if [ -f "$DISCUSSION_FILE" ]; then
        cp "$DISCUSSION_FILE" "$CANONICAL_INPUT"
      elif [ -f "$TXT_FILE" ]; then
        cp "$TXT_FILE" "$CANONICAL_INPUT"
      elif [ -f "$RAW_FILE" ]; then
        cp "$RAW_FILE" "$CANONICAL_INPUT"
      else
        cat <<EOF > "$DISCUSSION_FILE"
# $TOPIC

## 背景
（ここにスレッド要約を貼る）

## 現時点の論点
（ここに貼る）

## 制約
（ここに貼る）

## 次アクション候補
（ここに貼る）
EOF
        echo "Created template: $DISCUSSION_FILE"
        echo "要約を貼って再実行するか、--stdin / --from-file / --from-issue を使ってください。"
        exit 0
      fi
      ;;
    stdin)
      cat > "$CANONICAL_INPUT"
      ;;
    file)
      if [ ! -f "$INPUT_FILE" ]; then
        echo "Missing input file: $INPUT_FILE"
        exit 1
      fi
      cp "$INPUT_FILE" "$CANONICAL_INPUT"
      ;;
    issue)
      if ! command -v gh >/dev/null 2>&1; then
        echo "gh CLI not found"
        exit 1
      fi
      gh issue view "$FROM_ISSUE" --json title,body > "$TMP_DIR/issue.json"
      python3 - <<'PY' > "$CANONICAL_INPUT"
import json, os
p = os.path.expanduser(os.environ["TMP_JSON"])
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
print(f"# {d['title']}\n")
print(d.get("body",""))
PY
      ;;
    *)
      echo "Invalid input mode"
      exit 1
      ;;
  esac
}
export TMP_JSON="$TMP_DIR/issue.json"
resolve_input

# -------------------------------
# Step 1: docs判定
# -------------------------------
echo "== Step 1: docs判定 =="
codex "$(cat <<EOF
$(cat "$ROOT_DIR/docs/prompts/docs_update_judge.md")

対象テキスト:
$(cat "$CANONICAL_INPUT")

出力先:
$TMP_DIR/docs_judge.md

Write result to the file above.
Do not modify repository files yet.
EOF
)"

# -------------------------------
# Step 2: docs bundle生成
# -------------------------------
echo "== Step 2: docs bundle生成 =="
codex "$(cat <<EOF
$(cat "$ROOT_DIR/docs/prompts/docs_bundle_generation.md")

対象テキスト:
$(cat "$CANONICAL_INPUT")

補助情報:
$(cat "$TMP_DIR/docs_judge.md")

出力先:
$TMP_DIR/docs_bundle.md

Write result to the file above.
Do not modify repository files yet.
EOF
)"

# -------------------------------
# Step 3: docs + AGENTS同期
# -------------------------------
echo "== Step 3: docs + AGENTS同期 =="
codex "$(cat <<EOF
$(cat "$ROOT_DIR/docs/prompts/docs_agents_sync.md")

Bundle:
$(cat "$TMP_DIR/docs_bundle.md")
EOF
)"

# -------------------------------
# Step 4: Issue bundle生成（番号なし）
# -------------------------------
echo "== Step 4: Issue bundle生成 =="
codex "$(cat <<EOF
$(cat "$ROOT_DIR/docs/prompts/issue_generation.md")

追加ルール:
- do NOT use numbering
- filename format: issues/<category>_<topic>_<action>.md
- sort issues by priority (highest first)
- include one line near the top: Priority: High/Medium/Low
- include one line near the top: Type: parent/child/concept/review

対象テキスト:
$(cat "$CANONICAL_INPUT")

出力先:
$TMP_DIR/issues_bundle.md

Write result to the file above.
Do not modify repository files yet.
EOF
)"

# -------------------------------
# Step 5: Issueファイル作成
# -------------------------------
echo "== Step 5: Issueファイル作成 =="
codex "$(cat <<EOF
Create issue files from the bundle below.

Requirements:
- create directories if needed
- create every file exactly as provided
- do not modify wording
- do not skip any file
- filenames are already canonical and contain no numbering
- minimal diff
- do not change unrelated files
- do not commit or push

Bundle:
$(cat "$TMP_DIR/issues_bundle.md")
EOF
)"

# -------------------------------
# Step 6: 最優先Issue選択
# -------------------------------
echo "== Step 6: 最優先Issue選択 =="
python3 "$ROOT_DIR/scripts/pick_priority_issue.py" "$TMP_DIR/issues_bundle.md" > "$TMP_DIR/selected_issue.txt"
SELECTED_ISSUE="$(cat "$TMP_DIR/selected_issue.txt")"

if [ -z "$SELECTED_ISSUE" ]; then
  echo "No executable issue selected."
  exit 0
fi

echo "Selected issue: $SELECTED_ISSUE"

# -------------------------------
# Step 7: Codexで実装
# -------------------------------
echo "== Step 7: Codexで実装 =="
codex "$(cat <<EOF
$(cat "$ROOT_DIR/docs/prompts/codex_execution.md")

Implement the following issue:
$SELECTED_ISSUE

Rules:
- follow AGENTS.md strictly
- consult docs/ when relevant
- minimal diff
- do not modify unrelated files
- preserve patent / NDA / pricing constraints
- keep mobile responsiveness where relevant

Output:
1. modified files
2. summary of changes
3. risks
4. ready for review
EOF
)"

# -------------------------------
# Step 8: GitHub Issue同期（任意）
# -------------------------------
if [ "$SYNC_GITHUB" = "true" ]; then
  echo "== Step 8: GitHub Issue同期 =="
  bash "$ROOT_DIR/scripts/sync_issues_to_github.sh" "$TMP_DIR/issues_bundle.md"
fi

echo "== Done =="
echo "Review with:"
echo "  git status"
echo "  git diff"