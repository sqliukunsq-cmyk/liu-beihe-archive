
from __future__ import annotations
import os, json, re, html
from pathlib import Path
from datetime import datetime
import requests
import markdown

ROOT = Path(__file__).resolve().parents[1]
SITE = os.environ.get("SITE_URL", "https://sqliukunsq-cmyk.github.io/liu-beihe-archive").rstrip("/")
TOKEN = os.environ["NOTION_API_KEY"]
DS = os.environ.get("NOTION_DATA_SOURCE_ID", "7e2c17cf-b76f-4b0b-bd6c-b54dbaaaa98c")
VERSION = "2026-03-11"

RESEARCH = ROOT / "research"
RESEARCH.mkdir(exist_ok=True)
STATE_PATH = RESEARCH / "_notion_state.json"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": VERSION,
    "Content-Type": "application/json",
}

def api(method, url, **kwargs):
    r = requests.request(method, url, headers=HEADERS, timeout=60, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f"Notion API {r.status_code}: {r.text[:1000]}")
    return r.json()

def plain_rich(arr):
    return "".join(x.get("plain_text", "") for x in (arr or []))

def prop(page, name):
    p = page.get("properties", {}).get(name, {})
    typ = p.get("type")
    if typ == "title":
        return plain_rich(p.get("title"))
    if typ == "rich_text":
        return plain_rich(p.get("rich_text"))
    if typ == "select":
        x = p.get("select")
        return (x or {}).get("name", "")
    if typ == "multi_select":
        return [x.get("name","") for x in p.get("multi_select", [])]
    if typ == "date":
        x = p.get("date")
        return (x or {}).get("start", "")
    if typ == "number":
        return p.get("number")
    if typ == "status":
        x = p.get("status")
        return (x or {}).get("name", "")
    return ""

def slugify(value, fallback):
    s = (value or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:80] or fallback)

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {"pages": {}}

def query_all_pages():
    rows, cursor = [], None
    while True:
        body = {
            "page_size": 100,
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
        }
        if cursor:
            body["start_cursor"] = cursor
        data = api("POST", f"https://api.notion.com/v1/data_sources/{DS}/query", json=body)
        rows.extend([x for x in data.get("results", []) if x.get("object") == "page"])
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return rows

def page_markdown(page_id):
    data = api("GET", f"https://api.notion.com/v1/pages/{page_id}/markdown")
    md = data.get("markdown", "")
    md = re.sub(r'<mention-[^>]+>(.*?)</mention-[^>]+>', r'\1', md, flags=re.S)
    return md

def render_article(rec, md):
    lang = "en" if rec["category"] == "English Essay" else "zh-CN"
    desc = rec.get("english_title") or rec["title"]
    desc = re.sub(r"\s+", " ", desc)[:155]
    content = markdown.markdown(md, extensions=["extra", "sane_lists"])
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": rec["title"],
        "alternativeHeadline": rec.get("english_title", ""),
        "author": {"@type": "Person", "name": "LIU BEIHE / 刘北河"},
        "datePublished": rec["date"],
        "dateModified": rec["last_edited_time"],
        "mainEntityOfPage": rec["url"],
        "keywords": rec.get("keywords", []),
    }
    return f"""<!doctype html><html lang="{lang}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(rec["title"])} | LIU BEIHE / 刘北河</title>
<meta name="description" content="{html.escape(desc, quote=True)}">
<link rel="canonical" href="{rec["url"]}">
<meta property="og:title" content="{html.escape(rec["title"], quote=True)}">
<meta property="og:description" content="{html.escape(desc, quote=True)}">
<meta property="og:type" content="article"><meta property="og:url" content="{rec["url"]}">
<link rel="stylesheet" href="{SITE}/style.css">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
</head><body><div class="wrap"><nav>
<a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a>
<div class="links"><a href="{SITE}/about/">About</a>
<a href="{SITE}/artist-statement/">Statement</a>
<a href="{SITE}/#works">Works</a><a href="{SITE}/research/">Research</a></div></nav>
<article><section class="hero"><div class="kicker">{html.escape(rec["category"])} · {html.escape(rec["date"])}</div>
<h1>{html.escape(rec["title"])}</h1>
<p class="meta">{html.escape(rec.get("english_title",""))}</p></section>
{content}</article>
<footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>
Official website: <a href="https://liukun.puruimier.com/">https://liukun.puruimier.com/</a><br>
© {rec["date"][:4] if rec["date"] else datetime.now().year} LIU BEIHE. All rights reserved.</footer>
</div></body></html>"""

def rebuild_archive(records):
    records = sorted(records, key=lambda x: (x.get("date",""), x.get("last_edited_time","")), reverse=True)
    cards = []
    for r in records[:500]:
        kws = " · ".join(r.get("keywords", [])[:4])
        meta = f'{r.get("category","Research")} · {r.get("date","")}'
        if kws:
            meta += f" · {kws}"
        cards.append(
            f'<div class="card"><div class="meta">{html.escape(meta)}</div>'
            f'<h3><a href="{html.escape(r["url"], quote=True)}">{html.escape(r["title"])}</a></h3>'
            f'<p>{html.escape(r.get("english_title",""))}</p></div>'
        )
    archive = f"""<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>刘北河研究档案 | LIU BEIHE Research Archive</title>
<meta name="description" content="刘北河关于机器观看、后摄影机电影、生成式影像、作者性、身份、感知与视觉证据的持续研究档案。">
<link rel="canonical" href="{SITE}/research/"><meta property="og:type" content="website">
<link rel="stylesheet" href="{SITE}/style.css"></head><body><div class="wrap"><nav>
<a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a>
<div class="links"><a href="{SITE}/about/">About</a>
<a href="{SITE}/artist-statement/">Statement</a><a href="{SITE}/#works">Works</a>
<a href="{SITE}/research/">Research</a></div></nav>
<section class="hero"><div class="kicker">Living Research Archive</div>
<h1>Research Archive<br>研究档案</h1>
<p class="lead">刘北河关于电影、生成式影像、机器观看、作者性、身份、感知与视觉证据的持续研究档案。</p>
<p class="en">A continuously expanding research archive by LIU BEIHE.</p></section>
<section><h2>Latest Research</h2><div class="grid">{''.join(cards)}</div></section>
<footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>
© {datetime.now().year} LIU BEIHE.</footer></div></body></html>"""
    (RESEARCH / "index.html").write_text(archive, "utf-8")
    return cards

def patch_home(cards):
    home = ROOT / "index.html"
    if not home.exists():
        return
    h = home.read_text("utf-8")
    if f'href="{SITE}/research/"' not in h:
        h = h.replace(
            f'<a href="{SITE}/#writing">Writing</a>',
            f'<a href="{SITE}/#writing">Writing</a><a href="{SITE}/research/">Research</a>'
        )
    block = f"""<!-- AUTO_RESEARCH_START --><section id="daily-research">
<h2>Latest Research / 最新研究</h2><div class="grid">{''.join(cards[:10])}</div>
<p><a href="{SITE}/research/">View complete research archive →</a></p></section>
<!-- AUTO_RESEARCH_END -->"""
    if "<!-- AUTO_RESEARCH_START -->" in h:
        h = re.sub(r"<!-- AUTO_RESEARCH_START -->.*?<!-- AUTO_RESEARCH_END -->", block, h, flags=re.S)
    else:
        h = h.replace("<footer>", block + "<footer>", 1)
    home.write_text(h, "utf-8")

def rebuild_sitemap():
    urls = []
    for p in ROOT.rglob("index.html"):
        rel = p.relative_to(ROOT)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.as_posix() == "index.html":
            u = SITE + "/"
        else:
            u = SITE + "/" + rel.parent.as_posix().strip("/") + "/"
        urls.append(u)
    urls = sorted(set(urls))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += f"  <url><loc>{html.escape(u)}</loc></url>\n"
    xml += "</urlset>\n"
    (ROOT / "sitemap.xml").write_text(xml, "utf-8")

state = load_state()
pages_state = state.setdefault("pages", {})
rows = query_all_pages()
changed = 0
publishable_ids = set()

for page in rows:
    status = prop(page, "Status")
    if status and status not in ("Ready", "Published"):
        continue

    page_id = page["id"]
    publishable_ids.add(page_id)
    last_edit = page.get("last_edited_time", "")
    title = prop(page, "Title") or "Untitled Research"
    english_title = prop(page, "English Title")
    category = prop(page, "Category") or "Research"
    keywords = prop(page, "Keywords")
    if not isinstance(keywords, list):
        keywords = []
    date = prop(page, "Date") or page.get("created_time", "")[:10]
    slug = prop(page, "SEO Slug")
    slug = slugify(slug or english_title or title, page_id.replace("-","")[:12])
    url = f"{SITE}/research/{date}/{slug}/"

    old = pages_state.get(page_id)
    rec = {
        "page_id": page_id,
        "title": title,
        "english_title": english_title,
        "category": category,
        "keywords": keywords,
        "date": date,
        "slug": slug,
        "url": url,
        "last_edited_time": last_edit,
        "status": status or "Ready",
    }

    target = RESEARCH / date / slug / "index.html"
    if not old or old.get("last_edited_time") != last_edit or not target.exists():
        md = page_markdown(page_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_article(rec, md), "utf-8")
        changed += 1

    pages_state[page_id] = rec

for pid in list(pages_state):
    if pid not in publishable_ids:
        pages_state.pop(pid, None)

STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
records = list(pages_state.values())
cards = rebuild_archive(records)
patch_home(cards)
rebuild_sitemap()

print(f"Notion pages visible: {len(rows)}")
print(f"Research archive entries: {len(records)}")
print(f"New/updated pages rendered: {changed}")
