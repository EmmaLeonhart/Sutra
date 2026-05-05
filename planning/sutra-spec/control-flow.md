# Control flow

This section describes what the compiler actually accepts and how it
lowers each construct, as of 2026-04-22. Where a construct is parsed
but rejected at codegen, that's called out explicitly — several
familiar control-flow keywords are in this category.

## Branching

### `select` — the only runtime branching primitive

`select` is the main conditional-branching primitive in Sutra.
Single-option `select`, multi-option `select`, and
`select ... else fallback` are the three forms. Semantically
`select` is fuzzy weighted superposition over the named options
rather than a discrete `if`. The result is a vector that is the
softmax-weighted sum of the options; it can be passed to further
operations.

`select` is not a primitive vector operation (bind/bundle/…); it is
a separate kind of thing — control flow.

### `if` / `else` is parsed but rejected at codegen

The lexer has `KW_IF` / `KW_ELSE` tokens and the parser accepts the
usual `if (cond) { then } else { else }` form. **But the codegen
rejects them** (`codegen_base.py`):
"if/else is not supported by the V1 codegen — the whole point is to
compile it away into a prototype-table lookup."

So in practice: if a `.su` program contains an `if` statement, it
fails to compile with a clear error. Programs that need branching
rewrite to `select`:

- Fuzzy weighted superposition over several options:
  `examples/fuzzy_branching.su` (2-dimensional conditional over
  smell × hunger).
- Hard-dispatch-looking code:
  `examples/fuzzy_dispatch.su` (N-way `select` over weighted
  scores).

This is a design commitment, not a missing feature. If you want
"if," you write `select` with two options.

## Loops

The language has several loop surface forms. All of them compile to
one of two underlying mechanisms: **compile-time unroll** (bounded,
known iteration count) or **eigenrotation** (data-dependent
termination on the substrate).

### `loop[N]` — bounded, unrolls at compile time

`loop (N) { body }` or `loop (N as i) { body }` where `N` is an
integer literal unrolls at compile time. Zero runtime iteration,
zero eigenrotation — the compiler emits the body `N` times, with
the index variable `i` substituted with `0, 1, …, N-1` in each
iteration if the `as i` form is used.

If `N` is a non-literal expression, the codegen currently emits a
Python `for _ in range(N)` loop around the body (no unrolling).
That's a compile-time choice, not a runtime eigenrotation — the
substrate doesn't see any rotation in this case.

### `loop(cond)` — data-dependent, branchless RNN unroll on the substrate

When the loop's termination is data-dependent (`loop (cond)` where
`cond` is not an integer literal), the codegen lowers to an
**RNN-style unrolled cell on the substrate** (2026-04-30). The compiler:

1. Extracts the target vector from the condition — the shape
   `similarity(state, target_expr) < threshold` is recognized and
   `target_expr` is pulled out (`_extract_loop_target` in
   `codegen.py`).
2. Emits a Haar-random orthogonal rotation `R` seeded by the
   runtime seed.
3. Calls `_VSA.loop()`, which runs **T fixed cell steps unconditionally**:
   - Cell: `state, halted = _step(state, R, target, halted, k, threshold)`
   - `_step` computes `cand = R · state`, normalizes, computes
     `sim = cos(cand, target)`, computes soft halt
     `halt = sigmoid(k · (sim - threshold))`, accumulates monotonically
     `halted = min(halted + halt, 1)`, and freezes via soft mux
     `state = (1 - halted) · cand + halted · state`.
   - Pure tensor ops at every step: multiply, add, divide, exp, minimum.
     **No host-side `if`, no host-side `while`, no host-side iteration
     count** in the cell.
4. After T steps, gates the value-bearing axes by `halted` so a
   non-converging loop emits a near-zero output. The cumulative
   halt is written to `synthetic[AXIS_LOOP_DONE]` as the
   substrate-side completion flag.

This is the RNN dual of Sutra's MLP-shaped non-looping path:
non-looping programs are a single forward pass; looping programs
are a recurrent forward pass. Both are branchless on the substrate.

Defaults: `T = max_iters = 50`, `k = 20.0` (sigmoid sharpness),
`threshold = 0.5` (cosine convergence gate).

**Output gating + AXIS_LOOP_DONE.** The reserved synthetic axis at
index 4 carries the cumulative halt (`halted ∈ [0, 1]`):
- `halted ≈ 1` → loop converged; output is valid; value axes
  are unchanged.
- `halted < 1` → loop did not converge within T steps; value
  axes are scaled by `halted` (toward zero), so downstream code
  sees a near-zero output it can detect as "incomplete." This is
  the loop-specific instance of the broader **exception channel**
  pattern (divide-by-zero, NaN propagation; see `todo.md`).

Demo programs: `examples/loop_rotation.su`,
`examples/counter_loop.su`, `examples/concept_search.su`. All pass
under the new RNN unroll.

### `while` and `for` — also eigenrotation

Surprisingly, `while (cond) { body }` and C-style
`for (init; cond; step) { body }` are both parsed AND both compile
to eigenrotation loops — **not** to Python-style host-runtime
loops. The codegen extracts a target (for `while`) or an iteration
bound (for `for`) and lowers to the same substrate machinery as
`loop(cond)`.

This is design-intentional: Sutra runs computation on the
substrate, not on the host. A `for` that compiled to a Python
`for` loop would mean the loop counter lives on the host — which
CLAUDE.md explicitly rejects ("the 'counter' for `loop(condition)`
IS the angular position on the helix R^i·v₀ in the substrate").

Programs that want bounded iteration should prefer `loop[N]`
(unrolls cleanly); `while` and `for` work but lower to the same
eigenrotation as `loop(cond)` and carry the same caveats.

### `do-while` — desugars to `body; while (cond) { body }` (2026-04-22)

`do { body } while (cond)` lowers by executing `body` once
unconditionally, then entering a `while (cond) { body }` that
lowers via the existing `WhileStmt → eigenrotation-loop` path.
User direction: "decompose to a single iteration, followed by a
while loop of it." Implementation in
`codegen_flybrain.py::_translate_stmt` branches on `DoWhileStmt`
and synthesizes the `WhileStmt` AST node internally.

This matches classical do-while semantics (body always runs at
least once). It also means do-while's body inherits the while-
half's eigenrotation semantics: the second-and-subsequent
iterations are eigenrotation on the substrate, not re-executions
of the written body. That's consistent with how Sutra's `while`
already works.

Test: `sdk/sutra-compiler/tests/corpus/valid/do_while.su`.

### `foreach` over compile-time-known collections (2026-04-22)

`foreach (TYPE x in [a, b, c]) { body }` unrolls at compile
time — one body emission per element, with the loop variable
bound to the element's translated source. User direction: start
with the compile-time-known case; dynamic foreach (over a named
collection or a runtime expression) is a compile-time error
pending the dynamic-foreach design (see todo.md).

The iterable must be an `ArrayLiteral` (`[a, b, c]` in source).
Anything else raises a compile-time `CodegenNotSupported` with
guidance pointing at the array-literal form or manual unrolling.

Test: `sdk/sutra-compiler/tests/corpus/valid/foreach_literal.su`.

### `try-catch` — parsed but rejected

The parser accepts `try { … } catch { … }`. The codegen rejects
it — there is no raise / throw primitive in Sutra today, so
"what would catch catch" is an unresolved design question rather
than a missing implementation. Parser support exists so the
surface syntax is reserved; the feature itself is parked in
`todo.md` as a longer-term item.

## `return`

Functions can return a value (`return expr;`) or nothing
(`return;`). Both parse and both codegen. The return type in the
function signature is a convention, not a check — the compiler
doesn't verify that the returned expression's type matches the
declared return type.

## Open questions

- **Exact semantics of multi-option `select`'s firing threshold**
  and of `select ... else` when all named options are low. (Tracked
  in `todo.md`.)
- **When `loop[N]` can't be unrolled** (non-literal N), current
  codegen silently emits a host-Python `for _ in range(N)`. Is
  that acceptable (it's a counter on the host), or should the
  compiler error and force `loop(cond)`? Open.
- **Rotation operator for `loop(cond)`** — currently Haar-random,
  seeded by runtime seed. Is that always right, or should the
  operator be substrate-specific / per-loop-site?
- **Non-similarity loop conditions.** `loop(cond)` currently
  expects `similarity(state, target) < threshold`. Can a bool
  crossing a threshold or a counter hitting a ceiling terminate a
  loop, and do those need their own lowering paths?
  **(Partially resolved 2026-04-30 by the soft-halt mechanism:**
  any sigmoid-able scalar can be the halt source, so adding new
  termination shapes is a matter of swapping `sim` for the
  appropriate quantity in `_step`. Stabilization termination
  `||state_n - state_{n-1}|| < eps` fits the same shape — track
  the previous state via a one-step delay and feed the difference
  norm into the sigmoid.) Still open: surface syntax for
  selecting between target-similarity vs stabilization vs custom
  predicates.
- **Decide fate of parser-only features.** `do-while`, `foreach`,
  `try-catch`, `if/else`: should they stay parsed-but-rejected (to
  reserve the surface syntax), get removed entirely, or get
  implemented? `if/else` is design-rejected (use `select`); the
  others are just unimplemented. Flag in a future pass.
