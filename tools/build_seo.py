# -*- coding: utf-8 -*-
"""
build_seo.py：drpeipei.com 全站 SEO / AI 搜尋（GEO）建置器。2026-09-16 建。
用法：在母版資料夾執行  python tools/build_seo.py
做五件事（每次執行都重做，冪等）：
 1. 讀 npo_data.js、news_data.js、posts_data.js，為每篇文章產生靜態頁 p/<slug>.html（Article JSON-LD、麵包屑、上一篇下一篇）
    ＋ p/index.html 全文索引 ＋ permalinks.js（列表頁 overlay 顯示固定網址用）。
 2. 十個站頁 <head> 注入：meta author / robots、Organization＋BreadcrumbList＋頁型 JSON-LD（用 <!-- seo:auto --> 標記，重跑先移除再注入）。
 3. sitemap.xml 全部重產（站頁＋文章頁，lastmod＝文章日期或今天）。
 4. robots.txt（明示允許主要 AI 爬蟲）＋ llms.txt（給 AI 搜尋引擎的網站說明）。
 5. 站頁頁尾加「全部文章索引｜網站地圖」連結；articles.html、news.html overlay 加固定網址。
文章內容一字不動，只轉格式。禁破折號規則不套在老師原文。
"""
import io, os, re, json, html, datetime, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SITE = "https://drpeipei.com"
TODAY = datetime.date.today().isoformat()
BRAND = "佩佩老師的會計魔法教室"
AUTHOR = "劉沂佩"
FB = "https://www.facebook.com/p/%E4%BD%A9%E4%BD%A9%E8%80%81%E5%B8%AB%E7%9A%84%E6%9C%83%E8%A8%88%E9%AD%94%E6%B3%95%E6%95%99%E5%AE%A4-100063655793258/"
NAV = [("about.html","關於佩佩"),("articles.html","觀點文章"),("npo-finance.html","NPO 財務教室"),("news.html","永續新知"),
       ("accounting-learning-map.html","會計人的學習地圖"),("cert-library.html","證照圖書館"),("five-passbooks.html","五大存摺"),("books.html","著作")]

def rd(p): return io.open(p, encoding="utf-8").read()
def wr(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# ---------- 1. 讀資料 ----------
def js_string_at(s, i):
    """從 s[i]（引號或反引號）讀一個 JS 字串，回傳 (值, 結束索引)。"""
    q = s[i]; j = i + 1; out = []
    while j < len(s):
        c = s[j]
        if c == "\\" and q != "`":
            n = s[j+1]; out.append({"n":"\n","t":"\t","\"":"\"","'":"'","\\":"\\","/":"/"}.get(n, n)); j += 2; continue
        if c == q: return "".join(out), j + 1
        out.append(c); j += 1
    raise ValueError("unterminated string")

def parse_js_objects(src, keys):
    """粗略解析 const X = [ {k: v, ...}, ... ] 的物件陣列（值只有字串、數字）。"""
    items = []; i = src.find("[")
    while True:
        i = src.find("{", i)
        if i < 0: break
        obj = {}; j = i + 1
        while True:
            m = re.compile(r"\s*([A-Za-z_]+)\s*:\s*").match(src, j)
            if not m: break
            key = m.group(1); j = m.end()
            if src[j] in "\"'`":
                val, j = js_string_at(src, j)
            else:
                m2 = re.compile(r"[-\d.]+").match(src, j); val = m2.group(0); j = m2.end()
            obj[key] = val
            m3 = re.compile(r"\s*,?\s*").match(src, j); j = m3.end()
            if src[j] == "}": j += 1; break
        if obj.get("title"): items.append(obj)
        i = j
    return items

def load_articles():
    arts = []
    for o in parse_js_objects(rd("npo_data.js"), None):
        arts.append(dict(kind="npo", cat="NPO 財務", title=o["title"], date=o["date"], ts=int(o["timestamp"]), text=o["text"],
                         unit=o.get("unit",""), source="", sourceUrl="", section="NPO 財務教室", back="npo-finance.html"))
    for o in parse_js_objects(rd("news_data.js"), None):
        arts.append(dict(kind="news", cat="永續新知", title=o["title"], date=o["date"], ts=int(o["timestamp"]), text=o["text"],
                         unit="", source=o.get("source",""), sourceUrl=o.get("sourceUrl",""), section="永續新知", back="news.html"))
    t = rd("posts_data.js"); m = re.search(r'JSON\.parse\("(.*)"\)\s*;?\s*$', t, re.S)
    for o in json.loads(json.loads('"' + m.group(1) + '"')):
        arts.append(dict(kind="fb", cat=o.get("category","生活對話"), title=o["title"], date=o["date"], ts=int(o["timestamp"]), text=o["text"],
                         unit="", source="", sourceUrl="", section="觀點文章", back="articles.html"))
    # slug：kind-YYYYMMDD-n
    seen = {}
    for a in sorted(arts, key=lambda x: (x["ts"], x["title"])):
        base = f'{a["kind"]}-{a["date"].replace("-","")}'
        seen[base] = seen.get(base, 0) + 1
        a["slug"] = f'{base}-{seen[base]}'
        a["url"] = f'{SITE}/p/{a["slug"]}.html'
    return arts

# ---------- 2. 文章頁 ----------
CSS = """
:root{--bg:#F7F8F5;--ink:#26302A;--muted:#5C6B60;--accent:#2F6B3A;--soft:#E7F0E5;--line:#DCE4DC;--gold:#8A6D1B}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft JhengHei","Noto Sans TC","PingFang TC",sans-serif;line-height:1.9}
a{color:var(--accent)}header{background:#fff;border-bottom:1px solid var(--line)}.nw{max-width:1060px;margin:auto;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
.brand{font-weight:900;text-decoration:none;color:var(--ink);font-size:18px}.brand small{display:block;font-weight:400;font-size:12px;color:var(--muted)}
nav a{margin-left:14px;text-decoration:none;color:var(--ink);font-size:14px}nav a:hover{color:var(--accent)}
main{max-width:760px;margin:auto;padding:28px 20px 80px}.crumb{font-size:13px;color:var(--muted)}.crumb a{color:var(--muted);text-decoration:none}
.cat{display:inline-block;background:var(--soft);color:var(--accent);font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;margin-top:18px}
h1{font-size:clamp(24px,4vw,34px);line-height:1.3;margin:12px 0 8px}.meta{font-size:14px;color:var(--muted);margin-bottom:26px}
.body p{margin:0 0 1.1em;font-size:17px;white-space:pre-wrap;word-break:break-word}.src{margin-top:32px;padding-top:14px;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}
.pn{display:flex;justify-content:space-between;gap:16px;margin-top:40px;font-size:14px}.pn a{text-decoration:none;max-width:48%}
.box{margin-top:44px;padding:18px 20px;background:#fff;border:1px solid var(--line);border-radius:14px;font-size:15px}
footer{text-align:center;color:var(--muted);font-size:13px;padding:30px 20px;border-top:1px solid var(--line)}footer a{color:var(--muted)}
@media(max-width:640px){nav{display:flex;flex-wrap:wrap;gap:8px}nav a{margin:0}}
"""
def esc(s): return html.escape(s, quote=True)
def para_html(text):
    def linkify(t):
        t = esc(t)
        return re.sub(r'(https?://[^\s<]+)', r'<a href="\1" rel="nofollow noopener" target="_blank">\1</a>', t)
    parts = [p for p in re.split(r"\n\s*\n", text.strip())]
    return "\n".join(f"<p>{linkify(p)}</p>" for p in parts if p.strip())

def header_html(prefix):
    nav = "".join(f'<a href="{prefix}{h}">{t}</a>' for h, t in NAV)
    return (f'<header><div class="nw"><a class="brand" href="{prefix}index.html">Dr. Peipei｜{BRAND}<small>會計能夠救地球 Accounting Can Save the Earth</small></a>'
            f'<nav>{nav}</nav></div></header>')
FOOT = ('<footer>{b}｜<a href="mailto:lyipei@gmail.com">lyipei@gmail.com</a>｜<a href="{p}p/index.html">全部文章索引</a>｜<a href="{p}sitemap.xml">網站地圖</a>'
        '<br>會計能夠救地球 Accounting Can Save the Earth</footer>')

def article_ld(a, desc):
    d = {"@context":"https://schema.org","@type":"BlogPosting","headline":a["title"][:110],"description":desc,
         "datePublished":a["date"],"dateModified":a["date"],"inLanguage":"zh-Hant","articleSection":a["cat"],
         "wordCount":len(re.sub(r"\s","",a["text"])),
         "author":{"@type":"Person","name":AUTHOR,"alternateName":"佩佩老師","url":f"{SITE}/about.html"},
         "publisher":{"@type":"Organization","name":BRAND,"url":SITE+"/","logo":{"@type":"ImageObject","url":f"{SITE}/peipei-mascot.jpg"}},
         "mainEntityOfPage":{"@type":"WebPage","@id":a["url"]},"url":a["url"],"image":f"{SITE}/peipei-photo.jpg",
         "isAccessibleForFree":True}
    tags = re.findall(r"#([^\s#]+)", a["text"])
    if tags: d["keywords"] = "、".join(dict.fromkeys(tags))[:200]
    if a["sourceUrl"]: d["isBasedOn"] = a["sourceUrl"]; d["citation"] = a["source"]
    bc = {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"首頁","item":SITE+"/"},
        {"@type":"ListItem","position":2,"name":a["section"],"item":f'{SITE}/{a["back"]}'},
        {"@type":"ListItem","position":3,"name":a["title"][:60],"item":a["url"]}]}
    return json.dumps(d, ensure_ascii=False), json.dumps(bc, ensure_ascii=False)

def build_article_pages(arts):
    for f in glob.glob("p/*.html"): os.remove(f)
    by_kind = {}
    for a in sorted(arts, key=lambda x: (x["ts"], x["title"])): by_kind.setdefault(a["kind"], []).append(a)
    for kind, lst in by_kind.items():
        for i, a in enumerate(lst):
            desc = re.sub(r"\s+", " ", a["text"]).strip()[:150]
            ld, bc = article_ld(a, desc)
            prev = lst[i-1] if i > 0 else None; nxt = lst[i+1] if i+1 < len(lst) else None
            pn = '<div class="pn">' + (f'<a href="{prev["slug"]}.html">← 上一篇：{esc(prev["title"][:28])}</a>' if prev else "<span></span>") + \
                 (f'<a href="{nxt["slug"]}.html">下一篇：{esc(nxt["title"][:28])} →</a>' if nxt else "<span></span>") + "</div>"
            src = f'<div class="src">資料來源：{esc(a["source"])}' + (f'　<a href="{esc(a["sourceUrl"])}" rel="nofollow noopener" target="_blank">原文連結</a>' if a["sourceUrl"] else "") + "</div>" if a["source"] else ""
            unit = f'<div class="meta">{esc(a["unit"])}</div>' if a["unit"] else ""
            page = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(a["title"])}｜{a["section"]}｜{BRAND}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="{AUTHOR}（佩佩老師）"><meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<link rel="canonical" href="{a["url"]}">
<meta property="og:type" content="article"><meta property="og:locale" content="zh_TW"><meta property="og:site_name" content="{BRAND}">
<meta property="og:title" content="{esc(a["title"])}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{a["url"]}">
<meta property="og:image" content="{SITE}/peipei-photo.jpg"><meta property="article:published_time" content="{a["date"]}"><meta property="article:author" content="{AUTHOR}"><meta property="article:section" content="{esc(a["cat"])}">
<meta name="twitter:card" content="summary"><link rel="icon" type="image/jpeg" href="../peipei-mascot.jpg">
<script type="application/ld+json">{ld}</script>
<script type="application/ld+json">{bc}</script>
<style>{CSS}</style>
</head>
<body>
{header_html("../")}
<main>
<div class="crumb"><a href="../index.html">首頁</a> › <a href="../{a["back"]}">{a["section"]}</a> › {esc(a["cat"])}</div>
<span class="cat">{esc(a["cat"])}</span>
<h1>{esc(a["title"])}</h1>
<div class="meta">{AUTHOR}（佩佩老師）・{a["date"]}</div>{unit}
<article class="body">
{para_html(a["text"])}
</article>
{src}
{pn}
<div class="box"><b>關於作者</b>：{AUTHOR}（佩佩老師），靜宜大學會計學系教授，國立臺北大學會計學博士；專長永續會計、永續報告書（IFRS S1／S2、SASB、GRI）、內部控制、碳管理（ISO 14064-1、ISO 14067、CBAM）與非營利組織財務。<a href="../about.html">認識佩佩老師 →</a>　<a href="../{a["back"]}">回{a["section"]} →</a></div>
</main>
{FOOT.format(b=BRAND, p="../")}
</body></html>
"""
            wr(f'p/{a["slug"]}.html', page)
    # 全文索引
    groups = [("NPO 財務教室","npo"),("永續新知","news"),("觀點文章","fb")]
    body = ""
    for name, kind in groups:
        lst = sorted([a for a in arts if a["kind"] == kind], key=lambda x: -x["ts"])
        cats = {}
        for a in lst: cats.setdefault(a["cat"], []).append(a)
        body += f"<h2>{name}（{len(lst)} 篇）</h2>"
        for cat, items in cats.items():
            body += f"<h3>{esc(cat)}（{len(items)} 篇）</h3><ul>" + "".join(f'<li><a href="{a["slug"]}.html">{esc(a["title"])}</a> <small>{a["date"]}</small></li>' for a in items) + "</ul>"
    ld = json.dumps({"@context":"https://schema.org","@type":"CollectionPage","name":f"全部文章索引｜{BRAND}","url":f"{SITE}/p/index.html","inLanguage":"zh-Hant",
                     "isPartOf":{"@type":"WebSite","name":BRAND,"url":SITE+"/"},"numberOfItems":len(arts)}, ensure_ascii=False)
    wr("p/index.html", f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全部文章索引｜{BRAND}</title><meta name="description" content="佩佩老師（劉沂佩）全部文章的靜態索引：NPO 財務教室、永續新知、觀點文章（生活對話、會計知識、永續 ESG），共 {len(arts)} 篇，依日期排列。">
<meta name="author" content="{AUTHOR}（佩佩老師）"><meta name="robots" content="index,follow"><link rel="canonical" href="{SITE}/p/index.html">
<meta property="og:type" content="website"><meta property="og:title" content="全部文章索引｜{BRAND}"><meta property="og:url" content="{SITE}/p/index.html"><meta property="og:image" content="{SITE}/peipei-photo.jpg">
<link rel="icon" type="image/jpeg" href="../peipei-mascot.jpg"><script type="application/ld+json">{ld}</script><style>{CSS} main{{max-width:900px}} li{{margin:4px 0}} small{{color:var(--muted)}}</style></head>
<body>{header_html("../")}<main><div class="crumb"><a href="../index.html">首頁</a> › 全部文章索引</div><h1>全部文章索引</h1><p class="meta">共 {len(arts)} 篇，每篇都有獨立網址可以分享。更新日期 {TODAY}。</p>{body}</main>{FOOT.format(b=BRAND, p="../")}</body></html>
""")
    # permalinks.js
    mp = {f'{a["ts"]}|{a["title"]}': f'p/{a["slug"]}.html' for a in arts}
    wr("permalinks.js", "// 由 tools/build_seo.py 產生：文章固定網址對照表（key＝timestamp|title）\nconst PERMALINKS = " + json.dumps(mp, ensure_ascii=False) + ";\n")

# ---------- 3. 站頁注入 ----------
PAGE_LD = {
 "index.html": ("WebPage", "佩佩老師的會計魔法教室：永續會計、ESG 課程、企業輔導"),
 "about.html": (None, None),  # 已有 ProfilePage，另加 FAQ
 "articles.html": ("CollectionPage", "觀點文章：生活對話、會計知識、永續 ESG"),
 "npo-finance.html": ("CollectionPage", "NPO 財務教室：非營利組織財務六單元"),
 "news.html": ("CollectionPage", "永續新知：每週一篇永續與 ESG 法規實務新知"),
 "accounting-learning-map.html": ("WebPage", "會計人的學習地圖：學習風格小測驗、四年路線圖、證照圖書館"),
 "cert-library.html": ("WebPage", "證照圖書館：會計與永續相關證照的考試時間、科目與教材"),
 "learning-style-quiz.html": ("WebApplication", "學習風格小測驗：十六題測視覺、聽覺、動手、讀寫型"),
 "five-passbooks.html": ("WebApplication", "我的大學五本存摺：開帳、存款、人文素養佐證、組織活動、期末結帳"),
 "books.html": ("WebPage", "著作：永續方程式 認識 ESG"),
 "s2-workshop.html": ("WebPage", "IFRS S2 工作坊"),
}
ORG = {"@type":"Organization","@id":SITE+"/#org","name":BRAND,"alternateName":"Dr. Peipei","url":SITE+"/","logo":f"{SITE}/peipei-mascot.jpg",
       "image":f"{SITE}/peipei-photo.jpg","email":"lyipei@gmail.com","founder":{"@type":"Person","name":AUTHOR,"alternateName":"佩佩老師","url":f"{SITE}/about.html"},
       "sameAs":[FB],"areaServed":"TW","knowsAbout":["永續會計","ESG","IFRS S1","IFRS S2","SASB","GRI","永續報告書","內部控制","碳盤查","ISO 14064-1","ISO 14067","CBAM","非營利組織財務","會計教育"]}
FAQ = [
 ("佩佩老師是誰？","劉沂佩，靜宜大學會計學系教授，國立臺北大學會計學博士；現任全球永續雙軌教育學會理事長、台灣舞弊防治與鑑識協會理事。"),
 ("佩佩老師提供哪些課程與輔導？","企業與公部門的 ESG 課程與演講、永續報告書（IFRS S1／S2、SASB、GRI）評估編撰與查核輔導、內部控制制度建置與上市櫃輔導、財務預測與 TCFD 氣候風險評估、碳盤查與碳足跡（ISO 14064-1、ISO 14067、CBAM）、非營利組織財務培力。"),
 ("佩佩老師有哪些國際證照？","SGS ISO 14067 服務與產品碳足跡查證主任查證員、SGS ISO 14064-1:2018 組織溫室氣體建置與查證員、BSI CQI 與 IRCA ISO 50001:2018 能源管理系統主導稽核員、ISO 14001:2015 環境管理系統內部稽核員、BSI 氣候相關財務揭露建置與實務證書。"),
 ("如何邀請佩佩老師演講、上課或輔導？","來信 lyipei@gmail.com，或到 Facebook 粉絲頁「佩佩老師的會計魔法教室」私訊，內容可依對象與規模調整深度。"),
]
def inject_pages():
    for f, (ptype, name) in PAGE_LD.items():
        s = rd(f)
        s = re.sub(r"\n?<!-- seo:auto -->.*?<!-- /seo:auto -->\n?", "\n", s, flags=re.S)
        url = SITE + ("/" if f == "index.html" else "/" + f)
        title = re.search(r"<title>(.*?)</title>", s, re.S).group(1).strip()
        graph = [ORG]
        crumbs = [{"@type":"ListItem","position":1,"name":"首頁","item":SITE+"/"}]
        if f != "index.html": crumbs.append({"@type":"ListItem","position":2,"name":title.split("｜")[0],"item":url})
        graph.append({"@type":"BreadcrumbList","itemListElement":crumbs})
        if ptype:
            g = {"@type":ptype,"name":title,"description":name,"url":url,"inLanguage":"zh-Hant","isPartOf":{"@type":"WebSite","name":BRAND,"url":SITE+"/"},"author":{"@type":"Person","name":AUTHOR,"url":f"{SITE}/about.html"}}
            if ptype == "WebApplication": g.update({"applicationCategory":"EducationalApplication","operatingSystem":"Web","offers":{"@type":"Offer","price":"0","priceCurrency":"TWD"}})
            graph.append(g)
        if f == "about.html":
            graph.append({"@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q, a in FAQ]})
        ld = json.dumps({"@context":"https://schema.org","@graph":graph}, ensure_ascii=False)
        extra = ""
        if 'name="author"' not in s: extra += f'<meta name="author" content="{AUTHOR}（佩佩老師）">\n'
        if 'name="robots"' not in s: extra += '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">\n'
        if 'rel="alternate" hreflang' not in s: extra += f'<link rel="alternate" hreflang="zh-Hant" href="{url}">\n'
        block = f'<!-- seo:auto -->\n{extra}<script type="application/ld+json">{ld}</script>\n<!-- /seo:auto -->\n'
        s = s.replace("</head>", block + "</head>", 1)
        # 頁尾連結
        if "p/index.html" not in s and "<footer>" in s:
            s = s.replace("</footer>", '  <div class="footer-sub"><a href="p/index.html" style="text-decoration:underline">全部文章索引</a>　<a href="sitemap.xml" style="text-decoration:underline">網站地圖</a></div>\n</footer>', 1)
        # about 可見 FAQ
        if f == "about.html" and "seo-faq" not in s:
            faq_html = '<section id="seo-faq" style="max-width:860px;margin:40px auto;padding:0 24px"><h2 style="font-size:1.4rem;margin-bottom:12px">常見問題</h2>' + \
                "".join(f'<details style="margin:8px 0;padding:10px 14px;background:#fff;border:1px solid #DCE4DC;border-radius:12px"><summary style="font-weight:700;cursor:pointer">{esc(q)}</summary><p style="margin:8px 0 0;line-height:1.9">{esc(a)}</p></details>' for q, a in FAQ) + "</section>\n"
            s = s.replace("<footer>", faq_html + "<footer>", 1)
        # overlay 固定網址
        if f in ("articles.html", "news.html"):
            if "permalinks.js" not in s:
                s = s.replace("</head>", '<script src="permalinks.js"></script>\n</head>', 1)
            if 'id="overlayPermalink"' not in s:
                s = s.replace('<div class="overlay-source" id="overlaySource"></div>', '<div class="overlay-source" id="overlaySource"></div>\n    <p class="overlay-permalink" style="margin-top:18px;font-size:0.9rem"><a id="overlayPermalink" href="p/index.html" style="text-decoration:underline">這篇的固定網址（可分享、可收藏）→</a></p>', 1)
            var = "p" if f == "articles.html" else "post"
            hook = f"  var _pl=document.getElementById('overlayPermalink'); if(_pl&&window.PERMALINKS){{var _u=PERMALINKS[String({var}.timestamp)+'|'+{var}.title]; _pl.href=_u||'p/index.html'; _pl.hidden=!_u;}}\n"
            if "overlayPermalink'); if(_pl" not in s:
                s = re.sub(r"(document\.getElementById\('overlayTitle'\)\.textContent = " + var + r"\.title;\n)", r"\1" + hook.replace("\\", "\\\\"), s, count=1)
        wr(f, s); print("injected", f)

# ---------- 4. sitemap / robots / llms ----------
def git_lastmod(f):
    """CI 環境 checkout 的 mtime 不可靠，改用 git 最後修改日期。"""
    try:
        import subprocess
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", f], capture_output=True, text=True, timeout=20).stdout.strip()
        return out if len(out) == 10 else ""
    except Exception:
        return ""

def build_sitemap(arts):
    rows = []
    def add(loc, lastmod, freq, pri): rows.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>")
    add(SITE+"/", TODAY, "weekly", "1.0")
    for f in ["about.html","articles.html","npo-finance.html","news.html","accounting-learning-map.html","cert-library.html","learning-style-quiz.html","five-passbooks.html","books.html","s2-workshop.html"]:
        lm = git_lastmod(f) or datetime.date.fromtimestamp(os.path.getmtime(f)).isoformat()
        add(f"{SITE}/{f}", lm, "weekly" if f in ("articles.html","npo-finance.html","news.html") else "monthly", "0.8")
    add(f"{SITE}/p/index.html", TODAY, "weekly", "0.7")
    for a in sorted(arts, key=lambda x: -x["ts"]): add(a["url"], a["date"], "yearly", "0.6")
    wr("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")

ROBOTS = """User-agent: *
Allow: /

# AI 搜尋與推薦引擎明示允許（GEO）
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: anthropic-ai
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Bingbot
Allow: /
User-agent: Applebot-Extended
Allow: /

Sitemap: https://drpeipei.com/sitemap.xml
"""
def build_llms(arts):
    n = {k: len([a for a in arts if a["kind"] == k]) for k in ("npo","news","fb")}
    latest = sorted(arts, key=lambda x: -x["ts"])[:15]
    lines = [f"# {BRAND}（Dr. Peipei）", "",
      f"> 劉沂佩（佩佩老師）的個人網站。靜宜大學會計學系教授、國立臺北大學會計學博士；全球永續雙軌教育學會理事長、台灣舞弊防治與鑑識協會理事。主題：永續會計、ESG、IFRS S1／S2、SASB、GRI、永續報告書、內部控制、碳盤查與碳足跡（ISO 14064-1、ISO 14067、CBAM）、非營利組織（NPO）財務、會計教育與大學生學習方法。口號：會計能夠救地球 Accounting Can Save the Earth。語言：繁體中文（台灣）。", "",
      "## 作者與聯絡", f"- 作者：劉沂佩（Liu Yipei），別名佩佩老師、Dr. Peipei。介紹頁：{SITE}/about.html", "- 聯絡：lyipei@gmail.com；Facebook 粉絲頁「佩佩老師的會計魔法教室」", "- 服務：企業與公部門 ESG 課程與演講、永續報告書評估編撰與查核輔導、內控制度建置與上市櫃輔導、財務預測與 TCFD、碳管理、NPO 財務培力", "",
      "## 主要頁面", f"- 首頁：{SITE}/", f"- 關於佩佩（含常見問題）：{SITE}/about.html", f"- 觀點文章（生活對話、會計知識、永續 ESG，{n['fb']} 篇）：{SITE}/articles.html",
      f"- NPO 財務教室（{n['npo']} 篇，每週一更新）：{SITE}/npo-finance.html", f"- 永續新知（{n['news']} 篇，每週二更新）：{SITE}/news.html",
      f"- 會計人的學習地圖：{SITE}/accounting-learning-map.html", f"- 學習風格小測驗：{SITE}/learning-style-quiz.html", f"- 證照圖書館：{SITE}/cert-library.html",
      f"- 我的大學五本存摺（大學入門課程工具）：{SITE}/five-passbooks.html", f"- 著作《永續方程式：認識 ESG》：{SITE}/books.html",
      f"- 全部文章索引（每篇有獨立網址）：{SITE}/p/index.html", f"- 網站地圖：{SITE}/sitemap.xml", "",
      "## 最新文章"] + [f"- [{a['title']}]({a['url']})（{a['date']}，{a['cat']}）" for a in latest] + ["",
      "## 引用建議", "引用本站文章請標示作者「劉沂佩（佩佩老師）」與文章網址。本站文章皆為作者原創，永續新知頁另附官方資料來源連結。"]
    wr("llms.txt", "\n".join(lines) + "\n")

if __name__ == "__main__":
    arts = load_articles()
    print("文章數：", len(arts), {k: len([a for a in arts if a["kind"] == k]) for k in ("npo","news","fb")})
    build_article_pages(arts); print("文章頁已產：", len(glob.glob("p/*.html")))
    inject_pages()
    build_sitemap(arts); wr("robots.txt", ROBOTS); build_llms(arts)
    print("sitemap / robots / llms 完成")
