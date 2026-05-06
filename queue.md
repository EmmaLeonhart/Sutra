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
- PR #31's two reviewer-targeted polish paragraphs (§3.4
  gradient-stability, §6 MNIST/CLEVR pointer) reverted in body
  to restore the 9-page cap. Both v46 and v47 still listed the
  same cons unchanged, so the additions cost a page without
  moving reviewer signal. Awaiting `paper-pdf.yml` confirmation
  that body is back to 9.
- v47 review (2026-05-06, post 2361): **Accept** (Gemini 3 Flash).
  Cons unchanged from v46; gradient-stability and MNIST-Addition /
  CLEVR-Hans still flagged, confirming the two paragraphs were
  not buying the rating.
- v46 review (2026-05-06, post 2360): **Strong Accept**.
- Two TikZ figures still in body: `fig:halt-cell` (§3.4),
  `fig:k3-pipeline` (§3.6).
- 70+ inline/display math expressions render correctly via
  pandoc `markdown-smart` → lualatex.
- `paper-pdf.yml` and `papers-ci.yml` both green on master.
  CI is unusually slow today (3-15min vs the usual 1.5min).
- **Title mismatch fixed**: `paper/paper.tex` had the OLD title
  hardcoded in `\title{}` (`Compiling a Vector Symbolic
  Architecture to a Tensor-Op Recurrent Neural Network via Beta
  Reduction`, from PR #28's rename); paper.md H1 had the
  canonical post-revert title. The PDF title page was therefore
  showing the old title while the clawRxiv-submitted title used
  the H1. Both now use `Sutra: Tensor-Op RNNs as a Compilation
  Target for Vector Symbolic Architectures`.
- **Em-dashes stripped from body.** All 66 U+2014 em-dashes in the
  body rewritten to natural punctuation (parens for parentheticals,
  colon for label-then-description, comma for pause). Title and
  abstract untouched (frozen, and had zero em-dashes).

## Active

- Confirm `paper-pdf.yml` shows body back at 9 pages after the
  PR #31 paragraph revert. If it does, the page-count blocker is
  cleared for the May 6 AOE NeurIPS submission window.

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
- **9-page body achieved (then regressed by PR #31).** Two cuts
  landed 2026-05-06: `fig:compile-pipeline` moved to Appendix J
  (commit `9f642f2`), and §5 / §6 / §7 prose tightened to pull
  the conclusion onto page 9 (commit `e30ca6b`). PR #31 then
  added two paragraphs and pushed the body back to 10. Trim is
  the headline blocker — see Active section.
- **SKILL.md "13-program smoke test" → "10-program"** to match
  body §5 and Appendix I (the actual `_smoke_test.py` has
  exactly 10 `run_*` functions). Commit `131d4c7`.
- **clawRxiv review trajectory v20→v46.** Stable at Accept /
  Strong Accept since v23. v44 (2026-05-06): Accept (one step
  down from v43's Strong Accept); cons unchanged. v45
  (2026-05-06, post 2359): Strong Accept. v46 (2026-05-06,
  post 2360): Strong Accept; the two cons PR #31 targeted are
  still listed.
- **§3.4 gradient-stability paragraph + §6 MNIST-Addition /
  CLEVR-Hans pointer landed then reverted.** Two optional polish
  items landed in PR #31 in response to v44/v45 cons, then
  reverted today after v46 (Strong Accept) and v47 (Accept) both
  listed the same cons unchanged: the additions cost a page and
  bought no reviewer movement.
- **paper.tex title sync to canonical.** `\title{}` had the old
  PR-#28 title (`Compiling a Vector Symbolic Architecture to a
  Tensor-Op Recurrent Neural Network via Beta Reduction`); now
  matches `paper.md` H1 and CLAUDE.md canonical.
- **Em-dashes removed from body.** All 66 U+2014 stripped via
  context-aware rewrite (parens for parentheticals, colon for
  labels, comma for pauses). Frozen title + abstract untouched.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
