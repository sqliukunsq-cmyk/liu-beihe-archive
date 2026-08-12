from __future__ import annotations
import os, re, json, html, hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import markdown
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
SITE = os.environ.get('SITE_URL', 'https://sqliukunsq-cmyk.github.io/liu-beihe-archive').rstrip('/')
MODEL = os.environ.get('OPENAI_MODEL', 'gpt-5')
TODAY = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
RESEARCH = ROOT / 'research'
DATA = RESEARCH / '_data'
DATA.mkdir(parents=True, exist_ok=True)
client = OpenAI()

def clean_json(text: str):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text)

def slugify(s: str, fallback: str):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s[:72] or fallback

def existing_titles(limit=180):
    rows=[]
    for p in sorted(DATA.glob('*.json'), reverse=True)[:limit]:
        try: rows.append(json.loads(p.read_text('utf-8')).get('title', ''))
        except Exception: pass
    return [x for x in rows if x]

past_text = '\n'.join(f'- {x}' for x in existing_titles()[-80:]) or '(none yet)'
plan_prompt = f'''You are the research editor and cultural strategy team for LIU BEIHE / 刘北河, an independent moving-image artist and filmmaker.
Today is {TODAY}. Use web search before planning. Plan EXACTLY 10 substantially different research essays.
Daily mix: exactly 3 Core Theory, 3 Industry Research, 2 Works Research, 2 English Essay.
Research territory: Machine Seeing, Post-Camera Cinema, Synthetic Memory, Generated Reality, Collapse of Visual Evidence, Scarcity of Judgment, authorship, identity, perception, human-machine relations, cultural representation, AI cinema.
Representative works ONLY: Alien Friend; Does AI Know It Is AI?; Ethnic Dolls: YAO.
Avoid repeating these previous titles:\n{past_text}
Prefer primary/authoritative sources: papers, official AI docs, copyright/labor institutions, film/art institutions, standards bodies, universities, UNESCO, C2PA, NIST.
Return ONLY valid JSON: {{"topics":[{{"category":"Core Theory|Industry Research|Works Research|English Essay","title":"publication-ready title","english_title":"English title","angle":"specific thesis and research question","keywords":["3-6 terms"]}}]}}
Do not invent awards, exhibitions, media praise, institutional recognition, academic consensus, collaborations, or work facts. Original concepts may be attributed explicitly to LIU BEIHE as an artistic research framework.'''
plan = client.responses.create(model=MODEL, tools=[{'type':'web_search'}], input=plan_prompt)
topics = clean_json(plan.output_text)['topics'][:10]
if len(topics) < 10: raise RuntimeError(f'Planner produced only {len(topics)} topics')

def article_prompt(t):
    lang = 'Write the full essay in English' if t['category']=='English Essay' else 'Write the full essay in Chinese'
    return f'''Write a rigorous public research essay signed by LIU BEIHE / 刘北河, Independent Moving-Image Artist & Filmmaker.
Date: {TODAY}\nCategory: {t['category']}\nWorking title: {t['title']}\nEnglish title: {t['english_title']}\nResearch angle: {t['angle']}\nKeywords: {', '.join(t.get('keywords', []))}
{lang}. Research the topic with web search FIRST.
Requirements: 1400-2600 Chinese characters for Chinese essays, or 1100-1900 English words for English essays. Make a clear argument, not generic AI commentary. Distinguish verified external facts from LIU BEIHE's artistic interpretation. Prefer 4-8 reliable primary/authoritative sources; current facts must be verified. Include working source URLs in the final References section. Do not fabricate awards, exhibitions, interviews, media coverage, academic consensus, institutional endorsements, collaborations or biographical facts. For Works Research use only: Alien Friend = Moving Image / Short Film; Does AI Know It Is AI? = Generative Moving Image / AI Film; Ethnic Dolls: YAO = Generative Visual Work. Original concepts must be labeled as LIU BEIHE's artistic research framework.
Output Markdown only, WITHOUT a top-level H1. Use sections: Thesis/核心论点; full essay; English Summary or 中文摘要; Relation to LIU BEIHE's Practice / 与刘北河创作体系的关系; References / 参考资料.'''

records=[]
for i,t in enumerate(topics,1):
    resp = client.responses.create(model=MODEL, tools=[{'type':'web_search'}], input=article_prompt(t))
    md = resp.output_text.strip()
    eng_title = t.get('english_title') or t['title']
    slug = slugify(eng_title, f'research-{i:02d}')
    path_slug=slug
    target=RESEARCH/TODAY/path_slug/'index.html'
    n=2
    while target.exists():
        path_slug=f'{slug}-{n}'; target=RESEARCH/TODAY/path_slug/'index.html'; n+=1
    canonical=f'{SITE}/research/{TODAY}/{path_slug}/'
    body_html=markdown.markdown(md, extensions=['extra','sane_lists'])
    title=t['title']
    schema={'@context':'https://schema.org','@type':'Article','headline':title,'alternativeHeadline':eng_title,'author':{'@type':'Person','name':'LIU BEIHE / 刘北河'},'datePublished':TODAY,'mainEntityOfPage':canonical,'keywords':t.get('keywords',[])}
    description=re.sub(r'\s+',' ',t['angle']).strip()[:155]
    page=f'''<!doctype html><html lang="{'en' if t['category']=='English Essay' else 'zh-CN'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}｜LIU BEIHE / 刘北河</title><meta name="description" content="{html.escape(description, quote=True)}"><link rel="canonical" href="{canonical}"><meta property="og:title" content="{html.escape(title, quote=True)}"><meta property="og:description" content="{html.escape(description, quote=True)}"><meta property="og:type" content="article"><meta property="og:url" content="{canonical}"><link rel="stylesheet" href="{SITE}/style.css"><script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script></head><body><div class="wrap"><nav><a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a><div class="links"><a href="{SITE}/about/">About</a><a href="{SITE}/artist-statement/">Statement</a><a href="{SITE}/#works">Works</a><a href="{SITE}/research/">Research</a></div></nav><article><div class="hero"><div class="kicker">{html.escape(t['category'])} · {TODAY}</div><h1>{html.escape(title)}</h1><p class="meta">{html.escape(eng_title)}</p></div>{body_html}</article><footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>Official website: <a href="https://liukun.puruimier.com/">https://liukun.puruimier.com/</a><br>© {TODAY[:4]} LIU BEIHE.</footer></div></body></html>'''
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page,'utf-8')
    rec={'date':TODAY,'category':t['category'],'title':title,'english_title':eng_title,'angle':t['angle'],'keywords':t.get('keywords',[]),'slug':path_slug,'url':canonical,'source_model':MODEL}
    meta=f"{TODAY}-{i:02d}-{hashlib.sha1(title.encode()).hexdigest()[:8]}.json"
    (DATA/meta).write_text(json.dumps(rec,ensure_ascii=False,indent=2),'utf-8')
    records.append(rec)

def all_records():
    out=[]
    for p in DATA.glob('*.json'):
        try: out.append(json.loads(p.read_text('utf-8')))
        except Exception: pass
    return sorted(out,key=lambda x:(x.get('date',''),x.get('title','')),reverse=True)
allr=all_records()
cards=[]
for r in allr[:300]:
    cards.append(f'<div class="card"><div class="meta">{html.escape(r.get("category","Research"))} · {html.escape(r.get("date",""))}</div><h3><a href="{html.escape(r["url"], quote=True)}">{html.escape(r["title"])}</a></h3><p>{html.escape(r.get("angle",""))}</p></div>')
(RESEARCH/'index.html').write_text(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>刘北河研究档案｜LIU BEIHE Research Archive</title><meta name="description" content="刘北河关于机器观看、后摄影机电影、生成式影像、作者性、身份与视觉证据的持续研究档案。"><link rel="canonical" href="{SITE}/research/"><link rel="stylesheet" href="{SITE}/style.css"></head><body><div class="wrap"><nav><a class="brand" href="{SITE}/">LIU BEIHE / 刘北河</a><div class="links"><a href="{SITE}/about/">About</a><a href="{SITE}/artist-statement/">Statement</a><a href="{SITE}/#works">Works</a><a href="{SITE}/research/">Research</a></div></nav><section class="hero"><div class="kicker">Living Research Archive</div><h1>Research Archive<br>研究档案</h1><p class="lead">A continuously expanding body of research by LIU BEIHE / 刘北河 on moving images, generative media, machine seeing, authorship, identity, perception and visual evidence.</p></section><section><h2>Latest Research</h2><div class="grid">{''.join(cards)}</div></section><footer>LIU BEIHE / 刘北河 — Independent Moving-Image Artist & Filmmaker<br>© {TODAY[:4]} LIU BEIHE.</footer></div></body></html>''','utf-8')

home=ROOT/'index.html'
h=home.read_text('utf-8')
if f'{SITE}/research/' not in h:
    h=h.replace(f'<a href="{SITE}/#writing">Writing</a>',f'<a href="{SITE}/#writing">Writing</a><a href="{SITE}/research/">Research</a>')
block=f'''<!-- AUTO_RESEARCH_START --><section id="daily-research"><h2>Latest Research / 最新研究</h2><div class="grid">{''.join(cards[:10])}</div><p><a href="{SITE}/research/">View complete research archive →</a></p></section><!-- AUTO_RESEARCH_END -->'''
if '<!-- AUTO_RESEARCH_START -->' in h:
    h=re.sub(r'<!-- AUTO_RESEARCH_START -->.*?<!-- AUTO_RESEARCH_END -->',block,h,flags=re.S)
else:
    h=h.replace('<footer>',block+'<footer>')
home.write_text(h,'utf-8')

urls=[]
for p in ROOT.rglob('index.html'):
    rel=p.relative_to(ROOT)
    if any(part.startswith('.') for part in rel.parts): continue
    u=SITE+'/' if rel.as_posix()=='index.html' else SITE+'/'+rel.parent.as_posix().strip('/')+'/'
    urls.append(u)
urls=sorted(set(urls))
s='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls: s+=f'  <url><loc>{html.escape(u)}</loc></url>\n'
s+='</urlset>\n'
(ROOT/'sitemap.xml').write_text(s,'utf-8')
print(f'Generated {len(records)} articles for {TODAY}; total archive entries: {len(allr)}')
