# Repo audit — 2026-04-13

Per STATUS.md queue item. Walk every top-level directory and ask: is this needed for the two Claw4S 2026 papers (`fly-brain-paper/`, `sutra-paper/`)? What's dead weight? What can go?

The answer is mostly "keep, scoped for different purposes" — this repo hosts the two papers plus their substrate (fly-brain + Sutra compiler), the Sutra language itself, a sibling project (SutraDB), and the docs site. The overall shape is intentional. The specific dead-weight candidates are called out in bold.

## Paper-load-bearing (must keep)

- **`fly-brain-paper/`** — paper.md + reviews/ + SKILL.md. One of the two Claw4S submissions.
- **`sutra-paper/`** — paper.md + reviews/ + scripts/ + data/. The other submission.
- **`fly-brain/`** — the Drosophila hemibrain + FlyWire substrate. Every experiment cited in fly-brain-paper runs out of this directory. After the 2026-04-13 cleanup pass it holds ~15 paper-load-bearing `.py` files plus connectome data. `ROTATION-MANIFEST.md` documents which rotation script does what; consult before adding new `real_rotation_*.py` variants (see CLAUDE.md "Avoiding fly-brain Python sprawl").
- **`sdk/sutra-compiler/`** — the Sutra compiler. Emits Python that calls `fly-brain/vsa_operations.py`. Both papers cite `.su` programs compiled through this. Load-bearing.
- **`planning/`** — design docs, findings, open questions, competition analysis. Referenced throughout both papers (especially `planning/sutra-spec/` and `planning/findings/`). Load-bearing.
- **`examples/`** — `.su` example programs. Small (~10 files). Paper cites them in the language-surface sections. Keep.
- **`scripts/`** — `extract_chat.py`, `fetch_reviews.py`, `fetch_top_papers.py`, `fetch_all_papers.py`, `competition_*.json`. Used for chat extraction (see CLAUDE.md) and clawRxiv review fetching. Keep.
- **`chats/`** — archived claude.ai design conversations (HTML + extracted .md). Sutra-paper §7.2 explicitly cites these as archived design conversations. Keep. 31 files.

## Sibling projects (keep, not paper-load-bearing)

- **`sutraDB/`** — Rust RDF-star triplestore with HNSW vector indexing. 283 tracked files. Separate project with its own Cargo.toml, README, CI. Not cited by either 2026 paper, but (a) shares the Sutra name for coherent branding, and (b) is the planned execution backend for compiled-Sutra HNSW codebook operations (snap, cone, hop). Keep. Its internal `todo.md` has been merged into the root `todo.md` per STATUS.md.
- **`many-to-many/`** — 12 tracked files, separate paper + scripts + CLAUDE.md. A separate research thread the user has running in parallel. Not part of the Claw4S 2026 submissions but co-located for convenience. Keep.

## Docs site (keep, but narrow)

- **`docs/`** — source of the public sutra.dev-style docs site: `architecture.md`, `history.md`, `index.md`, `papers.md`, `vision.md`, plus `interactive/` and `tutorials/` subdirs. Referenced from `_site/`. Keep.
- **`_site/`** — generated static site, gitignored. 0 tracked files. Not in repo, no action.

## Non-tracked caches and build output

- `_site/`, `fly-brain/__pycache__/`, `fly-brain/flywire_data/` (the 74 MB working mirror of the connectome, gitignored — authoritative copy lives outside the repo at `C:\Users\Immanuelle\flybrain\` per CLAUDE.md), all `*.pyc`, `.venv/`. No audit action.

## Dead-weight candidates (considered, mostly nothing to cut)

- **Root-level transcript / session artifacts.** Earlier sessions dumped paralysis-transcript files (`dddd`) or session-resumption markers at the repo root. `git status` is clean as of the current commit; none linger. If one reappears, remove on sight.
- **Chat HTML files with no extracted `.md` sibling.** `chats/Clean up orphaned directories and resolve peer review issues _ Claude Code.html` parsed to 0 user / 0 assistant blocks in today's extraction run — it appears to be a Claude Code session transcript in a format `extract_chat.py` doesn't parse, not a claude.ai chat. **Candidate to delete** once confirmed it has no unique content, or leave alone if the user wants the raw HTML preserved.
- **`fly-brain/ROTATION-MANIFEST.md`.** Exists because of the historical `real_rotation_*.py` sprawl. Now that the family is pruned and the manifest is the index, it's load-bearing as long as any `real_rotation_*.py` files remain (currently several). Keep.
- **Old `competition-analysis-*.md` snapshots in `planning/`.** Five dated competition-analysis files plus `competition-analysis-latest.md`. These are session-frozen context about the Claw4S field. Not referenced from papers. Could be archived into `planning/archive/` post-submission to de-clutter `planning/` root, but they're small and cheap to keep until then.
- **Zero-inbound `test_*.py` files under `fly-brain/`.** CLAUDE.md flagged these as a failure mode (tests that no runner discovers). A pass through `fly-brain/test_*.py` to delete or wire into a runner is worth doing — but it's mechanical hygiene, not paper-blocking. Punt until after the paper deadline.

## Bottom line

Everything tracked in this repo is either (a) directly cited by one of the two 2026 papers, (b) the substrate/compiler infrastructure those papers depend on, (c) a sibling project the user is co-locating intentionally, or (d) the docs site. No large dead directories. Specific small-scale pruning opportunities (one unparseable chat HTML, orphan `fly-brain/test_*.py` files, old competition snapshots) are noted above but none are urgent. The main ongoing hygiene discipline is preventing `fly-brain/` from re-sprawling — codified in CLAUDE.md "Avoiding fly-brain Python sprawl" — not wholesale deletion.
