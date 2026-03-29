#!/usr/bin/env python3
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / "globalmedical"
INBOX = ROOT / "inbox"

TOPIC_RE = re.compile(r"^[a-z0-9_-]+$")

def read():
    raw = sys.stdin.buffer.read(4)
    if not raw:
        return None
    size = struct.unpack("<I", raw)[0]
    return json.loads(sys.stdin.buffer.read(size))

def send(msg):
    data = json.dumps(msg).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def validate(topic):
    if not TOPIC_RE.match(topic):
        raise ValueError("invalid topic")
    return topic

def ensure(topic):
    d = INBOX / topic
    d.mkdir(parents=True, exist_ok=True)
    return d

def save(topic, content):
    p = ensure(topic) / "raw.md"
    with p.open("a", encoding="utf-8") as f:
        f.write("\n\n" + content)
    return str(p)

def run(cmd):
    subprocess.run(cmd, cwd=str(ROOT), check=True)

def main():
    msg = read()
    if not msg:
        return

    try:
        topic = validate(msg["topic"])
        content = msg["content"]
        opt = msg.get("options", {})

        path = save(topic, content)

        if opt.get("clean"):
            run(["python3", "scripts/clean_capture.py", topic])

        if opt.get("summarize"):
            run(["python3", "scripts/summarize_discussion.py", topic])

        if opt.get("run_pipeline"):
            run(["bash", "scripts/run_topic_pipeline.sh", topic])

        send({
            "ok": True,
            "saved": path
        })

    except Exception as e:
        send({
            "ok": False,
            "error": str(e)
        })

if __name__ == "__main__":
    main()
