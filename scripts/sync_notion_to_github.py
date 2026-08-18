from __future__ import annotations
import os, json, re, html
from pathlib import Path
from datetime import datetime
from collections import Counter
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

CATEGORY_NOTES = {
    "Core Theory": "Texts on machine vision, authorship, perception, image philosophy and visual culture.",
    "Industry Research": "Observations on generative-image systems, industrial shifts, platforms and ecology.",
    "Works Research": "Research notes tied to specific works, series, production methods and visual cases.",
    "English Essay": "English-language essays and position papers on art, cinema and theory.",
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
        return [x.get("name", "") for x in p.get("multi_select", [])]
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
    return s[:80] or fallback


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
    return f'''<!doctype html><html lang="{lang}"><head>
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
<p class="meta">{html.escape(rec.get("english_title", ""))}</p></section>
{content}</article>
<footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>
Official website: <a href="https://liukun.puruimier.com/">https://liukun.puruimier.com/</a><br>
© {rec["date"][:4] if rec["date"] else datetime.now().year} LIU BEIHE. All rights reserved.</footer>
</div></body></html>'''


def build_entry(rec, i):
    idx = str(i + 1).zfill(2)
    search_blob = " ".join([
        rec.get("title", ""),
        rec.get("english_title", ""),
        rec.get("category", ""),
        rec.get("date", ""),
        " ".join(rec.get("keywords", [])),
    ]).lower()
    keywords = rec.get("keywords", [])[:6]
    keyword_html = " ".join(f'<span>{html.escape(k)}</span>' for k in keywords)
    summary = rec.get("english_title") or ""
    return f'''
<article class="archive-entry" data-category="{html.escape(rec.get("category", "Research"), quote=True)}" data-date="{html.escape(rec.get("date", ""), quote=True)}" data-search="{html.escape(search_blob, quote=True)}">
  <div class="entry-index">{idx}</div>
  <div class="entry-main">
    <div class="entry-kicker">{html.escape(rec.get("category", "Research"))} <span>·</span> {html.escape(rec.get("date", ""))}</div>
    <h3><a href="{html.escape(rec["url"], quote=True)}">{html.escape(rec["title"])}</a></h3>
    <p class="entry-en">{html.escape(summary)}</p>
  </div>
  <div class="entry-side">
    <div class="entry-tags">{keyword_html}</div>
    <a class="entry-link" href="{html.escape(rec["url"], quote=True)}">View Entry →</a>
  </div>
</article>'''


def rebuild_archive(records):
    records = sorted(records, key=lambda x: (x.get("date", ""), x.get("last_edited_time", "")), reverse=True)
    total = len(records)
    categories = sorted({(r.get("category") or "Research") for r in records})
    category_counts = Counter((r.get("category") or "Research") for r in records)
    dates = sorted({r.get("date", "") for r in records if r.get("date")}, reverse=True)
    latest_date = records[0].get("date", "") if records else ""

    category_summary = "".join(
        f'''<div class="summary-col"><div class="summary-label">{html.escape(cat)}</div><div class="summary-value">{category_counts[cat]}</div><p>{html.escape(CATEGORY_NOTES.get(cat, "Research archive section."))}</p></div>'''
        for cat in categories
    )

    category_options = "".join(
        f'<option value="{html.escape(cat, quote=True)}">{html.escape(cat)} ({category_counts[cat]})</option>'
        for cat in categories
    )
    date_options = "".join(
        f'<option value="{html.escape(d, quote=True)}">{html.escape(d)}</option>'
        for d in dates
    )
    entries = "".join(build_entry(rec, i) for i, rec in enumerate(records[:500]))

    archive_css = '''
<style>
:root{
  --paper:#f4f0e8;
  --ink:#111111;
  --muted:#6b675f;
  --line:#d8d1c6;
  --line-strong:#c7bfb3;
}
html,body{background:var(--paper);color:var(--ink)}
body{margin:0;font-family:Georgia,"Times New Roman","Noto Serif SC","Songti SC",serif;line-height:1.5}
a{text-decoration:none;color:inherit}
.wrap{max-width:1460px;margin:0 auto;padding:0 42px 70px}
nav{display:flex;justify-content:space-between;align-items:center;padding:26px 0 20px;border-bottom:1px solid var(--line-strong);font-family:Arial,"Helvetica Neue",sans-serif;letter-spacing:.02em}
nav .brand{font-size:16px;font-weight:600;letter-spacing:.07em;text-transform:uppercase}
nav .links{display:flex;gap:28px;align-items:center;font-size:14px}
nav .links a:last-child{padding-bottom:6px;border-bottom:2px solid var(--ink)}
.hero-editorial{display:grid;grid-template-columns:1.35fr .65fr;gap:42px;padding:46px 0 28px;border-bottom:1px solid var(--line)}
.hero-left .kicker,.archive-tools .tool-label,.list-meta,.archive-footnote,.entry-kicker,.summary-label,.mini-label{font-family:Arial,"Helvetica Neue",sans-serif;text-transform:uppercase;letter-spacing:.08em}
.hero-left .kicker{font-size:12px;color:var(--muted);margin-bottom:16px}
.hero-left h1{font-size:clamp(68px,8vw,118px);line-height:.9;margin:0 0 16px;font-weight:400;letter-spacing:-.04em}
.hero-left .zh{font-size:clamp(32px,4vw,58px);line-height:1.02;margin:0 0 22px}
.hero-copy{display:grid;grid-template-columns:1fr 1fr;gap:28px;max-width:920px}
.hero-copy p{margin:0;font-size:18px;color:#26231f}
.hero-copy p.en{font-size:17px;color:var(--muted)}
.hero-right{display:flex;flex-direction:column;justify-content:space-between;border-left:1px solid var(--line);padding-left:34px}
.hero-stats{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.hero-number{font-size:86px;line-height:.9;font-weight:400}
.mini-label{font-size:12px;color:var(--muted);margin-bottom:10px}
.mini-copy{font-size:17px}
.summary-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border-bottom:1px solid var(--line);padding:22px 0}
.summary-col{padding:0 18px 0 0;border-right:1px solid var(--line)}
.summary-col:last-child{border-right:none;padding-right:0}
.summary-value{font-size:54px;line-height:.95;margin:10px 0 10px;font-weight:400}
.summary-col p{font-size:15px;color:var(--muted);margin:0;max-width:260px}
.archive-tools{display:grid;grid-template-columns:1.4fr .9fr .9fr auto;gap:0;border-bottom:1px solid var(--line);align-items:center}
.archive-tools > *{min-height:72px;display:flex;align-items:center;padding:0 18px;border-right:1px solid var(--line)}
.archive-tools > *:last-child{border-right:none;justify-content:flex-end}
.archive-tools input,.archive-tools select,.archive-tools button{width:100%;border:none;background:transparent;color:var(--ink);font:inherit;outline:none}
.archive-tools input,.archive-tools select{font-family:Arial,"Helvetica Neue",sans-serif;font-size:15px}
.archive-tools button{font-family:Arial,"Helvetica Neue",sans-serif;font-size:13px;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.archive-resultline{display:flex;justify-content:space-between;gap:16px;padding:16px 0 10px;font-family:Arial,"Helvetica Neue",sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.archive-empty{display:none;padding:26px 0;border-top:1px solid var(--line);font-family:Arial,"Helvetica Neue",sans-serif;color:var(--muted)}
.archive-empty.show{display:block}
.archive-list{border-top:1px solid var(--line)}
.archive-entry{display:grid;grid-template-columns:84px 1.8fr 1fr;gap:28px;padding:26px 0;border-bottom:1px solid var(--line);align-items:start}
.entry-index{font-size:54px;line-height:1;font-weight:400;color:#1c1a17}
.entry-kicker{font-size:11px;color:var(--muted);margin-bottom:10px}
.entry-kicker span{margin:0 8px}
.entry-main h3{margin:0 0 8px;font-size:40px;line-height:1.06;font-weight:400;letter-spacing:-.02em;max-width:920px}
.entry-en{margin:0;color:var(--muted);font-size:22px;line-height:1.18}
.entry-side{display:flex;flex-direction:column;justify-content:space-between;gap:24px;min-height:100%}
.entry-tags{display:flex;flex-wrap:wrap;gap:8px}
.entry-tags span{display:inline-block;font-family:Arial,"Helvetica Neue",sans-serif;font-size:12px;letter-spacing:.04em;padding:0;color:var(--muted)}
.entry-link{font-family:Arial,"Helvetica Neue",sans-serif;font-size:13px;letter-spacing:.08em;text-transform:uppercase;align-self:flex-end}
.archive-pagination{display:flex;align-items:center;justify-content:center;gap:8px;padding:26px 0 10px}
.archive-pagination button{background:transparent;border:none;border-bottom:1px solid transparent;padding:8px 10px;cursor:pointer;font-family:Arial,"Helvetica Neue",sans-serif;font-size:13px;color:var(--ink)}
.archive-pagination button.active{border-color:var(--ink)}
.archive-pagination button[disabled]{opacity:.35;cursor:default}
.archive-foot{display:flex;justify-content:space-between;gap:18px;padding-top:16px;border-top:1px solid var(--line);font-family:Arial,"Helvetica Neue",sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
#research-category-tabs{display:flex;gap:26px;border-bottom:1px solid var(--line);padding:16px 0 0;margin-bottom:0;font-family:Arial,"Helvetica Neue",sans-serif;font-size:14px;overflow:auto}
#research-category-tabs button{background:transparent;border:none;padding:0 0 14px;cursor:pointer;color:var(--muted);white-space:nowrap}
#research-category-tabs button.active{color:var(--ink);border-bottom:2px solid var(--ink)}
@media(max-width:1180px){
  .hero-editorial{grid-template-columns:1fr}
  .hero-right{border-left:none;border-top:1px solid var(--line);padding-left:0;padding-top:24px}
  .summary-strip{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:22px}
  .summary-col:nth-child(2){border-right:none}
  .archive-entry{grid-template-columns:60px 1.5fr .9fr}
  .entry-main h3{font-size:32px}
  .entry-en{font-size:18px}
}
@media(max-width:860px){
  .wrap{padding:0 20px 50px}
  nav{flex-direction:column;align-items:flex-start;gap:12px}
  nav .links{gap:18px;flex-wrap:wrap}
  .hero-left h1{font-size:52px}
  .hero-left .zh{font-size:28px}
  .hero-copy{grid-template-columns:1fr}
  .hero-stats{grid-template-columns:1fr 1fr}
  .summary-strip{grid-template-columns:1fr}
  .summary-col{border-right:none;padding:0 0 18px;border-bottom:1px solid var(--line)}
  .summary-col:last-child{border-bottom:none;padding-bottom:0}
  .archive-tools{grid-template-columns:1fr}
  .archive-tools > *{border-right:none;border-bottom:1px solid var(--line)}
  .archive-tools > *:last-child{border-bottom:none;justify-content:flex-start}
  .archive-entry{grid-template-columns:1fr;gap:14px}
  .entry-index{font-size:34px}
  .entry-main h3{font-size:30px}
  .entry-link{align-self:flex-start}
}
</style>'''

    archive_js = '''
<script>
(() => {
  const entries = Array.from(document.querySelectorAll('.archive-entry'));
  const searchInput = document.getElementById('research-search');
  const categorySelect = document.getElementById('research-category');
  const dateSelect = document.getElementById('research-date');
  const clearButton = document.getElementById('research-clear');
  const resultCount = document.getElementById('research-count');
  const pagination = document.getElementById('research-pagination');
  const emptyState = document.getElementById('research-empty');
  const tabs = Array.from(document.querySelectorAll('#research-category-tabs button'));
  const pageSize = 10;
  let currentPage = 1;
  let tabCategory = '';

  function filteredEntries() {
    const query = searchInput.value.trim().toLowerCase();
    const category = categorySelect.value || tabCategory;
    const date = dateSelect.value;
    return entries.filter(entry => {
      const matchQuery = !query || entry.dataset.search.includes(query);
      const matchCategory = !category || entry.dataset.category === category;
      const matchDate = !date || entry.dataset.date === date;
      return matchQuery && matchCategory && matchDate;
    });
  }

  function button(label, page, disabled=false, active=false){
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.disabled = disabled;
    if(active) b.classList.add('active');
    if(!disabled){
      b.addEventListener('click', () => { currentPage = page; render(); window.scrollTo({top: document.getElementById('archive-anchor').offsetTop - 40, behavior:'smooth'}); });
    }
    return b;
  }

  function renderPagination(pageCount){
    pagination.innerHTML = '';
    if(pageCount <= 1) return;
    pagination.appendChild(button('←', currentPage - 1, currentPage === 1));
    for(let i=1; i<=pageCount; i++) pagination.appendChild(button(String(i), i, false, currentPage === i));
    pagination.appendChild(button('→', currentPage + 1, currentPage === pageCount));
  }

  function render(){
    const filtered = filteredEntries();
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    if(currentPage > pageCount) currentPage = pageCount;
    entries.forEach(e => e.hidden = true);
    const start = (currentPage - 1) * pageSize;
    filtered.slice(start, start + pageSize).forEach(e => e.hidden = false);
    resultCount.textContent = `Showing ${Math.min(filtered.length, start + 1)}–${Math.min(filtered.length, start + pageSize)} of ${filtered.length} / total ${entries.length}`;
    emptyState.classList.toggle('show', filtered.length === 0);
    renderPagination(pageCount);
  }

  searchInput.addEventListener('input', ()=>{ currentPage = 1; render(); });
  categorySelect.addEventListener('change', ()=>{ tabCategory = ''; tabs.forEach(t => t.classList.toggle('active', !t.dataset.value)); currentPage = 1; render(); });
  dateSelect.addEventListener('change', ()=>{ currentPage = 1; render(); });
  clearButton.addEventListener('click', ()=>{
    searchInput.value=''; categorySelect.value=''; dateSelect.value=''; tabCategory=''; currentPage=1;
    tabs.forEach(t => t.classList.toggle('active', !t.dataset.value));
    render();
  });
  tabs.forEach(tab => {
    tab.addEventListener('click', ()=>{
      tabCategory = tab.dataset.value || '';
      categorySelect.value = '';
      tabs.forEach(t => t.classList.toggle('active', t === tab));
      currentPage = 1;
      render();
    });
  });
  render();
})();
</script>'''

    tab_buttons = '<button type="button" class="active" data-value="">All / 全部</button>' + ''.join(
        f'<button type="button" data-value="{html.escape(cat, quote=True)}">{html.escape(cat)} ({category_counts[cat]})</button>'
        for cat in categories
    )

    archive = f'''<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>刘北河研究档案 | LIU BEIHE Research Archive</title>
<meta name="description" content="刘北河关于机器观看、后摄影机电影、生成式影像、作者性、身份、感知与视觉证据的持续研究档案。">
<link rel="canonical" href="{SITE}/research/"><meta property="og:type" content="website">
<link rel="stylesheet" href="{SITE}/style.css">{archive_css}
</head><body><div class="wrap"><nav>
<a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a>
<div class="links"><a href="{SITE}/about/">About</a><a href="{SITE}/artist-statement/">Statement</a><a href="{SITE}/#works">Works</a><a href="{SITE}/research/">Research</a></div></nav>
<section class="hero-editorial">
  <div class="hero-left">
    <div class="kicker">Living Research Archive</div>
    <h1>Research Archive</h1>
    <div class="zh">研究档案</div>
    <div class="hero-copy">
      <p>刘北河关于电影、生成式影像、机器观看、作者性、身份、感知与视觉证据的持续研究档案。</p>
      <p class="en">A continuing archive of essays, notes, and theoretical writing on cinema, generative image, machine seeing, authorship, identity, and the politics of visual culture.</p>
    </div>
  </div>
  <div class="hero-right">
    <div class="hero-stats">
      <div>
        <div class="mini-label">Public Entries</div>
        <div class="hero-number">{total}</div>
      </div>
      <div>
        <div class="mini-label">Latest Update</div>
        <div class="mini-copy">{html.escape(latest_date or '—')}</div>
      </div>
    </div>
    <div>
      <div class="mini-label">Archive Note</div>
      <div class="mini-copy">Ready / Published entries only. Drafts remain private.</div>
    </div>
  </div>
</section>
<section class="summary-strip">{category_summary}</section>
<div id="research-category-tabs">{tab_buttons}</div>
<div id="archive-anchor"></div>
<section class="archive-tools">
  <div><label class="tool-label" style="display:flex;align-items:center;gap:12px;width:100%;"><span>Search</span><input id="research-search" type="search" placeholder="搜索标题、英文标题、关键词… / Search title, keyword…"></label></div>
  <div><label class="tool-label" style="display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;"><span>Category</span><select id="research-category"><option value="">All</option>{category_options}</select></label></div>
  <div><label class="tool-label" style="display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;"><span>Date</span><select id="research-date"><option value="">All</option>{date_options}</select></label></div>
  <div><button id="research-clear" type="button">Clear Filters</button></div>
</section>
<div class="archive-resultline"><span id="research-count">Showing 1–10</span><span>Editorial index / 持续研究索引</span></div>
<div id="research-empty" class="archive-empty">没有找到符合当前条件的研究文章。</div>
<section class="archive-list">{entries}</section>
<div id="research-pagination" class="archive-pagination"></div>
<footer class="archive-foot"><span>© {datetime.now().year} LIU BEIHE. All rights reserved.</span><span>Built as a living archive</span></footer>
</div>{archive_js}</body></html>'''

    (RESEARCH / "index.html").write_text(archive, "utf-8")

    home_cards = []
    for r in records[:8]:
        home_cards.append(
            f'<div class="card"><div class="meta">{html.escape(r.get("category", "Research"))} · {html.escape(r.get("date", ""))}</div>'
            f'<h3><a href="{html.escape(r["url"], quote=True)}">{html.escape(r["title"])}</a></h3>'
            f'<p>{html.escape(r.get("english_title", ""))}</p></div>'
        )
    return home_cards


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
    block = f'''<!-- AUTO_RESEARCH_START --><section id="daily-research">
<h2>Latest Research / 最新研究</h2><div class="grid">{"".join(cards)}</div>
<p><a href="{SITE}/research/">View complete research archive →</a></p></section>
<!-- AUTO_RESEARCH_END -->'''
    if "<!-- AUTO_RESEARCH_START -->" in h:
        h = re.sub(r"<!-- AUTO_RESEARCH_START -->.*?<!-- AUTO_RESEARCH_END -->", block, h, flags=re.S)
    else:
        h = h.replace("<footer>", block + "<footer>", 1)
    home.write_text(h, "utf-8")


def patch_readme(records):
    readme = ROOT / "README.md"
    if not readme.exists():
        return
    total = len(records)
    category_counts = Counter((r.get("category") or "Research") for r in records)
    latest_date = records[0].get("date", "") if records else ""
    lines = "\n".join(f'- {cat}: {category_counts[cat]}' for cat in sorted(category_counts))
    block = f'''<!-- AUTO_RESEARCH_STATS_START -->
## Research archive status / 研究档案状态

**{total} public research entries / 共 {total} 篇公开研究文章**

{lines}

- Latest archive date: {latest_date or '—'}
- Draft entries are excluded from GitHub publication.
- Research Archive: {SITE}/research/
<!-- AUTO_RESEARCH_STATS_END -->'''
    txt = readme.read_text("utf-8")
    if "<!-- AUTO_RESEARCH_STATS_START -->" in txt:
        txt = re.sub(r"<!-- AUTO_RESEARCH_STATS_START -->.*?<!-- AUTO_RESEARCH_STATS_END -->", block, txt, flags=re.S)
    else:
        anchor = "Official website:"
        if anchor in txt:
            txt = txt.replace(anchor, block + "\n\n" + anchor, 1)
        else:
            txt = txt.rstrip() + "\n\n" + block + "\n"
    readme.write_text(txt, "utf-8")


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
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += f'  <url><loc>{html.escape(u)}</loc></url>\n'
    xml += '</urlset>\n'
    (ROOT / 'sitemap.xml').write_text(xml, 'utf-8')


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
    slug = slugify(slug or english_title or title, page_id.replace("-", "")[:12])
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
home_cards = rebuild_archive(records)
patch_home(home_cards)
patch_readme(records)
rebuild_sitemap()

print(f"Notion pages visible: {len(rows)}")
print(f"Research archive entries: {len(records)}")
print(f"New/updated pages rendered: {changed}")
