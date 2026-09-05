import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fetch import fetch_page, EventPageParser, filter_events, BASE_URL
os.makedirs("scratch/out", exist_ok=True)
html = fetch_page(f"{BASE_URL}?shop=1&date=202609")
open("scratch/out/tc_tokyo_202609.html", "w", encoding="utf-8").write(html)
print("HTML bytes:", len(html))
p = EventPageParser(2026, 9); p.feed(html)
print("parsed:", len(p.events))
for e in p.events:
    if e["date"] in ("2026-09-05", "2026-09-06", "2026-09-07") or "トライアル" in e["title"]:
        print("PARSED", e["date"], e["time"], repr(e["title"]), e["formats"], e["tags"], e["id"])
flt = filter_events(p.events, "pauper", None, True)
print("after filter:", [(e["date"], e["title"], e["id"]) for e in flt])
# raw li for day 6
m = re.search(r'<li[^>]*id="6"[^>]*>.*?(?=<li[^>]*class="[^"]*eventCalendar__calendarList__data[^"]*"[^>]*id="7")', html, re.S)
raw = m.group(0) if m else "NO li#6 FOUND"
open("scratch/out/li6.html", "w", encoding="utf-8").write(raw)
print("li#6 length:", len(raw))
for a in re.finditer(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', raw, re.S):
    txt = re.sub(r"<[^>]+>", "", a.group(2)); txt = re.sub(r"\s+", " ", txt).strip()
    cls = re.findall(r'format-icon-\w+', a.group(2))
    print("A", a.group(1), "|", txt, "|", cls)
for kw in ("トライアル", "神挑戦者"):
    for mm in re.finditer(kw, html):
        s = html.rfind('id="', 0, mm.start()); print("KW", kw, "ctx:", html[max(0, mm.start()-200):mm.start()+80].replace("\n", " ")[:280])
        break
