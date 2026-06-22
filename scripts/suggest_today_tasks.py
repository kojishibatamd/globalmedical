#!/usr/bin/env python3
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package is not installed.")
    print("Run: pip3 install anthropic")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
TODAY_ROOT = ROOT / "outputs" / "today_tasks"
REVISION_ROOT = ROOT / "outputs" / "project_context_revision"
REVIEW_ROOT = ROOT / "outputs" / "context_review"
PROGRESS_ROOT = ROOT / "outputs" / "progress"
PROGRESS_DAILY_CHAR_LIMIT = 4000

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


def redact_secrets(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED_SECRET]" if pattern.groups else "[REDACTED_SECRET]", text)
    return text


def read_text(path: Path) -> str:
    if not path.exists():
        return f"（ファイルなし: {path}）"
    return redact_secrets(path.read_text(encoding="utf-8", errors="replace"))


def latest_dir(root: Path) -> Optional[Path]:
    candidates = sorted(
        (path for path in root.glob("*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def read_recent_progress_logs(days: int = 7) -> list[tuple[Path, str]]:
    today = datetime.now().date()
    logs: list[tuple[Path, str]] = []

    for offset in range(days):
        day = today - timedelta(days=offset)
        path = PROGRESS_ROOT / f"{day:%Y-%m-%d}.md"
        if not path.exists():
            continue

        text = read_text(path)
        if len(text) > PROGRESS_DAILY_CHAR_LIMIT:
            text = (
                "（長いため末尾のみ表示）\n"
                + text[-PROGRESS_DAILY_CHAR_LIMIT:]
            )
        logs.append((path, text))

    return logs


def today_output_dir() -> Path:
    return TODAY_ROOT / datetime.now().strftime("%Y-%m-%d")


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


def collect_inputs() -> tuple[str, str]:
    revision_dir = latest_dir(REVISION_ROOT)
    review_dir = latest_dir(REVIEW_ROOT)

    sources = [
        ROOT / "docs" / "company" / "project_status.md",
        ROOT / "docs" / "company" / "decisions_log.md",
        ROOT / "docs" / "company" / "open_questions.md",
        ROOT / "docs" / "company" / "daily_log.md",
        ROOT / "docs" / "company" / "company_context_for_chatgpt.md",
    ]

    if revision_dir:
        sources.append(revision_dir / "project_instruction_revised.md")
    if review_dir and (review_dir / "review_notes.md").exists():
        sources.append(review_dir / "review_notes.md")

    snapshot_lines = [
        f"# inputs_snapshot.md",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- project_status: docs/company/project_status.md",
        f"- latest_project_context_revision: {revision_dir.relative_to(ROOT) if revision_dir else 'なし'}",
        f"- latest_context_review: {review_dir.relative_to(ROOT) if review_dir else 'なし'}",
        "",
        "## 参照した固定コンテキスト",
    ]
    source_materials_parts = []
    for path in sources:
        exists = path.exists()
        snapshot_lines.append(f"- {path.relative_to(ROOT)} ({'exists' if exists else 'missing'})")
        source_materials_parts.append(f"# SOURCE: {path.relative_to(ROOT)}\n\n{read_text(path)}")

    source_materials = "\n\n".join(source_materials_parts)
    progress_logs = read_recent_progress_logs()
    snapshot_lines.extend(["", "## 参照したprogress log"])
    if progress_logs:
        snapshot_lines.extend(f"- {path.relative_to(ROOT)}" for path, _ in progress_logs)
    else:
        snapshot_lines.append("- なし")

    progress_materials = "\n\n".join(
        f"# SOURCE: {path.relative_to(ROOT)}\n\n{text}" for path, text in progress_logs
    )
    materials = source_materials
    if progress_materials:
        materials += (
            "\n\n# Git管理外の作業進捗ログ（outputs/progress、直近7日分）\n\n"
            + progress_materials
        )

    return materials, "\n".join(snapshot_lines).rstrip() + "\n"


def build_prompt(materials: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""
以下の社内コンテキストを読み、{today}に代表者が今日やるべきタスクを最大3件に絞ってください。

# 重要ルール

- 今日やることは最大3件。
- 通常の放射線診断業務・日常読影業務は、最優先の前提ではあるが毎日実施するルーチンなので、「今日やること」には原則含めない。
- ただし、読影業務の維持に影響する契約・入金・運用トラブル・施設対応がある場合のみタスク化する。
- 医療鑑定本舗、KARTEの契約・補助金・特許・資金調達、既存収益維持に直結する非ルーチン事項を優先する。
- 自動化そのものを目的化しない。
- GitHub Issue整理や高度自動化は原則後回し。
- 「今日やらないこと」を必ず出す。
- 医療・契約・特許・広告リスクを明示する。
- 前提不足がある場合は rationale.md に「不足している前提情報」として明記する。
- 代表者一人運営で、作業負担を増やさない。
- 患者情報、契約詳細、未公開特許の技術核心、APIキー、認証情報は出力しない。
- outputs/progress はGit管理外の生進捗メモであり、今日やること最大3件の判断材料としてのみ使う。
- 出力は日本語。短く、実行可能にする。

# 出力形式

必ず以下の3セクションを出力してください。

=== today_tasks.md ===
# 今日やること

最大3件。各タスクは以下の形式にしてください。

## 1. タスク名
- 目的:
- 具体アクション:
- 完了条件:
- 所要目安:
- リスク注意:

最後に「今日やらないこと」も短く書く。

=== rationale.md ===
なぜこの3件以下に絞ったか。優先順位の理由を書く。
前提不足がある場合は「## 不足している前提情報」を設けて明記する。なければ「不足している前提情報: 特になし」と書く。

=== deferred_tasks.md ===
今日やらないこと、後回しにすること、未決事項を書く。

# 入力資料

{materials}
"""


def request_suggestion(client: Anthropic, user_prompt: str) -> str:
    system_prompt = """
あなたはグローバルメディカル株式会社の朝のタスク選定補助AIです。
代表者一人運営を前提に、今日やるべきことを最大3件に絞ってください。
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or reuse GM Today tasks.")
    parser.add_argument("--force", action="store_true", help="Regenerate today's files even if cached output exists.")
    args = parser.parse_args()

    out_dir = today_output_dir()
    today_file = out_dir / "today_tasks.md"
    if today_file.exists() and not args.force:
        print(f"Today tasks cached: {out_dir}")
        return 0

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Run: source ~/.env_globalmedical")
        return 1

    client = Anthropic(api_key=api_key)
    materials, inputs_snapshot = collect_inputs()
    raw = request_suggestion(client, build_prompt(materials))
    sections = split_sections(raw)

    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in sections.items():
        (out_dir / filename).write_text(content, encoding="utf-8")
    (out_dir / "_raw_response.md").write_text(raw, encoding="utf-8")
    (out_dir / "inputs_snapshot.md").write_text(inputs_snapshot, encoding="utf-8")

    print(f"Today tasks completed: {out_dir}")
    print("Generated files:")
    for path in sorted(out_dir.glob("*")):
        print(f" - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
