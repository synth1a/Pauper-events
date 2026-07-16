#!/usr/bin/env python3
"""events.json を読み取り、直近のイベントスケジュールを Discord Webhook に投稿・更新する。

初回は新規メッセージを投稿し、メッセージIDをファイルに保存する。
2回目以降は保存したIDのメッセージを編集する（＝ピン留めしておけば常に最新の掲示板になる）。
メッセージが削除されていた場合は自動で再投稿する。

環境変数 DISCORD_WEBHOOK に Webhook URL を設定して実行する。
未設定の場合は何もせず正常終了する（Actions で secret 未設定でも落ちないように）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

JST = timezone(timedelta(hours=9))
PAGES_URL = "https://synth1a.github.io/Pauper-events/"
EMBED_COLOR = 0x2ECC71  # 緑
FIELD_VALUE_LIMIT = 1024
EMBED_TOTAL_LIMIT = 5800  # 実際の上限6000に対して余裕を持たせる


def load_events(json_path):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def build_embed(data, days):
    today = datetime.now(JST).date()
    end = today + timedelta(days=days)

    by_date = {}
    for e in data.get("events", []):
        d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if today <= d <= end:
            by_date.setdefault(e["date"], []).append(e)

    fields = []
    for date_str in sorted(by_date):
        events = sorted(by_date[date_str], key=lambda x: x["time"])
        d = datetime.strptime(date_str, "%Y-%m-%d")
        name = f"📅 {d.month}/{d.day}（{events[0]['weekday']}）"
        lines = [
            f"{e['time']} [{e['title']}]({e['url']})｜{e['shop']}"
            for e in events
        ]
        value = "\n".join(lines)
        if len(value) > FIELD_VALUE_LIMIT:
            value = value[:950] + f"\n…（続きは [Webページ]({PAGES_URL}) へ）"
        fields.append({"name": name, "value": value})

    embed = {
        "title": f"⚔️ 晴れる屋 Pauperイベント（直近{days}日）",
        "url": PAGES_URL,
        "color": EMBED_COLOR,
        "footer": {
            "text": f"データ更新: {data.get('fetched_at', '不明')}（毎朝9時に自動更新）"
        },
    }

    if not fields:
        embed["description"] = "直近の開催予定はありません"
        return embed

    # Embed 全体の文字数上限を超えないよう、超過分の日付フィールドを削る
    total = len(embed["title"])
    kept = []
    for f_ in fields:
        total += len(f_["name"]) + len(f_["value"])
        if total > EMBED_TOTAL_LIMIT:
            kept.append({
                "name": "…",
                "value": f"以降の日程は [Webページ]({PAGES_URL}) で確認",
            })
            break
        kept.append(f_)
    embed["fields"] = kept
    return embed


def api_request(url, payload, method):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            # Discord(Cloudflare)は Python-urllib のデフォルトUAを403で弾くため必須
            "User-Agent": "PauperEventsBot (https://github.com/synth1a/Pauper-events, 1.0)",
        },
        method=method,
    )
    with urllib.request.urlopen(req) as res:
        body = res.read().decode("utf-8")
        return json.loads(body) if body else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="docs/events.json")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--id-file", default="docs/discord_message_id.txt")
    parser.add_argument("--dry-run", action="store_true",
                        help="投稿せずペイロードを表示する")
    args = parser.parse_args()

    data = load_events(args.json)
    embed = build_embed(data, args.days)
    payload = {"embeds": [embed]}

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        print("DISCORD_WEBHOOK が未設定のためスキップします")
        return

    message_id = None
    if os.path.exists(args.id_file):
        with open(args.id_file, encoding="utf-8") as f:
            message_id = f.read().strip() or None

    # 既存メッセージの編集を試み、404（削除済み）なら新規投稿にフォールバック
    if message_id:
        try:
            api_request(f"{webhook}/messages/{message_id}", payload, "PATCH")
            print(f"メッセージ {message_id} を更新しました")
            return
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            print("既存メッセージが見つからないため新規投稿します")

    res = api_request(f"{webhook}?wait=true", payload, "POST")
    message_id = res.get("id", "")
    with open(args.id_file, "w", encoding="utf-8") as f:
        f.write(message_id)
    print(f"新規メッセージ {message_id} を投稿しました（ピン留め推奨）")


if __name__ == "__main__":
    main()
