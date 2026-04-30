# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the **persistent
task list across sessions**. Claude loads items from here into the
task tool (`TaskCreate`) at session start, works through them, and
**removes completed items from this file** as they finish. Finished
work lives in `git log` and `planning/findings/`; this file is only
the *pending* work.

See CLAUDE.md §"STATUS.md and the task tool" for the full workflow.

The work here is **making Sutra the language actually work** — the
compiler, the spec, the substrate-backed runtime, the demo programs.
No papers, no submission deadlines. The question each queue item
answers is: *what does it take to make this language a real thing
someone can use?*

Longer-horizon items (pre-Anthropic-grant-app, pre-YC-pitch, this-
year) live in `todo.md`. Items in this file are the ones Claude should
pick up next.

## Queued work

### Loop surface redesign — substrate-pure for ALL loop forms (2026-04-30)

Audit on 2026-04-30 surfaced two pre-existing substrate violations
plus one redundancy in the loop surface. None caught by tests
because the example programs all use no-op bodies.

Design direction stated by Emma 2026-04-30. Full writeup:
`planning/open-questions/loop-surface-redesign.md`. Companion
quirk doc: `planning/open-questions/loop-body-semantics.md`.

**Final loop surface — four forms (after this work lands):**

| Form | Behavior | Status |
|---|---|---|
| `loop(N)` literal N | Compile-time unroll, body runs N times. | ✅ works today |
| `loop(N)` runtime N | Substrate-pure iteration up to N. | ❌ today bails to host Python `for` |
| `while(cond) { body }` | Substrate iteration; body IS the cell, runs each tick. | ❌ today body is discarded, replaced with fixed Haar `R · state` |
| `do_while(cond) { body }` | Body runs unconditionally each tick; condition evaluated at end produces halt signal that propagates as program-completion flag. | ❌ today desugars to body-once + while(cond), and while inherits body-discard. **First loop primitive to implement (item 3 below).** |
| `foreach(T x in iterable)` | Per-element iteration. Iterable can be literal OR runtime binding-array. | ❌ today literals only; binding-array case errors at compile time |

**Dropped:**
- `loop[N]` square-bracket syntax — `[]` doesn't mean anything else
  in Sutra; collapse to `loop(N)` as a regular argument. The compiler
  decides literal-vs-runtime at compile time.
- `loop(cond)` — redundant alias for `while(cond)`. Choose one
  name (Emma chose `while`).
- `loop(N)` fallback to host Python `for _ in range(N)` — substrate
  violation that snuck in for runtime-N.
- `for(init; cond; step)` — body-discard variant; supersede with
  `loop(N)` or `while`.

**Concrete queue items, in implementation order (revised 2026-04-30
per Emma's "do-while first" call):**

1. **Drop the `loop[N]` square-bracket syntax.** Collapse to
   `loop(N)` as a regular call-style argument. Parser change +
   AST node consolidation. Cheap.
2. **Drop `loop(cond)`; unify with `while(cond)`.** Parser
   deprecation warning + codegen collapse to one path. Cheap.
3. **Implement `do_while(cond) { body }` as a substrate-pure RNN
   with body-as-cell.** This is the **first real loop primitive**
   to land — Emma's call. Rationale: do-while has the cleanest
   shape for substrate iteration. Body runs unconditionally
   (matches "first iteration always happens"), then the condition
   evaluated at the end is naturally the halt signal. Specifically:
   - Compile body as a cell function `cell(state) → state'`.
   - Compile condition as a soft predicate `cond(state) → scalar
     in [0, 1]`.
   - Run T fixed steps. Each step:
     - `cand = cell(state)`
     - `cond_val = cond(cand)`  (soft scalar; high = keep going)
     - `halt_term = sigmoid(k · (1 − cond_val))`  (halt when cond
       falls toward 0 — i.e., "while is false")
     - `halt_cum = min(halt_cum + halt_term, 1)`
     - `state = (1 − halt_cum)·cand + halt_cum·state`
   - After T: write `halt_cum` to `AXIS_LOOP_DONE`; output-gate
     value axes by `halt_cum`.
   - Per Emma: "when the while is false at the end of it, then
     it spits out the information saying that the program is
     completed" — this is exactly the `halt_cum` saturating; the
     completion flag rides on `AXIS_LOOP_DONE` and propagates to
     the program-level output gating (item 4 below).
4. **Program-level completion flag propagation.** Today
   `AXIS_LOOP_DONE` only marks the loop's local result. Emma's
   vision: the flag rides through nested layers all the way to
   the final program output, which is gated branchlessly: if any
   loop along the way didn't complete, the whole program emits
   a wiped output rather than a partial one. Concretely: every
   compose / call site that consumes a looped value should AND
   its own halt_cum with the upstream halt_cum (or use
   element-wise multiply since halt_cum ∈ [0, 1]); the final
   program output gets multiplied by the propagated cumulative
   halt before return.
5. **Apply the do-while body-as-cell pattern to `while(cond)`.**
   `while(cond) { body }` desugars to "if cond then do_while(cond)
   { body } else don't run body" — but since we want branchless,
   the more natural lowering is: same as do-while but with an
   initial halt evaluation that gates the first body execution.
   Or just: while is "do-while with halt evaluated before each
   step instead of after." Either lowering works.
6. **Substrate-pure `loop(N)` with runtime N.** Today emits host
   Python `for _ in range(N)`. Replace with a soft-masked
   `loop(T_MAX)` unroll where each step's effect is gated by
   `(i < N)` — branchless multiplication-by-indicator. Body runs
   each step; past `N` the masked-off updates are discarded.
7. **`foreach` over runtime binding-arrays.** Binding-array =
   substrate vector storing N entries via N rotation-binding
   slots, with a runtime length scalar. Compile `foreach` to
   `loop(CAPACITY)` over the slots, masked by `(i < length)`.
   Per-element body runs branchlessly. Needs the binding-array
   primitive designed first.
8. **Drop `for(init; cond; step)`.** No clean substrate semantic;
   compile-time error pointing users to `loop(N)` or `while`.
9. **Tests for body-actually-runs.** New tests that put a
   meaningful statement in a `do_while` / `while` body and
   assert the side effect happens. Today's tests use no-op
   bodies and missed the discard for months.

Sequencing rationale:
- (1) and (2) are parser-level cleanups — cheap, do them
  together.
- (3) is the **first substantive loop primitive**. Emma chose
  do-while because the always-run-once-then-check shape composes
  most cleanly with the soft-halt mechanism and the program-
  completion-flag idea (item 4).
- (4) follows naturally — the propagation is the same scalar
  flowing from AXIS_LOOP_DONE up through layers via element-wise
  multiplication.
- (5) reuses (3)'s machinery.
- (6) and (7) are medium-scope follow-ups built on (3)'s cell
  pattern.
- (8) is small.
- (9) gates merge.

Why this matters: Sutra's whole substrate-purity story ("programs
are forward passes through tensor ops on CUDA") is only true if
every loop form actually compiles to substrate operations. Today
half of them either discard their bodies or bail to host Python.
The redesign closes both holes.

### Rename `STATUS.md` → `queue.md` — naming for clarity

Emma 2026-04-30: "this status.md is being ignored enough, is being
improperly used enough that it should have a more clear name like
queue.md." Rename touches CLAUDE.md and several planning docs that
reference "STATUS.md" by name; not done in the same commit as the
loop redesign capture to keep diffs reviewable. Queue this as a
small follow-up: rename the file, sweep references in CLAUDE.md +
todo.md + planning/ + sdk/ + examples/ to point at `queue.md`,
verify the workflow still resolves.

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
- **Exception channel unification.** `AXIS_LOOP_DONE = 4` (added
  2026-04-30 for loop-incomplete-output) is the first instance of a
  broader pattern: reserved synthetic axes flagging "this output is
  suspect" conditions (divide-by-zero, log of zero, NaN
  propagation, future user-defined try/catch). Should be unified
  into one shared exception-flags sub-block. Sketched in
  `planning/findings/2026-04-30-rnn-loop-architecture.md` § "Unify
  with the broader exception channel". Not designed yet.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` literal unrolls at compile time. Zero runtime
   iteration.** `while(cond)` is the data-dependent form (which
   currently has a body-discard bug — see queued work above).
2. **No loop counters live on the host at runtime.** The "counter"
   for substrate iteration IS the angular position on the helix
   `R^i·v₀` in the substrate (or, post-redesign, the soft-mask
   index in a fixed-T unroll).
3. **Rotation runs in the synthetic subspace, not on connectome
   weights.** The retired fly-brain investigation established that
   real FlyWire weight matrices do not function as rotation operators
   (they're compressive projections). Synthetic Givens rotations on
   the dedicated subspace are what the language compiles to today.
   Findings: `planning/findings/2026-04-13-shiu-rotate-collapses.md`
   and the cluster of 2026-04-13 / 2026-04-18 docs.
4. **Semantic roles are learned matrices; semantic `bind` is
   `R @ filler`.** Not random vectors (HRR), not sign-flip. A
   *semantic* role is a matrix fit to the substrate.
   See `planning/sutra-spec/binding.md` §"Semantic binding".
   **Implementation status: deferred.**
5. **Sutra has two binding kinds: semantic (learned-matrix) and
   rotation.** Spec-level design in
   `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
   Rotation binding works today; semantic binding is deferred.
6. **Sign-flip binding is retired** (from the codegen as of
   2026-04-22). Rotation is the current `bind` implementation.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** `synthetic[AXIS_TRUTH=2]`. Spec target in
   `planning/sutra-spec/equality-and-defuzzification.md`.
8. **PyTorch is the compiler's runtime target.** `codegen_pytorch.py`
   emits torch modules picking CUDA at module init. `codegen.py` is
   an internal IR step. `--emit` and `--run` go to PyTorch.
9. **Defuzzification polarizes, never binarizes.** `is_true` and
   `defuzzify` keep the result fuzzy and differentiable. No commit
   primitive exists; `select` does all branching. Don't reintroduce
   `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.** Carries a defuzz
    counter as compile-time metadata. A bool value is a scalar on
    the canonical truth axis.
11. **Sutra's "arrays" are binding-based, not heap-allocated.** An
    array is a substrate vector storing N entries via N rotation-
    binding slots (built on `slot_store` / `slot_load` / `rotate_slot`).
    No memory allocation; everything is a vector. The binding-array
    `foreach` queue item builds on this.
12. **Canonical synthetic axis allocation:** `synthetic[0]=AXIS_REAL`,
    `[1]=AXIS_IMAG`, `[2]=AXIS_TRUTH`, `[3]=AXIS_CHAR_FLAG`,
    `[4]=AXIS_LOOP_DONE`, `[5+]=SLOT_BASE` (47 disjoint 2D Givens
    slots at default `synthetic_dim=100`).

## Pointers

- Longer-horizon agenda: `todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
