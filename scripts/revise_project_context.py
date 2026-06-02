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
REVIEW_ROOT = ROOT / "outputs" / "context_review"
REVISION_ROOT = ROOT / "outputs" / "project_context_revision"

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_INSTRUCTION_CHARS = 8000
TARGET_INSTRUCTION_CHARS = 7000
MAX_GENERATION_ATTEMPTS = 3
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)([A-Za-z0-9_]*API[_ -]?KEY\s*[:=]\s*)[^\s\"']+"),
]
SECTION_NAMES = [
    "project_instruction_revised.md",
    "revision_summary.md",
    "removed_or_compressed_items.md",
    "unresolved_items.md",
    "risk_check.md",
]
SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:===\s*)?"
    rf"(?P<name>{'|'.join(re.escape(name) for name in SECTION_NAMES)})"
    r"(?:\s*===)?\s*$"
)


def redact_secrets(text: str) -> str:
    text = SECRET_PATTERNS[0].sub("[REDACTED_API_KEY]", text)
    return SECRET_PATTERNS[1].sub(r"\1[REDACTED_API_KEY]", text)


def read_text(path: Path) -> str:
    if not path.exists():
        return f"（ファイルなし: {path}）"
    return redact_secrets(path.read_text(encoding="utf-8", errors="replace"))


def latest_context_review() -> Path:
    candidates = sorted(
        (p for p in REVIEW_ROOT.glob("*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No context review output found.")
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
        elif current:
            buffer.append(line)

    if current:
        sections[current] = "\n".join(buffer).strip() + "\n"

    missing = [name for name in SECTION_NAMES if name not in sections]
    for name in missing:
        sections[name] = f"# {name}\n\n（抽出エラー: AI応答内に対応する見出しがありません）\n"

    if missing:
        note = sections["unresolved_items.md"].rstrip()
        missing_names = ", ".join(missing)
        sections["unresolved_items.md"] = (
            f"{note}\n\n"
            "## 自動抽出エラー\n"
            f"- 見出しを抽出できなかったセクション: {missing_names}\n"
            "- `_raw_response.md` を確認し、人間がレビューしてください。\n"
        )

    return sections


def build_prompt(review_dir: Path) -> str:
    sources = [
        ROOT / "docs" / "company" / "company_context_for_chatgpt.md",
        ROOT / "docs" / "company" / "project_status.md",
        ROOT / "docs" / "company" / "decisions_log.md",
        ROOT / "docs" / "company" / "open_questions.md",
        ROOT / "docs" / "operation" / "security_policy.md",
        ROOT / "docs" / "operation" / "context_update_policy.md",
        review_dir / "project_instruction_patch.md",
        review_dir / "company_context_update_plan.md",
        review_dir / "decisions_log_append.md",
        review_dir / "open_questions_update.md",
        review_dir / "review_notes.md",
        review_dir / "risk_check.md",
    ]
    materials = "\n\n".join(
        f"# SOURCE: {path.relative_to(ROOT)}\n\n{read_text(path)}" for path in sources
    )

    return f"""
以下の既存コンテキストと最新レビューを統合し、ChatGPTプロジェクト指示欄に貼り替えるための改訂版を作成してください。

# 必須要件

- 追記案ではなく、単独で利用できる改訂版プロジェクト指示を作る。
- `project_instruction_revised.md` は必ず8,000字以内にする。
- 可能なら6,000〜7,000字程度に抑える。
- 古い情報、重複情報、運用に不要な詳細は削除または圧縮する。
- 確定事項、方針、未決事項を混同しない。
- 未公開特許情報、患者情報、契約詳細、APIキー、認証情報を含めない。
- 遠隔化本舗については事業方針レベルに抽象化し、再現可能な技術詳細を含めない。
- KARTEについては内部アーキテクチャ、AIパイプライン、内部データ構造などの再現可能な詳細を含めない。
- 代表者一人運営で、省力化を最優先する前提を残す。
- 自動反映は行わず、人間レビュー前提とする。
- 出力は日本語。

# 出力形式

必ず以下の5セクションを出力してください。

=== project_instruction_revised.md ===
ChatGPTプロジェクト指示欄にそのまま貼り替えられる完成版だけを書く。

=== revision_summary.md ===
主要な改訂内容を短く書く。

=== removed_or_compressed_items.md ===
削除または圧縮した項目と理由を書く。

=== unresolved_items.md ===
人間が確認すべき未決事項を書く。

=== risk_check.md ===
機密情報、患者情報、契約詳細、未公開特許、医療広告、過大表現、個人事情の露出がないか確認する。

# 入力資料

{materials}
"""


def request_revision(client: Anthropic, user_prompt: str) -> str:
    system_prompt = """
あなたはグローバルメディカル株式会社のChatGPTプロジェクト指示改訂補助AIです。
既存情報を圧縮統合し、公開リポジトリに置いてよい抽象度のプロジェクト指示を作成してください。
機密情報や認証情報は出力しないでください。
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=12000,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return redact_secrets(response.content[0].text)


def main():
    if len(sys.argv) != 1:
        print("Usage: python3 scripts/revise_project_context.py")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Run: source ~/.env_globalmedical")
        sys.exit(1)

    review_dir = latest_context_review()
    client = Anthropic(api_key=api_key)
    prompt = build_prompt(review_dir)

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        raw = request_revision(client, prompt)
        sections = split_sections(raw)
        revised = sections["project_instruction_revised.md"]
        revised_chars = len(revised)
        if "（抽出エラー:" not in revised and revised_chars <= MAX_INSTRUCTION_CHARS:
            break
        if attempt == MAX_GENERATION_ATTEMPTS:
            print("ERROR: failed to generate project instructions within 8,000 characters.")
            sys.exit(1)
        prompt = f"""
前回の出力を修正してください。
`project_instruction_revised.md` が抽出可能で、必ず{MAX_INSTRUCTION_CHARS:,}字以内になるように圧縮してください。
目標は{TARGET_INSTRUCTION_CHARS:,}字以内です。
他の4セクションも維持してください。
機密情報、患者情報、契約詳細、未公開特許情報、APIキー、認証情報は含めないでください。

# 前回の出力

{raw}
"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    revision_dir = REVISION_ROOT / timestamp
    revision_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in sections.items():
        (revision_dir / filename).write_text(content, encoding="utf-8")
    (revision_dir / "_raw_response.md").write_text(raw, encoding="utf-8")

    print(f"Project context revision completed: {revision_dir}")
    print(f"Project instruction characters: {revised_chars}")
    print("Generated files:")
    for path in sorted(revision_dir.glob("*")):
        print(f" - {path.name}")


if __name__ == "__main__":
    main()
