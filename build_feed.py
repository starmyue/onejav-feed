#!/usr/bin/env python3
"""OneJav RSS feed builder -- 图片优先的 RSS 2.0 订阅源.

输入: items.json -- 条目列表, 每项字段:
    code    番号, 如 "1START-628"
    title   标题
    url     详情页 URL, 如 "https://onejav.com/torrent/1start628"
    image   封面图 URL (原始地址)
    actress 女优 (可选)
    studio  片商 (可选)
    date    发布/更新日期 YYYY-MM-DD (可选)
    local_image  本地预览用图片路径, 仅用于 preview.html (可选)

输出:
    onejav-feed.xml -- RSS 2.0 + Media RSS, 图片通过三种方式突出:
        1. <media:thumbnail>/<media:content> (Feedly/Inoreader 等识别展示大图)
        2. <enclosure> 图片附件 (部分阅读器展示)
        3. <description> 内嵌大图 <img> (所有阅读器兜底)
    preview.html -- 图片优先的订阅预览页 (大图卡片网格)
"""
import json
import html
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent
ITEMS_JSON = BASE / "items.json"
FEED_XML = BASE / "onejav-feed.xml"
PREVIEW_HTML = BASE / "preview.html"

FEED_TITLE = "OneJav 每日更新"
FEED_LINK = "https://onejav.com/new"
FEED_DESC = "OneJav 每日新片速递 -- 封面图优先展示"


def rfc2822(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def qattr(s):
    return escape(s, {'"': "&quot;"})


def img_mime(url):
    u = url.lower().split("?")[0]
    if u.endswith(".png"):
        return "image/png"
    if u.endswith(".gif"):
        return "image/gif"
    if u.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def full_title_of(it):
    code = it.get("code", "")
    title = it.get("title", "")
    if code and title:
        return "【" + code + "】" + title
    return code or title


def build_description(item):
    """description 内嵌大图: 图片永远在最前面、最显眼."""
    parts = []
    img = item.get("image", "")
    if img:
        parts.append(
            '<p style="margin:0 0 12px 0;text-align:center;">'
            + '<a href="' + qattr(item.get("url", "")) + '">'
            + '<img src="' + qattr(img) + '" '
            + 'style="max-width:100%;height:auto;border-radius:8px;" '
            + 'alt="' + escape(item.get("code", "")) + '"/>'
            + "</a></p>"
        )
    meta = []
    if item.get("actress"):
        meta.append("女优: " + html.escape(item["actress"]))
    if item.get("studio"):
        meta.append("片商: " + html.escape(item["studio"]))
    if item.get("date"):
        meta.append("日期: " + html.escape(item["date"]))
    if meta:
        parts.append("<p>" + "<br/>".join(meta) + "</p>")
    if item.get("title"):
        parts.append("<p>" + html.escape(item["title"]) + "</p>")
    return "".join(parts)


def build_xml(items, note):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" '
             'xmlns:atom="http://www.w3.org/2005/Atom">')
    L.append("  <channel>")
    L.append("    <title>" + escape(FEED_TITLE) + "</title>")
    L.append("    <link>" + FEED_LINK + "</link>")
    L.append("    <description>" + escape(FEED_DESC) + "</description>")
    L.append("    <language>zh-cn</language>")
    L.append("    <lastBuildDate>" + now + "</lastBuildDate>")
    L.append('    <atom:link href="' + FEED_LINK + '" rel="self" type="application/rss+xml"/>')
    L.append("    <!-- " + escape(note) + " -->")
    for it in items:
        img = it.get("image", "")
        mime = img_mime(img) if img else "image/jpeg"
        L.append("    <item>")
        L.append("      <title>" + escape(full_title_of(it)) + "</title>")
        L.append("      <link>" + escape(it.get("url", "")) + "</link>")
        L.append('      <guid isPermaLink="true">' + escape(it.get("url", "")) + "</guid>")
        L.append("      <pubDate>" + rfc2822(it.get("date", "")) + "</pubDate>")
        if it.get("actress"):
            L.append("      <author>" + escape(it["actress"]) + "</author>")
        if img:
            dim = ""
            if it.get("img_w") and it.get("img_h"):
                dim = ' width="%s" height="%s"' % (it["img_w"], it["img_h"])
            L.append('      <media:thumbnail url="' + qattr(img) + '"' + dim + "/>")
            L.append('      <media:content url="' + qattr(img) + '" type="' + mime + '" '
                     "medium=\"image\"" + dim + "/>")
            L.append('      <enclosure url="' + qattr(img) + '" type="' + mime + '"/>')
        L.append("      <description><![CDATA[" + build_description(it) + "]]></description>")
        L.append("    </item>")
    L.append("  </channel>")
    L.append("</rss>")
    return "\n".join(L) + "\n"


CARD_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#14161c;color:#e8eaf0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:24px 16px}
header{max-width:1200px;margin:0 auto 20px}
header h1{font-size:22px;margin-bottom:6px}
header p{color:#9aa0b0;font-size:13px}
.grid{max-width:1200px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.card{background:#1d2029;border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;display:block;transition:transform .15s}
.card:hover{transform:translateY(-3px)}
.card img{width:100%;aspect-ratio:800/537;object-fit:cover;display:block;background:#0c0e12}
.card .body{padding:12px 14px 14px}
.card .code{font-size:12px;color:#7fd4ff;letter-spacing:.5px;margin-bottom:6px}
.card .title{font-size:14px;line-height:1.5;margin-bottom:8px}
.card .meta{font-size:12px;color:#9aa0b0;line-height:1.7}
footer{max-width:1200px;margin:28px auto 0;color:#6b7280;font-size:12px;text-align:center}
"""


def build_html(items, note):
    cards = []
    for it in items:
        img = it.get("local_image") or it.get("image", "")
        meta = []
        if it.get("actress"):
            meta.append("女优 " + html.escape(it["actress"]))
        if it.get("studio"):
            meta.append(html.escape(it["studio"]))
        if it.get("date"):
            meta.append(html.escape(it["date"]))
        meta_html = '<div class="meta">' + " · ".join(meta) + "</div>" if meta else ""
        title_html = ""
        if it.get("title"):
            title_html = '<div class="title">' + html.escape(it["title"]) + "</div>"
        cards.append(
            '<a class="card" href="' + qattr(it.get("url", "")) + '" target="_blank" rel="noopener">'
            '<img loading="lazy" src="' + qattr(img) + '" alt="' + escape(it.get("code", "")) + '"/>'
            '<div class="body">'
            '<div class="code">' + escape(it.get("code", "")) + "</div>"
            + title_html
            + meta_html + "</div></a>"
        )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="UTF-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        "<title>" + html.escape(FEED_TITLE) + " -- 图片订阅预览</title>\n"
        "<style>" + CARD_CSS + "</style>\n</head>\n<body>\n<header>\n<h1>📡 "
        + html.escape(FEED_TITLE) + "</h1>\n<p>" + html.escape(note) + "</p>\n</header>\n"
        '<div class="grid">\n' + "".join(cards) + "\n</div>\n"
        "<footer>共 " + str(len(items)) + " 条 · 点击卡片打开原站详情页</footer>\n"
        "</body>\n</html>\n"
    )


def main():
    if not ITEMS_JSON.exists():
        print("缺少 %s, 先准备条目数据" % ITEMS_JSON, file=sys.stderr)
        sys.exit(1)
    items = json.loads(ITEMS_JSON.read_text(encoding="utf-8"))
    note = "共 %d 条, 生成于 %s UTC" % (len(items), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    FEED_XML.write_text(build_xml(items, note), encoding="utf-8")
    PREVIEW_HTML.write_text(build_html(items, note), encoding="utf-8")
    print("OK: %d items -> %s, %s" % (len(items), FEED_XML.name, PREVIEW_HTML.name))


if __name__ == "__main__":
    main()
