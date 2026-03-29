#!/usr/bin/env bash
set -e

TOPIC="$1"

python3 scripts/clean_capture.py "$TOPIC"
python3 scripts/summarize_discussion.py "$TOPIC"
bash scripts/ai_pipeline.sh "$TOPIC"
