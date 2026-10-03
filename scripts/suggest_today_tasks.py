#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
TODAY_ROOT = Path(os.getenv("GM_TODAY_OUTPUT_ROOT", ROOT / "outputs" / "today_tasks"))
REVISION_ROOT = Path(os.getenv("GM_TODAY_REVISION_ROOT", ROOT / "outputs" / "project_context_revision"))
REVIEW_ROOT = Path(os.getenv("GM_TODAY_REVIEW_ROOT", ROOT / "outputs" / "context_review"))
PROGRESS_ROOT = Path(os.getenv("GM_TODAY_PROGRESS_ROOT", ROOT / "outputs" / "progress"))
DAILY_SYNC_ROOT = Path(os.getenv("GM_TODAY_DAILY_SYNC_ROOT", ROOT / "outputs" / "daily_memory_sync"))
CURRENT_STATE_CANDIDATES = [
    ROOT / "outputs" / "current_state" / "current_state.md",
    ROOT / "outputs" / "current_state.md",
]
PROGRESS_DAILY_CHAR_LIMIT = 4000
DAILY_SYNC_DAILY_CHAR_LIMIT = 4000
TOKYO = ZoneInfo("Asia/Tokyo")
CURRENT_STATE_VALIDATION_SPEC_VERSION = "current_state.v3"

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GITHUB_PAT_PREFIX = "ghp" + "_"
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(rf"{GITHUB_PAT_PREFIX}[A-Za-z0-9_]{{12,}}"),
    re.compile(r"(?i)([A-Za-z0-9_]*API[_ -]?KEY\s*[:=]\s*)[^\s\"']+"),
    re.compile(r"(?i)(GITHUB_TOKEN\s*[:=]\s*)[^\s\"']+"),
]
SECTION_NAMES = [
    "today_tasks.md",
    "rationale.md",
    "deferred_tasks.md",
]
SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:===\s*)?"
    rf"(?P<name>{'|'.join(re.escape(name) for name in SECTION_NAMES)})"
    r"(?:\s*===)?\s*$"
)
TASK_ID_PATTERN = re.compile(r"(?:候補ID|作業ID|task_id|id)\s*[:：]\s*([A-Za-z0-9_.:-]+)", re.I)
CURRENT_STATE_TASK_HEADER = re.compile(
    r"^#{2,6}\s*(?:\[(?P<bracket>[A-Za-z0-9_.:-]+)\]|(?P<plain>[A-Za-z0-9_.:-]+))\s*(?P<title>.*)$"
)
FIELD_PATTERN = re.compile(r"^\s*[-*]?\s*([A-Za-z_]+|状態|status|title|件名|next_check|再確認日|blocked_by|contradicts|要確認)\s*[:：]\s*(.+?)\s*$", re.I)
FINAL_STATUSES = {"done", "completed", "complete", "完了", "stopped", "停止", "canceled", "cancelled", "中止", "superseded", "replaced", "置換済み"}
WAITING_STATUSES = {"waiting", "回答待ち", "保留"}
ACTIVE_STATUSES = {"open", "active", "pending", "todo", "未着手", "進行中", "候補"}
ALL_STATUSES = FINAL_STATUSES | WAITING_STATUSES | ACTIVE_STATUSES
VALID_APPROVAL_STATUSES = {"approved", "draft"}


@dataclass
class TaskCandidate:
    task_id: str
    title: str
    status: str
    body: str
    reason_today: str
    next_check: str
    blocked_by: str


class InputError(RuntimeError):
    pass


def redact_secrets(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED_SECRET]" if pattern.groups else "[REDACTED_SECRET]", text)
    return text


def read_text(path: Path) -> str:
    if not path.exists():
        return f"（ファイルなし: {path}）"
    return redact_secrets(path.read_text(encoding="utf-8", errors="replace"))


def now_tokyo() -> datetime:
    fixed = os.getenv("GM_TODAY_FIXED_NOW")
    if fixed:
        parsed = datetime.fromisoformat(fixed)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TOKYO)
        return parsed.astimezone(TOKYO)
    return datetime.now(TOKYO)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_meta(path: Path) -> dict[str, str | int | bool]:
    exists = path.exists()
    meta: dict[str, str | int | bool] = {
        "path": rel_path(path),
        "exists": exists,
    }
    if exists and path.is_file():
        stat = path.stat()
        meta.update(
            {
                "size_bytes": stat.st_size,
                "mtime_tokyo": datetime.fromtimestamp(stat.st_mtime, TOKYO).isoformat(timespec="seconds"),
                "sha256": file_hash(path),
            }
        )
    return meta


def latest_dir(root: Path) -> Optional[Path]:
    candidates = sorted(
        (path for path in root.glob("*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_recent_dated_logs(root: Path, today: datetime, days: int, char_limit: int) -> list[tuple[Path, str]]:
    logs: list[tuple[Path, str]] = []

    for offset in range(days):
        day = today.date() - timedelta(days=offset)
        path = PROGRESS_ROOT / f"{day:%Y-%m-%d}.md"
        if root != PROGRESS_ROOT:
            path = root / f"{day:%Y-%m-%d}.md"
        if not path.exists():
            continue

        text = read_text(path)
        if len(text) > char_limit:
            text = (
                "（長いため末尾のみ表示）\n"
                + text[-char_limit:]
            )
        logs.append((path, text))

    return logs


def latest_sync_status() -> str:
    success = DAILY_SYNC_ROOT / ".last_success.json"
    if not success.exists():
        return "unknown"
    try:
        data = json.loads(success.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return "parse_error"
    return str(data.get("status", "unknown")).strip() or "unknown"


def read_recent_daily_sync_logs(today: datetime, days: int = 14) -> tuple[list[tuple[Path, str]], str]:
    logs: list[tuple[Path, str]] = []
    status = latest_sync_status()
    for offset in range(days):
        day = today.date() - timedelta(days=offset)
        path = DAILY_SYNC_ROOT / f"{day:%Y-%m-%d}.gm_progress.md"
        if not path.exists():
            continue

        text = read_text(path)
        if text.lstrip().startswith("[SYNC_CONTEXT_MISSING]"):
            continue
        if len(text) > DAILY_SYNC_DAILY_CHAR_LIMIT:
            text = "（長いため末尾のみ表示）\n" + text[-DAILY_SYNC_DAILY_CHAR_LIMIT:]
        logs.append((path, text))
    return logs, status


def today_output_dir(now: datetime) -> Path:
    return TODAY_ROOT / now.strftime("%Y-%m-%d")


def current_state_path() -> Optional[Path]:
    override = os.getenv("GM_TODAY_CURRENT_STATE")
    if override:
        path = Path(override)
        return path if path.is_absolute() else ROOT / path
    for path in CURRENT_STATE_CANDIDATES:
        if path.exists():
            return path
    return None


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buffer: list[str] = []

    for line in text.splitlines():
        header = SECTION_HEADER_PATTERN.fullmatch(line)
        if header:
            if current:
                sections[current] = "\n".join(buffer).strip() + "\n"
            current = header.group("name")
            buffer = []
        elif current:
            buffer.append(line)

    if current:
        sections[current] = "\n".join(buffer).strip() + "\n"

    missing = [name for name in SECTION_NAMES if name not in sections]
    for name in missing:
        sections[name] = f"# {name}\n\n（抽出エラー: AI応答内に対応する見出しがありません）\n"

    if missing:
        sections["deferred_tasks.md"] = (
            sections["deferred_tasks.md"].rstrip()
            + "\n\n## 自動抽出エラー\n"
            + f"- 見出しを抽出できなかったセクション: {', '.join(missing)}\n"
        )

    return sections


def parse_date(value: str) -> Optional[datetime.date]:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        return None
    return datetime.strptime(match.group(0), "%Y-%m-%d").date()


def validate_dates(fields: dict[str, str], task_id: str, errors: list[str]) -> None:
    for key, value in fields.items():
        for match in re.finditer(r"\d{4}-\d{2}-\d{2}", value):
            candidate = match.group(0)
            try:
                datetime.strptime(candidate, "%Y-%m-%d")
            except ValueError:
                errors.append(f"{task_id}: invalid date in {key}: {candidate}")


def normalize_status(value: str) -> str:
    return value.strip().lower()


def parse_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        field = FIELD_PATTERN.match(line)
        if field:
            fields[field.group(1).strip()] = field.group(2).strip()
    return fields


def validate_current_state(current_state: str, target_date: datetime.date) -> tuple[list[TaskCandidate], list[str], dict[str, str]]:
    candidates: list[TaskCandidate] = []
    blocked_ids: set[str] = set()
    seen_ids: set[str] = set()
    errors: list[str] = []
    metadata_lines: list[str] = []
    metadata_complete = False
    current_id = ""
    current_title = ""
    current_lines: list[str] = []
    metadata: dict[str, str] = {}

    def flush() -> None:
        nonlocal current_id, current_title, current_lines
        if not current_id:
            return
        fields = parse_fields(current_lines)
        status = normalize_status(fields.get("status", fields.get("状態", "")))
        next_check = fields.get("next_check", fields.get("再確認日", ""))
        blocked_by = fields.get("blocked_by", fields.get("contradicts", fields.get("要確認", "")))
        title = fields.get("title", fields.get("件名", current_title)).strip()
        body = "\n".join(current_lines).strip()
        task_errors: list[str] = []
        validate_dates(fields, current_id, task_errors)
        if current_id in seen_ids:
            task_errors.append(f"{current_id}: duplicate task id")
        seen_ids.add(current_id)
        if not title:
            task_errors.append(f"{current_id}: title is required")
        if not status:
            task_errors.append(f"{current_id}: status is required")
        elif status not in ALL_STATUSES:
            task_errors.append(f"{current_id}: unknown status: {status}")
        if blocked_by:
            blocked_ids.add(current_id)
        if status in ACTIVE_STATUSES:
            for required in ["basis", "next_action"]:
                if not fields.get(required, "").strip():
                    task_errors.append(f"{current_id}: {required} is required for active candidate")
        errors.extend(task_errors)
        if not task_errors:
            if status in FINAL_STATUSES:
                pass
            elif status in WAITING_STATUSES:
                check_date = parse_date(next_check)
                if check_date and check_date <= target_date and not blocked_by:
                    candidates.append(TaskCandidate(current_id, title, status, body, "回答待ちの再確認日を満たしているため。", next_check, blocked_by))
            elif status in ACTIVE_STATUSES and not blocked_by:
                fields = parse_fields(current_lines)
                reason = fields.get("reason_today", fields.get("今日行う理由", "")).strip()
                candidates.append(TaskCandidate(current_id, title, status, body, reason, next_check, blocked_by))
        current_id = ""
        current_title = ""
        current_lines = []

    for line in current_state.splitlines():
        correction = re.search(r"(?:contradicts|要確認|blocked_by)\s*[:：]\s*([A-Za-z0-9_.:-]+)", line, re.I)
        if correction:
            blocked_ids.add(correction.group(1))
        header = CURRENT_STATE_TASK_HEADER.match(line)
        if header:
            metadata_complete = True
            flush()
            current_id = header.group("bracket") or header.group("plain") or ""
            current_title = header.group("title").strip()
            continue
        if not metadata_complete:
            metadata_lines.append(line)
        if current_id:
            current_lines.append(line)
    flush()

    metadata = parse_fields(metadata_lines)
    approval_status = normalize_status(metadata.get("approval_status", ""))
    if approval_status != "approved":
        if approval_status and approval_status not in VALID_APPROVAL_STATUSES:
            errors.append(f"approval_status is unknown: {approval_status}")
        else:
            errors.append("approval_status must be approved")
    if errors:
        raise InputError("current_state validation failed:\n - " + "\n - ".join(errors))
    if blocked_ids:
        candidates = [candidate for candidate in candidates if candidate.task_id not in blocked_ids]
    return candidates, sorted(blocked_ids), metadata


PRIORITY_NOTICE = (
    "上位3件は推奨順位です。すべてを今日完了する前提ではありません。\n"
    "下のリマインド候補を含め、当日の状況に応じて実施項目を選んでください。"
)


def state_tasks(text: str) -> list[TaskCandidate]:
    """Read already validated blocks, including waiting/blocked tasks for display."""
    tasks = []
    lines = text.splitlines()
    starts = [(i, CURRENT_STATE_TASK_HEADER.match(line)) for i, line in enumerate(lines)
              if CURRENT_STATE_TASK_HEADER.match(line)]
    for n, (i, header) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        body = "\n".join(lines[i + 1:end])
        fields = parse_fields(body.splitlines())
        tasks.append(TaskCandidate(
            header.group("bracket") or header.group("plain"),
            fields.get("title", fields.get("件名", header.group("title"))).strip(),
            normalize_status(fields.get("status", fields.get("状態", ""))), body,
            fields.get("reason_today", ""), fields.get("next_check", fields.get("再確認日", "")),
            fields.get("blocked_by", fields.get("contradicts", fields.get("要確認", ""))),
        ))
    return tasks


def progress_conflicts(tasks, state_metadata, logs, target_date):
    """Match explicit IDs or a unique exact title/declared progress_topic; never fuzzy match."""
    conflicts = {}
    for path, _ in logs:
        # Detection uses complete records, not the shortened AI context.
        text = read_text(path)
        file_date = parse_date(path.name)
        for block in re.split(r"^\s*(?:[-*]\s*)?\[GLMED_(?:PROGRESS|DAILY_SYNC)\]\s*$|^#{2,6} .*$", text, flags=re.M):
            fields = parse_fields(block.splitlines())
            kind = normalize_status(fields.get("type", fields.get("status", "")))
            if kind not in FINAL_STATUSES | WAITING_STATUSES | {"correction", "訂正"}:
                continue
            explicit_id = fields.get("task_id", "")
            matches = [task for task in tasks if task.task_id == explicit_id] if explicit_id else [
                task for task in tasks if fields.get("topic") in {
                    task.title, parse_fields(task.body.splitlines()).get("progress_topic", task.title)
                }
            ]
            if len(matches) != 1:
                continue
            task = matches[0]
            if task.status not in ACTIVE_STATUSES:
                continue
            try:
                event_date = parse_date(fields.get("date", "")) or file_date
                task_fields = parse_fields(task.body.splitlines())
                baseline = parse_date(task_fields.get("updated_at", "")) or parse_date(
                    state_metadata.get("as_of", state_metadata.get("approved_at", "")))
            except ValueError:
                continue
            if not event_date or event_date > target_date or (baseline and event_date <= baseline):
                continue
            proposal = ("根拠・次の行動とstatusを人間確認して更新（correctionは状態名ではありません）"
                        if kind in {"correction", "訂正"} else
                        "status: " + ("completed" if kind in {"done", "complete", "完了"} else kind))
            item = {"task_id": task.task_id, "status": task.status,
                    "date": str(event_date), "summary": fields.get("summary", fields.get("next", kind)),
                    "proposal": proposal, "source": rel_path(path)}
            if task.task_id not in conflicts or item["date"] >= conflicts[task.task_id]["date"]:
                conflicts[task.task_id] = item
    return list(conflicts.values())


def render_candidate_lists(sections: dict[str, str], metadata: dict[str, object]) -> None:
    """The model selects priorities only; approved tasks deterministically fill other lists."""
    priority = sections["today_tasks.md"].strip()
    selected = set(extract_selected_task_ids(priority))
    # The model cannot supply arbitrary reminders or resurrect terminal tasks there.
    details = re.search(r"^## \d+[.．]", priority, re.M)
    priority = priority[details.start():] if details else (
        "今回の優先候補はありません。リマインド候補から実施項目を選べます。"
        if metadata["display_candidates"] else "今日提示できる承認済み候補はありません。"
    )
    lines = [PRIORITY_NOTICE, "", "# 今日の優先候補", "", priority, "", "# リマインド候補", ""]
    reminders = [item for item in metadata["display_candidates"] if item["task_id"] not in selected]

    def compact(item):
        fields = parse_fields(item["body"].splitlines())
        result = [f"- [{item['task_id']}] {item['title']}",
                  f"  - 次の行動: {fields.get('next_action', '状況を再確認する。')}",
                  f"  - 根拠: {fields.get('basis', item['reason_today'] or '承認済みcurrent_state。')}"]
        due = fields.get("deadline", fields.get("due_date", fields.get("due", item["next_check"])))
        if due:
            result.append(f"  - 期限または再確認日: {due}")
        return result

    for item in reminders[:10]:
        lines.extend(compact(item))
    if not reminders:
        lines.append("なし。")
    if len(reminders) > 10:
        lines.append(f"\nほか{len(reminders) - 10}件は表示上限のため省略。全件はdeferred_tasks.mdに記載。")
    lines.extend(["", "# 状態更新待ち", ""])
    for item in metadata["state_conflicts"]:
        lines.extend([f"- task_id: {item['task_id']}", f"  - current_stateの状態: {item['status']}",
                      f"  - 新しい進捗の要約: {item['date']} {item['summary']}",
                      f"  - 推奨される状態変更案: {item['proposal']}"])
    if not metadata["state_conflicts"]:
        lines.append("なし。")
    lines.extend(["", "# 外部待ち・保留", ""])
    for item in metadata["held_candidates"]:
        lines.extend(compact(item))
    if not metadata["held_candidates"]:
        lines.append("なし。")
    sections["today_tasks.md"] = "\n".join(lines).rstrip() + "\n"
    # Local full list preserves active tasks beyond the daily reminder limit.
    deferred = ["# リマインド候補（全件）", ""]
    for item in reminders:
        deferred.extend(compact(item))
    if not reminders:
        deferred.append("なし。")
    tail = sections["today_tasks.md"].split("# 状態更新待ち", 1)[1]
    sections["deferred_tasks.md"] = "\n".join(deferred) + "\n\n# 状態更新待ち" + tail


def latest_slack_fetch_time() -> str:
    success = DAILY_SYNC_ROOT / ".last_success.json"
    if success.exists():
        try:
            data = json.loads(success.read_text(encoding="utf-8", errors="replace"))
            saved_at = str(data.get("saved_at", "")).strip()
            if saved_at:
                return saved_at
        except json.JSONDecodeError:
            return "parse_error"
    state = DAILY_SYNC_ROOT / ".last_slack_ts"
    if not state.exists():
        return "なし"
    return datetime.fromtimestamp(state.stat().st_mtime, TOKYO).isoformat(timespec="seconds")


def collect_inputs(now: datetime) -> tuple[str, str, dict[str, object], list[str]]:
    revision_dir = latest_dir(REVISION_ROOT)
    review_dir = latest_dir(REVIEW_ROOT)
    state_path = current_state_path()
    if not state_path or not state_path.exists():
        raise InputError("approved current_state is missing. Expected outputs/current_state/current_state.md or outputs/current_state.md.")

    sources = [
        state_path,
        ROOT / "docs" / "company" / "project_status.md",
        ROOT / "docs" / "company" / "decisions_log.md",
        ROOT / "docs" / "company" / "open_questions.md",
        ROOT / "docs" / "company" / "daily_log.md",
        ROOT / "docs" / "company" / "company_context_for_chatgpt.md",
    ]

    try:
        current_state_text = state_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise InputError(f"approved current_state is not readable: {e}") from e
    current_state_text = redact_secrets(current_state_text)
    candidates, blocked_ids, state_metadata = validate_current_state(current_state_text, now.date())
    progress_logs = read_recent_dated_logs(PROGRESS_ROOT, now, 7, PROGRESS_DAILY_CHAR_LIMIT)
    daily_sync_logs, sync_status = read_recent_daily_sync_logs(now, 14)
    tasks = state_tasks(current_state_text)
    # Keep unresolved conflicts even after the short AI context window expires.
    conflict_paths = sorted(set(PROGRESS_ROOT.glob("????-??-??.md")) |
                            set(DAILY_SYNC_ROOT.glob("????-??-??.gm_progress.md")))
    conflict_logs = [(path, "") for path in conflict_paths]
    conflicts = progress_conflicts(tasks, state_metadata, conflict_logs, now.date())
    conflict_ids = {item["task_id"] for item in conflicts}
    display_candidates = [task for task in candidates if task.task_id not in conflict_ids]
    allowed_ids = [task.task_id for task in display_candidates if task.status in ACTIVE_STATUSES]
    displayed_ids = {task.task_id for task in display_candidates} | conflict_ids
    held_candidates = [task for task in tasks if task.status not in FINAL_STATUSES
                       and task.task_id not in displayed_ids]

    snapshot_lines = [
        f"# inputs_snapshot.md",
        "",
        f"- generated_at: {now.isoformat(timespec='seconds')}",
        f"- timezone: Asia/Tokyo",
        f"- target_date: {now:%Y-%m-%d}",
        f"- current_state_sha256: {file_hash(state_path)}",
        f"- validation_spec_version: {CURRENT_STATE_VALIDATION_SPEC_VERSION}",
        f"- slack_fetch_success_at: {latest_slack_fetch_time()}",
        f"- slack_sync_status: {sync_status}",
        f"- project_status: docs/company/project_status.md",
        f"- excluded_unapproved_project_context_revision: {rel_path(revision_dir) if revision_dir else 'なし'}",
        f"- excluded_unapproved_context_review: {rel_path(review_dir) if review_dir else 'なし'}",
        f"- selectable_task_ids: {', '.join(allowed_ids)}",
        f"- confirmation_required_task_ids: {', '.join(blocked_ids) if blocked_ids else 'なし'}",
        "",
        "## 参照した固定コンテキスト",
    ]
    source_materials_parts = []
    for path in sources:
        exists = path.exists()
        snapshot_lines.append(f"- {rel_path(path)} ({'exists' if exists else 'missing'})")
        source_materials_parts.append(f"# SOURCE: {rel_path(path)}\n\n{read_text(path)}")

    source_materials = "\n\n".join(source_materials_parts)
    snapshot_lines.extend(["", "## 参照したprogress log"])
    if progress_logs:
        snapshot_lines.extend(f"- {rel_path(path)}" for path, _ in progress_logs)
    else:
        snapshot_lines.append("- なし")
    snapshot_lines.extend(["", "## 参照したdaily sync log"])
    if daily_sync_logs:
        snapshot_lines.extend(f"- {rel_path(path)}" for path, _ in daily_sync_logs)
    else:
        snapshot_lines.append("- なし")

    snapshot_lines.extend(["", "## 状態矛盾判定の参照ログ（省略なし・保存済み全期間）"])
    snapshot_lines.extend(f"- {rel_path(path)}" for path in conflict_paths)
    snapshot_lines.append("- 状態更新待ち: " + (", ".join(sorted(conflict_ids)) or "なし"))

    progress_materials = "\n\n".join(
        f"# SOURCE: {rel_path(path)}\n\n{text}" for path, text in progress_logs
    )
    daily_sync_materials = "\n\n".join(
        f"# SOURCE: {rel_path(path)}\n\n{text}" for path, text in daily_sync_logs
    )
    materials = source_materials
    if progress_materials:
        materials += (
            "\n\n# Git管理外の作業進捗ログ（outputs/progress、直近7日分）\n\n"
            + progress_materials
        )
    if daily_sync_materials:
        materials += (
            "\n\n# Slack GLMED_PROGRESS 日次同期ログ（outputs/daily_memory_sync、直近14日分）\n\n"
            + daily_sync_materials
        )

    metadata = {
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Tokyo",
        "target_date": f"{now:%Y-%m-%d}",
        "model": MODEL,
        "current_state_sha256": file_hash(state_path),
        "state_version_sha256": file_hash(state_path),
        "validation_spec_version": CURRENT_STATE_VALIDATION_SPEC_VERSION,
        "approval_status": state_metadata.get("approval_status", ""),
        "allowed_task_ids": allowed_ids,
        "display_candidates": [asdict(task) for task in display_candidates],
        "held_candidates": [asdict(task) for task in held_candidates],
        "state_conflicts": conflicts,
        "conflict_sources": [file_meta(path) for path in conflict_paths],
        "confirmation_required_task_ids": blocked_ids,
        "sources": [file_meta(path) for path in sources if path.exists()],
        "progress_sources": [file_meta(path) for path, _ in progress_logs],
        "daily_sync_sources": [file_meta(path) for path, _ in daily_sync_logs],
        "slack_fetch_success_at": latest_slack_fetch_time(),
        "slack_sync_status": sync_status,
        "excluded_sources": [
            rel_path(revision_dir / "project_instruction_revised.md") if revision_dir else "なし",
            rel_path(review_dir / "review_notes.md") if review_dir else "なし",
        ],
    }

    return materials, "\n".join(snapshot_lines).rstrip() + "\n", metadata, allowed_ids


def build_prompt(materials: str, now: datetime, allowed_ids: list[str]) -> str:
    today = now.strftime("%Y-%m-%d")

    return f"""
以下の社内コンテキストを読み、{today}（Asia/Tokyo）について、代表者に提示する今日の優先候補を最大3件選んでください。

# 重要ルール

- 今日の優先候補は最大3件。今日必ずすべて完了する前提ではない。0件・1件でもよい。
- 選択できる候補IDは次のみ: {', '.join(allowed_ids)}
- 上記候補IDにない仕事を新規作成・補完・捏造しない。
- 完了・停止・中止・置換済み（superseded / replacedを含む）、または新しい進捗ログと矛盾する候補は採用しない。
- waitingは優先候補に採用しない。再確認日到来済みはプログラムがリマインドへ表示する。
- 予定・未確定・条件付き事項を確定事実へ変更しない。
- 各タスクに必ず「候補ID」「根拠」「今日行う理由」を含める。
- 通常の放射線診断業務・日常読影業務は、最優先の前提ではあるが毎日実施するルーチンなので、「今日やること」には原則含めない。
- ただし、読影業務の維持に影響する契約・入金・運用トラブル・施設対応がある場合のみタスク化する。
- 医療鑑定本舗、KARTEの契約・補助金・特許・資金調達、既存収益維持に直結する非ルーチン事項を優先する。
- 自動化そのものを目的化しない。
- GitHub Issue整理や高度自動化は原則後回し。
- 優先候補以外のactiveはプログラムがリマインド候補へ残す。新しいタスクは生成しない。
- 医療・契約・特許・広告リスクを明示する。
- 前提不足がある場合は rationale.md に「不足している前提情報」として明記する。
- 代表者一人運営で、作業負担を増やさない。
- 患者情報、契約詳細、未公開特許の技術核心、APIキー、認証情報は出力しない。
- outputs/progress はGit管理外の生進捗メモであり、今日の優先候補の判断材料としてのみ使う。
- outputs/daily_memory_sync はSlack GLMED_PROGRESSから保存された進捗ログであり、今日の優先候補の判断材料としてのみ使う。
- project_instruction_revised.md と review_notes.md は未承認のAI提案なので、通常のタスク選定入力に使わない。
- 出力は日本語。短く、実行可能にする。

# 出力形式

必ず以下の3セクションを出力してください。

=== today_tasks.md ===
# 今日の優先候補

最大3件。各タスクは以下の形式にしてください。

## 1. タスク名
- 候補ID:
- 目的:
- 具体アクション:
- 完了条件:
- 所要目安:
- 根拠:
- 今日行う理由:
- リスク注意:

優先候補だけを出力する。リマインド候補・状態更新待ち・外部待ち・保留はプログラムが承認済み状態から付加する。0件なら「候補なし」と書く。

=== rationale.md ===
なぜこの3件以下に絞ったか。優先順位の理由を書く。
前提不足がある場合は「## 不足している前提情報」を設けて明記する。なければ「不足している前提情報: 特になし」と書く。

=== deferred_tasks.md ===
プログラムがリマインド候補・状態更新待ち・外部待ち・保留を生成するため「自動生成」とだけ書く。

# 入力資料

{materials}
"""


def empty_task_sections(now: datetime) -> dict[str, str]:
    target = now.strftime("%Y-%m-%d")
    return {
        "today_tasks.md": (
            "# 今日の優先候補\n\n"
            f"- 対象日: {target}（Asia/Tokyo）\n"
            "- 今日提示できる承認済み候補はありません。\n\n"
        ),
        "rationale.md": (
            f"# rationale.md\n\n"
            f"{target}（Asia/Tokyo）時点で、承認済みcurrent_stateに選択可能な候補IDがありません。\n"
            "AIによる架空タスク生成を避けるため、今日やることは提示しません。\n"
            "不足している前提情報: 特になし\n"
        ),
        "deferred_tasks.md": (
            "# deferred_tasks.md\n\n"
            "- 完了・停止・中止済み、回答待ち条件未達、要確認、または未承認の作業。\n"
        ),
    }


def validate_cache(out_dir: Path, metadata: dict[str, object]) -> list[str]:
    manifest = out_dir / "generation_manifest.json"
    if not manifest.exists():
        return ["generation_manifest.json is missing"]
    try:
        cached = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        return [f"generation_manifest.json is invalid JSON: {e}"]
    errors: list[str] = []
    for key in ["current_state_sha256", "validation_spec_version", "state_conflicts"]:
        if cached.get(key) != metadata.get(key):
            errors.append(f"{key} mismatch")
    return errors


def request_suggestion(client, user_prompt: str) -> str:
    system_prompt = """
あなたはグローバルメディカル株式会社の朝のタスク選定補助AIです。
代表者一人運営を前提に、今日の優先候補を最大3件選んでください。すべてを今日完了する前提ではありません。候補は0件でも構いません。
機密情報、患者情報、契約詳細、未公開特許の技術核心、APIキー、認証情報は出力しないでください。
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return redact_secrets(response.content[0].text)


def extract_selected_task_ids(today_tasks: str) -> list[str]:
    return TASK_ID_PATTERN.findall(today_tasks.split("# リマインド候補", 1)[0])


def validate_sections(sections: dict[str, str], allowed_ids: list[str]) -> list[str]:
    errors: list[str] = []
    today_tasks = sections.get("today_tasks.md", "")
    selected = extract_selected_task_ids(today_tasks)
    if not allowed_ids and not selected:
        return []
    if not selected and "候補なし" not in today_tasks:
        errors.append("today_tasks.md contains no selected task ids or explicit 候補なし")
    if "今日やらないこと" in today_tasks:
        errors.append("obsolete 今日やらないこと output")
    task_headers = re.findall(r"^## \d+[.．]", today_tasks, re.M)
    if len(task_headers) != len(selected):
        errors.append("each priority must have one numbered heading and one task id")
    if re.search(r"^# (?:リマインド候補|状態更新待ち|外部待ち)", today_tasks, re.M):
        errors.append("additional lists must be generated from approved state, not by AI")
    if len(selected) > 3:
        errors.append(f"selected task count exceeds 3: {len(selected)}")
    unknown = sorted(set(selected) - set(allowed_ids))
    if unknown:
        errors.append(f"selected unknown task ids: {', '.join(unknown)}")
    if selected and len(selected) != len(set(selected)):
        errors.append("duplicate selected task ids found")
    for required in ["候補ID", "根拠", "今日行う理由"]:
        if selected and required not in today_tasks:
            errors.append(f"today_tasks.md is missing required field: {required}")
    return errors


def archive_existing_output(out_dir: Path, now: datetime) -> Optional[Path]:
    if not out_dir.exists() or not any(out_dir.iterdir()):
        return None
    archive_dir = out_dir / "_previous_versions" / now.strftime("%H%M%S")
    archive_dir.mkdir(parents=True, exist_ok=True)
    for path in out_dir.iterdir():
        if path.name == "_previous_versions":
            continue
        destination = archive_dir / path.name
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
    return archive_dir


def write_state_update_proposal(out_dir: Path, metadata: dict[str, object], selected_ids: list[str]) -> None:
    lines = [
        "# state_update_proposal.md",
        "",
        "このファイルは案です。明示承認なしに current_state 正本へ反映しないでください。",
        "",
        f"- generated_at: {metadata['generated_at']}",
        f"- timezone: {metadata['timezone']}",
        f"- target_date: {metadata['target_date']}",
        f"- current_state_sha256: {metadata['current_state_sha256']}",
        f"- validation_spec_version: {metadata['validation_spec_version']}",
        f"- selected_task_ids: {', '.join(selected_ids) if selected_ids else 'なし'}",
        "",
        "## 状態更新案",
    ]
    if selected_ids:
        lines.extend(f"- {task_id}: 本日候補として提示。完了・停止・中止への変更は人間確認後に正本へ反映する。" for task_id in selected_ids)
    else:
        lines.append("- なし")
    for item in metadata["state_conflicts"]:
        lines.append(f"- {item['task_id']}: {item['date']} {item['summary']} → {item['proposal']}")
    (out_dir / "state_update_proposal.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_input_diagnostics(now: datetime) -> int:
    state_path = current_state_path()
    diagnostics: dict[str, object] = {
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Tokyo",
        "target_date": f"{now:%Y-%m-%d}",
        "current_state": file_meta(state_path) if state_path else {"path": "outputs/current_state/current_state.md", "exists": False},
        "slack_progress": {
            "channel_env": "GLMED_PROGRESS_CHANNEL_ID",
            "storage": rel_path(DAILY_SYNC_ROOT),
            "fetch_success_at": latest_slack_fetch_time(),
        },
        "excluded_unapproved_inputs": [
            "outputs/project_context_revision/*/project_instruction_revised.md",
            "outputs/context_review/*/review_notes.md",
        ],
        "inputs": [],
    }
    paths = [
        ROOT / "docs" / "company" / "project_status.md",
        ROOT / "docs" / "company" / "decisions_log.md",
        ROOT / "docs" / "company" / "open_questions.md",
        ROOT / "docs" / "company" / "daily_log.md",
        ROOT / "docs" / "company" / "company_context_for_chatgpt.md",
    ]
    if state_path:
        paths.insert(0, state_path)
    diagnostics["inputs"] = [file_meta(path) for path in paths]
    progress = read_recent_dated_logs(PROGRESS_ROOT, now, 7, PROGRESS_DAILY_CHAR_LIMIT)
    daily_sync, sync_status = read_recent_daily_sync_logs(now, 14)
    diagnostics["progress_count"] = len(progress)
    diagnostics["progress_files"] = [file_meta(path) for path, _ in progress]
    diagnostics["daily_sync_count"] = len(daily_sync)
    diagnostics["slack_sync_status"] = sync_status
    diagnostics["daily_sync_files"] = [file_meta(path) for path, _ in daily_sync]
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or reuse GM Today tasks.")
    parser.add_argument("--force", action="store_true", help="Regenerate today's files even if cached output exists.")
    parser.add_argument("--regenerate-after-state-change", action="store_true", help="Explicitly regenerate after approved current_state changes.")
    parser.add_argument("--diagnose-inputs", action="store_true", help="Print input metadata only. Does not print file bodies or secrets.")
    parser.add_argument("--date", help="Target date in Asia/Tokyo, YYYY-MM-DD. Intended for tests.")
    parser.add_argument("--mock-response-file", help="Use a local mock AI response file. Intended for tests.")
    args = parser.parse_args()
    now = now_tokyo()
    if args.date:
        now = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TOKYO)

    if args.diagnose_inputs:
        return print_input_diagnostics(now)

    out_dir = today_output_dir(now)
    today_file = out_dir / "today_tasks.md"

    try:
        materials, inputs_snapshot, metadata, allowed_ids = collect_inputs(now)
    except InputError as e:
        print(f"ERROR: {e}")
        return 1

    if today_file.exists() and not args.force and not args.regenerate_after_state_change:
        cache_errors = validate_cache(out_dir, metadata)
        if cache_errors:
            print("ERROR: cached GM Today cannot be used. Explicit regeneration is required.")
            for error in cache_errors:
                print(f" - {error}")
            return 1
        print(f"Today tasks cached: {out_dir}")
        return 0

    if not allowed_ids:
        sections = empty_task_sections(now)
        raw = "\n\n".join(
            f"=== {name} ===\n{content.rstrip()}" for name, content in sections.items()
        )
    elif args.mock_response_file:
        raw = read_text(Path(args.mock_response_file))
        sections = split_sections(raw)
    else:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY is not set.")
            print("Run: source ~/.env_globalmedical")
            return 1
        try:
            from anthropic import Anthropic
        except ImportError:
            print("ERROR: anthropic package is not installed.")
            print("Run: pip3 install anthropic")
            return 1
        client = Anthropic(api_key=api_key)
        raw = request_suggestion(client, build_prompt(materials, now, allowed_ids))
        sections = split_sections(raw)
    validation_errors = validate_sections(sections, allowed_ids)
    if validation_errors:
        print("ERROR: generated tasks failed validation.")
        for error in validation_errors:
            print(f" - {error}")
        return 1

    render_candidate_lists(sections, metadata)

    out_dir.mkdir(parents=True, exist_ok=True)
    archived_to = archive_existing_output(out_dir, now) if args.force or args.regenerate_after_state_change else None
    if archived_to:
        metadata["previous_version_archived_to"] = rel_path(archived_to)

    for filename, content in sections.items():
        (out_dir / filename).write_text(content, encoding="utf-8")
    (out_dir / "_raw_response.md").write_text(raw, encoding="utf-8")
    (out_dir / "inputs_snapshot.md").write_text(inputs_snapshot, encoding="utf-8")
    (out_dir / "generation_manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_state_update_proposal(out_dir, metadata, extract_selected_task_ids(sections["today_tasks.md"]))

    print(f"Today tasks completed: {out_dir}")
    print("Generated files:")
    for path in sorted(out_dir.glob("*")):
        print(f" - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
