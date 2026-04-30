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
No papers, no submission deadlines. The question each queue item
answers is: *what does it take to make this language a real thing
someone can use?*

Longer-horizon items (pre-Anthropic-grant-app, pre-YC-pitch, this-
year) live in `todo.md`. Items in this file are the ones Claude should
pick up next.

## Queued work — top of queue (work through in order)

### 1. Deprecate or remove the old loop forms

The function-declaration loop forms (`do_while NAME(...)`,
`while_loop NAME(...)`, `iterative_loop NAME(...)`, `foreach_loop
NAME(...)` + `loop NAME(...);` call site) shipped 2026-04-30 and all
four kinds work end-to-end (17 tests pass). The OLD C-style forms —
`while(cond) { body }`, `for(init; cond; step) { body }`,
`loop(cond) { body }`, `do { body } while (cond);` — still parse and
compile, but their codegen is the body-discard variant that doesn't
actually run the body. Two parallel surfaces, one of which is broken.

Pick one of:
- **Hard removal**: parser rejects the old forms with
  `CodegenNotSupported` pointing at the function-decl forms.
- **Deprecation warning**: parser still accepts but emits a warning;
  removal in a later release.

Either way, the old `examples/loop_rotation.su`,
`examples/counter_loop.su`, `examples/concept_search.su` need to
either move to the new form or get deleted. They use no-op bodies
that never exercised the discarded code anyway.

The compile-time `loop(N) { body }` (literal N, unrolls at compile
time) stays — that's the cheap easy form Emma wants for arrays-of-
known-size cases. Do NOT remove that.

### 2. Program-level completion flag propagation

`AXIS_LOOP_DONE` is set on the loop's local result vector but
doesn't propagate through layers to the program's final output.
Today the call-site writeback grabs `_loopret_x` (the state value)
and stores it back into the caller's slot var, dropping the
`_loopret_halt` (the completion flag) on the floor. So the program
returns a normal-looking value even if a loop didn't converge.

Emma's design: every loop's halt_cum should multiply through to the
program's final output via element-wise multiply (since halt_cum ∈
[0, 1]). If any loop in the call chain didn't complete, the program
emits a near-zero (detectably wiped) output rather than a partial
result.

Concrete shape:
- Each loop call accumulates its halt_cum into a function-scope
  `_program_halt` variable.
- At each function's `return <expr>`, multiply the return value by
  `_program_halt`.
- For nested loops, the inner halt_cum gets multiplied into the
  outer's, and so on up to main's return.

This is medium-scope codegen work. Tests: programs with reachable
loops return correct values; programs with unreachable loops
(impossible condition) return wiped outputs.

## Queued work — middle of queue

### 3. SutraDB integration as the default vector backend

Emma 2026-04-30: "we should be using SutraDB with `nomic-embed-text`.
... SutraDB and runtime are small enough that we can reasonably embed
it in what we make. ... Particularly for hash mapping and stuff, it's
probably better to do this than to rely on the arg max thing.
Especially in the future, for larger files, it should probably be the
default, the default thing that we compile with."

So this isn't just "use SutraDB for tests" — it's **make SutraDB the
default vector backend that every compiled Sutra program embeds and
queries.** The host-Python `argmax_cosine` / `snap` / hashmap-lookup
loops get replaced with SutraDB queries.

Concrete shape:
- **Embedded mode** (`.sdb` file like SQLite, no daemon). Each
  compiled Sutra program opens its own `.sdb` at module init and
  queries it inline.
- **`nomic-embed-text` is the embedding model** (already CLAUDE.md
  default). MxBai/MiniLM are the comparison substrates for
  cross-substrate experiments, but compiled programs default to
  nomic.
- **Hashmap (`hashmap_set` / `hashmap_get`) routes through SutraDB**
  too — instead of bind/bundle accumulator with bit-identical-key
  lookup, store key-value pairs as triples in SutraDB and query by
  vector similarity. Soft lookup falls out for free (HNSW is
  approximate-nearest-neighbor).
- **`argmax_cosine` / `snap`** become SutraDB nearest-neighbor
  queries. The "loop over candidates" violation dissolves: SutraDB
  does the work in Rust + HNSW.

Implementation pieces (rough sequencing):
1. Embed SutraDB CLI / FFI binding into the runtime so compiled
   modules can query a `.sdb` without a separate process.
2. Codegen: at module init, open a `.sdb` populated with the
   program's known vectors (codebook, role rotations, etc.).
3. Replace `argmax_cosine` / `snap` runtime methods with SutraDB
   nearest-neighbor queries.
4. Replace `hashmap_*` runtime methods with SutraDB triple
   insert/query.
5. `atman.toml` `[vector_db]` section to override defaults
   (nomic-embed-text, sdb file path, HNSW params).

This is bigger than the rest of the queue items combined. Will
likely need its own design doc + plan when the slot at the front
of the queue rolls around to it. Worth flagging as "default for
larger files in the future" — small programs may stay on the
in-process bind/bundle/argmax path during the transition.

### 4. make_random_rotation pre-warm at compile time

Today, the first call to `bind` for each role triggers
`make_random_rotation` (numpy random + QR + Givens construction).
Cache-hit path is fine; cache-miss is host Python.

Fix: scan all role names used in the program at compile time, emit
a pre-warm block at the top of the generated module that constructs
all role rotations up front. Runtime then only ever hits the cached
matmul.

Verify with a test that runs a compiled program twice with timing
and asserts the second run has zero rotation construction.

## Queued work — back of queue (boundary leaks; "Python is just IO" target)

### 5. Boundary leaks (Python touching scalars where it shouldn't)

These are real but small — they don't break correctness, just keep
the runtime from being purely tensor ops:

- **`slot_load` returns Python float** via `float(state[i])`. If the
  next op is a tensor op the value gets re-vectorized; if it's
  Python arithmetic, the work happens on CPU. Used everywhere slot
  vars are read.
- **Loop halt check uses Python `bool()`** on the truth-axis scalar
  extracted from the condition's fuzzy-vector result. Branchless in
  the soft-mux sense, but the comparison happens in Python.
- **`if key not in self._rot_cache`** — runtime conditional on
  first-use of each role. Fine if all roles are pre-warmed (item 4
  above); leaky otherwise.
- **`array_get` returns Python float** — same shape as `slot_load`.

Fix: keep values as 0-dim tensors throughout the runtime methods;
only `.item()` extract at the program's final IO boundary (return
to user, print, etc.). Requires touching: slot_load, slot_store
(maybe — currently writes a float into a tensor position),
similarity, the loop halt check, array_get, the vector accessors
(real, imag, truth, component).

### 6. "Python is just IO" target — three pieces

Emma's framing: ideally the Python wrapper does *only* IO/console
shell work; everything else runs as one big tensor-op graph.
Distance is small but non-zero:

- **Full unroll**: replace the `for _t in range(50)` in each loop
  function with T inline tensor-op calls. Substrate sees the same
  graph; emitted source has no Python loops at all. Mostly cosmetic
  but useful for `torch.compile` to fully fuse.
- **No `.item()` / `bool()` at the boundary**: see item 5 above.
  Same fix.
- **`torch.compile` the whole module**: once items 5+6 land, the
  emitted module is a pure tensor-op graph and torch.compile can
  trace + fuse the whole thing into a single CUDA kernel (or a few).

These are the "make Python wrapper genuinely just IO" pieces. After
they land, the wrapper is module load + `_VSA` instance setup +
`main()` call + return value to console — nothing else.

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

## Pinned semantic corrections (I keep dropping these)

1. **`loop(N)` literal N unrolls at compile time. Zero runtime
   iteration.** The four function-declaration loop kinds (`do_while`,
   `while_loop`, `iterative_loop`, `foreach_loop`) are the runtime
   data-dependent forms.
2. **No loop counters live on the host at runtime.** The "counter"
   for substrate iteration IS the soft-mask cumulative halt in a
   fixed-T tensor-op unroll. The `for _t in range(50)` in the
   emitted Python is meta-iteration, not a runtime counter — the
   substrate sees T inline cell evaluations regardless.
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
   emits torch modules picking CUDA at module init.
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
    Body uses `pass <exprs>` (tail-recursive yield, one expr per
    state param; `replace` keyword keeps an input value). Call site
    is `loop NAME(...)` and mutates caller variables by reference.
    Loop functions have NO outer-scope access — pure functions over
    their declared parameters only. The four kinds: `do_while` (body
    runs once + while-style continuation), `while_loop` (body skipped
    if cond false at start), `iterative_loop` (runs N times; body
    sees `iterator` keyword), `foreach_loop` (walks binding-array;
    body sees `element` keyword). Substrate execution: T fixed cell
    steps with soft-halt sigmoid + monotone cumulative + soft-mux
    freeze. AXIS_LOOP_DONE marks completion.
14. **Idiomatic-loop cleanup is queued for later this year.** Today's
    by-reference call shape is acknowledged non-idiomatic; the
    cleanup direction (return tuples, no by-ref mutation) is in
    `todo.md` § "Make loops idiomatic." Don't touch the design
    until a few real programs have exercised the by-ref form.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
