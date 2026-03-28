# グローバルメディカル株式会社 — 会社コンテキスト
> このファイルはClaude Codeおよびクロードとの会話の冒頭に貼り付けることで、会社の状況を即座に共有するためのものです。
> 最終更新: 2026年3月

---

## 1. 会社基本情報

| 項目 | 内容 |
|---|---|
| 会社名 | グローバルメディカル株式会社 |
| 英文社名 | Global Medical Co., Ltd. |
| 設立 | 2018年8月27日 |
| 代表者 | 柴田 幸司（Koji Shibata, M.D.） |
| 住所 | 東京都新宿区西新宿8-3-1 GFビル2F |
| Email | admin@globalmedical.jp（サイト表記: info[@]globalmedical.jp） |
| Webサイト | https://globalmedical.jp |
| 代表者専門 | 放射線診断専門医・26年・読影件数20万件超 |

---

## 2. 事業概要

### 2-1. 遠隔化本舗
- **内容**: 遠隔画像診断・DX支援
- **対象**: クリニック・診療所
- **技術**: 仮想化（VMware）＋RDP＋L2層NIC排他接続によるセキュアな遠隔読影システム
- **実績**: 5医療機関で約2年間の実証実験済み・業務トラブルなし
- **LP**: https://globalmedical.jp/enkakuka.html

### 2-2. 医療鑑定本舗
- **内容**: 弁護士・法律事務所向け医療鑑定（医療訴訟・交通事故・労災）
- **特徴**: 現役放射線診断医による鑑定書・報告書作成、無料ZOOM相談
- **実績**: 100件以上
- **LP**: https://globalmedical.jp/kantei.html

### 2-3. KARTE（開発中）
- **内容**: 患者向け医療AIプラットフォーム（PHR）
- **コンセプト**: 「医師がAIを武器にするなら、患者もAIという武器を持つべき」。医療の民主化。
- **主要機能**:
  - 医療データ一元管理（DICOM画像対応）
  - AIコンシェルジュ（柴田医師の読影実績をもとに訓練・24時間対応）
  - 患者コミュニティ・SNS（疾患別・匿名設定対応）
  - 病歴要約・セカンドオピニオン支援・紹介状作成サポート
  - オンラインクリニック連携（構想中）
- **ドメイン**: karte.app（所有済み）、karte.cloud（所有済み）
- **URL**: https://globalmedical.jp/karte.html

---

## 3. Webサイト構成

| ファイル | 役割 |
|---|---|
| index.html | コーポレートサイトトップ |
| enkakuka.html | 遠隔化本舗LP |
| kantei.html | 医療鑑定本舗LP |
| karte.html | KARTEプロダクトページ（スライド形式・10枚） |
| logo.jpg / logo.png | ロゴ画像 |

- ホスティング: GitHub Pages（globalmedical.jp）
- ドメイン管理: お名前.com
- CDN/リダイレクト: Cloudflare（karte.app, karte.cloud, glmed.jp → globalmedical.jp）

### デザイン方針
- コーポレート: ダーク系（#050a0f背景）、ブルー（#00a0e9）×レッド（#e60012）アクセント
- KARTE: ティール（#0D9A8A）基調、患者向け温かみ重視
- フォント: Noto Sans JP + Montserrat

---

## 4. KARTE開発状況

| 項目 | 内容 |
|---|---|
| 補助金 | ものづくり補助金 採択済み（補助額750万円・総開発費1,500万円） |
| 開発パートナー | 株式会社野本（ベトナムオフショア・VNEXT社活用・エンジニア4名体制） |
| 契約金額 | 1,500万円（税抜） |
| 開発期間 | 2026年3月4日〜9月30日 |
| 補助金支払期限 | 2026年10月2日 |
| マイルストーン | 着手200万 / 中間1,000万 / 完了300万 |
| 契約状況 | 交渉中（仕様書の契約別紙化・議事録書面化を確認中） |

### 資金調達戦略
- 調達目標: 5,000万円（18ヶ月ランウェイ）
- 優先順位: エンジェル投資家（ANGEL PORT・医師ネットワーク）→ ピッチイベント → FUNDINNO → 公的補助金追加

---

## 5. 商標出願状況（2026年3月時点）

| 整理番号 | 商標 | 区分 | 状態 |
|---|---|---|---|
| R8M10T1 | 医療鑑定本舗 | 42類・44類・45類 | 出願手続き進行中 |
| R8M10T2 | 遠隔化本舗 | 9類・42類・44類 | 出願手続き進行中 |
| R8M10T3 | KARTE.app | 9類・42類・44類 | 出願手続き進行中 |

- 代理人: 瀬戸 麻希 弁理士（弁理士法人セトマキ）
- 出願人: 柴田 幸司（個人名義 ※「医業」を含めるため）

---

## 6. 特許出願検討状況

### 発明①: PHR×専門医AI統合プラットフォーム
患者PHRデータと放射線診断専門医の実績AIを統合したKARTEのコア構成

### 発明②: セキュア仮想化環境下でのAIエージェント読影支援（最優先）
- **現行実装**: VMware仮想化＋RDP＋L2層NIC排他接続（USB-Ethernetアダプタ）
- **NIC排他設定**: `.vmx`に `usb.autoConnect.device0 = "0x(VID):0x(PID)"` を追記
- **L2分離維持**: Windowsグループポリシーでデバイスインストール禁止＋スタートアップbatによる自動復帰
- **KVMモード**: `vmware-kvm.exe`でフルスクリーン起動→一般ユーザーにホストOSを見せない設計
- **次フェーズ構想**: ホストOSにAIエージェントを配置し、ゲストOS（院内LAN側）と分離した状態で読影支援

### 発明③: 患者主権型セカンドオピニオン支援システム
DICOM画像AIによる複数治療選択肢提示＋紹介状自動生成の一体フロー

- 先行技術調査: 瀬戸弁理士に依頼済み・報告書受領済み
- 技術補足説明書: 作成済み（L2分離の誤解解消・グループポリシー設定・KVM設計等を補足）

---

## 7. ドメインリダイレクト設定（Cloudflare）

| ドメイン | 転送先 |
|---|---|
| karte.app / www.karte.app | https://globalmedical.jp/karte.html |
| karte.cloud / www.karte.cloud | https://globalmedical.jp/karte.html |
| glmed.jp / www.glmed.jp | https://globalmedical.jp/index.html |

---

## 8. 主要外部サービス・連絡先

| サービス | 内容 |
|---|---|
| TimeRex | ZOOM相談予約（https://timerex.net/s/admin_848e_49a5/b21e64a7） |
| Google Apps Script | お問い合わせフォーム送信処理 |
| Cloudflare | DNS・CDN管理（admin@globalmedical.jp） |
| お名前.com | ドメイン管理 |
| GitHub Pages | Webサイトホスティング |
| 瀬戸 麻希 弁理士 | 商標・特許代理（080-2191-8350） |

---

## 9. 作成済み主要ファイル・成果物

| ファイル名 | 内容 |
|---|---|
| karte.html | KARTEプロダクトページ（10枚スライド・レスポンシブ対応済み） |
| index.html | コーポレートサイトトップ |
| enkakuka.html | 遠隔化本舗LP |
| kantei.html | 医療鑑定本舗LP |
| FAXDM_遠隔化本舗.pdf | クリニック向けFAX DM |
| FAXDM_医療鑑定本舗.pdf | 弁護士向けFAX DM |
| 遠隔読影システム導入のご提案.pptx | 医療機関向け提案資料（8枚） |
| KARTE_pitch_deck.pptx | 投資家向けピッチデック（5枚・調達5,000万円） |
| KARTE_action_plan.pptx | 投資獲得90日間アクションプラン |
| KARTE_sales_deck.pptx / .html | 販路拡大用プレゼン（10枚） |
| 先行技術調査依頼書_KARTE特許.docx | 瀬戸弁理士への特許調査依頼書（3発明） |
| 技術補足説明書_v2.docx | 先行技術調査報告へのコメント・L2分離の技術詳細 |
| 商標登録願_原稿①②③.pdf | 3商標の出願書類 |

---

## 10. Claude Codeでの作業方針

### ファイル管理
- Webサイトファイルはプロジェクトディレクトリを作成して管理する
- 変更前は必ずバックアップを取る

### コーディング規約
- 日本語UIは`Noto Sans JP`フォント使用
- 英字見出しは`Montserrat`フォント使用
- カラー変数はCSSカスタムプロパティ（`--logo-blue`等）で統一
- モバイルファースト・レスポンシブ対応必須（特にiPhone対応）

### 重要な注意事項
- karte.htmlの「750万円」という金額表記は患者向けページでは不適切なため、「国の補助金採択プロジェクト」等の表現に変更することを検討中
- 医療情報を扱うため、不正確な医療情報の記載は絶対に避ける
- 個人情報・患者データに関する記述は慎重に扱う

---
## Git運用ルール
- ファイル修正後は必ずgit add & commitする
- コミットメッセージは日本語で「ファイル名: 変更内容」の形式
- git pushは明示的に指示された時のみ実行する
  （誤って本番に反映しないための安全弁）
```

---

## フォルダ構成の推奨
```
~/globalmedical/        ← git管理フォルダ（ここでclaudeを起動）
├── CLAUDE.md           ← Claude Codeへの指示書
├── index.html
├── karte.html
├── enkakuka.html
├── kantei.html
└── logo.png

## Knowledge source priority
Before proposing changes, consult these when relevant:

1. docs/patent/disclosure_rules.md
2. docs/company/overview.md
3. docs/operations/workflow.md
4. docs/prompts/
5. docs/products/
6. docs/investor/

## Rules
- Treat docs/ as persistent project knowledge
- Treat issues/ as execution units
- Prefer updating docs/ when knowledge changes
- Prefer creating issues/ when execution is needed
- Do not disclose patent-sensitive implementation details
- Do not add pricing to 医療鑑定本舗 public materials

*このファイルは随時更新してください。新しい開発・交渉・決定事項が生じた際に追記することで、常に最新のコンテキストを維持できます。*
