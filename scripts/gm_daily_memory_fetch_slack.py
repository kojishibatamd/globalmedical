#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("/Users/globalmedical/work/globalmedical")
OUT_DIR = Path(os.environ.get("GLMED_DAILY_SYNC_OUT_DIR", ROOT / "outputs" / "daily_memory_sync"))
STATE_FILE = OUT_DIR / ".last_progress_checkpoint.json"
EVENTS_FILE = OUT_DIR / "progress_events.jsonl"
LAST_SUCCESS_FILE = OUT_DIR / ".last_success.json"
LEGACY_STATE_FILE = OUT_DIR / ".last_slack_ts"
TOKYO = ZoneInfo("Asia/Tokyo")

CHANNEL_ID = os.environ.get("GLMED_PROGRESS_CHANNEL_ID") or os.environ.get("GLMED_DAILY_SYNC_CHANNEL_ID", "C0BQATZK29K")
TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
MARKERS = ["[GLMED_PROGRESS]", "[GLMED_DAILY_SYNC]"]
MAX_RATE_LIMIT_RETRIES = 2

SECRET_PATTERNS = [
    re.compile(r"sk-ant-", re.I),
    re.compile(r"sk-proj-", re.I),
    re.compile(r"ghp_", re.I),
    re.compile(r"xox[baprs]-", re.I),
    re.compile(r"hooks\.slack\.com/services/", re.I),
    re.compile(r"GITHUB_TOKEN\s*=.*ghp", re.I),
    re.compile(r"OPENAI_API_KEY\s*=.*sk", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*=.*sk", re.I),
    re.compile(r"SLACK_BOT_TOKEN\s*=.*xox", re.I),
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def now_iso() -> str:
    return datetime.now(TOKYO).isoformat(timespec="seconds")


def api_history_page(cursor: str = "", oldest: str = "") -> dict:
    if not TOKEN:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")
    params = {"channel": CHANNEL_ID, "limit": "200"}
    if cursor:
        params["cursor"] = cursor
    if oldest:
        params["oldest"] = oldest
        params["inclusive"] = "false"
    req = urllib.request.Request(
        f"https://slack.com/api/conversations.history?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    retries = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429 and retries < MAX_RATE_LIMIT_RETRIES:
                retry_after = int(e.headers.get("Retry-After", "1"))
                retries += 1
                time.sleep(max(retry_after, 1))
                continue
            raise


def fetch_all_messages(oldest: str = "") -> tuple[list[dict], dict]:
    cursor = ""
    messages: list[dict] = []
    page_count = 0
    while True:
        data = api_history_page(cursor=cursor, oldest=oldest)
        page_count += 1
        messages.extend(data.get("messages", []))
        cursor = str(data.get("response_metadata", {}).get("next_cursor", "")).strip()
        if not cursor:
            return messages, {"page_count": page_count, "complete": True}


def parse_sync(text: str) -> dict | None:
    marker = next((candidate for candidate in MARKERS if text.startswith(candidate)), None)
    if not marker:
        return None
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    m = re.match(r"^date:\s*(\d{4}-\d{2}-\d{2})\s*$", lines[1].strip())
    if not m:
        return None
    body = "\n".join(lines[2:]).strip()
    if not body:
        return None
    kind = "progress"
    if marker == "[GLMED_DAILY_SYNC]":
        kind = "legacy_daily_sync"
        if body.startswith("[SYNC_CONTEXT_MISSING]"):
            kind = "sync_context_missing"
    parsed = {"date": m.group(1), "marker": marker, "kind": kind, "body": body}
    # Preserve only an explicitly supplied ID; never infer one from topic/summary.
    ids = re.findall(r"^task_id:\s*([A-Za-z0-9_.:-]+)\s*$", body, re.M)
    if len(ids) == 1:
        parsed["task_id"] = ids[0]
    return parsed


def load_events() -> dict[str, dict]:
    events: dict[str, dict] = {}
    if not EVENTS_FILE.exists():
        return events
    for line in EVENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        events[str(event["event_id"])] = event
    return events


def write_events(events: dict[str, dict]) -> None:
    ordered = sorted(events.values(), key=lambda item: (item["date"], float(item["ts"]), item["event_id"]))
    EVENTS_FILE.write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in ordered),
        encoding="utf-8",
    )


def managed_marker_path(date: str) -> Path:
    return OUT_DIR / f"{date}.gm_progress.md"


def rebuild_daily_markdown(events: dict[str, dict]) -> list[Path]:
    written: list[Path] = []
    dates = sorted({event["date"] for event in events.values() if event.get("kind") == "progress"})
    for date in dates:
        progress = [
            event for event in events.values()
            if event.get("date") == date and event.get("kind") == "progress"
        ]
        progress.sort(key=lambda item: float(item["ts"]))
        lines = [
            "# GLMED_PROGRESS",
            "",
            f"- date: {date}",
            f"- generated_at: {now_iso()}",
            f"- item_count: {len(progress)}",
            "",
        ]
        for index, event in enumerate(progress, 1):
            lines.extend(
                [
                    f"## {index}. {event['channel_id']}:{event['ts']}",
                    "",
                    event["body"].rstrip(),
                    "",
                ]
            )
        out = managed_marker_path(date)
        out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        written.append(out)
        legacy_out = OUT_DIR / f"{date}.md"
        if not legacy_out.exists():
            legacy_out.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(legacy_out)
    return written


def load_checkpoint() -> str:
    if not STATE_FILE.exists():
        return ""
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8", errors="replace"))
        return str(data.get("latest_complete_ts", "")).strip()
    except json.JSONDecodeError:
        return ""


def since_ts_from_args(args: argparse.Namespace) -> str:
    if args.since_ts:
        return args.since_ts
    if args.lookback_days:
        start = datetime.now(TOKYO) - timedelta(days=args.lookback_days)
        return str(start.timestamp())
    return load_checkpoint()


def checkpoint_ts(messages: list[dict], previous: str) -> str:
    ts_values = [float(str(msg.get("ts", "0")) or "0") for msg in messages]
    if not ts_values:
        return previous
    return str(max(ts_values))


def save_success(status: str, added: int, valid_progress_count: int, sync_missing_count: int, checkpoint: str, pages: int) -> None:
    LAST_SUCCESS_FILE.write_text(
        json.dumps(
            {
                "saved_at": now_iso(),
                "channel_id": CHANNEL_ID,
                "status": status,
                "added_events": added,
                "valid_progress_count": valid_progress_count,
                "sync_context_missing_count": sync_missing_count,
                "latest_complete_ts": checkpoint,
                "page_count": pages,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and store GLMED_PROGRESS messages by Slack post.")
    parser.add_argument("--since-ts", help="Backfill from a Slack timestamp without using legacy .last_slack_ts.")
    parser.add_argument("--lookback-days", type=int, help="Backfill a recent period. Does not call API unless this script is executed.")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    previous_checkpoint = load_checkpoint()
    oldest = since_ts_from_args(args)
    try:
        messages, fetch_meta = fetch_all_messages(oldest=oldest)
    except Exception as e:
        log(f"ERROR: fetch_failed: {type(e).__name__}: {e}")
        return 1

    events = load_events()
    before = len(events)
    valid_progress_count = 0
    sync_missing_count = 0
    legacy_count = 0
    for msg in messages:
        ts = str(msg.get("ts", ""))
        parsed = parse_sync(str(msg.get("text", "")))
        if not parsed or not ts:
            continue
        event_id = f"{CHANNEL_ID}:{ts}"
        if any(pattern.search(parsed["body"]) for pattern in SECRET_PATTERNS):
            log(f"ERROR: possible secret/token pattern detected in {event_id}. Refusing to save.")
            return 1
        event = {
            "event_id": event_id,
            "channel_id": CHANNEL_ID,
            "ts": ts,
            "date": parsed["date"],
            "marker": parsed["marker"],
            "kind": parsed["kind"],
            "body": parsed["body"],
            "fetched_at": now_iso(),
        }
        if "task_id" in parsed:
            event["task_id"] = parsed["task_id"]
        events[event_id] = event
        if parsed["kind"] == "progress":
            valid_progress_count += 1
        elif parsed["kind"] == "sync_context_missing":
            sync_missing_count += 1
        else:
            legacy_count += 1

    write_events(events)
    written = rebuild_daily_markdown(events)
    latest_ts = checkpoint_ts(messages, previous_checkpoint)
    STATE_FILE.write_text(
        json.dumps(
            {
                "latest_complete_ts": latest_ts,
                "updated_at": now_iso(),
                "channel_id": CHANNEL_ID,
                "note": ".last_slack_ts is legacy and is not used as proof that all progress was saved.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    added = len(events) - before
    if valid_progress_count:
        status = "success_with_progress"
    elif sync_missing_count and not legacy_count:
        status = "sync_context_missing_only"
    else:
        status = "success_no_new_progress"
    save_success(status, added, valid_progress_count, sync_missing_count, latest_ts, int(fetch_meta["page_count"]))
    if LEGACY_STATE_FILE.exists():
        log("Legacy .last_slack_ts ignored for checkpointing.")
    log(f"Saved events: added={added}, total={len(events)}, daily_files={len(written)}, status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
