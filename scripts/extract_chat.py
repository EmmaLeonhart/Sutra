"""
Extract a Claude.ai web-chat HTML export (dropped in chats/*.html) into
a clean markdown file next to it.

Usage:
    python scripts/extract_chat.py "chats/Some Title - Claude.html"
    python scripts/extract_chat.py  # extracts any *.html in chats/ with
                                    # no matching .md sibling

The Claude.ai export uses class markers `font-user-message` for user
turns and `font-claude-response` for assistant turns. Everything else
(sidebar, recents list, etc.) is chrome and should be dropped.

The output filename is slugified from the HTML title ("Some Title").
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


def slugify(s: str) -> str:
    s = re.sub(r"\s*-\s*Claude\s*$", "", s.strip())
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip()).lower()
    return s[:80] or "chat"


class BlockExtractor(HTMLParser):
    """Extract visible text from a fragment of HTML, preserving paragraph
    breaks and code blocks."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.in_code = 0
        self.in_pre = 0

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre += 1
            self.parts.append("\n```\n")
        elif tag == "code" and not self.in_pre:
            self.in_code += 1
            self.parts.append("`")
        elif tag in ("p", "br", "div", "li"):
            self.parts.append("\n")
        elif tag in ("ul", "ol"):
            self.parts.append("\n")
        elif tag == "h1":
            self.parts.append("\n# ")
        elif tag == "h2":
            self.parts.append("\n## ")
        elif tag == "h3":
            self.parts.append("\n### ")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre -= 1
            self.parts.append("\n```\n")
        elif tag == "code" and not self.in_pre:
            self.in_code -= 1
            self.parts.append("`")
        elif tag in ("p", "div", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_blocks(html: str, marker: str) -> list[str]:
    """Find all top-level div openings whose class contains `marker`,
    then scan forward balancing <div>...</div> to capture the full block."""
    blocks: list[str] = []
    # Match opening div tag containing the marker in its class attribute.
    for m in re.finditer(
        rf'<div[^>]*class="[^"]*{re.escape(marker)}[^"]*"[^>]*>', html
    ):
        start = m.end()
        depth = 1
        i = start
        while i < len(html) and depth > 0:
            nxt_open = html.find("<div", i)
            nxt_close = html.find("</div>", i)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                i = nxt_open + 4
            else:
                depth -= 1
                i = nxt_close + 6
        blocks.append(html[start : i - 6])
    return blocks


def to_markdown(block: str) -> str:
    e = BlockExtractor()
    e.feed(block)
    return clean("".join(e.parts))


def extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    if not m:
        return "chat"
    return m.group(1).strip()


def extract_one(path: Path, force: bool = False) -> Path | None:
    html = path.read_text(encoding="utf-8", errors="ignore")
    title = extract_title(html)
    slug = slugify(title)
    out = path.parent / f"{slug}.md"
    if out.exists() and not force:
        print(f"SKIP {path.name}: {out.name} already exists", file=sys.stderr)
        return None

    user_blocks = extract_blocks(html, "font-user-message")
    assistant_blocks = extract_blocks(html, "font-claude-response")
    print(f"  {path.name}: {len(user_blocks)} user, "
          f"{len(assistant_blocks)} assistant blocks")
    if not user_blocks and not assistant_blocks:
        print(f"  WARNING: no message blocks found in {path.name}",
              file=sys.stderr)
        return None

    out_lines: list[str] = [f"# {re.sub(r' - Claude$', '', title)}", ""]
    out_lines.append("*Extracted from Claude.ai chat.*")
    out_lines.append("")

    # Interleave — typical Claude.ai chats alternate user -> assistant.
    n = max(len(user_blocks), len(assistant_blocks))
    for i in range(n):
        if i < len(user_blocks):
            out_lines.append("## User")
            out_lines.append("")
            out_lines.append(to_markdown(user_blocks[i]))
            out_lines.append("")
        if i < len(assistant_blocks):
            out_lines.append("## Claude")
            out_lines.append("")
            out_lines.append(to_markdown(assistant_blocks[i]))
            out_lines.append("")

    out.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"  wrote {out}")
    return out


def main():
    args = sys.argv[1:]
    if args:
        for p in args:
            extract_one(Path(p), force=True)
    else:
        chats_dir = Path("chats")
        for html_path in sorted(chats_dir.glob("*.html")):
            extract_one(html_path, force=False)


if __name__ == "__main__":
    main()
