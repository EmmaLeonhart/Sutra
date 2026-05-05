# Loop surface redesign — drop redundancy, fix substrate violations

**Surfaced:** 2026-04-30
**Status:** Design direction stated by Emma; implementation not started.
**Companion:** `planning/open-questions/loop-body-semantics.md`
(the underlying body-discard quirk that this redesign addresses).

## Context

The 2026-04-30 audit of loop forms (in `queue.md` § "Loop-form
audit") surfaced two distinct problems:

1. **Body-discard in `loop(cond)` / `while(cond)` / `for(...)`.**
   The body's statements don't run; only the state-variable name
   and the condition's target are extracted, and the body is
   replaced with `R · state`.
2. **Python `for _ in range(N)` fallback in runtime `loop[N]`.**
   When `N` isn't a literal integer, the codegen emits a host-side
   Python for loop. That's an iteration counter living on the host
   — exactly the substrate violation the RNN refactor was supposed
   to close.

Plus a redundancy: `loop(cond)` and `while(cond)` compile to
literally the same thing today. Two surface keywords, one
behavior.

## The redesign Emma stated

### Final loop surface — four forms

| Form | Semantics | Notes |
|---|---|---|
| `loop(N)` literal N | Compile-time unroll. Body emitted N times inline. | Already works for literal N. |
| `loop(N)` runtime N | Substrate-pure iteration up to N via soft-masked unroll. | Today bails to host Python — needs replacement. |
| `while(cond) { body }` | Substrate iteration; the body **is the RNN cell**. Runs each tick on the current state until cond fires (soft halt) or T cap. | Needs implementation work — body must actually translate as the cell function. |
| `do_while(cond) { body }` | Body runs once unconditionally, then `while(cond) { body }` with body-as-cell. | Already desugars to body + while; depends on while-body running. |
| `foreach (T x in iterable) { body }` | Per-element body emission. Iterable can be a compile-time literal OR a substrate-value binding-array. Body runs per element. | Literal case already works; binding-array case needs implementation work. |

### Dropped

- **`loop[N]` square-bracket syntax** — `[]` doesn't mean anything
  else in Sutra; collapse to `loop(N)` as a regular argument
  position. The compiler decides literal-vs-runtime at compile time
  based on whether `N` is an integer literal or an expression.
- `loop(cond)` — redundant with `while(cond)`. Choose one name;
  Emma chose `while`. Parser keeps `loop(cond)` as a deprecated
  alias temporarily, or removes it outright. Programs that used
  `loop(cond)` rewrite to `while(cond)`.
- `loop(N)` runtime-N fallback → host Python `for _ in range(N)`.
  Runtime-N must compile to substrate iteration (soft-masked unroll
  up to a compile-time T_MAX, with each step gated by `(i < N)`).
- `foreach` over arbitrary runtime expression that errors today.
  Replaced with the binding-array case below.
- `for(init; cond; step)` — body-discard variant; supersede with
  `loop(N)` or `while`.

## What "binding-array" means for `foreach`

Emma's clarification: not heap-allocated dynamic arrays
(allocating new memory points). Specifically: arrays that are
themselves substrate values, updated via binding. In Sutra
terms: a vector that stores N entries via N rotation-binding
slots, where you can add an entry by binding it into a fresh
slot, and `foreach` walks the slots.

Concretely the existing `slot_store` / `slot_load` /
`rotate_slot` machinery (codegen.py:870+, 48 disjoint slots
post-axis-bump) is the substrate primitive a binding-array
would sit on top of. A binding-array has:
- A capacity (compile-time-known number of slots)
- A current length (substrate scalar — number of slots used)
- An append operation (write to the next slot, increment length)
- A `foreach` that iterates `0..length-1`, reading each slot
  and binding the value to the loop var

The iteration count is data-dependent (current length) but the
upper bound is compile-time-known (capacity). So `foreach`
can compile to `loop[CAPACITY]` unroll where each iteration is
gated by a soft mask `(current_length > i ? 1 : 0)` —
branchless, body runs per slot but the result is masked off
past the actual length. Same soft-halt-style trick as the
loop refactor.

This needs design work. Sketched here so it's not lost.

## What "the body IS the cell" means concretely

Today `_translate_eigenrotation_loop` extracts the state-var
name from the body and discards everything else. The body
should instead translate as a cell function:

```
while (similarity(state, v_dog) < 0.9) {
    state = bind(state, v_step);
}
```

Should compile to something like:

```python
def _cell(state):
    state = self.bind(state, v_step)   # ← body translated literally
    return state

state, halted, iters = _VSA.while_loop(
    state, _cell, target=v_dog, threshold=0.9, max_iters=50,
    k=20.0,
)
```

And `_VSA.while_loop` runs T fixed steps of:
```python
cand = _cell(state)
sim = cosine(cand, target)
halt = sigmoid(k * (sim - threshold))
halted = min(halted + halt, 1)
state = (1 - halted) * cand + halted * state
```

Notice the cell can be **any** sequence of substrate operations
the user wrote. Bind, bundle, complex_mul, exp, log, anything.
The recurrence is no longer a fixed Haar rotation; it's the
program text itself, applied repeatedly.

This is a substantially bigger change than the 2026-04-30
refactor. The 2026-04-30 work fixed the *execution mechanism*
(no host-side for/if); this would fix the *semantics* (the body
actually means what it says).

## Implementation order if we proceed

1. **Drop `loop(cond)` / unify with `while(cond)`.** Parser-level
   deprecation warning that points users to `while`. Codegen
   collapses both AST nodes to one path.
2. **Make the body the cell in `while(cond)`.** Rewrite
   `_translate_while_as_geometric_loop` to emit the body as a
   Python function (or inline cell) and feed it to a new
   `_VSA.while_loop` that runs the body T times under the same
   soft-halt + output-gating pattern as the current `_VSA.loop`.
   Drop the body-discard, drop the fixed Haar R.
3. **Substrate-pure runtime-N `loop[N]`.** Two options:
   (a) Compile-time error forcing the user to choose between
   compile-time-known N or `while(i < N)` — clear semantics.
   (b) Treat runtime-N `loop[N]` as `while(counter < N)` with an
   implicit counter, lowering to the substrate.
   Probably (a) — it forces the user to be explicit. (b) hides
   the fact that runtime-N requires a substrate counter.
4. **Binding-array `foreach`.** Design the binding-array primitive
   first (likely a new stdlib type wrapping the slot machinery),
   then wire `foreach` to lower to a soft-masked `loop[CAPACITY]`
   over its slots.

Each step is gated on the previous; (1) is cheap, (2) is
substantial, (3) is small if (2) lands first, (4) is its own
medium-scope project.

## Tests that need adding

The current loop tests are blind to body-discard because all
example programs use no-op bodies. New tests need to:
- Put a meaningful statement in a `while(cond)` body and assert
  the side effect happens (e.g. `state` actually changes per
  iteration in a way that matches the body).
- Verify `loop(cond)` no longer parses (or warns).
- Verify runtime-N `loop[N]` no longer emits `for _ in range`.
- Verify `foreach` over a binding-array iterates over the actual
  stored values.

## Open sub-questions

- Surface syntax for binding-arrays: `array<T>(capacity)`?
  Builtin, stdlib, or postponed?
- How does the `while` body talk about "this iteration's
  candidate" vs "the prior state"? Does the body see `state`
  as the prior state (read-only within body, written by the
  cell harness)? Or does the body read AND write `state`
  freely?
- What if the body has side effects that aren't tensor ops
  (e.g. allocates a new vector via `embed`, calls a stdlib
  function)? Is the cell still a pure tensor op, or do we
  accept that the user's body might escape the substrate-
  purity guarantee?
- The output-gating pattern (multiply value axes by halted)
  was designed for the current "rotation only" cell. Does it
  still make sense for arbitrary user bodies? What does
  "incomplete output" mean when the body did N partial bind
  operations?

## Why this matters

The whole substrate-purity story Sutra tells — "Sutra programs
are forward passes through tensor ops on CUDA" — is only true
if every loop form actually compiles to substrate operations.
Today three of the loop forms (data-dependent loops with
discarded bodies) effectively don't run user code, and one
(`loop[N]` runtime) bails to host Python. Both are silent
violations that no test caught because no program exercised
them.

The redesign closes both holes. It also shrinks the language's
loop surface from seven forms to four, which is a separate
win for spec coherence.
