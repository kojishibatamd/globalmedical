#!/usr/bin/env python3
import re
import sys

bundle_path = sys.argv[1]

with open(bundle_path, "r", encoding="utf-8") as f:
    text = f.read()

blocks = re.split(r"=== FILE: ", text)
candidates = []

priority_score = {"High": 0, "Medium": 1, "Low": 2}
type_penalty = {"child": 0, "review": 1, "concept": 2, "parent": 3}

for block in blocks:
    if not block.strip():
      continue
    lines = block.splitlines()
    path = lines[0].strip().replace(" ===", "")
    body = "\n".join(lines[1:])
    pr_match = re.search(r"^Priority:\s*(High|Medium|Low)\s*$", body, re.MULTILINE)
    ty_match = re.search(r"^Type:\s*(parent|child|concept|review)\s*$", body, re.MULTILINE)
    pr = pr_match.group(1) if pr_match else "Medium"
    ty = ty_match.group(1) if ty_match else "child"
    score = (priority_score.get(pr, 1), type_penalty.get(ty, 0), path)
    if ty != "parent":
        candidates.append((score, path))

if not candidates:
    print("")
else:
    candidates.sort()
    print(candidates[0][1])