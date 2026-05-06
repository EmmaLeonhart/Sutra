# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the
**stuff being worked on right at this moment**. Finished work
lives in `git log` and `planning/findings/`; longer-horizon
work lives in `todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task
tool stay in sync.

## Sprint: NeurIPS 2026 full-paper deadline (May 6 AOE)

**Abstract is submitted.** Title and abstract frozen per
CLAUDE.md §"Title and abstract are FROZEN — submitted to
NeurIPS." Body remains editable.

Current paper state (post-abstract-submission, 2026-05-05):
- 1098 lines of `paper.md`. Latest build (`paper-pdf.yml` run
  25375551372 on commit `21c8b21`): **20 total PDF pages** —
  10 body pages, 1 reference page, 9 appendix pages (A–I).
- ⚠️  **Body is currently 10 pages, NeurIPS hard cap is 9.** A
  prior queue.md note claimed body was 9 pages but actual PDF
  measurement places References on page 11. The 70+ math
  expressions and three TikZ figures landed earlier this sprint
  pushed body 1 page over without anyone noticing. Fix needed
  before the May-6 submission.
- Three TikZ figures in body: `fig:halt-cell` (§3.4),
  `fig:k3-pipeline` (§3.6), `fig:compile-pipeline` (§4).
- 70+ inline/display math expressions render correctly via
  pandoc `markdown-smart` → lualatex.
- `paper-pdf.yml` build is green on every push since 2026-05-04;
  `papers-ci.yml` auto-submission to clawRxiv is also green.
- Latest review (v43, 2026-05-05 12:11 UTC, post 2356):
  **Strong Accept**.

## Active

Time remaining: ~45–48 hours to May 6 AOE (≈ May 7 12:00 UTC).
Body argument is intact, figures build, reviewers stabilized at
Accept / Strong Accept since v23. Two real items remain.

- [ ] ⚠️  **Cut body from 10 pages to 9.** NeurIPS hard cap is 9
  content pages; refs and appendix unlimited. This pre-existed
  the current sprint but the queue's "9 pages" claim was stale.
  Decision needed on which lever:
  - **(a)** Move `fig:compile-pipeline` (§4) to appendix. The
    figure is a flowchart of the five-stage compile pipeline and
    is essentially redundant with the prose right above it.
    Lowest-cost cut; saves ~⅓ page of vertical space.
  - **(b)** Move `fig:halt-cell` (§3.4) to appendix. Figure is
    illustrative but the prose stands on its own. Saves another
    ~⅓ page.
  - **(c)** Trim §3.6 prose around the K=20 result. Some of the
    rule-graph walk-through could compress.
  - **(d)** Trim §1.1 contribution #2's TNF defense + §2.3's
    differentiable-programming/AOT compilation comparisons.
  - **(e)** Some combination of the above.

  Need to land on something that produces a build with References
  starting on page 10 or earlier.

- [ ] **End-to-end pre-submission read of `paper.md`.** Mostly
  done as of 2026-05-05 — all `\ref{}` resolve, all abstract↔body
  numbers match (§3.6: 4%→95%, 50/300 epochs, 992 words, K=20;
  §3.2: 100% through k=8, Hadamard 2.5% on mxbai / 7.5% on minilm
  / 28.7% on ESM-2; round-trip 1.5×10⁻¹⁵). One inconsistency
  fixed: SKILL.md said "13-program smoke test" but actual is 10
  (matches body §5 / Appendix I).

## Open issues to address (not blocking paper deadline)

- **SutraDB FFI tests fail locally because `sutra_ffi.dll` isn't
  built.** `tests/test_sutradb_embedded.py` raises
  `FileNotFoundError`. Fix locally with
  `cd sutraDB && cargo build --release -p sutra-ffi`. All other
  245+ tests pass without this. Carries no paper-submission
  weight; fix when convenient.

## Done this sprint (2026-05-05)

- **Abstract + title submitted to NeurIPS.** Title in commit
  `65e0fb0`, abstract in commit `84f3465`; both frozen per
  CLAUDE.md.
- **Real LaTeX math + TikZ diagrams in `paper.md`.** Emma's three
  May-6 asks (diagrams of runtime behavior, formal notation,
  worked beta-reduction) are satisfied with rendering, not just
  in form. 70+ math expressions; three real TikZ figures
  (halt-cell, K=3 pipeline, compile pipeline). lualatex render
  verified via the `paper-pdf.yml` CI pipeline.
- **Body trimmed to 9 pages.** Latest rendered PDF: 9 body + 1
  reference + 9 appendix = 19 total. References at p.10,
  Appendix A–I at pp.11–19.
- **clawRxiv review trajectory v20→v43.** Stable at Accept /
  Strong Accept since v23. v43 (today): Strong Accept by
  Gemini 3 Flash. Reviewer cons map onto the §6 Limitations
  strengthening item above.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
