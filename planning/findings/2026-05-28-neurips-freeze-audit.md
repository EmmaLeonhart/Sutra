# 2026-05-28 — `paper/neurips/` freeze audit (Emma sweep Q1)

Audit triggered by Emma sweep 2026-05-28 Q1 answer "Both — carve-out + audit": verify that no non-identity drift slipped through `paper/neurips/` between the freeze date (2026-05-10) and now.

## Audit method

```
git log --since="2026-05-10" --until="2026-05-29" --oneline --name-only -- paper/neurips/
```

## Result — ONE COMMIT

| commit | date | files touched | identity? | substantive? |
|---|---|---|---|---|
| `599424f8` | 2026-05-24 | `paper/neurips/paper.tex` | YES — contact email standardization (`contact@emmaleonhart.com`) | NO |

That's the entirety of `paper/neurips/` touches since freeze. The freeze rule held — no substantive drift slipped through.

## Carve-out added to CLAUDE.md

Per Emma's Q1 answer, the CLAUDE.md NeurIPS freeze rule now codifies a **project-wide identity changes** carve-out. The rule still blocks substantive paper edits, reviewer-response edits, finding-driven edits, typo fixes inside the paper body, and anything that changes what the paper claims. It only allows identity metadata (author contact email, `.mailmap` consolidation, repository username changes) to flow into `paper/neurips/` without re-asking.

`599424f8` is now the canonical example of the carve-out.

## What this audit does NOT do

- It does NOT review `paper/paper.md` (the live paper) — that has its own (time-bounded) freeze through May 31; arXiv-v2 corrections have been touching it under explicit Emma authorization, which is a separate workflow.
- It does NOT audit `paper/formal-verification/paper.md` — that paper is explicitly live + free to evolve per CLAUDE.md.
- It does NOT review changes to `docs/neurips-2026.md` — that's the user-facing download page, not the frozen archive.

## Closure

Audit #1 from queue.md State Inventory B (now relocated to section "Emma decisions LANDED 2026-05-28") is **closed clean**. The carve-out is in CLAUDE.md; the audit confirms no other drift; the rule going forward is the carve-out + the existing freeze.
