#!/usr/bin/env python3
"""抓取 onejav.com/new 最新更新, 合并入 items.json, 重新生成 onejav-feed.xml.

供 GitHub Actions 定时调用, 也可本地运行:  python3 refresh.py
依赖: pip install requests beautifulsoup4
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
ITEMS_JSON = BASE / "items.json"
FEED_XML = BASE / "onejav-feed.xml"
LIST_URL = "https://onejav.com/new"
MAX_ITEMS = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date(text):
    """"Aug. 6, 2026" / "Sept. 29, 2026" -> "2026-08-06"."""
    m = re.match(r"\s*([A-Za-z]+)\.\s*(\d{1,2}),\s*(\d{4})", text or "")
    if not m:
        return ""
    mon = MONTHS.get(m.group(1).lower(), 0)
    if not mon:
        return ""
    return "%s-%02d-%02d" % (m.group(3), mon, int(m.group(2)))


def parse_list(html):
    """按 onejav 列表页结构 (Bulma 卡片) 提取条目."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("div.card.mb-3"):
        a = card.select_one("h5.title.is-4.is-spaced a")
        if not a:
            continue
        code = a.get_text(strip=True)
        m = re.search(r"/torrent/([a-z0-9]+)", a.get("href") or "")
        if not m:
            continue
        slug = m.group(1)
        img = card.select_one("img.image")
        img_url = (img.get("src") or "").strip() if img else ""
        if img_url.startswith("data:"):
            img_url = ""
        d_a = card.select_one("p.subtitle.is-6 a")
        date_iso = parse_date(d_a.get_text()) if d_a else ""
        t_p = card.select_one("p.level.has-text-grey-dark")
        title = t_p.get_text(strip=True) if t_p else ""
        out.append({
            "code": code,
            "title": title,
            "url": "https://onejav.com/torrent/" + slug,
            "image": img_url,
            "date": date_iso,
        })
    return out


def fetch_cards():
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(LIST_URL, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return parse_list(r.text)
        except Exception as e:  # noqa: BLE001 - 抓取失败统一重试
            last_err = e
            print("抓取失败 (第 %d/3 次): %s" % (attempt + 1, e), flush=True)
            time.sleep(10)
    raise SystemExit("连续 3 次抓取失败, 放弃本次更新: %s" % last_err)


def main():
    fetched = fetch_cards()
    print("抓到 %d 条" % len(fetched), flush=True)
    existing = []
    if ITEMS_JSON.exists():
        existing = json.loads(ITEMS_JSON.read_text(encoding="utf-8"))
    seen = {it.get("url") for it in existing}
    new_items = [it for it in fetched if it.get("url") and it["url"] not in seen]
    merged = (new_items + existing)[:MAX_ITEMS]
    ITEMS_JSON.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sys.path.insert(0, str(BASE))
    import build_feed  # noqa: E402
    note = "共 %d 条, 本次新增 %d 条, 生成于 %s UTC" % (
        len(merged), len(new_items),
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    FEED_XML.write_text(build_feed.build_xml(merged, note), encoding="utf-8")
    print("新增 %d 条, 订阅已更新 (共 %d 条)" % (len(new_items), len(merged)), flush=True)


if __name__ == "__main__":
    main()
