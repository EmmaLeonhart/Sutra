"""Build the Sutra website — a multi-page static site on the shared
emmaleonhart.com identity (web/identity.css). No MkDocs.

Every `docs/**/*.md` (except `docs/interactive/**`) is rendered to a
static page, plus `paper/paper.md` -> `/paper/`:

    /                 docs/index.md          — what Sutra is (home)
    /<name>/          docs/<name>.md         — a conceptual page
    /tutorials/...    docs/tutorials/*.md    — the tutorials
    /neurips-2026/    docs/neurips-2026.md   — frozen-submission archive
    /paper/           paper/paper.md         — the paper, readable HTML
                                               (+ PDF / anon / zip downloads)

The doc sources are the original MkDocs-flavoured Markdown; `clean_md`
sanitises the MkDocs-only syntax (YAML frontmatter, `!!!` admonitions,
`:material-:` icons, `{.attr}` lists, ```mermaid fences, `*.md` links)
at render time, so the sources stay faithful and the conversion is
re-runnable.

Output identity.css + CNAME are copied from web/. The paper PDFs and
the supplementary zip are produced by the Pages workflow and dropped
into the output root so `/paper.pdf` etc. resolve.

Usage:  python scripts/build_site.py [--output _site]
"""
from __future__ import annotations

import argparse
import html as _html
import posixpath
import re
import shutil
import sys
from pathlib import Path

import markdown

PAGE_CSS = """
body { display: flex; flex-direction: column; min-height: 100vh; position: relative; overflow-x: hidden; }
.topbar {
  position: relative; z-index: 2;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 20px 28px; border-bottom: 1px solid var(--border);
}
.topbar a { font-family: var(--mono); font-size: 0.82rem; font-weight: 500; text-decoration: none; transition: color 0.2s; }
.topbar .home { color: var(--text-mute); }
.topbar .home:hover { color: var(--accent-bright); }
main { position: relative; z-index: 2; flex: 1; display: flex; justify-content: center; padding: 64px 28px 96px; }
.container { max-width: 820px; width: 100%; position: relative; }
.scroll { font-size: 2.4rem; line-height: 1; }
h1 {
  font-size: clamp(2.1rem, 5.5vw, 3rem); font-weight: 700;
  margin: 16px 0 22px; letter-spacing: -1px; line-height: 1.08;
  background: linear-gradient(120deg, var(--text-strong) 0%, var(--accent-bright) 55%, var(--sutra) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.lede { font-size: 1.04rem; color: var(--text-mute); line-height: 1.65; margin-bottom: 30px; }
.back {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--mono); font-size: 0.78rem; color: var(--text-mute);
  text-decoration: none; margin-bottom: 26px;
}
.back:hover { color: var(--accent-bright); }
.downloads { display: grid; gap: 12px; margin-bottom: 48px; }
.dl { display: flex; align-items: center; gap: 16px; text-decoration: none; color: var(--text-strong); }
.dl .dl-body { flex: 1; min-width: 0; }
.dl .dl-name { font-weight: 600; font-size: 1rem; }
.dl .dl-sub { font-size: 0.85rem; color: var(--text-mute); margin-top: 3px; line-height: 1.5; }
.dl .dl-arrow { color: var(--accent); font-size: 1.2rem; flex: none; transition: transform 0.2s; }
.dl:hover .dl-arrow { transform: translateX(3px); }
.links { display: flex; flex-wrap: wrap; gap: 12px; margin: 30px 0 8px; }
.links a {
  font-family: var(--mono); font-size: 0.84rem; font-weight: 500;
  text-decoration: none; color: var(--accent); padding: 10px 18px;
  border: 1px solid var(--border-hover); border-radius: 8px;
  background: var(--accent-soft); transition: all 0.2s;
}
.links a:hover { color: var(--accent-bright); border-color: var(--accent); transform: translateY(-1px); }
.links a.primary { background: linear-gradient(135deg, var(--accent-deep) 0%, var(--accent-deep-hover) 100%); color: var(--on-accent-deep); border-color: var(--accent-deep); }

/* Homepage "Explore" contents grid */
.explore-h {
  font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 2px; color: var(--text-mute);
  margin: 52px 0 16px;
}
.explore { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 12px; margin-bottom: 8px; }
.explore a {
  display: block; text-decoration: none; padding: 14px 16px;
  border: 1px solid var(--border); border-radius: 10px; background: var(--bg-card);
  transition: border-color 0.2s, transform 0.2s, background 0.2s;
}
.explore a:hover { border-color: var(--accent); transform: translateY(-2px); }
.explore .ex-t { font-weight: 600; font-size: 0.95rem; color: var(--text-strong); }
.explore .ex-d { font-size: 0.82rem; color: var(--text-mute); margin-top: 3px; line-height: 1.45; }

/* Rendered markdown body */
.doc { color: var(--text); line-height: 1.7; }
.doc > p:first-child { font-size: 1.18rem; color: var(--text-strong); line-height: 1.55; margin-top: 0; }
.doc h2 {
  font-size: 1.5rem; font-weight: 700; color: var(--text-strong);
  margin: 48px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border);
  letter-spacing: -0.4px;
}
.doc h3 { font-size: 1.15rem; font-weight: 600; color: var(--text-strong); margin: 32px 0 12px; }
.doc h4 { font-size: 1rem; font-weight: 600; color: var(--text-strong); margin: 24px 0 10px; }
.doc p { margin: 14px 0; }
.doc ul, .doc ol { margin: 14px 0; padding-left: 1.4em; }
.doc li { margin: 6px 0; }
.doc a { color: var(--accent); }
.doc a:hover { color: var(--accent-bright); }
.doc strong { color: var(--text-strong); font-weight: 600; }
.doc code {
  font-family: var(--mono); font-size: 0.86em;
  background: var(--bg-soft); border: 1px solid var(--border);
  padding: 1px 6px; border-radius: 5px; color: var(--text-strong);
}
.doc pre {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; overflow-x: auto; margin: 18px 0;
}
.doc pre code { background: none; border: none; padding: 0; font-size: 0.84em; }
.doc blockquote {
  margin: 18px 0; padding: 4px 18px; border-left: 3px solid var(--accent);
  background: var(--accent-soft); border-radius: 0 8px 8px 0; color: var(--text-mute);
}
.doc blockquote p { margin: 10px 0; }
.doc table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.92rem; }
.doc th, .doc td { text-align: left; padding: 10px 14px; border: 1px solid var(--border); }
.doc th { background: var(--bg-soft); color: var(--text-strong); font-weight: 600; }
.doc hr { border: none; border-top: 1px solid var(--border); margin: 40px 0; }
.doc .mermaid { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin: 18px 0; text-align: center; }
footer {
  position: relative; z-index: 2; padding: 24px 28px;
  border-top: 1px solid var(--border);
  font-family: var(--mono); font-size: 0.72rem; letter-spacing: 1px;
  color: var(--text-faint);
}
@media (max-width: 600px) { .topbar { padding: 16px 18px; } main { padding: 48px 20px 72px; } }
"""

TOGGLE = """
  <button id="theme-toggle" class="theme-toggle" type="button" aria-label="Toggle light and dark theme" title="Toggle light / dark">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,2L14.39,5.42C13.65,5.15 12.84,5 12,5C11.16,5 10.35,5.15 9.61,5.42L12,2M3.34,7L7.5,6.65C6.9,7.16 6.36,7.78 5.94,8.5C5.5,9.24 5.25,10 5.11,10.79L3.34,7M3.36,17L5.12,13.23C5.26,14 5.53,14.78 5.95,15.5C6.37,16.24 6.91,16.86 7.5,17.37L3.36,17M20.65,7L18.88,10.79C18.74,10 18.47,9.23 18.05,8.5C17.63,7.78 17.1,7.15 16.5,6.64L20.65,7M20.64,17L16.5,17.36C17.09,16.85 17.62,16.22 18.04,15.5C18.46,14.77 18.73,14 18.87,13.21L20.64,17M12,22L9.59,18.56C10.33,18.83 11.14,19 12,19C12.82,19 13.63,18.86 14.37,18.59L12,22Z"></path></svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95M17.33,17.97C14.5,17.81 11.7,16.64 9.53,14.5C7.36,12.31 6.2,9.5 6.04,6.68C3.23,9.82 3.34,14.4 6.35,17.41C9.37,20.43 14,20.54 17.33,17.97Z"></path></svg>
  </button>
"""

GH_PILL = """<a class="gh" href="https://github.com/EmmaLeonhart/Sutra" data-gh-repo="EmmaLeonhart/Sutra" aria-label="EmmaLeonhart/Sutra on GitHub">
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      <span class="gh-name">GitHub</span>
      <span class="gh-stat gh-stars" hidden title="GitHub stars"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/></svg><span class="gh-stars-n">&ndash;</span></span>
      <span class="gh-stat gh-ver" hidden title="Latest release / tag"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.474l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.75 1.75 0 0 1 1 7.775ZM2.75 2.5a.25.25 0 0 0-.25.25v5.025c0 .066.026.13.073.177l6.25 6.25a.25.25 0 0 0 .354 0l5.025-5.025a.25.25 0 0 0 0-.354l-6.25-6.25a.25.25 0 0 0-.177-.073H2.75ZM6 5a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"/></svg><span class="gh-ver-n">&ndash;</span></span>
    </a>"""

GH_JS = """  <script>
  (function(){
    var el=document.querySelector('a.gh[data-gh-repo]');if(!el)return;
    var repo=el.getAttribute('data-gh-repo');
    function put(sel,val){var s=el.querySelector(sel);if(!s)return;
      var n=s.querySelector('span');if(n)n.textContent=val;s.hidden=false;}
    fetch('https://api.github.com/repos/'+repo).then(function(r){return r.ok?r.json():null;})
      .then(function(d){if(d&&typeof d.stargazers_count==='number')put('.gh-stars',d.stargazers_count.toLocaleString());}).catch(function(){});
    fetch('https://api.github.com/repos/'+repo+'/releases/latest').then(function(r){return r.ok?r.json():null;})
      .then(function(d){if(d&&d.tag_name){put('.gh-ver',d.tag_name);return;}
        return fetch('https://api.github.com/repos/'+repo+'/tags').then(function(r){return r.ok?r.json():null;})
          .then(function(t){if(t&&t.length&&t[0].name)put('.gh-ver',t[0].name);});}).catch(function(){});
  })();
  </script>"""

MERMAID_JS = """  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    var dark = document.documentElement.getAttribute('data-theme') !== 'light';
    mermaid.initialize({ startOnLoad: true, theme: dark ? 'dark' : 'neutral', securityLevel: 'loose' });
  </script>"""

# MathJax 3. The Markdown source carries LaTeX ($...$, $$...$$,
# \\begin{align*}...). build_site protects those spans from the
# Markdown processor and restores them HTML-escaped, so MathJax sees
# the correct text; it skips <pre>/<code> by default.
MATHJAX_JS = """  <script>
    window.MathJax = {
      tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']], processEnvironments: true, processEscapes: true },
      options: { skipHtmlTags: ['script','noscript','style','textarea','pre','code','annotation','annotation-xml'] }
    };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>"""

DOWNLOAD_CARDS = """
    <div class="downloads">
      <a class="card dl" href="/paper.pdf">
        <div class="dl-body">
          <div class="dl-name">Paper (PDF)</div>
          <div class="dl-sub">The Sutra language paper &mdash; author-attributed, full version.</div>
        </div>
        <span class="dl-arrow">&rarr;</span>
      </a>
      <a class="card dl" href="/paper-anonymized.pdf">
        <div class="dl-body">
          <div class="dl-name">Paper (PDF, anonymized)</div>
          <div class="dl-sub">The double-blind review version &mdash; author identity stripped, same content.</div>
        </div>
        <span class="dl-arrow">&rarr;</span>
      </a>
      <a class="card dl" href="/sutra-neurips-supplementary.zip">
        <div class="dl-body">
          <div class="dl-name">Reproduction archive (ZIP)</div>
          <div class="dl-sub">Compiler source, tests, paper-claim reproduction scripts, and the agent-runnable replication recipe.</div>
        </div>
        <span class="dl-arrow">&rarr;</span>
      </a>
    </div>
"""

# The /paper/ page links only the paper itself and the reproduction
# archive (the anonymized PDF lives on /neurips-2026/, the submission
# record). The ZIP is called out as carrying SKILL.md.
PAPER_DOWNLOADS = """
    <div class="downloads">
      <a class="card dl" href="/paper.pdf">
        <div class="dl-body">
          <div class="dl-name">Paper (PDF)</div>
          <div class="dl-sub">The full Sutra language paper, author-attributed.</div>
        </div>
        <span class="dl-arrow">&rarr;</span>
      </a>
      <a class="card dl" href="/sutra-replication-package.zip">
        <div class="dl-body">
          <div class="dl-name">Replication package (ZIP)</div>
          <div class="dl-sub">Compiler source, tests, and paper-claim reproduction scripts &mdash; including <code>SKILL.md</code>, the agent-runnable replication recipe.</div>
        </div>
        <span class="dl-arrow">&rarr;</span>
      </a>
    </div>
"""


def shell(title: str, inner: str, mermaid: bool = False, math: bool = False) -> str:
    extra = (("\n" + MERMAID_JS) if mermaid else "") + (("\n" + MATHJAX_JS) if math else "")
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Sutra — a geometrically compiled language where logical operations over vector spaces resolve at compile time into matrix multiplications.">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="Sutra — a geometrically compiled language where logical operations over vector spaces resolve at compile time into matrix multiplications.">
  <meta property="og:url" content="https://sutra.emmaleonhart.com">
  <title>{title}</title>

  <script>(function(){{try{{var t=localStorage.getItem('theme');if(t!=='light'&&t!=='dark')t='dark';document.documentElement.setAttribute('data-theme',t);}}catch(e){{document.documentElement.setAttribute('data-theme','dark');}}}})();</script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/identity.css">
  <style>{PAGE_CSS}</style>
</head>
<body>
  <div class="aurora" aria-hidden="true"></div>
{TOGGLE}
  <header class="topbar">
    <a class="home" href="https://emmaleonhart.com">&larr; emmaleonhart.com</a>
    {GH_PILL}
  </header>
  <main>
    <div class="container">
{inner}
    </div>
  </main>
  <footer>sutra.emmaleonhart.com</footer>
  {GH_JS}{extra}
  <script>
    (function(){{
      var b=document.getElementById('theme-toggle');
      if(b)b.addEventListener('click',function(){{var c=document.documentElement.getAttribute('data-theme')==='light'?'light':'dark';var n=c==='light'?'dark':'light';document.documentElement.setAttribute('data-theme',n);try{{localStorage.setItem('theme',n);}}catch(e){{}}}});
    }})();
  </script>
</body>
</html>
"""


# ---- MkDocs-flavoured Markdown -> clean Markdown -------------------

def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n") or text.startswith("---\r\n"):
        m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, flags=re.DOTALL)
        if m:
            return text[m.end():]
    return text


def _rewrite_link(target: str, src_dir: str) -> str:
    """Resolve a Markdown link relative to its source file's docs dir,
    then map a docs-relative `*.md` target to its clean site URL."""
    t = target.strip()
    if not t or t[0] in "#/" or "://" in t or t.startswith("mailto:"):
        return target
    anchor = ""
    if "#" in t:
        t, anchor = t.split("#", 1)
        anchor = "#" + anchor
    if not t.lower().endswith(".md"):
        return target  # asset (pdf/zip/png/...) — leave
    base = "" if src_dir in (".", "") else src_dir
    rel = posixpath.normpath(posixpath.join(base, t)).lstrip("/")
    if rel in ("index.md", "."):
        return "/" + anchor
    if rel == "theory-and-paper.md":
        return "/paper/" + anchor
    if rel.startswith("interactive/"):
        return "/" + anchor  # interactive pages are not rebuilt
    rel = rel[:-3]  # drop .md
    if rel.endswith("/index"):
        rel = rel[:-len("/index")]
    return f"/{rel}/" + anchor


def clean_md(text: str, src_dir: str = ".") -> tuple[str, bool]:
    """Return (clean_markdown, uses_mermaid)."""
    text = _strip_frontmatter(text)

    # pymdownx snippet includes — drop the directive line
    text = re.sub(r"^\s*--8<--\s+.*$", "", text, flags=re.MULTILINE)

    # ```mermaid fences -> <div class="mermaid"> ... </div>
    uses_mermaid = False

    def _mermaid(m: re.Match) -> str:
        nonlocal uses_mermaid
        uses_mermaid = True
        return '<div class="mermaid">\n' + m.group(1).strip() + "\n</div>"

    text = re.sub(r"```mermaid\s*\n(.*?)\n```", _mermaid, text, flags=re.DOTALL)

    # Material grid-cards wrapper -> drop the wrapper tags, keep inner
    text = re.sub(r'<div class="grid cards"[^>]*>', "", text)

    # icon shortcodes
    text = re.sub(r":(?:material|fontawesome|octicons|simple|fontawesome-brands)-[\w-]+:", "", text)

    # attr-lists: { .class }, { #id }, {: ... } — only when it looks like one
    text = re.sub(r"\{\:?\s*[.#][^}\n]*\}", "", text)

    # !!! / ??? admonitions -> blockquote with bold title
    out_lines: list[str] = []
    lines = text.split("\n")
    i = 0
    adm_re = re.compile(r'^(\s*)(?:!!!|\?\?\?\+?|\?\?\?)\s+([\w-]+)(?:\s+"([^"]*)")?\s*$')
    while i < len(lines):
        m = adm_re.match(lines[i])
        if m:
            indent = m.group(1)
            title = m.group(3) or m.group(2).replace("-", " ").title()
            out_lines.append("")
            out_lines.append(f"> **{title}**")
            i += 1
            base = len(indent) + 4
            while i < len(lines):
                ln = lines[i]
                if ln.strip() == "":
                    out_lines.append(">")
                    i += 1
                    continue
                if len(ln) - len(ln.lstrip(" ")) >= base:
                    out_lines.append("> " + ln[base:])
                    i += 1
                    continue
                break
            out_lines.append("")
            continue
        out_lines.append(lines[i])
        i += 1
    text = "\n".join(out_lines)

    # rewrite [..](x.md) links relative to the source file's docs dir
    text = re.sub(r"\]\(([^)\s]+)\)",
                   lambda m: "](" + _rewrite_link(m.group(1), src_dir) + ")", text)
    return text, uses_mermaid


def split_title(md_text: str) -> tuple[str, str]:
    lines = md_text.splitlines()
    heading = "Sutra"
    start = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            continue
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            heading = m.group(1).strip()
            start = i + 1
        break
    return heading, "\n".join(lines[start:]).lstrip("\n")


_MATH_ENVS = r"align\*?|equation\*?|gather\*?|multline\*?|alignat\*?|flalign\*?|aligned"


def _protect_math(text: str) -> tuple[str, list[str]]:
    """Pull LaTeX math out before Markdown can mangle it. Safe here:
    paper.md has no `$` inside code (verified), so no false matches."""
    store: list[str] = []

    def keep(m: "re.Match[str]") -> str:
        store.append(m.group(0))
        return f"@@MJX{len(store) - 1}@@"

    # Inner equivalents valid inside $$...$$ display math. A *bare*
    # \begin{align*} relies on MathJax's processEnvironments scan,
    # which proved unreliable here (the gate tables rendered as
    # run-on raw LaTeX). Wrapping the body in $$ \begin{aligned} ...
    # forces the verified display-math path, so every \\ row (e.g.
    # XOR then XNOR) lands on its own line.
    env_inner = {"align": "aligned", "align*": "aligned",
                 "alignat": "aligned", "alignat*": "aligned",
                 "flalign": "aligned", "flalign*": "aligned",
                 "gather": "gathered", "gather*": "gathered",
                 "multline": "aligned", "multline*": "aligned",
                 "aligned": "aligned"}

    def keep_env(m: "re.Match[str]") -> str:
        env, body = m.group(1), m.group(2).strip("\n")
        inner = env_inner.get(env)
        if env in ("equation", "equation*") or inner is None:
            wrapped = f"$$\n{body}\n$$"
        else:
            wrapped = f"$$\n\\begin{{{inner}}}\n{body}\n\\end{{{inner}}}\n$$"
        store.append(wrapped)
        return f"@@MJX{len(store) - 1}@@"

    text = re.sub(r"\$\$.+?\$\$", keep, text, flags=re.DOTALL)            # display
    text = re.sub(r"\\begin\{(" + _MATH_ENVS + r")\}(.*?)\\end\{\1\}",    # AMS envs
                   keep_env, text, flags=re.DOTALL)
    text = re.sub(r"(?<!\\)\$(?!\$)([^\n$]{1,400}?)\$(?!\$)", keep, text)  # inline
    return text, store


def _restore_math(html_str: str, store: list[str]) -> str:
    # HTML-escape so raw <, >, & in LaTeX (align uses &) stay valid
    # markup; the browser decodes them back to text for MathJax.
    for i, s in enumerate(store):
        html_str = html_str.replace(f"@@MJX{i}@@", _html.escape(s, quote=False))
    return html_str


def render(md_text: str, src_dir: str = ".") -> tuple[str, str, bool, bool]:
    cleaned, mer = clean_md(md_text, src_dir)
    heading, body_md = split_title(cleaned)
    body_md, math_store = _protect_math(body_md)
    body_html = markdown.markdown(
        body_md, extensions=["extra", "sane_lists", "smarty"], output_format="html5"
    )
    body_html = _restore_math(body_html, math_store)
    return heading, body_html, mer, bool(math_store)


# Preferred reading order for the homepage "Explore" list. Anything
# present but not listed is appended alphabetically.
ORDER = [
    "what-is-sutra", "vision", "paradigms", "ontology", "primitive-classes",
    "operators", "logical-operations", "numeric-math", "memory", "loops",
    "promises", "typescript-to-sutra", "compilation", "demos", "history",
]
BLURB = {
    "what-is-sutra": "The short version: a typed language whose compiled forward pass is a neural net.",
    "vision": "Why embedding spaces look like graphs but behave like geometry.",
    "paradigms": "What programming paradigms Sutra is in conversation with.",
    "ontology": "The type system and the role of OWL-style classes.",
    "primitive-classes": "Built-in primitive types and their geometric semantics.",
    "operators": "The operator set and what each one compiles to.",
    "logical-operations": "&&, ||, ! over fuzzy three-valued truth.",
    "numeric-math": "How integers, floats, and complex numbers live in the substrate.",
    "memory": "bind, unbind, bundle — the role-filler model.",
    "loops": "First-class loop functions as substrate-pure RNN cells.",
    "promises": "Promises and async/await, geometrically.",
    "typescript-to-sutra": "How TypeScript source maps onto Sutra.",
    "compilation": "The five-stage pipeline from source to fused tensor graph.",
    "demos": "Every program in the smoke test.",
    "history": "How the language got to its current shape.",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    docs = repo / "docs"
    out = repo / args.output
    out.mkdir(parents=True, exist_ok=True)

    # Discover every doc page except the interactive ones.
    sources = [
        p for p in sorted(docs.rglob("*.md"))
        if "interactive" not in p.relative_to(docs).parts
    ]
    titles: dict[str, str] = {}

    def write(rel_url: str, out_path: Path, title: str, inner: str,
              mer: bool = False, mth: bool = False):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(shell(title, inner, mer, mth), encoding="utf-8")
        print(f"wrote {out_path.relative_to(out)}  ->  {rel_url}")

    home_md = None
    for src in sources:
        rel = src.relative_to(docs)
        slug = rel.as_posix()[:-3]  # drop .md
        src_dir = rel.parent.as_posix()  # "." or "tutorials"
        heading, body, mer, mth = render(src.read_text(encoding="utf-8"), src_dir)
        titles[slug] = heading
        if slug == "index":
            home_md = (heading, body, mer, mth)
            continue
        if slug == "neurips-2026":
            inner = (f'    <a class="back" href="/">&larr; Sutra home</a>\n'
                     f'    <span class="eyebrow">Sutra</span>\n    <h1>{heading}</h1>\n'
                     f'    <p class="lede">The immutable record of the Sutra paper as submitted to NeurIPS 2026. Downloads:</p>\n'
                     f'{DOWNLOAD_CARDS}\n    <div class="doc">\n{body}\n    </div>\n')
        else:
            inner = (f'    <a class="back" href="/">&larr; Sutra home</a>\n'
                     f'    <span class="eyebrow">Sutra</span>\n    <h1>{heading}</h1>\n'
                     f'    <div class="doc">\n{body}\n    </div>\n')
        if slug.endswith("/index"):
            sub = slug[: -len("/index")]
            out_path = out / sub / "index.html"
            url = f"/{sub}/"
        else:
            out_path = out / slug / "index.html"
            url = f"/{slug}/"
        write(url, out_path, f"{heading} — Sutra", inner, mer, mth)

    # The paper, readable on-site, from paper/paper.md
    paper_src = repo / "paper" / "paper.md"
    paper_ok = paper_src.exists()
    if paper_ok:
        p_head, p_body, p_mer, p_mth = render(paper_src.read_text(encoding="utf-8"))
        inner = (f'    <a class="back" href="/">&larr; Sutra home</a>\n'
                 f'    <span class="eyebrow">Sutra &middot; Paper</span>\n    <h1>{p_head}</h1>\n'
                 f'    <p class="lede">The full Sutra paper, readable here. Downloads:</p>\n'
                 f'{PAPER_DOWNLOADS}\n    <div class="doc">\n{p_body}\n    </div>\n')
        write("/paper/", out / "paper" / "index.html", f"{p_head} — Sutra", inner, p_mer, p_mth)

    # Homepage: explanation + Explore contents + paper link
    if home_md is None:
        print("error: docs/index.md missing", file=sys.stderr)
        return 1
    h_head, h_body, h_mer, h_mth = home_md
    page_slugs = [s for s in titles if s not in ("index", "neurips-2026")]
    ordered = [s for s in ORDER if s in page_slugs] + sorted(
        s for s in page_slugs if s not in ORDER
    )
    cards = []
    if paper_ok:
        cards.append('<a href="/paper/"><div class="ex-t">The paper</div>'
                     '<div class="ex-d">Tensor-Op RNNs as a compilation target for VSAs — full text, readable here.</div></a>')
    for s in ordered:
        if s.startswith("tutorials/") and s != "tutorials/index":
            continue  # surfaced via the tutorials index
        t = titles[s]
        d = BLURB.get(s, "")
        url = "/tutorials/" if s == "tutorials/index" else f"/{s}/"
        if s == "tutorials/index":
            t = "Tutorials"
            d = "Hands-on: hello Sutra, bind/unbind, snap-to-nearest."
        cards.append(f'<a href="{url}"><div class="ex-t">{t}</div><div class="ex-d">{d}</div></a>')
    cards.append('<a href="/neurips-2026/"><div class="ex-t">NeurIPS 2026 archive</div>'
                 '<div class="ex-d">The frozen submission record + paper / anonymized / zip downloads.</div></a>')
    explore = ('    <div class="explore-h">Explore</div>\n    <div class="explore">\n      '
               + "\n      ".join(cards) + "\n    </div>\n")
    paper_link = '<a class="primary" href="/paper/">Read the paper</a>' if paper_ok else ""
    home_inner = (
        '    <span class="eyebrow">Sutra</span>\n'
        '    <div class="scroll" aria-hidden="true">📜</div>\n'
        f'    <h1>{h_head}</h1>\n'
        f'    <div class="doc">\n{h_body}\n    </div>\n'
        f'{explore}'
        '    <div class="links">\n'
        f'      {paper_link}\n'
        '      <a href="https://github.com/EmmaLeonhart/Sutra">View source on GitHub</a>\n'
        '      <a href="https://github.com/EmmaLeonhart/Sutra/releases">Releases &amp; downloads</a>\n'
        '      <a href="https://emmaleonhart.com/projects/">All projects</a>\n'
        '    </div>\n'
    )
    (out / "index.html").write_text(
        shell("Sutra — a geometrically compiled language", home_inner, h_mer, h_mth),
        encoding="utf-8",
    )
    print("wrote index.html  ->  /")

    web = repo / "web"
    for name in ("identity.css", "CNAME"):
        shutil.copyfile(web / name, out / name)
        print(f"copied {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
