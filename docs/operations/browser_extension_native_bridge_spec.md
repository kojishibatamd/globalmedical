# Browser Extension Native Bridge Spec

## Purpose
ブラウザ拡張からローカル環境（WSL）へ直接データを保存し、
その後のAIパイプラインを自動実行するための仕様。

---

## Flow
1. ブラウザでテキスト選択
2. ExtensionでCapture
3. native_host.pyへ送信
4. raw.md保存
5. clean_capture.pyで整形
6. summarize_discussion.pyで構造化
7. run_topic_pipeline.sh実行

---

## Output

### raw
inbox/<topic>/raw.md

### discussion
inbox/<topic>/discussion.md

---

## Message Format

{
  "action": "save_capture",
  "topic": "kantei_faxdm",
  "mode": "raw",
  "content": "...",
  "meta": {
    "url": "...",
    "title": "...",
    "service": "chatgpt"
  },
  "options": {
    "clean": true,
    "summarize": true,
    "run_pipeline": false,
    "append": true
  }
}

---

## Security
- ローカルのみ
- git自動実行なし
- topic validation必須
