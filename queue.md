# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the **persistent
task list across sessions**. Claude loads items from here into the
task tool (`TaskCreate`) at session start, works through them, and
**removes completed items from this file** as they finish. Finished
work lives in `git log` and `planning/findings/`; this file is only
the *pending* work.

See CLAUDE.md §"queue.md and the task tool" for the full workflow.

The work here is **making Sutra the language actually work** — the
compiler, the spec, the substrate-backed runtime, the demo programs.
**The last queue item, after the language works, is writing the
paper and shipping it** (Claw4S workshop + NeurIPS + a follow-up
workshop, with a CI/CD pipeline). The question each queue item
answers is: *what does it take to make this language a real thing
someone can use, and then publish?*

Longer-horizon items (pre-Anthropic-grant-app, pre-YC-pitch, this-
year) live in `todo.md`. Items in this file are the ones Claude should
pick up next.

## Queued work — only item

### 1. Paper draft, three submission targets, and CI/CD pipeline — IN PROGRESS

The language works end-to-end on real programs. Last queue item is
**writing the paper and shipping it**. Three submission targets
(Emma 2026-04-30):

1. **Claw4S workshop** — the AI-workshops conference / preprint
   server pair (`clawRxiv`). Repo had a substantial Claw4S submission
   pipeline before the Sutra rebrand; that infrastructure is
   recoverable from git history (commits like `b353ff3 exploratory:
   Claw4S paper draft on Sutra as compile-time VSA`, `f09a3f2
   Complete documentation overhaul + SKILL.md for Claw4S submission`,
   `1b73781 Reorganize repo for two Claw4S 2026 papers`). Recovery
   recipe is in `DEVLOG.md` Phase 4.
2. **NeurIPS** — main conference, double-blind. Emma's read 2026-04-30
   is the current pipeline already follows NeurIPS rules properly,
   but verify before submitting.
3. **A second workshop after NeurIPS** — TBD which one; identify
   during 1a.

#### Sub-items, in rough order

**1a. Audit submission rules for all three targets first.** Read
current Claw4S, NeurIPS, and the post-NeurIPS workshop author guides;
capture in a findings doc:
- Page limit + format per target (LaTeX templates).
- Anonymization rules (double-blind for NeurIPS at minimum).
- Supplementary material rules.
- Reproducibility checklist requirements.
- Deadlines: abstract registration, full submission, camera-ready.

Output: `planning/findings/YYYY-MM-DD-paper-submission-rules.md`.
This document is what the CI/CD pipeline gets built against.

**1b. Recover Claw4S infrastructure from git history.** Per
DEVLOG.md Phase 4, the three workflows (`papers-ci.yml`,
`submit-papers.yml`, `competition-cron.yml`) plus submission
scripts (`scripts/fetch_all_papers.py`, `scripts/fetch_reviews.py`)
plus per-paper `SKILL.md` template are all recoverable from
`903308e^`. The `CLAWRXIV_API_KEY` repo secret is still configured
per Emma 2026-04-30. Restore selectively rather than reinventing.

**1c. Write the paper itself.** Substance, not yet plumbing:
- The narrative arc per `project_sutra_paper_real_scope.md`:
  displacements in frozen embedding spaces → consolidate into rotation
  binding → learned matrices as the natural extension. Sign-flip is at
  most a side note; the headline is learned-matrix (semantic) binding.
- Empirical foundation from `latent-space-cartography` (sibling repo
  — verify numbers against source, do not quote from memory).
- The Sutra language as the realization of the program: a programming
  language whose primitives are the operations that fall out of the
  embedding-space analysis.
- Substrate-purity story: every operation runs as tensor ops on the
  substrate; no host-Python compute; the compiler is the safety
  boundary because the runtime has no error channel by mechanism.
- Demo programs (`hello world`, `fuzzy_dispatch`, `role_filler_record`,
  the loop demos) as worked examples.

This is the work-product itself, not infrastructure. Likely lives in
a new `paper/` directory at repo root with `paper.tex` + `paper.bib`
+ figures.

**1d. CI/CD pipeline — single source, four outputs.** From the same
LaTeX/Markdown source, the pipeline produces:
1. **HTML on the docs site** (`sutralang.dev`) — for casual readers
   and AI-agent consumers.
2. **Downloadable PDF on the website** — full version with author
   names, links, acknowledgments.
3. **Anonymized PDF on the website** — author names stripped, repo
   URLs anonymized, third-person self-references. This is the version
   that goes to NeurIPS double-blind review. (Why on the website too?
   So reviewers who find the paper outside the OpenReview portal land
   on the same anonymized version they're supposed to be reviewing.)
4. **Claw4S / clawRxiv upload** — Claw4S workshop submission +
   preprint mirror. The previous repo had a working push-to-clawRxiv
   action; recover it (per 1b).

Pipeline shape (rough): GitHub Actions workflow on push to
`paper/` triggers two LaTeX builds (full + anonymized via `\if`
macros), uploads the PDFs as workflow artifacts, deploys both PDFs
+ rendered HTML to the docs site, and (optionally, on a tag) pushes
to the preprint server's API.

**1e. Anonymization macros.** A single-source approach uses LaTeX
conditionals to swap in/out the deanonymizing pieces:
```latex
\ifanon
  \author{Anonymous Authors}
  \newcommand{\repo}{[anonymized repository]}
\else
  \author{Emma Leonhart}
  \newcommand{\repo}{\url{https://github.com/...}}
\fi
```
Build flag (`-DANON=1`) flips between modes. Avoids the trap of
forking two paper sources that drift from each other.

**1f. Reproducibility submission.** NeurIPS reproducibility
checklist will require pointing at runnable code. The Sutra repo
itself is the answer; the submission references it (anonymized in
1e via `\repo`) and includes a `paper/REPRODUCE.md` with
"clone, install, run these commands, get these numbers."

#### Why this is at the end, not the start

The paper claims things about the language. The language has to
actually do those things first. The pre-paper queue items were the language being
*real* (substrate-pure, complete RNN compilation, no boundary
leaks, default vector backend). this paper item is the language being
*defended* in print. Doing the paper first would mean writing a paper about
aspirational software, which is the failure mode the
safety-critical preamble in CLAUDE.md exists to prevent.

## Queued work — flagged but not blocking

### Repo bloat sweep — flagged item

**Flagged for user decision:** local `fly-brain/` working copy is
**101 MB** as of 2026-04-29. Gitignored (`.gitignore` line 39),
canonical copy at `C:\Users\Immanuelle\flybrain\` outside the
repo. Worth confirming whether the local mirror is actively
needed or whether it can be reclaimed.

## Deferred (see `todo.md`)

These are real commitments but not "next active session" work. Kept
here as pointers so they don't fall off the radar:

- **`main(embedding_space: string)` compile-time override.** Partial
  progress: file-level (`// @embedding`) and project-level
  (`atman.toml` `[project.embedding]`) substrate declarations both
  land in the harness 2026-04-22. The third layer — declaring the
  substrate from inside `.su` source itself — is a compile-time
  concern (not runtime as earlier framed) and sequenced post-
  Anthropic-grant-app per user direction 2026-04-23. Full scope
  in `todo.md`.
- **Learned-matrix binding** (pre-Anthropic-grant-app): `role X =
  learned_from(data)` fits a matrix at compile time; `bind` for
  semantic roles becomes `R @ filler`. Deferred from 2026-04-22 per
  user priority. Full spec in `todo.md` and
  `planning/sutra-spec/binding.md` §"Semantic binding".
- **MLP-backed Monte-Carlo attractor search** (pre-Anthropic-grant-
  app, not today): train an MLP as an attractor function over the
  codebook, run Monte-Carlo trajectories from `v0 = king - man +
  woman` into the learned basins, compare attractor quality across
  substrates. Full details in `todo.md`.
- **Exception channel unification.** `AXIS_LOOP_DONE = 4` is the
  first instance of a broader pattern: reserved synthetic axes
  flagging "this output is suspect" conditions (divide-by-zero,
  log of zero, NaN propagation, future user-defined try/catch).
  Should be unified into one shared exception-flags sub-block.
  Sketched in
  `planning/findings/2026-04-30-rnn-loop-architecture.md` § "Unify
  with the broader exception channel".
- **Numpy backend full file deletion.** `codegen.py` was deprecated
  2026-04-30 (deprecation header + behavior tests moved to PyTorch
  backend) but the file is retained for emit-shape tests. Full
  deletion + literal-hook migration into `BaseCodegen` is queued
  but not blocking.
- **Full `atman.toml [vector_db]` config schema.** Today's SutraDB
  path is configurable via `SUTRA_DB_PATH` env var. Full TOML
  schema (HNSW M / ef_construction / embedding model override)
  deferred until there's a concrete config use case.

## Pinned semantic corrections (I keep dropping these)

1. **`loop(N)` literal N unrolls at compile time. Zero runtime
   iteration.** The four function-declaration loop kinds (`do_while`,
   `while_loop`, `iterative_loop`, `foreach_loop`) are the runtime
   data-dependent forms.
2. **No loop counters live on the host at runtime.** The "counter"
   for substrate iteration IS the soft-mask cumulative halt in a
   fixed-T tensor-op unroll. The `for _t in range(50)` in the
   emitted Python is meta-iteration, not a runtime counter — the
   substrate sees T inline cell evaluations regardless. (Item 1
   above eliminates even the meta-iteration via full unroll.)
3. **Rotation runs in the synthetic subspace, not on connectome
   weights.** Real FlyWire weight matrices do not function as
   rotation operators (they're compressive projections). Synthetic
   Givens rotations on the dedicated subspace are what the language
   compiles to today.
4. **Semantic roles are learned matrices; semantic `bind` is
   `R @ filler`.** Not random vectors (HRR), not sign-flip. A
   *semantic* role is a matrix fit to the substrate.
   See `planning/sutra-spec/binding.md` §"Semantic binding".
   **Implementation status: deferred.**
5. **Sutra has two binding kinds: semantic (learned-matrix) and
   rotation.** Rotation binding works today; semantic binding is
   deferred.
6. **Sign-flip binding is retired** (from the codegen as of
   2026-04-22). Rotation is the current `bind` implementation.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** `synthetic[AXIS_TRUTH=2]`.
8. **PyTorch is the compiler's runtime target.** `codegen_pytorch.py`
   emits torch modules picking CUDA at module init. The numpy
   backend (`codegen.py`) is deprecated as of 2026-04-30.
9. **Defuzzification polarizes, never binarizes.** `is_true` and
   `defuzzify` keep the result fuzzy and differentiable. No commit
   primitive exists; `select` does all branching. Don't reintroduce
   `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.**
11. **Sutra's "arrays" are binding-based, not heap-allocated.** A
    binding-array is a substrate vector with `arr[0] = length` and
    `arr[1..length] = elements`. Built on `array_from_literal` /
    `array_length` / `array_get` runtime methods (shipped 2026-04-30).
12. **Canonical synthetic axis allocation:** `synthetic[0]=AXIS_REAL`,
    `[1]=AXIS_IMAG`, `[2]=AXIS_TRUTH`, `[3]=AXIS_CHAR_FLAG`,
    `[4]=AXIS_LOOP_DONE`, `[5+]=SLOT_BASE` (47 disjoint 2D Givens
    slots at default `synthetic_dim=100`).
13. **Loops are first-class declared functions** (Emma 2026-04-30).
    `<kind> NAME(condition_or_array_or_count, type state, ...) { body; pass values; }`.
    Body uses `pass <exprs>` OR `return NAME(args)` (tail-recursive
    yield, one value per state param; `replace` keyword keeps an
    input value in the `pass` form). Call site is `loop NAME(...)`
    and mutates caller variables by reference. Loop functions have
    NO outer-scope access — pure functions over their declared
    parameters only. The four kinds: `do_while` (body runs once +
    while-style continuation), `while_loop` (body skipped if cond
    false at start), `iterative_loop` (runs N times; body sees
    `iterator` keyword), `foreach_loop` (walks binding-array; body
    sees `element` keyword). Substrate execution: T fixed cell
    steps with soft-halt sigmoid + monotone cumulative + soft-mux
    freeze. AXIS_LOOP_DONE marks completion.
14. **Idiomatic-loop cleanup is queued for later this year.** Today's
    by-reference call shape is acknowledged non-idiomatic; the
    cleanup direction (return tuples, no by-ref mutation) is in
    `todo.md` § "Make loops idiomatic." Don't touch the design
    until a few real programs have exercised the by-ref form.
15. **SutraDB is the embedded codebook.** Every embedded string in
    a Sutra program goes into SutraDB at compile time via
    `_VSA.populate_sutradb()`. `_VSA.nearest_string(query)` decodes
    any vector back to the nearest string label. `SUTRA_DB_PATH`
    env var configures persistent .sdb across runs. Build prereq:
    `cd sutraDB && cargo build --release -p sutra-ffi`.
16. **Rotation cache is pre-warmed at compile time.** Every
    codebook entry gets its rotation matrix computed in
    `_VSA.prewarm_rotation_cache()` at module init, after
    embed_batch + populate_sutradb. The runtime never pays QR cost
    on the hot path.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
