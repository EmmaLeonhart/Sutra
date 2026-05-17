"""Build the entire Sutra website: one static page.

The Sutra site used to be a ~23-page MkDocs Material site. It is now a
single static page rendered from `docs/neurips-2026.md` onto the shared
emmaleonhart.com visual identity (web/identity.css), with the paper +
reproduction-archive downloads at the top. No MkDocs, no nav, no other
pages.

Output (default `_site/`):
    index.html      rendered neurips-2026.md + download cards
    identity.css    copied from web/identity.css
    CNAME           copied from web/CNAME (pins sutra.emmaleonhart.com)

The paper PDFs and the supplementary zip are produced by the Pages
workflow and dropped into the same output dir next to index.html, so
the on-page links (/paper.pdf, /paper-anonymized.pdf,
/sutra-neurips-supplementary.zip) resolve.

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
body { display: flex; justify-content: center; padding: 92px 24px 120px; position: relative; overflow-x: hidden; }
.container { max-width: 820px; width: 100%; position: relative; z-index: 2; }
.scroll { font-size: 2.4rem; line-height: 1; }
h1 {
  font-size: clamp(2.1rem, 5.5vw, 3rem); font-weight: 700;
  margin: 16px 0 12px; letter-spacing: -1px; line-height: 1.08;
  background: linear-gradient(120deg, var(--text-strong) 0%, var(--accent-bright) 55%, var(--sutra) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.lede { font-size: 1.04rem; color: var(--text-mute); line-height: 1.65; margin-bottom: 34px; }
.downloads { display: grid; gap: 12px; margin-bottom: 56px; }
.dl { display: flex; align-items: center; gap: 16px; text-decoration: none; color: var(--text-strong); }
.dl .dl-body { flex: 1; min-width: 0; }
.dl .dl-name { font-weight: 600; font-size: 1rem; }
.dl .dl-sub { font-size: 0.85rem; color: var(--text-mute); margin-top: 3px; line-height: 1.5; }
.dl .dl-arrow { color: var(--accent); font-size: 1.2rem; flex: none; transition: transform 0.2s; }
.dl:hover .dl-arrow { transform: translateX(3px); }

/* Rendered markdown body */
.doc { color: var(--text); line-height: 1.7; }
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
.doc table {
  width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.92rem;
}
.doc th, .doc td {
  text-align: left; padding: 10px 14px; border: 1px solid var(--border);
}
.doc th { background: var(--bg-soft); color: var(--text-strong); font-weight: 600; }
.doc hr { border: none; border-top: 1px solid var(--border); margin: 40px 0; }
.foot { margin-top: 56px; font-family: var(--mono); font-size: 0.75rem; color: var(--text-faint); letter-spacing: 0.5px; }
.foot a { color: var(--text-mute); }
.foot a:hover { color: var(--accent-bright); }
@media (max-width: 600px) { body { padding: 80px 16px 80px; } }
"""

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

TOGGLE = """
  <button id="theme-toggle" class="theme-toggle" type="button" aria-label="Toggle light and dark theme" title="Toggle light / dark">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,2L14.39,5.42C13.65,5.15 12.84,5 12,5C11.16,5 10.35,5.15 9.61,5.42L12,2M3.34,7L7.5,6.65C6.9,7.16 6.36,7.78 5.94,8.5C5.5,9.24 5.25,10 5.11,10.79L3.34,7M3.36,17L5.12,13.23C5.26,14 5.53,14.78 5.95,15.5C6.37,16.24 6.91,16.86 7.5,17.37L3.36,17M20.65,7L18.88,10.79C18.74,10 18.47,9.23 18.05,8.5C17.63,7.78 17.1,7.15 16.5,6.64L20.65,7M20.64,17L16.5,17.36C17.09,16.85 17.62,16.22 18.04,15.5C18.46,14.77 18.73,14 18.87,13.21L20.64,17M12,22L9.59,18.56C10.33,18.83 11.14,19 12,19C12.82,19 13.63,18.86 14.37,18.59L12,22Z"></path></svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95M17.33,17.97C14.5,17.81 11.7,16.64 9.53,14.5C7.36,12.31 6.2,9.5 6.04,6.68C3.23,9.82 3.34,14.4 6.35,17.41C9.37,20.43 14,20.54 17.33,17.97Z"></path></svg>
  </button>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Sutra — a geometrically compiled language. The paper (PDF) and the NeurIPS 2026 reproduction archive.">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="The Sutra language paper (PDF) and the NeurIPS 2026 reproduction archive.">
  <meta property="og:url" content="https://sutra.emmaleonhart.com">
  <title>{title}</title>

  <script>(function(){{try{{var t=localStorage.getItem('theme');if(t!=='light'&&t!=='dark')t='dark';document.documentElement.setAttribute('data-theme',t);}}catch(e){{document.documentElement.setAttribute('data-theme','dark');}}}})();</script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/identity.css">
  <style>{css}</style>
</head>
<body>
  <div class="aurora" aria-hidden="true"></div>
{toggle}
  <div class="container">
    <span class="eyebrow">Sutra</span>
    <div class="scroll" aria-hidden="true">📜</div>
    <h1>{heading}</h1>
    <p class="lede">A geometrically compiled language where logical operations over vector spaces resolve at compile time into matrix multiplications. The paper and the reproduction archive:</p>
{downloads}
    <div class="doc">
{body}
    </div>
    <p class="foot">Source: <a href="https://github.com/EmmaLeonhart/Sutra">github.com/EmmaLeonhart/Sutra</a></p>
  </div>
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
    heading = "NeurIPS 2026"
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    src = repo_root / "docs" / "neurips-2026.md"
    if not src.exists():
        print(f"error: {src} not found", file=sys.stderr)
        return 1

    heading, body_md = split_title(src.read_text(encoding="utf-8"))
    body_html = markdown.markdown(
        body_md,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )

    page = HTML_TEMPLATE.format(
        title=f"{heading} — Sutra",
        css=PAGE_CSS,
        toggle=TOGGLE,
        heading=heading,
        downloads=DOWNLOAD_CARDS,
        body=body_html,
    )

    out_dir = repo_root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {out_dir / 'index.html'}")

    web = repo_root / "web"
    for name in ("identity.css", "CNAME"):
        shutil.copyfile(web / name, out_dir / name)
        print(f"copied {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
