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
import sys
import time
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
    # --- Research-direction context (Emma 2026-06-16, queue incorporation) -------------
    # Downloaded for context only; analyzed, never committed (copyright).
    "schmidhuber-fki-126-90": (
        "https://people.idsia.ch/~juergen/FKI-126-90_%28revised%29bw_ocr.pdf",
        "Schmidhuber, FKI-126-90 (revised) — the 1990 'making the world "
        "differentiable' / recurrent-controller-and-model report. Seed reference "
        "for the differentiable-substrate / world-model research direction.",
    ),
    "arxiv-1802-08864": (
        "https://arxiv.org/pdf/1802.08864",
        "arXiv:1802.08864 — seed reference (Emma 2026-06-16); title/role to be "
        "confirmed from the downloaded PDF in the RC3 analysis notes.",
    ),
    "arxiv-2604-06425": (
        "https://arxiv.org/abs/2604.06425",
        "arXiv:2604.06425 — seed reference (Emma 2026-06-16); title/role to be "
        "confirmed from the downloaded PDF in the RC3 analysis notes.",
    ),
    "metauto-neuralcomputer": (
        "https://metauto.ai/neuralcomputer/",
        "MetaUto 'neural computer' page — seed reference (Emma 2026-06-16) for "
        "the neural-computer / agent research direction. HTML page, not a PDF.",
    ),
}

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "references"
_RETRIES = 3


def _normalize(url: str) -> tuple[str, str]:
    """Return (download_url, file_extension). Normalizes arXiv `/abs/<id>` to the PDF
    endpoint, and picks `.pdf` for PDF sources / `.html` for everything else (e.g. web
    pages) so the robust downloader handles non-PDF reference sources too."""
    u = url
    if "arxiv.org/abs/" in u:
        u = u.replace("/abs/", "/pdf/")
    ext = ".pdf" if (u.lower().endswith(".pdf") or "arxiv.org/pdf/" in u) else ".html"
    return u, ext


def fetch(slug: str, url: str, description: str) -> Path:
    """Download `url` to references/<slug>.<ext>, overwriting any existing file. Retries
    transient failures; normalizes arXiv abs URLs and saves non-PDF sources as .html."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dl_url, ext = _normalize(url)
    out = CACHE_DIR / f"{slug}{ext}"
    print(f"Fetching {slug}: {description}")
    print(f"  source: {dl_url}")
    print(f"  dest:   {out}")
    req = urllib.request.Request(
        dl_url,
        headers={"User-Agent": "Mozilla/5.0 (Sutra reference-fetch script)"},
    )
    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            out.write_bytes(data)
            print(f"  bytes:  {len(data):,}" + (f"  (attempt {attempt})" if attempt > 1 else ""))
            return out
        except Exception as e:  # noqa: BLE001 — retry any transient network error
            last_err = e
            print(f"  attempt {attempt}/{_RETRIES} failed: {e}", file=sys.stderr)
            if attempt < _RETRIES:
                time.sleep(2 * attempt)
    raise last_err  # type: ignore[misc]


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
