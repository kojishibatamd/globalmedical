# Context Update Policy

## 目的

ChatGPTスレッド解析から生成された context_update_proposal.md を、会社コンテキスト・プロジェクト状態・意思決定ログへ安全に反映するための方針を定める。

## 基本原則

- AI出力は更新案であり、自動反映しない
- 人間レビュー後に必要部分のみ反映する
- 機密情報は通常のcontextに入れない
- 公開可能情報と内部情報を分ける
- 未確定事項は確定情報として記録しない

## 反映先候補

### docs/company/overview.md

会社・事業の安定情報を記載する。

例：

- 会社概要
- 事業概要
- 公開済みサービス
- 公開済みLP
- 公開可能な代表者プロフィール

### docs/company/project_status.md

現在の進行状況を記載する。

例：

- KARTE開発状況
- 医療鑑定本舗の営業状況
- 遠隔化本舗の営業準備状況
- Webサイト改善状況
- 資金調達準備状況

### docs/company/decisions_log.md

意思決定履歴を記載する。

例：

- 採用した方針
- 後回しにした事項
- その理由
- 関連Issue
- 決定日

### docs/company/open_questions.md

未決事項を記載する。

例：

- 要調査事項
- 要相談事項
- 未確定の仕様
- 外部確認待ち事項
- 判断保留中の論点

### docs/operation/

業務フロー・運用ルールを記載する。

例：

- AIパイプライン
- セキュリティ方針
- context更新ルール
- Issue化手順
- GitHub運用ルール

## 反映してはいけない情報

以下は通常のcontextに反映しない。

- 患者情報
- 医療鑑定の具体案件
- 弁護士相談内容
- 契約交渉の詳細
- 未公開特許の技術核心
- APIキー・パスワード
- NDA対象情報

## 反映手順

1. outputs/thread_analysis/<topic>_<timestamp>/context_update_proposal.md を確認する
2. 内容を Public / Internal / Confidential / Highly Confidential に分類する
3. 反映先ファイルを選ぶ
4. 必要部分だけ手動で編集する
5. git diff で確認する
6. 機密情報が混入していないことを確認する
7. コミットする

## decisions_log.md への記録基準

以下は decisions_log.md に記録する。

- 明確に採用した方針
- 明確に却下または延期した方針
- 優先順位の変更
- 重要な業務フロー変更
- 外部パートナーとの合意事項のうち、機密でない範囲

以下は記録しない。

- 単なる思いつき
- 検討途中の仮説
- 個別患者・個別案件に関する内容
- 未公開特許の技術核心
- 契約書の具体条項そのもの

## project_status.md への記録基準

以下は project_status.md に記録する。

- 各事業の進捗
- 開発状況
- 営業準備状況
- 資料作成状況
- 直近の優先タスク

ただし、進捗は過度に細かく書きすぎない。

## open_questions.md への記録基準

以下は open_questions.md に記録する。

- 未決事項
- 外部確認が必要な事項
- 弁護士・弁理士・開発会社等への確認事項
- 将来判断する事項

## コミット例

git add docs/company/project_status.md docs/company/decisions_log.md
git commit -m "Update project status and decisions from AI workflow discussion"

## 原則

contextは確定した会社の外部記憶として扱う。

議論中の仮説や未検証情報は、open_questions.md または GitHub Issue に留める。

自動反映よりも、正確性・機密管理・後から見たときの分かりやすさを優先する。
