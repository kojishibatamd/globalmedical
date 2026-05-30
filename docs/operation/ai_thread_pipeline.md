# AI Thread Analysis Pipeline

## 目的

ChatGPTプロジェクト内のスレッド内容を、以下の成果物に分解する。

- 要約
- 意思決定ログ
- GitHub Issue案
- context更新案
- Webサイト更新案
- リスクチェック

## 基本フロー

1. ChatGPTスレッド内容を手動でコピーする
2. `inbox/<topic>/discussion.md` に保存する
3. APIキーを読み込む
4. `scripts/analyze_thread_api.py <topic>` を実行する
5. `outputs/thread_analysis/<topic>_<timestamp>/` に成果物が生成される
6. 人間がレビューする
7. 必要なものだけ `docs/`、GitHub Issue、Webサイト等へ反映する

## 実行例

```bash
cd ~/work/globalmedical

mkdir -p inbox/ai_workflow_thread
nano inbox/ai_workflow_thread/discussion.md

source ~/.env_globalmedical
python3 scripts/analyze_thread_api.py ai_workflow_thread

latest=$(ls -td outputs/thread_analysis/ai_workflow_thread_* | head -1)

cat "$latest/summary.md"
cat "$latest/decisions.md"
cat "$latest/issues_proposal.md"
cat "$latest/context_update_proposal.md"
cat "$latest/website_update_proposal.md"
cat "$latest/risk_check.md"
出力ファイル
summary.md
decisions.md
issues_proposal.md
context_update_proposal.md
website_update_proposal.md
risk_check.md
_raw_response.md
運用原則
出力はすべてAI生成の案であり、人間レビュー必須とする
context更新案は自動反映しない
GitHub Issueは自動作成せず、まず人間が選別する
Webサイト更新案は公開前に人間が確認する
医療広告、特許、契約に関わる内容は特に慎重に扱う
入れてはいけない情報

以下は原則として inbox/ に保存しない。

患者個人情報
医療鑑定の具体資料
弁護士相談内容
契約交渉の詳細
未公開特許の技術核心
APIキー・パスワード等の秘密情報
Codex CLI依存パイプラインとの違い

scripts/ai_pipeline.sh はCodex CLIに入力テキストを渡すため、非機密用途に限定する。

機微情報を含む可能性があるスレッド解析では、scripts/analyze_thread_api.py を使用する。
