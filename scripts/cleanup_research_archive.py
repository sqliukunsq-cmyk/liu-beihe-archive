from __future__ import annotations

import json
import os
import re
import shutil
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
STATE = RESEARCH / "_notion_state.json"
SITE = os.environ.get(
    "SITE_URL",
    "https://sqliukunsq-cmyk.github.io/liu-beihe-archive"
).rstrip("/")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_expected():
    if not STATE.exists():
        raise SystemExit("No research/_notion_state.json found; refusing cleanup.")
    data = json.loads(STATE.read_text("utf-8"))
    expected = set()
    for rec in data.get("pages", {}).values():
        date = str(rec.get("date", "")).strip()
        slug = str(rec.get("slug", "")).strip()
        if DATE_RE.fullmatch(date) and slug:
            expected.add((date, slug))
    return expected


def clean_orphans(expected):
    removed = []
    if not RESEARCH.exists():
        return removed

    for date_dir in RESEARCH.iterdir():
        if not date_dir.is_dir() or not DATE_RE.fullmatch(date_dir.name):
            continue

        for slug_dir in date_dir.iterdir():
            if not slug_dir.is_dir():
                continue
            key = (date_dir.name, slug_dir.name)
            if key in expected:
                continue

            # Safety: only delete generated article directories containing index.html.
            if not (slug_dir / "index.html").exists():
                print(f"SKIP non-generated-looking directory: {slug_dir}")
                continue

            shutil.rmtree(slug_dir)
            removed.append(slug_dir.relative_to(ROOT).as_posix())

        try:
            if not any(date_dir.iterdir()):
                date_dir.rmdir()
        except OSError:
            pass

    return removed


def rebuild_sitemap():
    urls = []
    for p in ROOT.rglob("index.html"):
        rel = p.relative_to(ROOT)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.as_posix() == "index.html":
            url = SITE + "/"
        else:
            url = SITE + "/" + rel.parent.as_posix().strip("/") + "/"
        urls.append(url)

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in sorted(set(urls)):
        xml += f"  <url><loc>{html.escape(url)}</loc></url>\n"
    xml += "</urlset>\n"
    (ROOT / "sitemap.xml").write_text(xml, "utf-8")


expected = load_expected()
removed = clean_orphans(expected)
rebuild_sitemap()

print(f"Current research URLs: {len(expected)}")
print(f"Stale research directories removed: {len(removed)}")
for path in removed:
    print(f"  removed: {path}")
print("Sitemap rebuilt after cleanup.")
