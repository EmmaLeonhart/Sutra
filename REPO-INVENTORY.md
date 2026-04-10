# Repository Inventory

What's in this repo, what it's for, and whether it's still useful.

## Active Projects

### `Akasha-paper/`
**The main event.** Akasha language design paper for Claw4S 2026 (deadline April 20). Contains paper draft, experiment scripts (empirical initiation, binding alternatives, chain depth, sign-flip deep testing), and data from cross-substrate validation. This is where active work happens.

### `planning/`
**Akasha design documentation.** Contains:
- `akasha-spec/` — 19 individual spec documents covering everything from operations to substrate candidates
- `akasha-pivot.md` — Overview doc with conversation archive links
- `akasha-paper-strategy.md` — Strategy for the Claw4S submission
- `competition-analysis-2026-04-08.md` — Latest competitive landscape assessment

### `examples/`
**Akasha syntax examples.** Six `.ak` files demonstrating objects, methods, types, control flow, operators, and executable files.

### `many-to-many/`
**Akasha-adjacent research.** A three-part matching primitive for embedding spaces (directional selection + orthogonal projection + residual similarity). Addresses many-to-many relations that cosine similarity conflates. Perfect precision in 6/9 experiments across 3 datasets x 3 models. The dimensional decomposition approach maps directly to Akasha's "computation is geometry" philosophy.

## Locked / Reference

### `VSA-paper/`
**Published, do not touch.** The FOL discovery paper — "Latent Space Cartography Applied to Wikidata" — currently at Strong Accept on clawRxiv (post 859, v15). Contains frozen model weights, scripts, reviews, and the SKILL.md. This paper provides the empirical foundation for Akasha (86 predicates as vector ops, r=0.861, mxbai defect discovery). Locked.

### `chats/`
**Design conversation archive.** 20 markdown transcripts of Claude conversations that produced the Akasha design ideas. Covers VSA, lambda calculus, Turing completeness, cartesian closedness, HDC-JEPA, compute savings, programming languages, embedding models, entity resolution, and more.

### `DEVLOG.md`
Development log documenting the VSA reframe disaster (wholesale rewrite turned Strong Accept into Rejects, recovered by reverting), Akasha pivot, syntax decisions, repo cleanup. Contains hard-won lessons about clawRxiv and incremental changes.

## Archive (Historical, Superseded)

### `old-stuff/`
All superseded content consolidated here:

| Subdirectory | What |
|---|---|
| `vsa-paper-old/` | Former `VSA-paper/old/` — old scripts (165 files), competition analyses, `redoing-paper/` with prototype code (semantic topology, syllogism gap, taxonomic direction, Linnaean hierarchy, word2vec projections) |
| `competition-analysis/` | 11 markdown files analyzing Claw4S competitors, review patterns, organizer profiles |
| `papers/` | Earlier paper versions (economics, mxbai-undersymbolic) |
| `planning/` | Original project vision, roadmap, strategic discussion, architecture decisions |
| `mxbai-diacritic-glitch/` | Standalone demo of the mxbai [UNK] collapse defect (redundant with VSA-paper scripts) |
| `*.json` | Raw competition analysis data, review data, paper details |
| `fetch_*.py` | Scripts for fetching clawRxiv data |

## Deleted (2026-04-09)

- **`inquisitive-transformer/`** — Independent paper on novel attention mechanism with "perceptiveness" parameter. Complete (GPT-2 implementation, 5 experiments, 51 tests, CI) but reported negative result and was not Akasha-related.
- **`many-to-many/Claude.html` + `Claude_files/`** — Saved browser page, pure clutter.
- **Discord DM archive** — Purged from git history entirely.

## Summary

| Directory | Status | Akasha Relevance |
|---|---|---|
| `Akasha-paper/` | Active | Core |
| `planning/` | Active | Core |
| `examples/` | Active | Core |
| `many-to-many/` | Active | High |
| `VSA-paper/` | Locked | Foundation |
| `chats/` | Archive | High |
| `DEVLOG.md` | Reference | Medium |
| `old-stuff/` | Superseded | Historical |
