"""Fetch arXiv:2604.06425v2 into replication_target/.

The **primary** download is the arXiv LaTeX / e-print **source**
(arxiv.org/src/...). It is far more token-efficient to read than the rendered
HTML (which embeds figures as huge base64 data-URIs you would otherwise have to
strip) and the .tex files read cleanly. It is also where authors most often
ship a reproduction recipe -- a SKILL.md / AGENTS.md, a reproduce/replicate/
run.sh script, a Makefile target, a Dockerfile, or a link to a replication zip
-- usually near the end of the paper.

This script downloads the source archive, extracts it to
``replication_target/source/`` (committed), saves the PDF as a fallback /
complete record (gitignored), and prints any files that look like a
reproduction recipe so the agent can find and run it FIRST.

arXiv submissions come in a few shapes; all are handled:
  * a gzip-compressed tar (the common case: many files)  -> extracted
  * a single gzip-compressed .tex (single-file paper)    -> source/main.tex
  * a PDF-only submission (no source available)          -> paper.pdf

arXiv rate-limits (HTTP 429/503), so requests retry with backoff that honours
the Retry-After header. Stdlib only.
"""

from __future__ import annotations

import gzip
import io
import socket
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SRC_URL = "https://arxiv.org/src/2604.06425v2"
PDF_URL = "https://arxiv.org/pdf/2604.06425v2"
HTML_URL = "https://arxiv.org/html/2604.06425v2"
ARXIV_ID = "2604.06425"

_TARGET = Path(__file__).parent / "replication_target"
_SOURCE = _TARGET / "source"
_MAX_RETRIES = 4
_BASE_BACKOFF = 3.0  # arXiv asks for ~3s between requests
# Socket read timeouts come up as plain TimeoutError (3.10+) or socket.timeout
# (3.9) and are NOT a subclass of urllib.error.URLError, so they need their
# own except-clause to participate in the retry loop.
_TIMEOUT_ERRORS = (TimeoutError, socket.timeout)

# Filenames that suggest a ready-made reproduction recipe / replication asset.
_RECIPE_HINTS = (
    "skill", "agents", "reproduc", "replicat", "run.sh", "makefile",
    "dockerfile", ".zip",
)


def _retry_after(err):
    val = err.headers.get("Retry-After") if err.headers else None
    try:
        return max(0.0, float(val)) if val else None
    except ValueError:
        return None


def _get(url):
    """GET url with retry/backoff for arXiv rate limiting; return bytes."""
    backoff = _BASE_BACKOFF
    for attempt in range(_MAX_RETRIES):
        last = attempt == _MAX_RETRIES - 1
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "cleanvibe-replicate"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and not last:
                wait = _retry_after(e) or backoff
                print(f"  rate-limited (HTTP {e.code}); retrying in {wait:.0f}s")
                time.sleep(wait)
                backoff *= 2
                continue
            raise
        except (urllib.error.URLError, *_TIMEOUT_ERRORS) as e:
            if last:
                raise
            print(f"  transient error ({e!r}); retrying in {backoff:.0f}s")
            time.sleep(backoff)
            backoff *= 2
    raise AssertionError("unreachable")


def _safe_extract(tar, dest):
    """Extract ``tar`` into ``dest``, refusing any member that escapes it."""
    dest = dest.resolve()
    members = tar.getmembers()
    for m in members:
        target = (dest / m.name).resolve()
        if dest != target and dest not in target.parents:
            raise RuntimeError(f"unsafe path in archive: {m.name!r}")
    try:
        # Python 3.12+ : the hardened 'data' filter (also silences the 3.14
        # deprecation warning). Older Pythons don't accept the kwarg.
        tar.extractall(dest, filter="data")
    except TypeError:
        tar.extractall(dest)
    return members


def _extract_source(data):
    """Turn raw /src bytes into files under source/. Returns list of rel paths.

    Handles the three arXiv source shapes (gzip-tar, single gzip-tex, PDF-only).
    """
    # PDF-only submission: no source to extract; let the PDF fetch cover it.
    if data[:5] == b"%PDF-":
        print("  source is a PDF-only submission; no .tex source available")
        return []

    _SOURCE.mkdir(parents=True, exist_ok=True)

    # Most submissions: a (gz/bz2/xz) tar of the project.
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            members = _safe_extract(tar, _SOURCE)
        names = [m.name for m in members if m.isfile()]
        print(f"  extracted {len(names)} file(s) to {_SOURCE}")
        return names
    except tarfile.ReadError:
        pass

    # Single-file submission: gzip of one .tex (no tar wrapper).
    try:
        tex = gzip.decompress(data)
        out = _SOURCE / "main.tex"
        out.write_bytes(tex)
        print(f"  single-file source -> {out}")
        return ["main.tex"]
    except (OSError, EOFError):
        pass

    # Unknown container: save the raw archive so nothing is lost.
    raw = _TARGET / "arxiv-source.bin"
    raw.write_bytes(data)
    print(f"  could not recognise source container; saved raw -> {raw}")
    return []


def _flag_recipes(names):
    """Print source files whose names hint at a reproduction recipe."""
    hits = [n for n in names if any(h in n.lower() for h in _RECIPE_HINTS)]
    if hits:
        print("\n  *** candidate reproduction recipe(s) in the source — "
              "look at these FIRST: ***")
        for n in hits:
            print(f"      {n}")
    else:
        print("\n  no obvious recipe filenames in the source; grep the .tex "
              "for 'reproduc'/'replicat'/'github.com' and check the paper's end")


def _save_binary(url, out, *, optional=False):
    if out.exists() and out.stat().st_size > 0:
        print(f"already present: {out}")
        return True
    print(f"downloading {url} -> {out}")
    try:
        data = _get(url)
    except urllib.error.HTTPError as e:
        if optional:
            print(f"  skipped (HTTP {e.code})")
            return False
        raise
    out.write_bytes(data)
    print(f"  wrote {out.stat().st_size} bytes")
    return data


def main() -> int:
    _TARGET.mkdir(parents=True, exist_ok=True)

    # 1) The LaTeX/e-print source — primary, token-efficient, recipe-bearing.
    if _SOURCE.exists() and any(_SOURCE.iterdir()):
        print(f"source already extracted: {_SOURCE}")
    else:
        print(f"downloading source {SRC_URL}")
        try:
            data = _get(SRC_URL)
            # Keep the raw archive too (gitignored) for provenance.
            (_TARGET / "arxiv-source.tar.gz").write_bytes(data)
            names = _extract_source(data)
            _flag_recipes(names)
        except urllib.error.HTTPError as e:
            print(f"  source unavailable (HTTP {e.code}); relying on the PDF")

    # 2) The PDF — fallback / complete visual record.
    _save_binary(PDF_URL, _TARGET / "paper.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
