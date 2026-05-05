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
- 1098 lines of `paper.md`; 9 body pages + references + 9
  appendices (A–I) by the latest `paper-pdf.yml` build.
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
The work below is paper polish only. No structural changes; the
abstract is locked, the body argument is intact, the figures
build, and reviewers have stabilized at Accept / Strong Accept
since v23.

- [ ] **Strengthen §6 Limitations.** It's currently 8 lines (just
  §6.1 codebook integration depth). Latest reviewer (v43) flagged
  four cons that the body acknowledges scattered across §3.2.1
  and §3.6 but §6 doesn't surface honestly:
  - Capacity ceiling: bundle decoding collapses by k≈8 on the
    weakest substrates; chain capacity drops to chance by L=8
    (§3.2.1 has the per-substrate sweep).
  - Evaluation scope: 992 words / K=20 is the largest end-to-end
    program; SE-scale benchmarks are future work.
  - Synthetic-dim allocation is fixed at compile time today
    (acknowledged elsewhere; should also surface in §6 as a
    revisitable design knob).
  - No head-to-head vs. a standard NN architecture on a complex
    benchmark — the K=20 result is the largest claim.

  Add §6.2 / §6.3 / §6.4 covering these honestly. **Do not touch
  the abstract.**

- [ ] **End-to-end pre-submission read of `paper.md`.** Cover-to-
  cover pass for typos, broken `\ref{}`s, inconsistent numbers
  across body and abstract, and stale claims. Specifically check
  that §3.6 numbers (4% → 95%, 50/300 epochs, 992 words, K=20)
  match the abstract verbatim, §3.2 capacity numbers match (100%
  through k=8; Hadamard 2.5% on mxbai, 7.5% on minilm, 28.7% on
  ESM-2 in the long abstract / 2.5% in body), and every appendix
  citation lands on a real label.

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
