#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path.home() / "globalmedical"

def main(topic):
    raw = ROOT / "inbox" / topic / "raw.md"
    out = ROOT / "inbox" / topic / "discussion.md"

    txt = raw.read_text()

    out.write_text(f"""# {topic}

## 背景
{txt[:500]}

## 現時点の論点
- 要整理

## 制約
- 要整理

## 次アクション候補
- Issue化
""")

if __name__ == "__main__":
    main(sys.argv[1])
