# redoing-paper

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Do not enter planning-only modes.** All thinking must produce files and commits. If scope is unclear, create a `planning/` directory and write `.md` files there instead of using an internal planning mode.
- **Keep this file up to date.** As the project takes shape, record architectural decisions, conventions, and anything needed to work effectively in this repo.
- **Update README.md regularly.** It should always reflect the current state of the project for human readers.

## Project Description
Reworking a neurosymbolic AI paper (`old-paper/`) that suffered from sloppy methodology. The original draft had significant problems with citations — many were hallucinated, excessive, or not ones the author actually sourced. This repo is a clean start to salvage the real work and produce a rigorous paper.

## Critical Rules for This Paper
- **NEVER hallucinate citations.** Do not invent references, DOIs, author names, or paper titles. If a claim needs a citation and we don't have one, mark it with `[CITATION NEEDED]` instead.
- **Only use citations the author has explicitly provided or verified.** Do not add references "for completeness" or because they seem relevant.
- **Less is more with references.** A small number of real, verified citations is infinitely better than a padded bibliography.
- **Flag uncertain claims.** If something reads like it needs a source but we don't have one, say so openly rather than papering over it.

## Architecture and Conventions
- `old-paper/` — subtree import of the original draft (read-only reference, do not modify)
- `sources/verified.md` — the single source of truth for citable references. A paper must be listed here before it can be cited.
- New work goes in the repo root as the project takes shape

# currentDate
Today's date is 2026-03-11.
