# NeurIPS 2026 — submission archive

This directory holds the version of the Sutra paper as it was
submitted to NeurIPS 2026 — the camera-ready snapshot used to build
the downloadable artifacts. The permanent, immutable record is the
git commit `ea6f8a01` (history never changes); the files here track
it as a working copy.

**The edit-freeze was retired 2026-06-18** (Emma: "give up on the
NeurIPS freeze, it's been causing more harm than good"). These files
may now be edited to fix factual drift — license, identity, stale
descriptions, broken references — keeping the archive honest rather
than frozen-wrong. Substantive corrections are logged as errata on
the website page (`docs/neurips-2026.md`). Do **not** rewrite the
submitted science to look better; do correct things that are now
factually false. `paper/paper.md` remains the separate next-venue
revision target. See `CLAUDE.md` § "NeurIPS freeze is LIFTED".

## What's in here

| File | Purpose |
|------|---------|
| `paper.md` | The camera-ready paper source (markdown), as submitted. |
| `paper.tex` | LaTeX wrapper that pandoc-builds `paper.md` into the PDF, as submitted. |
| `neurips_2026.sty` | Official NeurIPS 2026 style file (verbatim from the conference). |
| `supplementary/README.md` | Reviewer-facing doc explaining the supplementary archive's layout. |
| `supplementary/SKILL.md` | Agent-runnable replication skill — the reproduction recipe. |
| `supplementary/REPRODUCE.md` | Human-facing reproduction instructions. |
| `supplementary/SYNTAX.md` | Surface-syntax reference for the `.su` programs the paper cites. |

The supplementary **zip** that was uploaded to OpenReview is built
from `supplementary/` plus the wider repo state at submission time
by `scripts/build_supplementary_zip.py`. The zip itself is a build
artifact (not committed) — re-run the script to regenerate.

## Built PDFs

`paper-pdf.yml` builds two PDFs from `paper/paper.tex` (the live
copy) on every push to `paper/`. A future CI job can also build
PDFs from `paper/neurips/paper.tex` (this directory's frozen
version) and upload them as separate artifacts:

- `paper-neurips-named.pdf` — camera-ready, author-named version
- `paper-neurips-anonymized.pdf` — double-blind reviewer version
- `sutra-neurips-supplementary.zip` — the reproduction archive

## Why split this from the live `paper/paper.md`

Per Emma 2026-05-10:

> "There should be a part on our website that allows you to
> download the camera-ready version of the NeurIPS one … and the
> anonymized version and the zip file that was actually submitted
> with NeurIPS. … because we've split it off, the GitHub actions
> will build the NeurIPS stuff. The NeurIPS stuff is its own
> directory, basically, and then we can be free to potentially do
> updates to our paper with their own language, with our own
> stuff."

The live `paper/paper.md` may evolve toward the next venue (e.g. a
journal extension). The NeurIPS version stays here as the historical
record of what was actually submitted, and downloadable from the
website at `/neurips-2026/` for anyone who wants to verify the
record.
