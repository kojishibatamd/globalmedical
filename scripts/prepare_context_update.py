#!/usr/bin/env python3
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package is not installed.")
    print("Run: pip3 install anthropic")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "thread_analysis"
REVIEW_ROOT = ROOT / "outputs" / "context_review"

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)([A-Za-z0-9_]*API[_ -]?KEY\s*[:=]\s*)[^\s\"']+"),
]
SECTION_NAMES = [
    "project_instruction_patch.md",
    "company_context_update_plan.md",
    "decisions_log_append.md",
    "open_questions_update.md",
    "review_notes.md",
    "risk_check.md",
]
SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:===\s*)?"
    rf"(?P<name>{'|'.join(re.escape(name) for name in SECTION_NAMES)})"
    r"(?:\s*===)?\s*$"
)


def read_text(path: Path) -> str:
    if not path.exists():
        return f"（ファイルなし: {path}）"
    return redact_secrets(path.read_text(encoding="utf-8", errors="replace"))


def redact_secrets(text: str) -> str:
    text = SECRET_PATTERNS[0].sub("[REDACTED_API_KEY]", text)
    return SECRET_PATTERNS[1].sub(r"\1[REDACTED_API_KEY]", text)


def latest_thread_output(topic: str) -> Path:
    candidates = sorted(
        (p for p in OUTPUT_ROOT.glob(f"{topic}_*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No thread analysis output found for topic: {topic}")
    return candidates[0]


def split_sections(text: str) -> dict:
    sections = {}
    current = None
    buffer = []

    for line in text.splitlines():
        header = SECTION_HEADER_PATTERN.fullmatch(line)
        if header:
            name = header.group("name")
            if current:
                sections[current] = "\n".join(buffer).strip() + "\n"
            current = name
            buffer = []
        else:
            if current:
                buffer.append(line)

    if current:
        sections[current] = "\n".join(buffer).strip() + "\n"

    missing = [name for name in SECTION_NAMES if name not in sections]
    for name in missing:
        sections[name] = f"# {name}\n\n（抽出エラー: AI応答内に対応する見出しがありません）\n"

    if missing:
        note = sections["review_notes.md"].rstrip()
        missing_names = ", ".join(missing)
        sections["review_notes.md"] = (
            f"{note}\n\n"
            "## 自動抽出エラー\n"
            f"- 見出しを抽出できなかったセクション: {missing_names}\n"
            "- `_raw_response.md` を確認し、必要な内容を人間がレビューしてください。\n"
        )

    return sections


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/prepare_context_update.py <topic>")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Run: source ~/.env_globalmedical")
        sys.exit(1)

    topic = sys.argv[1]
    if not TOPIC_PATTERN.fullmatch(topic):
        print("ERROR: topic must contain only letters, numbers, underscores, and hyphens.")
        sys.exit(1)

    analysis_dir = latest_thread_output(topic)

    summary = read_text(analysis_dir / "summary.md")
    decisions = read_text(analysis_dir / "decisions.md")
    context_proposal = read_text(analysis_dir / "context_update_proposal.md")
    risk_check = read_text(analysis_dir / "risk_check.md")

    current_company_context = read_text(ROOT / "docs/company/company_context_for_chatgpt.md")
    current_project_status = read_text(ROOT / "docs/company/project_status.md")
    current_decisions_log = read_text(ROOT / "docs/company/decisions_log.md")
    current_open_questions = read_text(ROOT / "docs/company/open_questions.md")
    security_policy = read_text(ROOT / "docs/operation/security_policy.md")
    context_policy = read_text(ROOT / "docs/operation/context_update_policy.md")

    system_prompt = """
あなたはグローバルメディカル株式会社のChatGPTプロジェクト用コンテキスト更新補助AIです。

目的：
スレッド解析結果をもとに、ChatGPTプロジェクト指示およびMac側docsに反映すべき内容を整理してください。

重要原則：
- 自動反映しない。必ず人間レビュー前提。
- 既存コンテキストと重複する内容は、重複追記せず、修正・統合案にする。
- 確定事項、未決事項、推測を分ける。
- 機密情報・患者情報・契約詳細・未公開特許の技術核心は反映しない。
- APIキーや認証情報は出力しない。
- 公開リポジトリに置いてよい抽象度で書く。
- 代表者の省力化を最優先し、複雑な運用を増やさない。
- 出力は日本語。
"""

    user_prompt = f"""
以下の材料をもとに、ChatGPTプロジェクト指示およびdocs更新のためのレビュー成果物を作成してください。

# 解析対象topic

{topic}

# 最新スレッド解析ディレクトリ

{analysis_dir}

# スレッド解析結果 summary.md

{summary}

# スレッド解析結果 decisions.md

{decisions}

# スレッド解析結果 context_update_proposal.md

{context_proposal}

# スレッド解析結果 risk_check.md

{risk_check}

# 現在の company_context_for_chatgpt.md

{current_company_context}

# 現在の project_status.md

{current_project_status}

# 現在の decisions_log.md

{current_decisions_log}

# 現在の open_questions.md

{current_open_questions}

# security_policy.md

{security_policy}

# context_update_policy.md

{context_policy}

# 出力要件

必ず以下の6セクションを出力してください。

=== project_instruction_patch.md ===
ChatGPTプロジェクト指示欄に貼る候補だけを書く。
既存指示全体ではなく、追加・修正すべき差分案を中心に書く。
短く、実用的にする。

=== company_context_update_plan.md ===
docs/company/company_context_for_chatgpt.md, project_status.md, decisions_log.md, open_questions.md のどれに何を反映すべきかを整理する。
以下の形式で書く。

## 反映候補
- ファイル:
- 反映内容:
- 理由:
- 優先度:
- 注意:

=== decisions_log_append.md ===
decisions_log.md に追記すべき候補を書く。
追記不要なら「追記不要」と明記する。

=== open_questions_update.md ===
open_questions.md に追加・更新すべき未決事項を書く。
追加不要なら「追加不要」と明記する。

=== review_notes.md ===
人間が確認すべきポイントを短く書く。
「反映すべき」「反映しない方がよい」「要確認」に分ける。

=== risk_check.md ===
今回の反映に関するリスクを確認する。
特に、患者情報、契約情報、未公開特許、医療広告、過大表現、個人事情の露出に注意する。
"""

    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model=MODEL,
        max_tokens=12000,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = redact_secrets(response.content[0].text)
    sections = split_sections(raw)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    review_dir = REVIEW_ROOT / f"{topic}_{timestamp}"
    review_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in sections.items():
        (review_dir / filename).write_text(content, encoding="utf-8")

    (review_dir / "_raw_response.md").write_text(raw, encoding="utf-8")

    print(f"Context review completed: {review_dir}")
    print("Generated files:")
    for p in sorted(review_dir.glob("*")):
        print(f" - {p.name}")


if __name__ == "__main__":
    main()
