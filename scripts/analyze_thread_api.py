#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package is not installed.")
    print("Run: pip3 install anthropic")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


SYSTEM_PROMPT = """
あなたはグローバルメディカル株式会社の業務整理・意思決定ログ化AIです。

目的：
ChatGPTプロジェクト内のスレッド内容を解析し、以下の成果物に分解してください。

重要原則：
- 勝手に確定事項にしない。
- 「決定事項」「検討中」「未決事項」「推測」を明確に分ける。
- 医療情報、患者情報、契約情報、未公開特許情報、個人情報が含まれる可能性を常に意識する。
- Webサイト・SNS・外部資料に出してよい情報と、内部限定情報を分ける。
- GitHub Issue案は実行可能な粒度にする。
- context更新案は自動反映前提ではなく、人間レビュー前提にする。
- 出力は日本語。
"""


USER_PROMPT_TEMPLATE = """
以下は、グローバルメディカル株式会社のプロジェクト内スレッド内容です。
この内容をもとに、6種類の出力を作成してください。

全体制約：
- 出力全体を簡潔にしてください。
- summary.md は最大800字程度にしてください。
- decisions.md は各分類最大5項目までにしてください。
- issues_proposal.md は最大5件までにしてください。
- context_update_proposal.md は最大5項目までにしてください。
- website_update_proposal.md は最大5項目までにしてください。
- risk_check.md は必ず最後まで完結させてください。
- 長くなりそうな場合は、summary.md / decisions.md / issues_proposal.md を短縮し、risk_check.md を優先してください。

# 出力1: summary.md
以下を含める：
- スレッドの主題
- 背景
- 議論の流れ
- 現時点の結論
- 重要な補足

# 出力2: decisions.md
以下に分ける：
- 決定事項
- 事実として確認された事項
- 方針として概ね合意された事項
- まだ決定していない事項

# 出力3: issues_proposal.md
GitHub Issue案を作る。

重要：
- Issue案は最大5件までにしてください。
- 各IssueのTasksは最大5項目までにしてください。
- 各IssueのDone Criteriaは最大3項目までにしてください。
- 長くなりすぎる場合は、Issue本文を短縮してください。
- ただし、必ず最後の risk_check.md まで出力してください。

各Issueは以下の形式：
## Issue: タイトル
Priority: High/Medium/Low
Type: parent/child/review/task/research
Labels: 候補ラベル
### Background
### Tasks
- [ ] ...
### Done Criteria
- [ ] ...

# 出力4: context_update_proposal.md
company_context / project_status / decisions_log などへの更新案を作る。
ただし、直接反映ではなく「更新候補」として書く。

# 出力5: website_update_proposal.md
Webサイト、LP、KARTE.appページ等に反映しうる内容を整理する。
以下を必ず分ける：
- 公開可能と思われる内容
- 公開禁止または要注意の内容
- 追加確認が必要な内容

# 出力6: risk_check.md
このセクションは必ず出力してください。
前半の出力が長くなる場合でも、省略してはいけません。

以下を確認する：
- 患者情報・医療情報リスク
- 契約・NDAリスク
- 特許出願前公開リスク
- 医療広告ガイドライン上の注意
- 誤認・過大表現リスク

出力が長くなりそうな場合は、issues_proposal.md を短縮し、risk_check.md を優先してください。

出力形式：
必ず以下の区切りで出力してください。

=== summary.md ===
...

=== decisions.md ===
...

=== issues_proposal.md ===
...

=== context_update_proposal.md ===
...

=== website_update_proposal.md ===
...

=== risk_check.md ===
...

--- スレッド本文 ---
{thread_text}
"""


def read_input(topic: str) -> str:
    candidates = [
        ROOT / "inbox" / topic / "discussion.md",
        ROOT / "inbox" / topic / "raw.md",
        ROOT / "inbox" / topic / "discussion.txt",
    ]
    for path in candidates:
        if path.exists() and path.read_text(encoding="utf-8").strip():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "No input found. Expected one of:\n"
        + "\n".join(str(p) for p in candidates)
    )


def split_sections(text: str) -> dict:
    markers = [
        "summary.md",
        "decisions.md",
        "issues_proposal.md",
        "context_update_proposal.md",
        "website_update_proposal.md",
        "risk_check.md",
    ]
    allowed = set(markers)

    sections = {}
    current = None
    buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            name = stripped.strip("=").strip()

            # Only accept known section markers.
            # Ignore explanatory lines such as:
            # === 以下、6種類の出力を順に提示します ===
            if name not in allowed:
                continue

            if current:
                sections[current] = "\n".join(buffer).strip() + "\n"
            current = name
            buffer = []
        else:
            if current:
                buffer.append(line)

    if current:
        sections[current] = "\n".join(buffer).strip() + "\n"

    for marker in markers:
        sections.setdefault(marker, "")

    return sections


def write_outputs(topic: str, sections: dict, raw_response: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "thread_analysis" / f"{topic}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in sections.items():
        if not content.strip():
            content = f"# {filename}\n\n（AI出力から該当セクションを抽出できませんでした）\n"
        (out_dir / filename).write_text(content, encoding="utf-8")

    (out_dir / "_raw_response.md").write_text(raw_response, encoding="utf-8")
    return out_dir


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/analyze_thread_api.py <topic>")
        print("Example: python3 scripts/analyze_thread_api.py dummy_test")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Run: source ~/.env_globalmedical")
        sys.exit(1)

    topic = sys.argv[1]
    thread_text = read_input(topic)

    client = Anthropic(api_key=api_key)
    user_prompt = USER_PROMPT_TEMPLATE.format(thread_text=thread_text)

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=12000,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    sections = split_sections(raw)
    out_dir = write_outputs(topic, sections, raw)

    print(f"Analysis completed: {out_dir}")
    print("Generated files:")
    for p in sorted(out_dir.glob("*")):
        print(f" - {p.name}")


if __name__ == "__main__":
    main()
