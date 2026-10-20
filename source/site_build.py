#!/usr/bin/env python3
"""Generate the static site in ./site from ./playbook.md.

Usage:  python3 site_build.py            (requires: pip install markdown)
Optional: SITE_URL=https://example.org python3 site_build.py
          -> adds absolute og:url / og:image / canonical tags.

Generated: site/index.html, site/playbook.html, one page per section,
site/assessment.html, site/policy.html, site/404.html.
Hand-written assets (site/css, site/js, site/assets) are left untouched.
The PDF and DOCX are copied into site/downloads/.
"""
import html
import json
import os
import re
import shutil
import sys

try:
    import markdown
except ImportError:
    sys.exit("Missing dependency: pip install markdown")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "playbook.md")
OUT = os.path.join(HERE, "site")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
DOWNLOADS = [("AI_Safety_Playbook.pdf", "PDF"), ("AI_Safety_Playbook.docx", "Word")]

# Optional guard: regexes that must never appear in the generated site, separated by "||".
# e.g. FORBIDDEN_TERMS='Some Name||\bABC\b' python3 site_build.py
FORBIDDEN = [t for t in os.environ.get("FORBIDDEN_TERMS", "").split("||") if t]

SECTION_FILES = {
    "1": "why-ai-safety-matters.html",
    "2": "acceptable-use-policy-template.html",
    "3": "risk-self-assessment.html",
    "4": "use-cases-by-department.html",
    "5": "30-day-rollout-plan.html",
    "6": "employee-quick-reference.html",
    "7": "references.html",
}
# Short card blurbs for the landing page (summaries of each section).
SECTION_BLURBS = {
    "1": "The five risks that matter most: data leaks, IP, hallucinations, bias, and customer trust.",
    "2": "A copy-ready AI Acceptable Use Policy with data classes and a \u201cNever paste\u201d list.",
    "3": "Ten quick questions, scored 0\u201320, with an action plan for your risk level.",
    "4": "SAFE, CAUTION, and AVOID use cases with example prompts for six departments.",
    "5": "A week-by-week checklist to roll out AI safely in 30 days.",
    "6": "A one-page do\u2019s and don\u2019ts card to print and hand to every employee.",
    "7": "Free frameworks and guidance from NIST, OWASP, CISA, the FTC, and others.",
}

# ---------------------------------------------------------------- parsing

def read_source():
    text = open(SRC, encoding="utf-8").read()
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    return meta, text


def split_sections(body):
    """Split on level-1 headings. Returns (intro_md, [(num, title, md), ...])."""
    parts = re.split(r"^# (.+)$", body, flags=re.M)
    sections = []
    for i in range(1, len(parts), 2):
        title, md = parts[i].strip(), parts[i + 1]
        m = re.match(r"(\d+)\.\s+(.*)", title)
        if m:
            sections.append((m.group(1), m.group(2), md))
    intro_md = parts[2] if not re.match(r"\d+\.", parts[1]) else parts[0]
    return intro_md, sections


def parse_assessment(md):
    header = re.search(r"^\|\s*#\s*\|\s*Question\s*\|(.+)\|\s*$", md, re.M).group(1)
    options = []
    for cell in header.split("|"):
        m = re.match(r"\s*(.+?)\s*\((\d)\)\s*$", cell)
        if m:
            options.append({"label": m.group(1), "value": int(m.group(2))})
    questions = [{"n": int(n), "text": q.strip()} for n, q in
                 re.findall(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*☐", md, re.M)]
    bands = []
    for lo, hi, level, meaning, todo in re.findall(
            r"^\|\s*\*\*(\d+)\s*[–-]\s*(\d+)\*\*\s*\|\s*\*\*(\w+)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", md, re.M):
        actions = [s.strip() for s in re.split(r"(?<=\.)\s+(?=[A-Z])", todo) if s.strip()]
        bands.append({"min": int(lo), "max": int(hi), "level": level, "meaning": meaning,
                      "todo": todo, "actions": actions})
    instructions = re.search(r"^Answer each question.*$", md, re.M).group(0)
    # Sanity checks so a bad edit to playbook.md fails loudly.
    assert len(questions) == 10, f"expected 10 questions, got {len(questions)}"
    assert [o["value"] for o in options] == [0, 1, 2], options
    assert len(bands) == 3 and bands[0]["min"] == 0 and bands[-1]["max"] == 2 * len(questions), bands
    for a, b in zip(bands, bands[1:]):
        assert b["min"] == a["max"] + 1, "score bands must be contiguous"
    return {"instructions": instructions, "options": options, "questions": questions, "bands": bands}


def extract_policy_template(md):
    start = md.index("## [COMPANY NAME] AI Acceptable Use Policy")
    return md[start:].strip() + "\n"

# ---------------------------------------------------------------- rendering

MD_EXT = ["tables", "sane_lists", "toc"]
MD_CFG = {"toc": {"permalink": False, "slugify": None}}


def slug(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def md_to_html(md, shift=0):
    """Render Markdown and post-process: autolinks, badges, task lists, table wrappers."""
    conv = markdown.Markdown(extensions=MD_EXT, extension_configs={"toc": {"slugify": lambda v, sep: slug(v)}})
    out = conv.convert(md)
    # Demote headings (e.g. ## -> ### when the page already has an h1 from '#').
    if shift:
        def demote(m):
            lvl = min(6, int(m.group(2)) + shift)
            return f"<{m.group(1)}h{lvl}"
        out = re.sub(r"<(/?)h([1-6])", demote, out)
    # Autolink bare URLs (outside tags/attributes).
    def autolink(m):
        url = m.group(0)
        trail = ""
        while url and url[-1] in ".,;:":
            trail = url[-1] + trail
            url = url[:-1]
        return f'<a href="{url}" rel="noopener">{url}</a>{trail}'
    out = re.sub(r'(?<![="\'>/])https?://[^\s<)"]+', autolink, out)
    # Rating / risk badges in table cells.
    out = re.sub(r"<td>(SAFE|CAUTION|AVOID)</td>",
                 lambda m: f'<td><span class="badge {m.group(1).lower()}">{m.group(1)}</span></td>', out)
    out = re.sub(r"<td><strong>(LOW|MEDIUM|HIGH)</strong></td>",
                 lambda m: f'<td><span class="badge {m.group(1).lower()}">{m.group(1)}</span></td>', out)
    # Leading SAFE/CAUTION/AVOID in list items.
    out = re.sub(r"<li><strong>(SAFE|CAUTION|AVOID):</strong>",
                 lambda m: f'<li><span class="badge {m.group(1).lower()}">{m.group(1)}</span>', out)
    # Task lists: "- [ ] item".
    out = re.sub(r"<ul>\n<li>\[ \]", '<ul class="tasks">\n<li>[ ]', out)
    out = out.replace("<li>[ ] ", "<li>")
    # Scrollable, keyboard-focusable tables.
    counter = {"n": 0}
    def wrap_table(m):
        counter["n"] += 1
        return f'<div class="table-wrap" role="region" tabindex="0" aria-label="Table {counter["n"]} (scrollable)">{m.group(0)}</div>'
    out = re.sub(r"<table>.*?</table>", wrap_table, out, flags=re.S)
    return out


def link_sections(h, current=None):
    """Turn plain-text 'Section N' references into links to that section's page."""
    def rep(m):
        f = SECTION_FILES.get(m.group(1))
        return m.group(0) if not f or f == current else f'<a href="{f}">{m.group(0)}</a>'
    return re.sub(r"(?<![\w/\">])Section ([1-7])\b", rep, h)


def esc(s):
    return html.escape(s, quote=True)


def page(meta, *, filename, title, description, body, active=None, body_class="", scripts=()):
    full_title = title if title == meta["title"] else f"{title} \u00b7 {meta['title']}"
    nav = [("index.html", "Home"), ("playbook.html", "Playbook"),
           ("assessment.html", "Risk check"), ("policy.html", "Policy generator"),
           ("index.html#downloads", "Downloads")]
    nav_html = "\n".join(
        f'<li><a href="{h}"{" aria-current=\"page\"" if active == h else ""}>{t}</a></li>' for h, t in nav)
    canon = ""
    if SITE_URL:
        canon = (f'<link rel="canonical" href="{SITE_URL}/{filename}">\n'
                 f'<meta property="og:url" content="{SITE_URL}/{filename}">\n')
    og_img = (SITE_URL + "/" if SITE_URL else "") + "assets/og-image.png"
    version = meta["version"]
    scripts_html = "\n".join(f'<script src="{s}"></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="author" content="{esc(meta['author'])}">
<meta name="theme-color" content="#0F5C6E">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'none'; form-action 'none'; base-uri 'self'">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="css/style.css">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(meta['title'])}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(meta['title'])}, by {esc(meta['author'])}">
<meta name="twitter:card" content="summary_large_image">
{canon}</head>
<body class="{body_class}">
<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header">
<div class="container">
<a class="brand" href="index.html"><img src="assets/favicon.svg" alt="" width="30" height="30"><span>AI Safety Playbook</span></a>
<nav class="site-nav" aria-label="Main">
<ul>
{nav_html}
</ul>
</nav>
</div>
</header>
<main id="main" tabindex="-1">
{body}
</main>
<footer class="site-footer">
<div class="container">
<p class="legal">Not legal advice. This is general guidance, not legal, security, or compliance advice. Talk to a qualified lawyer or advisor before you finalize your policy.</p>
<p>\u201c{esc(meta['title'])}\u201d by {esc(meta['author'])} is licensed under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license noopener">CC BY 4.0</a>. You may share and adapt it for any purpose, including commercially, with attribution.</p>
<p>{esc(version)} \u00b7 <a href="downloads/AI_Safety_Playbook.pdf">PDF</a> \u00b7 <a href="downloads/AI_Safety_Playbook.docx">Word</a> \u00b7 No cookies, no trackers.</p>
</div>
</footer>
{scripts_html}
</body>
</html>
"""


def sidebar(sections, current=None, subheads=()):
    items = []
    for num, title, _ in sections:
        f = SECTION_FILES[num]
        cur = ' aria-current="page"' if f == current else ""
        items.append(f'<li><a href="{f}"{cur}>{num}. {esc(title)}</a>')
        if f == current and subheads:
            items.append('<ul class="toc-sub">' + "".join(
                f'<li><a href="#{i}">{t}</a></li>' for i, t in subheads) + "</ul>")
        items.append("</li>")
    intro_cur = ' aria-current="page"' if current == "playbook.html" else ""
    return f"""<aside class="doc-sidebar" aria-label="Playbook contents">
<details open>
<summary>Playbook contents <span class="toggle-hint muted">(tap to open/close)</span></summary>
<ol>
<li><a href="playbook.html"{intro_cur}>Introduction</a></li>
{''.join(items)}
</ol>
<h2>Tools</h2>
<ul>
<li><a href="assessment.html">2-minute risk check</a></li>
<li><a href="policy.html">Policy generator</a></li>
</ul>
</details>
</aside>"""


def downloads_info():
    out = []
    for fn, label in DOWNLOADS:
        p = os.path.join(OUT, "downloads", fn)
        size = os.path.getsize(p)
        out.append((fn, label, f"{size/1024:.0f} KB" if size < 1024 * 1024 else f"{size/1048576:.1f} MB"))
    return out


SHIELD = '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3zm-1.2 14.2-3.5-3.5 1.4-1.4 2.1 2.1 4.9-4.9 1.4 1.4-6.3 6.3z"/></svg>'

# ---------------------------------------------------------------- build

def build():
    meta, body = read_source()
    for k in ("title", "author", "version", "license"):
        assert k in meta, f"missing front-matter key: {k}"
    intro_md, sections = split_sections(body)
    assert [s[0] for s in sections] == list("1234567"), [s[0] for s in sections]
    sec_by_num = {s[0]: s for s in sections}

    # Copy downloads.
    os.makedirs(os.path.join(OUT, "downloads"), exist_ok=True)
    for fn, _ in DOWNLOADS:
        shutil.copy2(os.path.join(HERE, fn), os.path.join(OUT, "downloads", fn))
    dl = downloads_info()

    pages = {}
    value_prop = "Use AI safely in your small business \u2014 free, plain-English, ready to copy"

    # ---------- index.html
    cards = "\n".join(
        f'<li class="card"><span class="num" aria-hidden="true">{n}</span>'
        f'<h3><a href="{SECTION_FILES[n]}">{esc(t)}</a></h3><p>{esc(SECTION_BLURBS[n])}</p></li>'
        for n, t, _ in sections)
    dl_buttons = "\n".join(
        f'<a class="btn secondary" href="downloads/{fn}" download>Download {label} <small>({size})</small></a>'
        for fn, label, size in dl)
    index_body = f"""
<section class="hero">
<div class="container">
<span class="eyebrow">Free guide &amp; templates \u00b7 CC BY 4.0</span>
<h1>{esc(meta['title'])}</h1>
<p class="lead">{esc(value_prop)}</p>
<p class="byline">By {esc(meta['author'])} \u00b7 {esc(meta['version'])}</p>
<div class="btn-row">
<a class="btn" href="assessment.html">Take the 2-minute risk check</a>
<a class="btn" href="policy.html">Get the policy template</a>
{dl_buttons}
</div>
<div class="notice"><p><strong>Not legal advice.</strong> This playbook is general guidance for small businesses. It is not legal, security, or compliance advice. If you handle health, financial, children\u2019s, or government data, or work in a regulated industry, talk to a qualified lawyer or advisor before you finalize your policy.</p></div>
</div>
</section>
<section class="section-block" aria-labelledby="inside-h">
<div class="container">
<h2 id="inside-h">What\u2019s inside</h2>
<p class="muted">Seven short sections for owners and managers of businesses with 5 to 200 people who don\u2019t have a legal or security team. <a href="playbook.html">Start reading</a>.</p>
<ol class="cards">
{cards}
</ol>
</div>
</section>
<section class="section-block alt" aria-labelledby="how-h">
<div class="container">
<h2 id="how-h">How to use it</h2>
<ul class="features">
<li><strong>5 minutes</strong>Read <a href="{SECTION_FILES['1']}">Section 1</a> to understand the five risks.</li>
<li><strong>2 minutes</strong>Score yourself with the <a href="assessment.html">risk check</a>.</li>
<li><strong>1 to 2 hours</strong>Fill in your <a href="policy.html">AI Acceptable Use Policy</a>.</li>
<li><strong>30 days</strong>Follow the <a href="{SECTION_FILES['5']}">rollout plan</a> and hand out the <a href="{SECTION_FILES['6']}">quick-reference card</a>.</li>
</ul>
</div>
</section>
<section class="section-block" id="downloads" aria-labelledby="dl-h">
<div class="container">
<h2 id="dl-h">Downloads</h2>
<p>Get the full playbook to print, share, or adapt. Licensed under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license noopener">CC BY 4.0</a>: share and adapt it for any purpose with attribution.</p>
<div class="btn-row">
{dl_buttons}
</div>
<p class="muted">Suggested attribution: \u201c{esc(meta['title'])}\u201d by {esc(meta['author'])}, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). If you change it, add: \u201cAdapted by [YOUR NAME OR COMPANY].\u201d</p>
</div>
</section>
"""
    pages["index.html"] = page(meta, filename="index.html", title=meta["title"],
                               description=value_prop + ". A guide, risk check, and AI policy template by " + meta["author"] + ".",
                               body=index_body, active="index.html")

    # ---------- playbook.html (introduction)
    im = intro_md
    im = re.sub(r"^_A free, practical guide.*?_\s*$", "", im, flags=re.M)
    im = re.sub(r"^By .*· Version.*$", "", im, flags=re.M)
    im = re.sub(r"^## Contents\s*\n(?:\d+\..*\n?)+", "", im, flags=re.M)
    contents = "\n".join(f'<li><a href="{SECTION_FILES[n]}">{esc(t)}</a> \u2014 {esc(SECTION_BLURBS[n])}</li>'
                         for n, t, _ in sections)
    intro_html = link_sections(md_to_html(im))
    intro_body = f"""<div class="container doc-layout">
{sidebar(sections, "playbook.html")}
<article class="doc-content">
<p class="kicker">Introduction</p>
<h1>{esc(meta['title'])}</h1>
<p class="lead muted"><em>{esc(meta.get('subtitle', ''))}.</em></p>
<p class="muted">By {esc(meta['author'])} \u00b7 {esc(meta['version'])}</p>
{intro_html}
<h2 id="contents">Contents</h2>
<ol>
{contents}
</ol>
<nav class="pager" aria-label="Pages">
<a class="next" href="{SECTION_FILES['1']}"><span>Next</span><strong>1. {esc(sec_by_num['1'][1])}</strong></a>
</nav>
</article>
</div>"""
    pages["playbook.html"] = page(meta, filename="playbook.html", title="Playbook",
                                  description=meta.get("subtitle", meta["title"]),
                                  body=intro_body, active="playbook.html", scripts=["js/site.js"])

    # ---------- section pages
    callouts = {
        "2": '<div class="tool-callout no-print"><p><strong>Skip the find-and-replace.</strong> Fill in a short form and get this policy with your company details filled in, ready to copy, download, or print.</p><a class="btn" href="policy.html">Open the policy generator</a></div>',
        "3": '<div class="tool-callout no-print"><p><strong>Prefer to click?</strong> Take the interactive version: live score, your action plan, and a printable result. Runs entirely in your browser.</p><a class="btn" href="assessment.html">Take the 2-minute risk check</a></div>',
        "6": '<div class="tool-callout no-print"><p>Print this page and keep it at your desk. Replace the [BRACKETS] with your details first.</p><button type="button" class="btn secondary" data-print>Print this card</button></div>',
    }
    for idx, (num, title, md) in enumerate(sections):
        fn = SECTION_FILES[num]
        if num == "7":  # site footer already carries the closing attribution line
            md = re.sub(r"\n---\n+_AI Safety Playbook.*?_\s*$", "\n", md, flags=re.S)
        content = link_sections(md_to_html(md), fn)
        subheads = re.findall(r'<h[23] id="([^"]+)">(.*?)</h[23]>', content)
        # Keep only real sub-sections (h2 + h3 in section 2 is long; show h2/h3 except table-only noise).
        if len(subheads) > 14:
            subheads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', content) or subheads[:14]
        prev_link = next_link = ""
        if idx > 0:
            pn, pt, _ = sections[idx - 1]
            prev_link = f'<a class="prev" href="{SECTION_FILES[pn]}"><span>Previous</span><strong>{pn}. {esc(pt)}</strong></a>'
        else:
            prev_link = '<a class="prev" href="playbook.html"><span>Previous</span><strong>Introduction</strong></a>'
        if idx < len(sections) - 1:
            nn, nt, _ = sections[idx + 1]
            next_link = f'<a class="next" href="{SECTION_FILES[nn]}"><span>Next</span><strong>{nn}. {esc(nt)}</strong></a>'
        else:
            next_link = '<a class="next" href="assessment.html"><span>Next</span><strong>Take the risk check</strong></a>'
        body_html = f"""<div class="container doc-layout">
{sidebar(sections, fn, subheads)}
<article class="doc-content">
<p class="kicker">Section {num} of {len(sections)}</p>
<h1>{num}. {esc(title)}</h1>
{callouts.get(num, '')}
{content}
<nav class="pager" aria-label="Previous and next section">
{prev_link}
{next_link}
</nav>
</article>
</div>"""
        first_para = re.search(r"<p>(.*?)</p>", content, re.S)
        desc = re.sub(r"<[^>]+>", "", first_para.group(1)) if first_para else title
        desc = html.unescape(desc)
        if len(desc) > 180:
            desc = desc[:177].rsplit(" ", 1)[0] + "\u2026"
        pages[fn] = page(meta, filename=fn, title=f"{num}. {title}", description=desc,
                         body=body_html, active="playbook.html",
                         scripts=["js/site.js"])

    # ---------- assessment.html
    a = parse_assessment(sec_by_num["3"][2])
    a["sectionLinks"] = {n: SECTION_FILES[n] for n in SECTION_FILES}
    a["demo"] = {"low": [0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
                 "medium": [0, 1, 2, 1, 2, 1, 0, 2, 1, 1],
                 "high": [2, 2, 2, 2, 1, 2, 1, 2, 2, 2],
                 "1": [0, 1, 2, 1, 2, 1, 0, 2, 1, 1]}
    opt_labels = {0: "Yes", 1: "Partly / Not sure", 2: "No"}
    qs = []
    for q in a["questions"]:
        n = q["n"]
        opts = "".join(
            f'<label><input type="radio" name="q{n}" value="{o["value"]}" required> {opt_labels.get(o["value"], o["label"])} '
            f'<span class="pts">({o["value"]} {"pt" if o["value"] == 1 else "pts"})</span></label>'
            for o in a["options"])
        qs.append(f'<fieldset class="question" id="q{n}-fieldset"><legend><span class="qn" aria-hidden="true">{n}</span>'
                  f'<span><span class="visually-hidden">Question {n}: </span>{esc(q["text"])}</span></legend>'
                  f'<div class="options">{opts}</div></fieldset>')
    bands_li = "".join(
        f'<li data-level="{b["level"]}"><span><span class="badge {b["level"].lower()}">{b["level"]}</span></span><span>{b["min"]}\u2013{b["max"]}</span></li>'
        for b in a["bands"])
    bands_table = "".join(
        f'<tr><td>{b["min"]}\u2013{b["max"]}</td><td><span class="badge {b["level"].lower()}">{b["level"]}</span></td><td>{esc(b["meaning"])}</td><td>{esc(b["todo"])}</td></tr>'
        for b in a["bands"])
    a_json = json.dumps(a, ensure_ascii=False).replace("</", "<\\/")
    assess_body = f"""<div class="container tool-page">
<p class="kicker">From Section 3 of the playbook</p>
<h1>AI Risk Self-Assessment</h1>
<p>{esc(a['instructions'].replace('**', ''))}</p>
<p class="privacy">{SHIELD}<span><strong>Private by design.</strong> Your answers stay in this browser tab. Nothing is sent anywhere, saved, or tracked. Closing the page erases them.</span></p>
<div class="assess-layout">
<div>
<form id="assessment-form" aria-describedby="result-pending" novalidate>
{''.join(qs)}
</form>
<p id="result-pending" class="notice" role="status"></p>
<section id="result" class="result" hidden aria-live="polite"></section>
<details class="no-print">
<summary>How scoring works</summary>
<div class="table-wrap" role="region" tabindex="0" aria-label="Score bands"><table>
<thead><tr><th>Score</th><th>Risk level</th><th>What it means</th><th>What to do</th></tr></thead>
<tbody>{bands_table}</tbody></table></div>
</details>
</div>
<aside aria-label="Live score">
<div class="scorebox" aria-live="polite" aria-atomic="true">
<h2 class="visually-hidden">Live score</h2>
<div class="big"><span id="live-score">0</span><small> / {2 * len(a['questions'])}</small></div>
<div><div class="meter" aria-hidden="true"><span id="live-meter"></span></div>
<div id="live-answered" class="muted">0 of {len(a['questions'])} answered</div></div>
<ul class="bands">{bands_li}</ul>
</div>
</aside>
</div>
</div>
<script type="application/json" id="assessment-data">{a_json}</script>"""
    pages["assessment.html"] = page(meta, filename="assessment.html", title="2-minute AI risk check",
                                    description="Answer 10 questions to score your small business\u2019s AI risk (0\u201320) and get a matching action plan. Runs in your browser; nothing is sent.",
                                    body=assess_body, active="assessment.html",
                                    scripts=["js/logic.js", "js/assessment.js"])

    # ---------- policy.html
    tpl_md = extract_policy_template(sec_by_num["2"][2])
    tpl_html = md_to_html(tpl_md)
    tpl = {"markdown": tpl_md, "html": tpl_html,
           "demo": {"company": "Acme Plumbing Co.", "ownerName": "Jordan Lee", "ownerRole": "Operations Manager",
                    "tools": "ChatGPT Business, Microsoft 365 Copilot", "reviewMonths": "6",
                    "incidentContact": "Jordan Lee (ai@acmeplumbing.example, ext. 204)",
                    "toolsLocation": "the shared drive: Policies > AI", "requestContact": "ai@acmeplumbing.example",
                    "effectiveDate": "2026-11-01"}}
    for needle in ["[COMPANY NAME]", "[NAME, TITLE]", "[AI OWNER]", "[AI OWNER / CONTACT]", "[LIST TOOLS",
                   "every [6] months", "[DATE]", "[LOCATION]", "[EMAIL/FORM]"]:
        assert needle in tpl_md and needle in tpl_html, f"template placeholder missing: {needle}"
    tpl_json = json.dumps(tpl, ensure_ascii=False).replace("</", "<\\/")
    policy_body = f"""<div class="container tool-page">
<div class="tool-intro">
<p class="kicker">From Section 2 of the playbook</p>
<h1>AI Acceptable Use Policy generator</h1>
<p>Fill in the fields and the <a href="{SECTION_FILES['2']}">policy template</a> updates as you type. Then copy it into your own document, delete anything that doesn\u2019t fit your business, and keep it short enough that people will actually read it.</p>
<p class="privacy">{SHIELD}<span><strong>Private by design.</strong> Everything happens in this browser tab. Nothing you type is sent anywhere or saved.</span></p>
</div>
<div class="policy-layout">
<form id="policy-form" class="policy-form" aria-label="Policy details">
<div class="field"><label for="f-company">Company name</label><input id="f-company" name="company" autocomplete="organization" placeholder="e.g. Acme Plumbing Co."></div>
<div class="field-row">
<div class="field"><label for="f-owner">AI owner: name</label><input id="f-owner" name="ownerName" autocomplete="name" placeholder="e.g. Jordan Lee"></div>
<div class="field"><label for="f-role">AI owner: role</label><input id="f-role" name="ownerRole" autocomplete="organization-title" placeholder="e.g. Operations Manager"></div>
</div>
<div class="field"><label for="f-tools">Approved AI tools</label><span class="hint" id="h-tools">Separate with commas or new lines.</span><textarea id="f-tools" name="tools" rows="2" aria-describedby="h-tools" placeholder="e.g. ChatGPT Business, Microsoft 365 Copilot"></textarea></div>
<div class="field-row">
<div class="field"><label for="f-review">Review period</label><select id="f-review" name="reviewMonths"><option value="3">3 months</option><option value="6" selected>6 months</option><option value="12">12 months</option></select></div>
<div class="field"><label for="f-date">Effective date</label><input id="f-date" name="effectiveDate" type="date"></div>
</div>
<div class="field"><label for="f-incident">Contact for incidents</label><span class="hint" id="h-incident">Who staff report AI mistakes or data slips to (name, email, phone, or chat channel).</span><input id="f-incident" name="incidentContact" aria-describedby="h-incident" placeholder="e.g. Jordan Lee, ai@yourcompany.com"></div>
<details>
<summary>More options (optional)</summary>
<div class="field"><label for="f-loc">Where the Approved AI Tools List lives</label><input id="f-loc" name="toolsLocation" placeholder="e.g. the shared drive: Policies > AI"></div>
<div class="field"><label for="f-req">Where to request a new tool</label><input id="f-req" name="requestContact" placeholder="e.g. ai@yourcompany.com or a form link"></div>
<div class="field-row">
<div class="field"><label for="f-days">Approval time (business days)</label><input id="f-days" name="approvalDays" inputmode="numeric" value="5"></div>
<div class="field"><label for="f-window">Report problems within</label><input id="f-window" name="reportWindow" value="24 hours"></div>
</div>
<div class="field-row">
<div class="field"><label for="f-train">Training length (minutes)</label><input id="f-train" name="trainingMinutes" inputmode="numeric" value="30"></div>
<div class="field"><label for="f-refresh">Refresher every (months)</label><input id="f-refresh" name="refresherMonths" inputmode="numeric" value="12"></div>
</div>
</details>
<button type="reset" class="btn secondary">Clear form</button>
</form>
<section aria-labelledby="out-h">
<h2 id="out-h" class="visually-hidden">Your policy</h2>
<div class="toolbar no-print">
<button type="button" class="btn" data-action="copy">Copy to clipboard</button>
<button type="button" class="btn secondary" data-action="md">Download .md</button>
<button type="button" class="btn secondary" data-action="txt">Download .txt</button>
<button type="button" class="btn secondary" data-action="print">Print</button>
</div>
<p id="status" class="status no-print" role="status" aria-live="polite"></p>
<p id="remaining" class="remaining notice no-print" aria-live="polite"></p>
<article id="policy-output" class="policy-output">
{tpl_html}
</article>
<p class="muted">Template from \u201c{esc(meta['title'])}\u201d by {esc(meta['author'])} (CC BY 4.0). Generic starting point, not the policy of any specific company. Not legal advice.</p>
</section>
</div>
</div>
<script type="application/json" id="policy-template">{tpl_json}</script>"""
    pages["policy.html"] = page(meta, filename="policy.html", title="AI policy generator",
                                description="Fill in a few fields and get a ready-to-use AI Acceptable Use Policy for your small business. Copy, download, or print. Runs in your browser.",
                                body=policy_body, active="policy.html",
                                scripts=["js/logic.js", "js/policy.js"])

    # ---------- 404
    pages["404.html"] = page(meta, filename="404.html", title="Page not found", description="Page not found.",
                             body='<div class="container tool-page"><h1>Page not found</h1><p>Try the <a href="index.html">home page</a> or the <a href="playbook.html">playbook</a>.</p></div>')

    # Write + guard against forbidden terms.
    for fn, content in pages.items():
        for pat in FORBIDDEN:
            if re.search(pat, content):
                sys.exit(f"Forbidden term {pat!r} found in {fn}; aborting.")
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"Wrote {len(pages)} pages to {OUT}:")
    for fn in pages:
        print("  ", fn)


if __name__ == "__main__":
    build()
