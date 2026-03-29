#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path.home() / "globalmedical"

def clean(text):
    lines = [l.strip() for l in text.split("\n")]
    lines = [l for l in lines if l]
    return "\n".join(lines) + "\n"

def main(topic):
    p = ROOT / "inbox" / topic / "raw.md"
    txt = p.read_text()
    p.write_text(clean(txt))

if __name__ == "__main__":
    main(sys.argv[1])
