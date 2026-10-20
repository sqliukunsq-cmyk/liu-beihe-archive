from __future__ import annotations
import os, json, re, html, hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests
import markdown

ROOT = Path(__file__).resolve().parents[1]
SITE = os.environ.get("SITE_URL", "https://sqliukunsq-cmyk.github.io/liu-beihe-archive").rstrip("/")
TOKEN = os.environ.get("NOTION_API_KEY", "")
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
    if not TOKEN:
        raise RuntimeError("NOTION_API_KEY is required for legacy Notion synchronization")
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

def public_ledger_articles():
    """Load explicitly approved mirrors from the writable Notion ledger.

    These are committed by the writing task after it verifies the Notion page.
    No private ledger traversal or dependence on the legacy API token is needed.
    """
    manifest = RESEARCH / "_public_ledger.json"
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text("utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("pages"), dict):
        raise ValueError("Unsupported public ledger manifest")
    articles, destinations = [], set()
    sources_root = (RESEARCH / "sources").resolve()
    for page_id, entry in data["pages"].items():
        if entry.get("status") not in ("Ready", "Published"):
            continue
        if not re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", page_id):
            raise ValueError("Public ledger requires a Notion page UUID")
        date, slug = entry["date"], entry["slug"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("Invalid public ledger date")
        datetime.strptime(date, "%Y-%m-%d")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("Invalid public ledger slug")
        if (date, slug) in destinations:
            raise ValueError("Duplicate public ledger destination")
        destinations.add((date, slug))
        source = (ROOT / entry["source_path"]).resolve()
        if not source.is_relative_to(sources_root) or source.suffix != ".md":
            raise ValueError("Public source must be Markdown under research/sources")
        md = source.read_text("utf-8")
        # Daily long-form entries specify a substantive-body minimum; headings,
        # front matter, punctuation, and references do not count toward it.
        main = re.split(r"^## (?:参考文献|References)", md, maxsplit=1, flags=re.M)[0]
        first_section = re.search(r"^## ", main, flags=re.M)
        if first_section:
            main = main[first_section.start():]
        main = "\n".join(line for line in main.splitlines() if not line.startswith("#"))
        count = len(re.findall(r"[\u3400-\u9fff]", main))
        if count < entry.get("min_body_cjk", 0):
            raise ValueError(f"Public ledger body too short: {page_id}: {count}")
        rec = {key: entry[key] for key in (
            "title", "english_title", "category", "keywords", "date", "slug",
            "last_edited_time", "status", "source_path", "notion_url"
        )}
        rec.update(page_id=page_id, url=f"{SITE}/research/{date}/{slug}/",
                   source_sha256=hashlib.sha256(md.encode("utf-8")).hexdigest(),
                   body_cjk_count=count, source="public-ledger")
        articles.append((rec, md))
    return articles

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
    records = sorted(
        records,
        key=lambda x: (x.get("date", ""), x.get("last_edited_time", "")),
        reverse=True
    )

    total = len(records)
    categories = sorted({r.get("category", "Research") or "Research" for r in records})
    dates = sorted({r.get("date", "") for r in records if r.get("date")}, reverse=True)
    category_counts = Counter((r.get("category", "Research") or "Research") for r in records)

    category_options = ''.join(
        f'<option value="{html.escape(c, quote=True)}">{html.escape(c)} ({category_counts[c]})</option>'
        for c in categories
    )
    date_options = ''.join(
        f'<option value="{html.escape(d, quote=True)}">{html.escape(d)}</option>'
        for d in dates
    )
    category_chips = ''.join(
        f'<span class="archive-chip">{html.escape(c)} <strong>{category_counts[c]}</strong></span>'
        for c in categories
    )

    cards = []
    for r in records[:500]:
        kws = " · ".join(r.get("keywords", [])[:4])
        meta = f'{r.get("category","Research")} · {r.get("date","")}'
        if kws:
            meta += f" · {kws}"

        search_blob = " ".join([
            r.get("title", ""),
            r.get("english_title", ""),
            r.get("category", ""),
            r.get("date", ""),
            " ".join(r.get("keywords", [])),
        ]).lower()

        cards.append(
            f'<div class="card research-card" '
            f'data-category="{html.escape(r.get("category","Research"), quote=True)}" '
            f'data-date="{html.escape(r.get("date",""), quote=True)}" '
            f'data-search="{html.escape(search_blob, quote=True)}">'
            f'<div class="meta">{html.escape(meta)}</div>'
            f'<h3><a href="{html.escape(r["url"], quote=True)}">{html.escape(r["title"])}</a></h3>'
            f'<p>{html.escape(r.get("english_title",""))}</p></div>'
        )

    archive_css = """
<style>
.archive-overview{display:grid;grid-template-columns:minmax(220px,.8fr) 1.2fr;gap:18px;margin:32px 0 10px}
.archive-total,.archive-breakdown{border:1px solid var(--line);padding:24px}
.archive-total-number{display:block;font-size:clamp(54px,8vw,92px);line-height:.9;letter-spacing:-.055em;margin-bottom:16px}
.archive-total-label{color:var(--muted);font-size:13px;letter-spacing:.06em;text-transform:uppercase}
.archive-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.archive-chip{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--line);padding:7px 10px;font-size:13px;color:#c7c7c2}
.archive-tools{display:grid;grid-template-columns:1.5fr 1fr 1fr auto;gap:10px;margin:28px 0 12px}
.archive-tools input,.archive-tools select,.archive-tools button{
width:100%;background:#111;color:var(--fg);border:1px solid var(--line);padding:12px 13px;
font:inherit;min-height:46px;border-radius:0
}
.archive-tools button{cursor:pointer;width:auto;padding-left:18px;padding-right:18px}
.archive-tools input:focus,.archive-tools select:focus,.archive-tools button:focus{outline:1px solid #666;outline-offset:1px}
.archive-resultline{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:0 0 16px;color:var(--muted);font-size:13px}
.research-card{transition:transform .18s ease,border-color .18s ease}
.research-card:hover{transform:translateY(-2px);border-color:#494949}
.research-card[hidden]{display:none!important}
.archive-empty{border:1px solid var(--line);padding:32px;color:var(--muted);display:none}
.archive-empty.show{display:block}
.archive-pagination{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;margin:28px 0 0}
.archive-pagination button{background:#111;color:var(--fg);border:1px solid var(--line);padding:9px 12px;min-width:42px;cursor:pointer}
.archive-pagination button[disabled]{opacity:.35;cursor:default}
.archive-pagination button.active{border-color:#888;background:#1b1b1b}
@media(max-width:820px){
  .archive-overview{grid-template-columns:1fr}
  .archive-tools{grid-template-columns:1fr 1fr}
  .archive-tools input{grid-column:1/-1}
  .archive-tools button{width:100%}
}
@media(max-width:520px){
  .archive-tools{grid-template-columns:1fr}
  .archive-tools input{grid-column:auto}
  .archive-resultline{align-items:flex-start;flex-direction:column}
}
</style>
"""

    archive_js = """
<script>
(() => {
  const allCards = Array.from(document.querySelectorAll('.research-card'));
  const searchInput = document.getElementById('research-search');
  const categorySelect = document.getElementById('research-category');
  const dateSelect = document.getElementById('research-date');
  const clearButton = document.getElementById('research-clear');
  const resultCount = document.getElementById('research-count');
  const pagination = document.getElementById('research-pagination');
  const emptyState = document.getElementById('research-empty');
  const pageSize = 12;
  let currentPage = 1;

  function filteredCards() {
    const query = searchInput.value.trim().toLowerCase();
    const category = categorySelect.value;
    const date = dateSelect.value;

    return allCards.filter(card => {
      const matchesQuery = !query || card.dataset.search.includes(query);
      const matchesCategory = !category || card.dataset.category === category;
      const matchesDate = !date || card.dataset.date === date;
      return matchesQuery && matchesCategory && matchesDate;
    });
  }

  function makeButton(label, targetPage, disabled = false, active = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.disabled = disabled;
    if (active) button.classList.add('active');
    if (!disabled) {
      button.addEventListener('click', () => {
        currentPage = targetPage;
        render();
        document.getElementById('research-list').scrollIntoView({behavior:'smooth', block:'start'});
      });
    }
    return button;
  }

  function renderPagination(pageCount) {
    pagination.innerHTML = '';
    if (pageCount <= 1) return;

    pagination.appendChild(makeButton('←', currentPage - 1, currentPage === 1));

    for (let page = 1; page <= pageCount; page++) {
      pagination.appendChild(makeButton(String(page), page, false, page === currentPage));
    }

    pagination.appendChild(makeButton('→', currentPage + 1, currentPage === pageCount));
  }

  function render() {
    const filtered = filteredCards();
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (currentPage > pageCount) currentPage = pageCount;

    allCards.forEach(card => card.hidden = true);

    const start = (currentPage - 1) * pageSize;
    filtered.slice(start, start + pageSize).forEach(card => card.hidden = false);

    resultCount.textContent = `当前筛选 ${filtered.length} / 共 ${allCards.length} 篇`;
    emptyState.classList.toggle('show', filtered.length === 0);
    renderPagination(pageCount);
  }

  [searchInput, categorySelect, dateSelect].forEach(el => {
    el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => {
      currentPage = 1;
      render();
    });
  });

  clearButton.addEventListener('click', () => {
    searchInput.value = '';
    categorySelect.value = '';
    dateSelect.value = '';
    currentPage = 1;
    render();
  });

  render();
})();
</script>
"""

    archive = f"""<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>刘北河研究档案 | LIU BEIHE Research Archive</title>
<meta name="description" content="刘北河关于机器观看、后摄影机电影、生成式影像、作者性、身份、感知与视觉证据的持续研究档案。">
<link rel="canonical" href="{SITE}/research/"><meta property="og:type" content="website">
<link rel="stylesheet" href="{SITE}/style.css">
{archive_css}
</head><body><div class="wrap"><nav>
<a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a>
<div class="links"><a href="{SITE}/about/">About</a>
<a href="{SITE}/artist-statement/">Statement</a><a href="{SITE}/#works">Works</a>
<a href="{SITE}/research/">Research</a></div></nav>

<section class="hero"><div class="kicker">Living Research Archive</div>
<h1>Research Archive<br>研究档案</h1>
<p class="lead">刘北河关于电影、生成式影像、机器观看、作者性、身份、感知与视觉证据的持续研究档案。</p>
<p class="en">A continuously expanding research archive by LIU BEIHE. Ready / Published entries only; Drafts remain private.</p>
</section>

<section class="archive-overview" aria-label="Research archive summary">
  <div class="archive-total">
    <span class="archive-total-number">{total}</span>
    <div class="archive-total-label">Research Entries / 共 {total} 篇研究文章</div>
  </div>
  <div class="archive-breakdown">
    <div class="kicker">Archive Overview / 档案概览</div>
    <p>当前公开档案共 <strong>{total}</strong> 篇。可按标题、关键词、类别与日期快速筛选。</p>
    <div class="archive-chips">{category_chips}</div>
  </div>
</section>

<section id="research-list">
<h2>All Research / 全部研究</h2>
<div class="archive-tools">
  <input id="research-search" type="search" placeholder="搜索标题、英文标题、关键词… / Search…" aria-label="Search research">
  <select id="research-category" aria-label="Filter by category">
    <option value="">All Categories / 全部类别</option>
    {category_options}
  </select>
  <select id="research-date" aria-label="Filter by date">
    <option value="">All Dates / 全部日期</option>
    {date_options}
  </select>
  <button id="research-clear" type="button">清除筛选</button>
</div>
<div class="archive-resultline">
  <span id="research-count">当前筛选 {total} / 共 {total} 篇</span>
  <span>12 entries per page / 每页 12 篇</span>
</div>
<div id="research-empty" class="archive-empty">没有找到符合当前条件的研究文章。</div>
<div class="grid">{''.join(cards)}</div>
<div id="research-pagination" class="archive-pagination" aria-label="Research pagination"></div>
</section>

<footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>
© {datetime.now().year} LIU BEIHE.</footer></div>
{archive_js}
</body></html>"""

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

def patch_readme(records):
    readme = ROOT / "README.md"
    if not readme.exists():
        return

    records = sorted(
        records,
        key=lambda x: (x.get("date", ""), x.get("last_edited_time", "")),
        reverse=True
    )
    total = len(records)
    category_counts = Counter((r.get("category", "Research") or "Research") for r in records)
    latest_date = records[0].get("date", "") if records else ""

    category_lines = "\n".join(
        f"- {category}: {category_counts[category]}"
        for category in sorted(category_counts)
    )

    block = f"""<!-- AUTO_RESEARCH_STATS_START -->
## Research archive status / 研究档案状态

**{total} public research entries / 共 {total} 篇公开研究文章**

{category_lines}

- Latest archive date: {latest_date or "—"}
- Draft entries are excluded from GitHub publication.
- Research Archive: {SITE}/research/
<!-- AUTO_RESEARCH_STATS_END -->"""

    text = readme.read_text("utf-8")
    if "<!-- AUTO_RESEARCH_STATS_START -->" in text:
        text = re.sub(
            r"<!-- AUTO_RESEARCH_STATS_START -->.*?<!-- AUTO_RESEARCH_STATS_END -->",
            block,
            text,
            flags=re.S,
        )
    else:
        anchor = "Official website:"
        if anchor in text:
            text = text.replace(anchor, block + "\n\n" + anchor, 1)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"

    readme.write_text(text, "utf-8")

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

ledger_articles = public_ledger_articles()  # Validate before touching existing output.
ledger_only = os.environ.get("PUBLIC_LEDGER_ONLY") == "1"
if ledger_only and not STATE_PATH.exists():
    raise ValueError("Immediate ledger publication requires an existing legacy state")
state = load_state()
pages_state = state.setdefault("pages", {})
previous_pages = dict(pages_state)
rows = [] if ledger_only else query_all_pages()
changed = 0
publishable_ids = ({pid for pid, rec in pages_state.items()
                    if rec.get("source") != "public-ledger"}
                   if ledger_only else set())

for page in rows:
    status = prop(page, "Status")

    # IMPORTANT: Draft (and any other non-public state) stays out of GitHub.
    if status not in ("Ready", "Published"):
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
        "status": status,
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

# Merge the active ledger after legacy-source pruning so the next scheduled
# sync and orphan cleanup preserve approved new articles.
for rec, md in ledger_articles:
    page_id = rec["page_id"]
    if page_id in publishable_ids:
        raise ValueError("A page cannot be registered in both research sources")
    if any((item["date"], item["slug"]) == (rec["date"], rec["slug"])
           for item in pages_state.values()):
        raise ValueError("Public ledger destination collides with legacy research")
    old = previous_pages.get(page_id)
    target = RESEARCH / rec["date"] / rec["slug"] / "index.html"
    if old != rec or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_article(rec, md), "utf-8")
        changed += 1
    pages_state[page_id] = rec

STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
records = list(pages_state.values())
cards = rebuild_archive(records)
patch_home(cards)
patch_readme(records)
rebuild_sitemap()

print(f"Notion pages visible: {len(rows)}")
print(f"Approved active-ledger entries: {len(ledger_articles)}")
print(f"Research archive entries: {len(records)}")
print(f"New/updated pages rendered: {changed}")
