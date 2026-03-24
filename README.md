# Pauper Events

晴れる屋の全店舗からパウパーフォーマットのSE（争奪戦）イベントを自動収集し、GitHub Pagesで公開するツール。

## 機能

- 全31店舗のイベントを毎日自動取得（GitHub Actions）
- 土日祝のパウパー争奪戦を参加費1,000円以上でフィルタ
- HTML / JSON / ICS 形式で出力
- Google カレンダーへの自動同期（サービスアカウント）

## ローカル実行

```bash
pip install google-api-python-client google-auth

python fetch.py \
  --format pauper \
  --shop all \
  --months 3 \
  --days sat,sun \
  --se-only \
  --output all \
  --min-fee 1000 \
  --out-dir docs
```

## 設定

`config.example.json` を `config.json` にコピーして編集：

```json
{
  "gcal_id": "your-calendar-id@group.calendar.google.com",
  "pages_url": "https://your-username.github.io/Pauper-events/"
}
```

## GitHub Actions

毎日 JST 9:00 に自動実行。手動実行も可能（workflow_dispatch）。

Google カレンダー同期を使う場合は、リポジトリの Secrets に `GCAL_CREDENTIALS`（サービスアカウントキーJSON）を設定。
