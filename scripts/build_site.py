"""Build the Sutra website.

The Sutra site used to be a ~23-page MkDocs Material site. It is now
two static pages on the shared emmaleonhart.com visual identity
(web/identity.css), each rendered from a Markdown source:

    /                 docs/index.md          — what Sutra is (homepage)
    /neurips-2026/    docs/neurips-2026.md   — frozen-submission archive

No MkDocs, no nav generation, no other pages. The NeurIPS page is NOT
linked from the homepage — it is reachable by direct URL. The paper
PDFs and the supplementary zip are produced by the Pages workflow and
dropped into the output root, so the links on the NeurIPS page
(/paper.pdf, /paper-anonymized.pdf, /sutra-neurips-supplementary.zip)
resolve.

Output (default `_site/`):
    index.html
    neurips-2026/index.html
    identity.css      copied from web/identity.css
    CNAME             copied from web/CNAME (pins sutra.emmaleonhart.com)

Usage:
    python scripts/build_site.py [--output _site]
"""
from __future__ import annotations

import argparse
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
main { position: relative; z-index: 2; flex: 1; display: flex; justify-content: center; padding: 72px 28px 100px; }
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
.downloads { display: grid; gap: 12px; margin-bottom: 56px; }
.dl { display: flex; align-items: center; gap: 16px; text-decoration: none; color: var(--text-strong); }
.dl .dl-body { flex: 1; min-width: 0; }
.dl .dl-name { font-weight: 600; font-size: 1rem; }
.dl .dl-sub { font-size: 0.85rem; color: var(--text-mute); margin-top: 3px; line-height: 1.5; }
.dl .dl-arrow { color: var(--accent); font-size: 1.2rem; flex: none; transition: transform 0.2s; }
.dl:hover .dl-arrow { transform: translateX(3px); }
.links { display: flex; flex-wrap: wrap; gap: 12px; margin: 34px 0 8px; }
.links a {
  font-family: var(--mono); font-size: 0.84rem; font-weight: 500;
  text-decoration: none; color: var(--accent); padding: 10px 18px;
  border: 1px solid var(--border-hover); border-radius: 8px;
  background: var(--accent-soft); transition: all 0.2s;
}
.links a:hover { color: var(--accent-bright); border-color: var(--accent); transform: translateY(-1px); }

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
footer {
  position: relative; z-index: 2; padding: 24px 28px;
  border-top: 1px solid var(--border);
  font-family: var(--mono); font-size: 0.72rem; letter-spacing: 1px;
  color: var(--text-faint);
}
@media (max-width: 600px) {
  .topbar { padding: 16px 18px; }
  main { padding: 56px 20px 76px; }
}
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

GH_JS = """<script>
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


def shell(title: str, inner: str) -> str:
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
  {GH_JS}
  <script>
    (function(){{
      var b=document.getElementById('theme-toggle');
      if(b)b.addEventListener('click',function(){{var c=document.documentElement.getAttribute('data-theme')==='light'?'light':'dark';var n=c==='light'?'dark':'light';document.documentElement.setAttribute('data-theme',n);try{{localStorage.setItem('theme',n);}}catch(e){{}}}});
    }})();
  </script>
</body>
</html>
"""


def split_title(md_text: str) -> tuple[str, str]:
    """Pull the leading `# H1` off the markdown; return (heading, rest)."""
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


def render_md(path: Path) -> tuple[str, str]:
    heading, body_md = split_title(path.read_text(encoding="utf-8"))
    body_html = markdown.markdown(
        body_md,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )
    return heading, body_html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    docs = repo_root / "docs"
    home_src = docs / "index.md"
    neurips_src = docs / "neurips-2026.md"
    for p in (home_src, neurips_src):
        if not p.exists():
            print(f"error: {p} not found", file=sys.stderr)
            return 1

    out_dir = repo_root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    # Homepage — what Sutra is. No downloads, no NeurIPS link.
    home_heading, home_body = render_md(home_src)
    home_inner = f"""    <span class="eyebrow">Sutra</span>
    <div class="scroll" aria-hidden="true">📜</div>
    <h1>{home_heading}</h1>
    <div class="doc">
{home_body}
    </div>
    <div class="links">
      <a href="https://github.com/EmmaLeonhart/Sutra">View source on GitHub</a>
      <a href="https://github.com/EmmaLeonhart/Sutra/releases">Releases &amp; downloads</a>
      <a href="https://emmaleonhart.com/projects/">All projects</a>
    </div>
"""
    (out_dir / "index.html").write_text(
        shell("Sutra — a geometrically compiled language", home_inner),
        encoding="utf-8",
    )
    print(f"wrote {out_dir / 'index.html'}")

    # NeurIPS 2026 archive at /neurips-2026/ — preserved, direct-URL
    # only (intentionally not linked from the homepage).
    np_heading, np_body = render_md(neurips_src)
    np_inner = f"""    <a class="back" href="/">&larr; Sutra home</a>
    <span class="eyebrow">Sutra</span>
    <h1>{np_heading}</h1>
    <p class="lede">The immutable record of the Sutra paper as submitted to NeurIPS 2026. Downloads:</p>
{DOWNLOAD_CARDS}
    <div class="doc">
{np_body}
    </div>
"""
    neurips_dir = out_dir / "neurips-2026"
    neurips_dir.mkdir(parents=True, exist_ok=True)
    (neurips_dir / "index.html").write_text(
        shell(f"{np_heading} — Sutra", np_inner), encoding="utf-8"
    )
    print(f"wrote {neurips_dir / 'index.html'}")

    web = repo_root / "web"
    for name in ("identity.css", "CNAME"):
        shutil.copyfile(web / name, out_dir / name)
        print(f"copied {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
