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

Current paper state (post-abstract-submission, 2026-05-06):
- Latest build (`paper-pdf.yml` run 25409986512): **20 total PDF
  pages** — **9 body pages, 1 reference page, 10 appendix pages
  (A–J)**. References starts on page 10. NeurIPS 9-page body cap
  met as of commit `e30ca6b`.
- The earlier queue claim of "9 body pages" was stale — the
  actual prior state was 10. Bringing body to 9 took two cuts:
  (a) `fig:compile-pipeline` moved to Appendix J, and (b) §5/§6/§7
  prose tightened to pull §7 conclusion onto page 9.
- Two TikZ figures still in body: `fig:halt-cell` (§3.4),
  `fig:k3-pipeline` (§3.6).
- 70+ inline/display math expressions render correctly via
  pandoc `markdown-smart` → lualatex.
- `paper-pdf.yml` and `papers-ci.yml` both green on master.
  CI is unusually slow today (3-15min vs the usual 1.5min).
- Latest review (v44, 2026-05-06, post 2358): **Accept** (down
  one step from v43 Strong Accept after my reverted §6 expansion;
  reviewer cons unchanged from v43, so the §6 expansion didn't
  move the reviewer's mind but did cost a page).

## Active

Time remaining: ~36 hours to May 6 AOE (≈ May 7 12:00 UTC).
Body is at 9 pages; abstract is locked; reviewers stabilized at
Accept / Strong Accept since v23. Pre-submission state is
acceptable as-is. Optional polish below.

- [ ] **Optional: address v44 reviewer's new "soft-halt gradient
  vanishing/explosion" concern in §3.4 prose.** v44 raised this
  as a NEW con (v43 didn't flag it). The §3.4 prose mentions
  autograd records each iteration as it executes but doesn't say
  anything about the gradient stability of the soft-mux freeze.
  Could add one or two sentences to §3.4 noting that the §3.6
  K=20 result (gradient norms 0.94–4.20 across all twenty
  prototypes through 300 epochs of nineteen-AND-deep rule
  pipelines) is the strongest empirical evidence we have against
  pathological gradient flow through the cell. ~3 lines, doesn't
  push back over the 9-page cap.

- [ ] **Optional: add a one-sentence pointer to MNIST-Addition /
  CLEVR-Hans benchmarks in §6 as future work.** v44 specifically
  named these as the standard neuro-symbolic benchmarks Sutra
  doesn't compare against. Acknowledging them by name in §6
  would address the reviewer's specific phrasing without
  changing the substantive evaluation. ~1 line.

## Open issues to address (not blocking paper deadline)

- **SutraDB FFI tests fail locally because `sutra_ffi.dll` isn't
  built.** `tests/test_sutradb_embedded.py` raises
  `FileNotFoundError`. Fix locally with
  `cd sutraDB && cargo build --release -p sutra-ffi`. All other
  245+ tests pass without this. Carries no paper-submission
  weight; fix when convenient.

## Done this sprint (2026-05-05 → 2026-05-06)

- **Abstract + title submitted to NeurIPS.** Title in commit
  `65e0fb0`, abstract in commit `84f3465`; both frozen per
  CLAUDE.md.
- **Real LaTeX math + TikZ diagrams in `paper.md`.** Emma's three
  May-6 asks (diagrams of runtime behavior, formal notation,
  worked beta-reduction) satisfied. 70+ math expressions; three
  TikZ figures (halt-cell, K=3 pipeline, compile pipeline).
- **Body actually at 9 pages.** Two cuts landed 2026-05-06:
  `fig:compile-pipeline` moved to a new Appendix J (commit
  `9f642f2`), and §5 / §6 / §7 prose tightened to pull the
  conclusion onto page 9 (commit `e30ca6b`). PDF at run
  25409986512 confirms References on page 10.
- **SKILL.md "13-program smoke test" → "10-program"** to match
  body §5 and Appendix I (the actual `_smoke_test.py` has
  exactly 10 `run_*` functions). Commit `131d4c7`.
- **clawRxiv review trajectory v20→v44.** Stable at Accept /
  Strong Accept since v23. v44 (2026-05-06): Accept (one step
  down from v43's Strong Accept); cons unchanged.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
