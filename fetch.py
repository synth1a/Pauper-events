#!/usr/bin/env python3
"""晴れる屋イベント情報取得スクリプト（stdlib完結）"""
import argparse
import json
import re
import sys
import io
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
CONFIG_FILE = SCRIPT_DIR / "config.json"

BASE_URL = "https://www.hareruyamtg.com/ja/events"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# フォーマットアイコンのclass → フォーマット名マッピング
FORMAT_ICONS = {
    "format-icon-St": "standard",
    "format-icon-Pi": "pioneer",
    "format-icon-Mo": "modern",
    "format-icon-Le": "legacy",
    "format-icon-Pa": "pauper",
    "format-icon-Co": "commander",
    "format-icon-Vi": "vintage",
    "format-icon-Li": "limited",
    "format-icon-ML": "league",
    "format-icon-Ot": "other",
    "format-icon-Se": "sealed",
    "format-icon-Dr": "draft",
}

# フォーマット名の日本語キーワード（イベント名からの補助判定用）
FORMAT_KEYWORDS = {
    "パウパー": "pauper",
    "モダン": "modern",
    "レガシー": "legacy",
    "スタンダード": "standard",
    "パイオニア": "pioneer",
    "統率者": "commander",
    "EDH": "commander",
    "ヴィンテージ": "vintage",
    "リミテッド": "limited",
    "シールド": "sealed",
    "ドラフト": "draft",
}

# デフォルト店舗マッピング
DEFAULT_SHOPS = {
    "tc_tokyo": 1, "tc_osaka": 5,
    "sapporo": 4, "sendai": 9, "koriyama": 16, "utsunomiya": 14,
    "mito": 22, "takasaki": 28, "chiba": 26, "narita": 2,
    "omiya": 13, "shibuya": 27, "akihabara": 8, "kichijoji": 17,
    "machida": 30, "kawasaki": 21, "yokohama": 10,
    "niigata": 24, "kanazawa": 25, "kofu": 20, "nagano": 31, "shizuoka": 7,
    "nagoya": 6, "osu": 18, "kyoto": 29, "nipponbashi": 23, "sannomiya": 19,
    "hiroshima": 15, "takamatsu": 11, "fukuoka": 3, "nomeruya": 12,
}

# 店舗名 英語→日本語
SHOP_NAMES_JA = {
    "tc_tokyo": "TC東京", "tc_osaka": "TC大阪",
    "sapporo": "札幌", "sendai": "仙台", "koriyama": "郡山", "utsunomiya": "宇都宮",
    "mito": "水戸", "takasaki": "高崎", "chiba": "千葉", "narita": "成田",
    "omiya": "大宮", "shibuya": "渋谷", "akihabara": "秋葉原", "kichijoji": "吉祥寺",
    "machida": "町田", "kawasaki": "川崎", "yokohama": "横浜",
    "niigata": "新潟", "kanazawa": "金沢", "kofu": "甲府", "nagano": "長野", "shizuoka": "静岡",
    "nagoya": "名古屋", "osu": "大須", "kyoto": "京都", "nipponbashi": "日本橋",
    "sannomiya": "三宮", "hiroshima": "広島", "takamatsu": "高松", "fukuoka": "福岡",
    "nomeruya": "のめるや",
}

# Googleカレンダー イベントカラーID (1-11)
SHOP_GCAL_COLORS: dict[str, str] = {
    "tc_tokyo": "9", "tc_osaka": "9",       # ブルーベリー（濃青）
    "sapporo": "5", "sendai": "5",           # バナナ（黄）
    "koriyama": "5", "utsunomiya": "5",      # バナナ（黄）
    "mito": "10", "takasaki": "10",          # バジル（緑）
    "chiba": "10", "narita": "10",           # バジル（緑）
    "omiya": "6", "shibuya": "6",            # みかん（橙）
    "akihabara": "6", "kichijoji": "6",      # みかん（橙）
    "machida": "6", "kawasaki": "6",         # みかん（橙）
    "yokohama": "6",                         # みかん（橙）
    "niigata": "2", "kanazawa": "2",         # セージ（薄緑）
    "kofu": "2", "nagano": "2",              # セージ（薄緑）
    "shizuoka": "2",                         # セージ（薄緑）
    "nagoya": "11", "osu": "11",             # トマト（赤）
    "kyoto": "3", "nipponbashi": "3",        # ぶどう（紫）
    "sannomiya": "3",                        # ぶどう（紫）
    "hiroshima": "7", "takamatsu": "7",      # ピーコック（青緑）
    "fukuoka": "7",                          # ピーコック（青緑）
    "nomeruya": "8",                         # グラファイト（灰）
}

GCAL_COLOR_TO_CSS: dict[str, str] = {
    "2": "#33b679",   # セージ（薄緑）— 甲信越・北陸・静岡
    "3": "#8e24aa",   # ぶどう（紫）— 関西
    "5": "#f6bf26",   # バナナ（黄）— 北海道・東北
    "6": "#f4511e",   # みかん（橙）— 東京・神奈川
    "7": "#039be5",   # ピーコック（青緑）— 中国・四国・九州
    "8": "#616161",   # グラファイト（灰）— のめるや
    "9": "#3f51b5",   # ブルーベリー（濃青）— TC東京・TC大阪
    "10": "#0b8043",  # バジル（緑）— 北関東
    "11": "#d50000",  # トマト（赤）— 東海
}

WEEKDAY_JA = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
WEEKDAY_EN = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime:
    """月のn番目の指定曜日を返す (n=1で第1週)"""
    first = datetime(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return datetime(year, month, 1 + offset + 7 * (n - 1))


def _vernal_equinox(year: int) -> int:
    """春分日を返す"""
    if year <= 2099:
        return int(20.8431 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    return 20


def _autumnal_equinox(year: int) -> int:
    """秋分日を返す"""
    if year <= 2099:
        return int(23.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    return 23


def get_holidays(year: int) -> set[str]:
    """指定年の日本の祝日セットを返す (YYYY-MM-DD形式)"""
    holidays: list[datetime] = []

    # 固定祝日
    fixed = [
        (1, 1),   # 元日
        (2, 11),  # 建国記念の日
        (2, 23),  # 天皇誕生日
        (4, 29),  # 昭和の日
        (5, 3),   # 憲法記念日
        (5, 4),   # みどりの日
        (5, 5),   # こどもの日
        (8, 11),  # 山の日
        (11, 3),  # 文化の日
        (11, 23), # 勤労感謝の日
    ]
    for m, d in fixed:
        holidays.append(datetime(year, m, d))

    # ハッピーマンデー
    holidays.append(_nth_weekday(year, 1, 0, 2))   # 成人の日 (1月第2月曜)
    holidays.append(_nth_weekday(year, 7, 0, 3))   # 海の日 (7月第3月曜)
    holidays.append(_nth_weekday(year, 9, 0, 3))   # 敬老の日 (9月第3月曜)
    holidays.append(_nth_weekday(year, 10, 0, 2))  # スポーツの日 (10月第2月曜)

    # 春分の日・秋分の日
    holidays.append(datetime(year, 3, _vernal_equinox(year)))
    holidays.append(datetime(year, 9, _autumnal_equinox(year)))

    # 振替休日: 祝日が日曜の場合、翌平日が振替休日
    holiday_set = {h.strftime("%Y-%m-%d") for h in holidays}
    for h in holidays:
        if h.weekday() == 6:  # 日曜
            sub = h + timedelta(days=1)
            while sub.strftime("%Y-%m-%d") in holiday_set:
                sub += timedelta(days=1)
            holiday_set.add(sub.strftime("%Y-%m-%d"))

    # 国民の休日: 祝日に挟まれた平日
    sorted_holidays = sorted(holidays)
    for i in range(len(sorted_holidays) - 1):
        diff = (sorted_holidays[i + 1] - sorted_holidays[i]).days
        if diff == 2:
            between = sorted_holidays[i] + timedelta(days=1)
            if between.weekday() != 6:  # 日曜でない
                holiday_set.add(between.strftime("%Y-%m-%d"))

    return holiday_set


class EventPageParser(HTMLParser):
    """晴れる屋イベントカレンダーページのパーサー"""

    def __init__(self, year: int, month: int):
        super().__init__()
        self.year = year
        self.month = month
        self.events: list[dict] = []

        # パース状態
        self._in_day_item = False
        self._current_day: int | None = None
        self._current_weekday: str | None = None
        self._in_weekday_span = False
        self._in_event_link = False
        self._current_event: dict | None = None
        self._in_name_span = False
        self._span_depth = 0
        self._weekday_span_depth = 0
        self._date_wrapper_class = ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")

        # 日付のli要素
        if tag == "li" and "eventCalendar__calendarList__data" in cls:
            self._in_day_item = True
            day_id = d.get("id", "")
            if day_id.isdigit():
                self._current_day = int(day_id)
            self._current_weekday = None

        # 曜日を含むwrapper div
        if tag == "div" and "eventCalendar__calendarList__data__wrapper" in cls:
            self._date_wrapper_class = cls

        # 曜日span
        if (tag == "span" and "eventCalendar__calendarList__data__container" in cls
                and "weekday" in cls):
            self._in_weekday_span = True
            self._weekday_span_depth = 0

        if self._in_weekday_span and tag == "span":
            self._weekday_span_depth += 1

        # イベントリンク
        if tag == "a" and self._in_day_item:
            href = d.get("href", "")
            match = re.search(r"/events/(\d+)/detail", href)
            if match:
                self._in_event_link = True
                self._current_event = {
                    "id": match.group(1),
                    "url": href,
                    "formats": [],
                    "time": "",
                    "title": "",
                }

        # フォーマットアイコン
        if tag == "span" and self._in_event_link and self._current_event:
            for icon_cls, fmt_name in FORMAT_ICONS.items():
                if icon_cls in cls:
                    if fmt_name not in self._current_event["formats"]:
                        self._current_event["formats"].append(fmt_name)

        # イベント名 span
        if (tag == "span" and self._in_event_link
                and "eventCalendar__calendarList__data__name" in cls):
            self._in_name_span = True
            self._span_depth = 0

        if self._in_name_span and tag == "span":
            self._span_depth += 1

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        # 曜日テキスト
        if self._in_weekday_span and text in WEEKDAY_JA:
            self._current_weekday = text

        # イベント名テキスト
        if self._in_name_span and self._current_event is not None:
            if not self._current_event["time"] and re.match(r"\d{1,2}:\d{2}", text):
                self._current_event["time"] = text
            else:
                self._current_event["title"] += text

    def handle_endtag(self, tag):
        if tag == "span" and self._in_weekday_span:
            self._weekday_span_depth -= 1
            if self._weekday_span_depth <= 0:
                self._in_weekday_span = False

        if tag == "span" and self._in_name_span:
            self._span_depth -= 1
            if self._span_depth <= 0:
                self._in_name_span = False

        if tag == "a" and self._in_event_link and self._current_event:
            self._in_event_link = False
            ev = self._current_event
            self._current_event = None

            # タイトルからフォーマットを補助判定
            for kw, fmt in FORMAT_KEYWORDS.items():
                if kw in ev["title"] and fmt not in ev["formats"]:
                    ev["formats"].append(fmt)

            # タグ抽出（[5回戦], [SE], [競技], [予約可] 等）
            tags = re.findall(r"\[([^\]]+)\]", ev["title"])

            # 日付を構築
            day = self._current_day or 1
            try:
                date_str = f"{self.year}-{self.month:02d}-{day:02d}"
                datetime.strptime(date_str, "%Y-%m-%d")  # validate
            except ValueError:
                return

            # 曜日判定
            weekday = self._current_weekday
            if not weekday:
                # wrapper classから判定
                for wd_en, wd_num in [("saturday", 5), ("sunday", 6),
                                       ("monday", 0), ("tuesday", 1),
                                       ("wednesday", 2), ("thursday", 3),
                                       ("friday", 4)]:
                    if wd_en in self._date_wrapper_class:
                        ja_wds = list(WEEKDAY_JA.keys())
                        weekday = ja_wds[wd_num]
                        break

            self.events.append({
                "id": ev["id"],
                "title": ev["title"].strip(),
                "date": date_str,
                "time": ev["time"],
                "weekday": weekday or "",
                "formats": ev["formats"],
                "tags": tags,
                "url": ev["url"],
            })

        if tag == "li" and self._in_day_item:
            self._in_day_item = False


def fetch_page(url: str) -> str:
    """URLからHTMLを取得（0.5秒のレート制限付き）"""
    time.sleep(0.5)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def get_events(shop_id: int, year: int, month: int) -> list[dict]:
    """指定店舗・月のイベントを取得"""
    url = f"{BASE_URL}?shop={shop_id}&date={year}{month:02d}"
    html = fetch_page(url)
    parser = EventPageParser(year, month)
    parser.feed(html)
    return parser.events


def fetch_entry_fee(event_url: str) -> int | None:
    """イベント詳細ページから参加費(円)を取得。取得できなければNone"""
    try:
        html = fetch_page(event_url)
        # "■参加費" の後に続く金額を探す
        m = re.search(r"参加費\s*</?\w*>?\s*(?:<[^>]*>\s*)*?([\d,]+)\s*円", html)
        if m:
            return int(m.group(1).replace(",", ""))
    except Exception:
        pass
    return None


def filter_events(events: list[dict], fmt: str | None, days: list[int] | None,
                  se_only: bool) -> list[dict]:
    """イベントをフィルタリング"""
    # 祝日セットを構築（対象イベントの年を収集）
    years = {ev["date"][:4] for ev in events if ev.get("date")}
    holidays: set[str] = set()
    for y in years:
        holidays |= get_holidays(int(y))

    result = []
    for ev in events:
        # フォーマットフィルタ
        if fmt and fmt != "all":
            if fmt not in ev["formats"]:
                continue

        # 曜日フィルタ（祝日も通す）
        if days:
            is_holiday = ev["date"] in holidays
            weekday_num = WEEKDAY_JA.get(ev["weekday"])
            if weekday_num is None:
                # 日付から算出
                try:
                    dt = datetime.strptime(ev["date"], "%Y-%m-%d")
                    weekday_num = dt.weekday()
                except ValueError:
                    continue
            if weekday_num not in days and not is_holiday:
                continue

        # SEフィルタ
        if se_only:
            has_se = any("SE" in tag or "決勝" in tag for tag in ev["tags"])
            has_cup = "争奪" in ev["title"] or "トライアル" in ev["title"]
            if not has_se and not has_cup:
                continue

        result.append(ev)
    return result


def generate_ics(events: list[dict], shop_names: dict[int, str]) -> str:
    """iCalendar形式のテキストを生成"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HareruyaEvents//JP",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:晴れる屋イベント",
    ]
    for ev in events:
        dtstart = ev["date"].replace("-", "")
        if ev["time"]:
            h, m = ev["time"].split(":")
            dtstart += f"T{h}{m}00"
        uid = f"hareruya-{ev['id']}@hareruyamtg.com"
        summary = _ics_escape(ev["title"])
        shop = _ics_escape(ev.get("shop", ""))
        url = ev["url"]

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        if ev["time"]:
            lines.append(f"DTSTART;TZID=Asia/Tokyo:{dtstart}")
            # イベント時間は2時間をデフォルトとする
            try:
                dt = datetime.strptime(f"{ev['date']} {ev['time']}", "%Y-%m-%d %H:%M")
                dt_end = dt + timedelta(hours=2)
                dtend = dt_end.strftime("%Y%m%dT%H%M00")
                lines.append(f"DTEND;TZID=Asia/Tokyo:{dtend}")
            except ValueError:
                pass
        else:
            lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
        lines.append(f"SUMMARY:{summary}")
        if shop:
            lines.append(f"LOCATION:{shop}")
        lines.append(f"URL:{url}")
        fmt_str = ", ".join(ev.get("formats", []))
        tags_str = ", ".join(ev.get("tags", []))
        desc = f"フォーマット: {fmt_str}"
        if tags_str:
            desc += f"\\nタグ: {tags_str}"
        escaped_desc = _ics_escape(desc).replace("\\\\n", "\\n")
        lines.append(f"DESCRIPTION:{escaped_desc}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _ics_escape(text: str) -> str:
    """iCalendar用テキストエスケープ"""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _gcal_url(ev: dict) -> str:
    """Googleカレンダー追加用URLを生成"""
    import urllib.parse
    title = ev["title"]
    date_compact = ev["date"].replace("-", "")
    if ev["time"]:
        h, m = ev["time"].split(":")
        dtstart = f"{date_compact}T{h}{m}00"
        try:
            dt = datetime.strptime(f"{ev['date']} {ev['time']}", "%Y-%m-%d %H:%M")
            dt_end = dt + timedelta(hours=2)
            dtend = dt_end.strftime("%Y%m%dT%H%M00")
        except ValueError:
            dtend = dtstart
    else:
        dtstart = date_compact
        dtend = date_compact
    params = urllib.parse.urlencode({
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{dtstart}/{dtend}",
        "ctz": "Asia/Tokyo",
        "location": ev.get("shop", ""),
        "details": ev["url"],
    })
    return f"https://calendar.google.com/calendar/render?{params}"


def generate_html(events: list[dict], fmt_filter: str, generated_at: str,
                  gcal_id: str = "", pages_url: str = "") -> str:
    """静的HTMLページを生成"""
    # 日付でグループ化
    by_date: dict[str, list[dict]] = {}
    shops_set: set[str] = set()
    for ev in events:
        by_date.setdefault(ev["date"], []).append(ev)
        if ev.get("shop"):
            shops_set.add(ev["shop"])

    weekday_names = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}
    weekday_colors = {5: "#0060c0", 6: "#d00000"}

    # イベントカードHTML
    cards_html = ""
    for date_str in sorted(by_date.keys()):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        wd = weekday_names[dt.weekday()]
        wd_color = weekday_colors.get(dt.weekday(), "#333")
        cards_html += f'<h2 class="date-header" id="date-{date_str}" style="margin-top:1.5em;color:{wd_color}">{date_str} ({wd})</h2>\n'

        for ev in by_date[date_str]:
            shop_attr = _html_escape(ev.get("shop", ""))
            shop_key = ev.get("shop_key", "")
            gcal_color_id = SHOP_GCAL_COLORS.get(shop_key, "1")
            label_color = GCAL_COLOR_TO_CSS.get(gcal_color_id, "#1a73e8")
            gcal = _html_escape(_gcal_url(ev))
            is_trial = "true" if "トライアル" in ev.get("title", "") else "false"
            cards_html += f"""<div class="event-card" data-shop="{shop_attr}" data-trial="{is_trial}">
  <div class="event-time">{_html_escape(ev['time'])}</div>
  <div class="event-body">
    <a href="{_html_escape(ev['url'])}" target="_blank" rel="noopener noreferrer" class="event-title">{_html_escape(ev['title'])}</a>
    <div class="event-meta"><span class="shop-label" style="background:{label_color}">{shop_attr}</span><a href="{gcal}" target="_blank" rel="noopener noreferrer" class="gcal-link" title="Googleカレンダーに追加">Googleカレンダーに追加</a></div>
  </div>
</div>
"""

    # 店舗フィルタ用のオプションHTML
    kanto_shops = ["TC東京", "水戸", "宇都宮", "高崎", "千葉", "成田", "大宮", "渋谷", "秋葉原", "吉祥寺", "町田", "川崎", "横浜"]
    shop_options = '<option value="kanto" selected>関東圏</option>\n'
    shop_options += '        <option value="all">すべての店舗</option>\n'
    for shop in sorted(shops_set):
        shop_options += f'        <option value="{_html_escape(shop)}">{_html_escape(shop)}</option>\n'

    # Googleカレンダー埋め込み + ICS購読
    gcal_section = ""
    if gcal_id:
        gcal_embed = _html_escape(gcal_id)
        gcal_section += f"""<div class="gcal-embed">
<iframe src="https://calendar.google.com/calendar/embed?src={gcal_embed}&ctz=Asia/Tokyo&mode=MONTH&showTitle=0&showNav=1&showPrint=0&showTabs=0&showCalendars=0" style="border:0" width="100%" height="400" frameborder="0" scrolling="no"></iframe>
</div>
"""
    if pages_url:
        ics_url = pages_url.rstrip("/") + "/events.ics"
        subscribe_url = f"https://calendar.google.com/calendar/r?cid=webcal://{ics_url.replace('https://', '').replace('http://', '')}"
        gcal_section += f"""<div class="subscribe-bar">
<a href="{_html_escape(subscribe_url)}" target="_blank" rel="noopener noreferrer" class="subscribe-btn">Googleカレンダーに購読登録</a>
<span class="subscribe-note">登録すると毎日自動で最新イベントが同期されます</span>
</div>
"""

    filter_label = fmt_filter if fmt_filter != "all" else "全フォーマット"
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>晴れる屋パウパー 土日SEイベント</title>
<meta name="robots" content="noindex, nofollow">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 1rem; max-width: 800px; margin: 0 auto; }}
header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem; }}
header h1 {{ font-size: 1.4rem; margin-bottom: 0.5rem; }}
.header-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.8rem; font-size: 0.85rem; }}
.header-meta a {{ color: #8ecaff; text-decoration: none; }}
.header-meta a:hover {{ text-decoration: underline; }}
.updated {{ background: rgba(255,255,255,0.15); padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }}
.filter-bar {{ background: #fff; padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; }}
.filter-bar label {{ font-size: 0.85rem; font-weight: 500; color: #555; }}
.filter-bar select {{ padding: 0.3rem 0.6rem; border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; }}
.event-count {{ font-size: 0.8rem; color: #888; margin-left: auto; }}
h2 {{ font-size: 1.1rem; padding: 0.5rem 0; border-bottom: 2px solid #ddd; }}
.event-card {{ display: flex; gap: 0.8rem; background: #fff; padding: 0.8rem 1rem; border-radius: 6px; margin: 0.5rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.event-card.hidden {{ display: none; }}
.date-header.hidden {{ display: none; }}
.event-time {{ font-weight: bold; font-size: 0.95rem; min-width: 3.5rem; color: #555; padding-top: 0.1rem; }}
.event-body {{ flex: 1; }}
.event-title {{ color: #1a73e8; text-decoration: none; font-weight: 500; }}
.event-title:hover {{ text-decoration: underline; }}
.event-meta {{ margin-top: 0.3rem; display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; }}
.badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }}
.badge-pauper {{ background: #e8f5e9; color: #2e7d32; }}
.badge-modern {{ background: #e3f2fd; color: #1565c0; }}
.badge-legacy {{ background: #f3e5f5; color: #7b1fa2; }}
.badge-standard {{ background: #fff3e0; color: #e65100; }}
.badge-pioneer {{ background: #fce4ec; color: #c62828; }}
.badge-commander {{ background: #e0f2f1; color: #00695c; }}
.badge-vintage {{ background: #efebe9; color: #4e342e; }}
.badge-limited, .badge-sealed, .badge-draft {{ background: #f1f8e9; color: #558b2f; }}
.badge-league {{ background: #e8eaf6; color: #283593; }}
.badge-other {{ background: #eceff1; color: #546e7a; }}
.badge-tag {{ background: #f5f5f5; color: #666; border: 1px solid #ddd; }}
.badge-fee {{ background: #fff8e1; color: #f57f17; border: 1px solid #ffe082; }}
.shop-label {{ font-size: 0.8rem; font-weight: 700; color: #fff; background: #1a73e8; padding: 0.15rem 0.6rem; border-radius: 4px; white-space: nowrap; align-self: center; }}
.gcal-link {{ font-size: 0.7rem; color: #1a73e8; text-decoration: none; margin-left: 0.3rem; padding: 0.1rem 0.4rem; border: 1px solid #c5d8f8; border-radius: 3px; }}
.gcal-link:hover {{ background: #e8f0fe; }}
.gcal-embed {{ background: #fff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 0.5rem; margin-bottom: 1rem; overflow: hidden; }}
.subscribe-bar {{ background: #fff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 0.8rem 1rem; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; }}
.subscribe-btn {{ display: inline-block; background: #1a73e8; color: #fff; padding: 0.4rem 1rem; border-radius: 4px; text-decoration: none; font-size: 0.85rem; font-weight: 500; }}
.subscribe-btn:hover {{ background: #1557b0; }}
.subscribe-note {{ font-size: 0.8rem; color: #888; }}
.no-events {{ text-align: center; padding: 2rem; color: #999; }}
footer {{ text-align: center; margin-top: 2rem; padding: 1rem; font-size: 0.8rem; color: #999; }}
</style>
</head>
<body>
<header>
  <h1>晴れる屋パウパー 土日SEイベント</h1>
  <div class="header-meta">
    <span class="updated">最終更新: {_html_escape(generated_at)}</span>
  </div>
</header>
{gcal_section}<div class="filter-bar">
  <label for="shop-filter">店舗:</label>
  <select id="shop-filter" onchange="filterEvents()">
    {shop_options}
  </select>
  <label style="font-size:0.85rem;cursor:pointer;"><input type="checkbox" id="trial-filter" onchange="filterEvents()"> トライアル</label>
  <span class="event-count" id="event-count">{len(events)}件</span>
</div>
{cards_html if cards_html else '<div class="no-events">該当するイベントが見つかりませんでした。</div>'}
<footer>データ元: <a href="https://www.hareruyamtg.com/ja/events" target="_blank" rel="noopener noreferrer">晴れる屋</a></footer>
<script>
function filterByShop(shop) {{
  document.getElementById('shop-filter').value = shop;
  filterEvents();
}}
var KANTO = ["TC東京","水戸","宇都宮","高崎","千葉","成田","大宮","渋谷","秋葉原","吉祥寺","町田","川崎","横浜"];
function filterEvents() {{
  var shop = document.getElementById('shop-filter').value;
  var trialOnly = document.getElementById('trial-filter').checked;
  var cards = document.querySelectorAll('.event-card');
  var headers = document.querySelectorAll('.date-header');
  var count = 0;
  cards.forEach(function(card) {{
    var s = card.getAttribute('data-shop');
    var shopMatch = (shop === 'all' || (shop === 'kanto' ? KANTO.indexOf(s) !== -1 : s === shop));
    var trialMatch = (!trialOnly || card.getAttribute('data-trial') === 'true');
    if (shopMatch && trialMatch) {{
      card.classList.remove('hidden');
      count++;
    }} else {{
      card.classList.add('hidden');
    }}
  }});
  headers.forEach(function(h) {{
    var next = h.nextElementSibling;
    var hasVisible = false;
    while (next && !next.classList.contains('date-header') && next.tagName !== 'FOOTER') {{
      if (next.classList.contains('event-card') && !next.classList.contains('hidden')) {{
        hasVisible = true;
        break;
      }}
      next = next.nextElementSibling;
    }}
    h.classList.toggle('hidden', !hasVisible);
  }});
  document.getElementById('event-count').textContent = count + '件';
}}
filterEvents();
</script>
</body>
</html>"""


def _html_escape(text: str) -> str:
    """HTMLエスケープ"""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _build_gcal_event_id(hareruya_id: str) -> str:
    """晴れる屋イベントIDからGCal用イベントIDを生成（base32hex: a-v, 0-9のみ）"""
    return f"hrr{hareruya_id}"


def _build_gcal_body(ev: dict) -> dict:
    """イベント辞書からGCal APIリクエストボディを組み立てる"""
    body: dict = {
        "summary": ev["title"],
        "location": ev.get("shop", ""),
        "description": ev["url"],
        "source": {"title": "晴れる屋", "url": ev["url"]},
    }
    if ev["time"]:
        try:
            dt = datetime.strptime(f"{ev['date']} {ev['time']}", "%Y-%m-%d %H:%M")
            dt_end = dt + timedelta(hours=2)
            body["start"] = {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Tokyo"}
            body["end"] = {"dateTime": dt_end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Tokyo"}
        except ValueError:
            body["start"] = {"date": ev["date"]}
            body["end"] = {"date": ev["date"]}
    else:
        body["start"] = {"date": ev["date"]}
        body["end"] = {"date": ev["date"]}

    shop_key = ev.get("shop_key", "")
    color_id = SHOP_GCAL_COLORS.get(shop_key, "1")
    body["colorId"] = color_id
    return body


def sync_to_gcal(events: list[dict], gcal_id: str, creds_path: str) -> int:
    """Google Calendar APIでイベントをupsert同期。追加・更新件数を返す"""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)

    # 既存イベントを取得（ID→イベントのマップ）
    existing: dict[str, dict] = {}
    page_token = None
    while True:
        result = service.events().list(
            calendarId=gcal_id, pageToken=page_token, maxResults=250
        ).execute()
        for item in result.get("items", []):
            existing[item["id"]] = item
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    # 新しいイベントをupsert（insert or update）
    new_ids: set[str] = set()
    synced = 0
    for ev in events:
        gcal_event_id = _build_gcal_event_id(ev["id"])
        new_ids.add(gcal_event_id)
        body = _build_gcal_body(ev)

        if gcal_event_id in existing:
            # 既存イベントを更新
            service.events().update(
                calendarId=gcal_id, eventId=gcal_event_id, body=body
            ).execute()
        else:
            # 新規追加（IDを指定）
            body["id"] = gcal_event_id
            service.events().insert(calendarId=gcal_id, body=body).execute()
        synced += 1

    # 不要になったイベントを削除（新しいリストにないもの）
    for old_id in existing:
        if old_id not in new_ids:
            try:
                service.events().delete(
                    calendarId=gcal_id, eventId=old_id
                ).execute()
            except Exception:
                pass

    return synced


def load_config() -> dict:
    """設定ファイルを読み込み"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _to_ja(shop_key: str) -> str:
    """店舗キーを日本語名に変換"""
    return SHOP_NAMES_JA.get(shop_key, shop_key)


def resolve_shops(shop_arg: str, config: dict) -> dict[int, str]:
    """引数から対象店舗を解決。{shop_id: (shop_key, shop_name_ja)} を返す"""
    shops_map = config.get("shops", DEFAULT_SHOPS)
    # 逆引き: id → key
    id_to_key = {}
    for name, sid in shops_map.items():
        id_to_key[sid] = name

    def _resolve(keys: dict[int, str]) -> dict[int, str]:
        return {sid: _to_ja(key) for sid, key in keys.items()}

    if shop_arg == "all":
        return _resolve(id_to_key)

    result = {}
    for part in shop_arg.split(","):
        part = part.strip()
        if part.isdigit():
            sid = int(part)
            result[sid] = id_to_key.get(sid, f"shop_{sid}")
        elif part in shops_map:
            sid = shops_map[part]
            result[sid] = part
        else:
            # 部分一致
            for name, sid in shops_map.items():
                if part.lower() in name.lower():
                    result[sid] = name
    return _resolve(result)


def parse_days(days_arg: str | None) -> list[int] | None:
    """曜日引数をパース。'sat,sun' → [5, 6]"""
    if not days_arg:
        return None
    result = []
    for d in days_arg.split(","):
        d = d.strip().lower()
        if d in WEEKDAY_EN:
            result.append(WEEKDAY_EN[d])
        elif d in WEEKDAY_JA:
            result.append(WEEKDAY_JA[d])
    return result if result else None


def main():
    parser = argparse.ArgumentParser(description="晴れる屋イベント情報取得")
    parser.add_argument("--format", default="pauper",
                        help="フィルタするフォーマット (pauper/modern/legacy/standard/pioneer/commander/all)")
    parser.add_argument("--shop", default="all",
                        help="店舗指定 (all / 店舗名 / shop番号 / カンマ区切り)")
    parser.add_argument("--months", type=int, default=3,
                        help="何ヶ月先まで取得するか (デフォルト: 3)")
    parser.add_argument("--days", default=None,
                        help="曜日フィルタ (例: sat,sun / 土,日)")
    parser.add_argument("--se-only", action="store_true",
                        help="SE(決勝)ありのイベントのみ")
    parser.add_argument("--output", default="all",
                        help="出力形式 (json/ics/html/all)")
    parser.add_argument("--out-dir", default=None,
                        help="出力先ディレクトリ (デフォルト: outputs/)")
    parser.add_argument("--min-fee", type=int, default=0,
                        help="参加費の最低金額フィルタ (例: 1000)")
    parser.add_argument("--sync-gcal", action="store_true",
                        help="Googleカレンダーにイベントを同期")
    parser.add_argument("--gcal-creds", default=None,
                        help="サービスアカウントJSONキーのパス")
    args = parser.parse_args()

    config = load_config()
    shops = resolve_shops(args.shop, config)
    days_filter = parse_days(args.days)
    fmt = args.format.lower()

    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    all_events: list[dict] = []

    # 対象月リスト
    months = []
    for i in range(args.months):
        y = now.year
        m = now.month + i
        while m > 12:
            m -= 12
            y += 1
        months.append((y, m))

    print(f"取得中... 店舗数: {len(shops)}, 対象月: {len(months)}", file=sys.stderr)

    # 日本語名→英語キー逆引き
    ja_to_key = {v: k for k, v in SHOP_NAMES_JA.items()}

    for shop_id, shop_name in shops.items():
        for year, month in months:
            print(f"  {shop_name} ({year}/{month:02d})...", file=sys.stderr, end="", flush=True)
            try:
                events = get_events(shop_id, year, month)
                # 店舗名を付与
                shop_key = ja_to_key.get(shop_name, shop_name)
                for ev in events:
                    ev["shop"] = shop_name
                    ev["shop_key"] = shop_key
                    ev["shop_id"] = shop_id
                all_events.extend(events)
                print(f" {len(events)}件", file=sys.stderr)
            except Exception as e:
                print(f" エラー: {e}", file=sys.stderr)

    # フィルタリング
    filtered = filter_events(all_events, fmt, days_filter, args.se_only)

    # 実行日以前のイベントを除外
    today_str = now.strftime("%Y-%m-%d")
    filtered = [ev for ev in filtered if ev["date"] >= today_str]

    # 日付順でソート
    filtered.sort(key=lambda e: (e["date"], e["time"]))

    # 重複除去（同じイベントIDは1つだけ）
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for ev in filtered:
        if ev["id"] not in seen_ids:
            seen_ids.add(ev["id"])
            unique.append(ev)
    filtered = unique

    # 参加費フィルタ（詳細ページから取得）
    if args.min_fee > 0:
        print(f"\n参加費フィルタ ({args.min_fee}円以上)... {len(filtered)}件の詳細を取得中",
              file=sys.stderr)
        fee_filtered = []
        for ev in filtered:
            print(f"  {ev['shop']} {ev['date']} ...", file=sys.stderr, end="", flush=True)
            fee = fetch_entry_fee(ev["url"])
            ev["fee"] = fee
            if fee is not None and fee >= args.min_fee:
                print(f" {fee}円 ○", file=sys.stderr)
                fee_filtered.append(ev)
            elif fee is None:
                print(f" 不明 (スキップ)", file=sys.stderr)
            else:
                print(f" {fee}円 ×", file=sys.stderr)
        filtered = fee_filtered

    generated_at = now.strftime("%Y-%m-%d %H:%M")
    print(f"\n結果: {len(filtered)}件 (フィルタ: format={fmt}, days={args.days}, se_only={args.se_only}, min_fee={args.min_fee})",
          file=sys.stderr)

    # 出力先ディレクトリ
    out_dir = Path(args.out_dir) if args.out_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = args.output.lower().split(",") if args.output != "all" else ["json", "ics", "html"]

    if "json" in outputs:
        data = {
            "fetched_at": generated_at,
            "format_filter": fmt,
            "days_filter": args.days,
            "se_only": args.se_only,
            "total": len(filtered),
            "events": filtered,
        }
        out_path = out_dir / "events.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"JSON: {out_path}", file=sys.stderr)

    if "ics" in outputs:
        ics_text = generate_ics(filtered, {s: n for s, n in shops.items()})
        out_path = out_dir / "events.ics"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(ics_text)
        print(f"ICS:  {out_path}", file=sys.stderr)

    if "html" in outputs:
        gcal_id = config.get("gcal_id", "")
        pages_url = config.get("pages_url", "")
        html_text = generate_html(filtered, fmt, generated_at, gcal_id, pages_url)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_text)
        print(f"HTML: {out_path}", file=sys.stderr)

    # Googleカレンダー同期
    gcal_synced = 0
    if args.sync_gcal:
        gcal_id = config.get("gcal_id", "")
        creds_path = args.gcal_creds or str(SCRIPT_DIR / "gcal-credentials.json")
        if not gcal_id:
            print("エラー: config.json に gcal_id が設定されていません", file=sys.stderr)
        elif not Path(creds_path).exists():
            print(f"エラー: サービスアカウントキーが見つかりません: {creds_path}", file=sys.stderr)
        else:
            print(f"\nGoogleカレンダー同期中... ({len(filtered)}件)", file=sys.stderr)
            try:
                gcal_synced = sync_to_gcal(filtered, gcal_id, creds_path)
                print(f"GCal: {gcal_synced}件を同期完了", file=sys.stderr)
            except Exception as e:
                print(f"GCal同期エラー: {e}", file=sys.stderr)

    # stdout にJSON結果サマリーを出力（Claude連携用）
    summary = {
        "status": "ok",
        "total": len(filtered),
        "format": fmt,
        "days": args.days,
        "se_only": args.se_only,
        "shops": len(shops),
        "outputs": outputs,
        "gcal_synced": gcal_synced,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
