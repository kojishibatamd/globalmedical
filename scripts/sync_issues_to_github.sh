#!/usr/bin/env bash
set -euo pipefail

BUNDLE_FILE="${1:-}"

if [ -z "$BUNDLE_FILE" ] || [ ! -f "$BUNDLE_FILE" ]; then
  echo "Usage: sync_issues_to_github.sh <issues_bundle.md>"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found"
  exit 1
fi

python3 - "$BUNDLE_FILE" <<'PY'
import re
import sys
import subprocess
from pathlib import Path

bundle = Path(sys.argv[1]).read_text(encoding="utf-8")
parts = re.split(r"=== FILE: ", bundle)

for part in parts:
    if not part.strip():
        continue
    lines = part.splitlines()
    path = lines[0].strip().replace(" ===", "")
    body = "\n".join(lines[1:]).strip()

    title = None
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = Path(path).stem

    # 既存Issueの重複判定は簡易に title 検索
    search = subprocess.run(
        ["gh", "issue", "list", "--search", title, "--json", "title,number"],
        capture_output=True, text=True
    )
    if search.returncode != 0:
        print(f"skip search failed: {title}")
        continue

    if title in search.stdout:
        print(f"exists: {title}")
        continue

    result = subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"created: {title}")
    else:
        print(f"failed: {title}")
        print(result.stderr)
PY