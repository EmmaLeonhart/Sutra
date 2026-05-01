"""Download reference PDFs to a gitignored cache for paper-writing context.

Why this exists:
    When the Sutra paper needs to cite or compare against another paper
    (Scallop, DeepProbLog, LTN, etc.), we read those papers locally to
    ground the comparison. The PDFs themselves do not get committed —
    see CLAUDE.md § "Reference PDFs are re-downloaded each session, not
    committed" for the IP reasoning. This script re-fetches the PDFs
    fresh from their canonical source each time it runs.

Usage:
    python scripts/fetch_reference_pdfs.py             # fetch all
    python scripts/fetch_reference_pdfs.py scallop     # fetch one by name
    python scripts/fetch_reference_pdfs.py --list      # list registered

The cache directory is `references/` at the repo root. It is gitignored
(see .gitignore). If a PDF already exists, the script overwrites it
with a fresh download — the rule is "fresh fetch every session."

Adding a new reference:
    Append an entry to REFERENCES below. Use a slug as the local
    filename (no spaces). The URL must point at a freely-accessible
    PDF — ArXiv abs/<id>/pdf URLs are the standard form.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

# Registry: slug -> (canonical URL, one-line description)
REFERENCES: dict[str, tuple[str, str]] = {
    "scallop": (
        "https://arxiv.org/pdf/2304.04812",
        "Scallop: A Language for Neurosymbolic Programming (Li et al. 2023). "
        "The closest neuro-symbolic-language peer to Sutra; Datalog-like "
        "with PyTorch integration.",
    ),
    "hdcc": (
        "https://arxiv.org/pdf/2304.12398",
        "HDCC: A Hyperdimensional Computing compiler for classification on "
        "embedded systems and high-performance computing (Pale et al. 2023). "
        "An actual HDC *compiler* — relevant peer for the 'is Sutra the only "
        "HDC compiler with practical I/O?' question.",
    ),
    "torchhd": (
        "https://arxiv.org/pdf/2205.09208",
        "Torchhd: An Open Source Python Library to Support Research on HDC and "
        "VSA (Heddes et al. 2022/2023, JMLR 24). Reference for the closest "
        "HDC library peer.",
    ),
    # Add more entries here as the paper-comparison work expands.
    # Common candidates: deepproblog, ltn, neurasp, terpret, npi.
}

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "references"


def fetch(slug: str, url: str, description: str) -> Path:
    """Download `url` to references/<slug>.pdf, overwriting any existing file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{slug}.pdf"
    print(f"Fetching {slug}: {description}")
    print(f"  source: {url}")
    print(f"  dest:   {out}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Sutra paper-fetch script)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    out.write_bytes(data)
    print(f"  bytes:  {len(data):,}")
    return out


def list_references() -> None:
    print(f"Registered references ({len(REFERENCES)}):")
    for slug, (url, desc) in sorted(REFERENCES.items()):
        print(f"  {slug:<20} {url}")
        print(f"  {'':<20} {desc}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch reference PDFs for paper comparison work.",
    )
    parser.add_argument(
        "names", nargs="*",
        help="Slug(s) to fetch. If omitted, fetch all registered references.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List registered references and exit without fetching.",
    )
    args = parser.parse_args()

    if args.list:
        list_references()
        return 0

    targets = args.names or list(REFERENCES.keys())
    unknown = [n for n in targets if n not in REFERENCES]
    if unknown:
        print(f"ERROR: unknown reference(s): {unknown}", file=sys.stderr)
        print("Run with --list to see registered references.", file=sys.stderr)
        return 1

    failures: list[tuple[str, str]] = []
    for slug in targets:
        url, desc = REFERENCES[slug]
        try:
            fetch(slug, url, desc)
        except Exception as e:
            failures.append((slug, str(e)))
            print(f"  FAILED: {e}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)}/{len(targets)} fetches failed.", file=sys.stderr)
        return 1
    print(f"\nDone: fetched {len(targets)} reference(s) into {CACHE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
