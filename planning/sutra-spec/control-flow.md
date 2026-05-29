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

**The 2026-04-30 redesign supersedes the earlier C-style loop
surface.** Loops are now declared as **first-class functions** whose
parameters are exactly the recurrent state. Each loop kind is a
function-declaration form prefixed by a keyword; the body uses
`pass` for tail-recursive yield. At the call site, the `loop`
keyword invokes a declared loop function. The substrate executes
loops as an RNN-style branchless tail-recursive cell (a fixed-T
unroll of the body with a soft halt); the loop function's
parameters are the named recurrent state — the implicit axon the
loop threads from tick to tick.

The full design is at loop-function-declarations (pruned 2026-05-28; in git history)
and the user-facing surface is at `docs/loops.md`. This section
gives the canonical summary.

### The loop kinds

| Kind | First param | Body sees |
|---|---|---|
| `do_while NAME(cond, state...)` | Boolean condition; body always runs once before the first check. | Each tick re-evaluates condition after the body. |
| `while_loop NAME(cond, state...)` | Boolean condition; checked before each tick. | Body runs only if condition is true. |
| `iterative_loop NAME(count, state...)` | Integer count (cap on iterations). `iterator` reads current tick (1-indexed). | Body runs N times, no condition. |
| `foreach_loop NAME(arr, state...)` | Binding-array the body iterates over. | One element per tick, bound to the loop's element param. |

### Function declaration syntax

```sutra
do_while addNumber(x < 11, int x) {
    pass x + 1;
}
```

- `do_while` — kind keyword
- `addNumber` — function name
- `(x < 11, int x)` — parameter list. **First** param is the
  condition (`x < 11`); remaining params are the typed recurrent
  state vars (just `int x`).
- `{ … }` — body. Reads/writes the state vars.
- `pass <exprs>;` — tail-recursive yield. Required to provide a
  value for every recurrent state param in declaration order. The
  condition is *not* in the pass list — it's re-evaluated against
  the new state automatically.

The compiler accepts two equivalent body shapes:

```sutra
// Form A: pass an expression directly.
do_while addNumber(x < 11, int x) { pass x + 1; }

// Form B: mutate then pass.
do_while addNumber(x < 11, int x) { x = x + 1; pass x; }
```

The `replace` keyword in a `pass` list keeps a state slot at its
loop-call-time value for that tick:

```sutra
do_while foo(cond, int x, int y) {
    pass x + 1, replace;   // y stays at its initial value
}
```

### Call site syntax

```sutra
function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;       // x has been mutated to 11 by the loop
}
```

The caller declares state vars with the `slot` modifier so they
live in the synthetic-axis slot block (per the slot-rotation
runtime); the loop function rotates those slots in place per
tick.

- `loop` keyword marks this as a loop invocation (not a regular
  function call).
- After the loop call, the caller's variables passed as state
  args are mutated to the loop's final state values.

**This by-reference mutation is acknowledged as non-idiomatic.**
The cleanup direction (todo.md §"Make loops idiomatic") is to
move to a tuple-return form:

```sutra
x = loop addNumber(x < 11, x);            // single-state return
(max, count) = loop findMax(arr, 0, 0);   // multi-state return
```

Until that cleanup lands, the by-reference form is the canonical
surface.

### Tail-call return form

For a loop call as a tail expression of an enclosing function, the
`return NAME(args)` short form invokes the loop and returns the
resulting state in one step. See loop-tail-call-surface (pruned 2026-05-28; in git history) for
the surface and lowering.

### Substrate execution model

The loop function compiles to a Python "cell" function that runs
T fixed cell steps (T defaults to 50, compile-time-fixed). Each
step:

1. Evaluate condition / check tick number / fetch next array element.
2. Compute soft halt: a sigmoid that goes to 1 when the loop should
   stop.
3. Accumulate cumulative halt: `halted = min(halted + halt, 1)`.
4. Run the body; `pass` provides the next state.
5. Soft-mux: `state ← (1 − halted) · new_state + halted · old_state`.
   Once `halted` saturates at 1, state is frozen at its pre-halt
   value.

After T steps, `AXIS_LOOP_DONE` on the output carries the
cumulative halt (the completion flag); each state param's final
value is written back to the caller's variable.

The Python `for _t in range(T)` is meta-iteration over a compile-
time-fixed count — the substrate sees T inline cell calls, no data-
dependent control flow.

### `loop[N]` — bounded compile-time unroll (separate from the loop kinds above)

`loop (N) { body }` or `loop (N as i) { body }` where `N` is an
integer literal unrolls at compile time. Zero runtime iteration,
zero tail-recursive cell — the compiler emits the body `N` times, with
the index variable `i` substituted with `0, 1, …, N−1` in each
iteration if the `as i` form is used.

If `N` is a non-literal expression, the codegen currently emits a
Python `for _ in range(N)` loop around the body (no unrolling).
This is the substrate-purity escape hatch tracked under "Open
questions" below.

### `foreach` over array literals — compile-time unroll

`foreach (TYPE x in [a, b, c]) { body }` unrolls at compile time —
one body emission per element. The iterable must be an
`ArrayLiteral`. For dynamic foreach over a runtime binding-array,
use the `foreach_loop` kind instead. Test:
`sdk/sutra-compiler/tests/corpus/valid/foreach_literal.su`.

### Retired: C-style `while`, `for`, `do-while`, and `loop(cond)`

Prior to 2026-04-30 the language accepted C-style
`while (cond) { body }`, `for (init; cond; step) { body }`,
`do { body } while (cond);`, and the body-discard `loop(cond) { body }`
form. The codegen now **rejects all four** with `CodegenNotSupported`
pointing at the function-decl forms above. The parser still
accepts the syntax to give a clear error message, but no
substrate path remains. Programs hit by this should migrate to
the appropriate kind:

| Old form | New form |
|---|---|
| `while (cond) { body }` | `while_loop name(cond, state) { body; pass state'; }` + `loop name(cond, state);` |
| `for (init; cond; step) { body }` | `while_loop name(cond, state) { body; step; pass state'; }` (init done by caller) |
| `do { body } while (cond);` | `do_while name(cond, state) { body; pass state'; }` |
| `loop(cond) { body }` | one of the four kinds above, depending on the termination shape |

The semantic-corrections doc captures the migration; the loop
spec doc (loop-function-declarations (pruned 2026-05-28; in git history)) captures the design
history.

### `try-catch` — parsed but rejected

The parser accepts `try { … } catch { … }`. The codegen rejects
it — there is no raise / throw primitive in Sutra today, so
"what would catch catch" is an unresolved design question rather
than a missing implementation. Parser support exists so the
surface syntax is reserved; the feature itself is parked in
`todo.md` as a longer-term item.

The one carve-out: `try { await ... } catch { ... }` inside an
`async function` has a defined lowering, because an awaited promise
can reject and the surrounding async function needs a recovery path.
See `promises.md` §"Rejection propagation" — the `catch` block runs
unconditionally on rejection of the awaited promise, no exception
variable is bound. The general non-async `try` / `catch` remains
unimplemented.

## Promises and async/await — see `promises.md`

`async function`, `await expr`, and `Promise<T>` are syntactic sugar
over the tail-recursive loop machinery above. Each `await` becomes a
gated `while_loop` whose halt condition is "the awaited input axon
arrived." The full surface syntax, lowering, and three-state
(pending / fulfilled / rejected) semantics are specified in
`promises.md`. Promises are not a new control-flow primitive —
they're a controlled vocabulary the standard library exposes for
patterns the existing loops already express.

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
