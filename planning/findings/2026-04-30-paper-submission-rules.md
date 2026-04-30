# 2026-04-30 — Paper submission rules audit

**Per queue.md item 1, sub-item 1a.** First-pass audit of
submission rules for the three target venues. Marked **VERIFY**
where a deadline or rule needs current-year confirmation; marked
**KNOWN** where we have direct repo evidence from previous Claw4S
sprints.

## Target 1 — Claw4S workshop / clawRxiv preprint server

### Format

- **KNOWN:** clawRxiv accepts Markdown (`paper/paper.md` with
  `## Abstract` extracted). The paper-submit script
  (`scripts/paper_submit_and_fetch.py`, recovered from
  `903308e^`) POSTs `{title, abstract, content, tags,
  human_names, skill_md, supersedes?}` to
  `https://clawrxiv.io/api/posts`.
- **KNOWN:** SKILL.md is a per-paper agent-facing skill
  description; the submit endpoint accepts it as a `skill_md`
  payload field.
- **KNOWN:** `Skip-Submit: true` commit message trailer prevents
  the auto-submit workflow from re-firing on its own commits.
- **KNOWN:** Each paper has a `.post_id` file recording its
  clawRxiv post number; updates to an existing paper pass that
  number as `supersedes`.

### Deadlines

- **VERIFY:** Claw4S 2026 workshop deadline — previous repo had a
  2026-04-20 deadline (per the now-deleted `claw4s-scope.md`).
  That deadline has passed; check the next round.
- **VERIFY:** clawRxiv has rolling submission, no fixed deadline.

### Anonymization

- **KNOWN:** clawRxiv preprints are NOT anonymized. Author names
  go in `human_names` field.

### Reproducibility

- **KNOWN:** Reproducibility is via the `skill_md` field — the
  SKILL.md document is the agent-runnable reproduction recipe.
- **KNOWN:** No separate "reproducibility checklist" form.

### CI integration

- **READY:** `.github/workflows/papers-ci.yml` (this commit's
  rewrite) auto-submits `paper/paper.md` on push.
- **READY:** `CLAWRXIV_API_KEY` repo secret confirmed still
  configured per Emma 2026-04-30.

## Target 2 — NeurIPS main conference

### Format

- **VERIFY:** NeurIPS 2026 author guide / paper template URL.
  Past years used `neurips_YYYY.sty` LaTeX template; check the
  current year's. The template typically locks page count
  (~9 pages for main + appendices), font, line spacing, citation
  style.
- **READY:** `paper/paper.tex` is a skeleton with anon macros
  (`\ifanon` switch); template-specific styling deferred until
  the year's `.sty` is in hand.

### Deadlines

- **VERIFY:** NeurIPS 2026 abstract registration + full
  submission deadlines. Historically late-May for abstracts,
  early-June for full papers. Check `neurips.cc` for current
  cycle.

### Anonymization

- **KNOWN:** NeurIPS is double-blind. Anonymization rules:
  - No author names anywhere in the paper or supplementary.
  - No institution affiliations.
  - No GitHub URLs that deanonymize (e.g. `github.com/EmmaLeonhart/...`).
  - Self-citations in third person ("Leonhart [N] showed..."
    becomes "[N] showed...").
  - Acknowledgments removed from anonymized version.
- **READY:** `paper/paper.tex` `\ifanon` switch handles
  title/author/repo URL substitution. Single-source approach
  avoids two drift-prone .tex files.

### Reproducibility

- **VERIFY:** NeurIPS reproducibility checklist URL. Typically
  requires:
  - Public code link (anonymized for review; deanonymized for
    camera-ready).
  - Description of compute used.
  - Hyperparameter table.
  - Dataset access.
- **READY:** `paper/REPRODUCE.md` covers the runnable-code map;
  hardware section covers compute.

### CI integration

- **READY (skeleton):** `.github/workflows/paper-pdf.yml` (this
  commit) builds named + anonymized PDFs as workflow artifacts.
  Submission to OpenReview is manual (workflow uploads PDFs;
  human pastes into OpenReview).

## Target 3 — Post-NeurIPS workshop (TBD)

- **VERIFY:** Which workshop. Candidates:
  - NeurIPS workshops (co-located, ~December): VSA, neurosymbolic,
    program synthesis tracks all relevant.
  - ICML 2027 main or workshops (mid-2027 deadlines).
  - ICLR 2027 main (~late-2026 deadline).
- **DECISION NEEDED:** Picking the third venue depends on the
  Claw4S + NeurIPS submission outcomes (e.g. which review
  feedback to incorporate before the next submission).

## Summary of READY vs VERIFY

| Item | Status |
|---|---|
| clawRxiv submission infrastructure | READY (recovered, rewritten for `paper/`) |
| paper.md draft | READY (sub-item 1c shipped) |
| paper.tex skeleton + anon macros | READY (sub-item 1e shipped) |
| Named + anonymized PDF build CI | READY (sub-item 1d shipped) |
| REPRODUCE.md | READY (sub-item 1f shipped) |
| SKILL.md (agent reproduction) | READY |
| Claw4S 2026 next-round deadline | VERIFY |
| NeurIPS 2026/27 author guide URL + template | VERIFY |
| NeurIPS reproducibility checklist | VERIFY |
| Post-NeurIPS workshop target | DECISION NEEDED |

The READY items are all in place for the next clawRxiv push.
The VERIFY items can wait until the user has confirmed deadline
URLs to fetch.

## Open question: paper title

Today (2026-04-30) the paper title is "From Learned Displacements
to Learned Matrices: Sutra, a Programming Language for Vector-
Symbolic Computation in Frozen Embedding Spaces." This:

- Names the research arc (the three steps).
- Pitches the language (Sutra) as the realization.
- Is honest that step 3 (learned matrices) is the trajectory,
  not a finished result.

For NeurIPS double-blind, the anonymized version drops "Sutra" —
it could deanonymize. The skeleton already handles this.
