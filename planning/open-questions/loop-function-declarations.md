# Loops as first-class declared functions

**Surfaced:** 2026-04-30
**Status:** Implementation in progress per Emma's 2026-04-30 direction.
**Companion:** `planning/findings/2026-04-30-runtime-substrate-purity-audit.md`,
`planning/open-questions/loop-body-semantics.md`,
`planning/open-questions/loop-surface-redesign.md` (this doc supersedes
the body-as-cell-with-C-syntax part of those).

## Why this design exists

Sutra's substrate-purity claim ("programs compile to a forward pass through
tensor ops on CUDA") only holds if loops execute as substrate-native
recurrent forward passes — RNNs, not host control flow with a thin tensor
wrapper. The 2026-04-30 audit and Emma's pushback established that the
prior body-discard behavior was wrong, AND that a C-style `do { body }
while (cond);` body-as-cell version still wouldn't be RNN-shaped enough
because the recurrence would carry the entire program state through every
iteration. A real RNN's recurrent state is *named and explicit* — the cell
function's parameters ARE the hidden state.

Emma's 2026-04-30 redesign: **loops are first-class declared functions
whose parameters are exactly the recurrent state.** Each loop kind is a
special function decl form. Tail-recursive `pass` triggers the next
iteration. The `loop` keyword at the call site invokes one. By-reference
mutation of the caller's variables on completion is the (acknowledged
non-idiomatic) escape hatch that gets the prototype shipping.

Priority is **make it work**, not make it pretty. Idiomatic cleanup is
queued in `todo.md` for later-this-year.

## The four loop kinds

Each is a function decl prefixed by the kind keyword:

| Kind | First param semantic | Body sees |
|---|---|---|
| `do_while`     | Boolean condition; body always runs once before first check. | Each tick re-evaluates condition AFTER the body runs. |
| `while_loop`   | Boolean condition; checked before each tick. | Body runs only if condition true. |
| `iterative_loop` | Integer count (cap on iterations). The `iterator` keyword reads the current tick (1-indexed). | Body runs N times, no condition. |
| `foreach_loop` | Array (binding-array) the body iterates over. | One element per tick, bound to a name from the param list (TBD how exactly). |

## Function declaration syntax

```sutra
do_while addNumber(x < 11, x) {
    pass x + 1;
}
```

- `do_while` — kind keyword
- `addNumber` — function name
- `(x < 11, x)` — parameter list. **First** param is the condition expression
  (here `x < 11`). Remaining params are the recurrent state vars (here just
  `x`).
- `{ ... }` — body. Statements that read/write the state vars.
- `pass <exprs>;` — tail-recursive yield. Required to provide a value for
  every recurrent state param (in declaration order). The condition is
  *not* in the pass list — it's re-evaluated automatically against the
  new state.

Two equivalent body forms (compiler accepts both):

```sutra
// Form A: pass an expression directly.
do_while addNumber(x < 11, x) {
    pass x + 1;
}

// Form B: mutate then pass.
do_while addNumber(x < 11, x) {
    x = x + 1;
    pass x;
}
```

### `replace` keyword in `pass`

When a state param shouldn't update (you want to keep the value the loop
was called with for that slot), use `replace` instead of an expression:

```sutra
do_while foo(cond, x, y) {
    // ... only x changes; y stays at its initial value across iterations.
    pass x + 1, replace;
}
```

Useful when the loop has multiple state params but the body only updates
some of them per tick.

### Default initializers

Parameters can carry a default value at declaration:

```sutra
foreach_loop findMax(arr, max = 0) {
    // body uses the array element + max
    pass max_so_far;  // assuming max_so_far computed in body
}
```

When the loop is called without specifying that parameter, the default is
used. This pattern is common for accumulator state (running max, sum,
count, etc.).

## Call site syntax

```sutra
function int main() {
    int x = 9;
    loop addNumber(x < 11, x);
    return x;       // x has been mutated to 11 by the loop
}
```

- `loop` keyword prefix marks this as a loop invocation (vs a regular
  function call).
- `addNumber(x < 11, x)` — the loop function name + arguments.
  - First arg is evaluated to seed the condition for the first tick.
  - Remaining args are passed to the loop's state params.
- After the loop call, the caller's variables that were passed as state
  args have been mutated to the loop's final state values.
  This is by-reference passing. Acknowledged non-idiomatic; will be
  cleaned up later (see todo.md).

## The iterator keyword (iterative_loop only)

```sutra
iterative_loop fillArray(10, arr) {
    arr[iterator - 1] = iterator;  // iterator: 1, 2, ..., 10
    pass arr;
}
```

- `iterator` is read-only; cannot be assigned, cannot appear on the
  left side of `=`, cannot be passed.
- Starts at 1, increments by 1 each tick.
- Already exists in Sutra (used by `loop[N as i]` compile-time unroll); the
  iterative_loop kind reuses the same machinery.

## Substrate execution model (the RNN)

The loop function compiles to a Python function (the cell) that runs T
fixed cell steps. T defaults to 50 (compile-time-fixed). Each step:

1. Evaluate condition (for while/do_while) or check tick number (for
   iterative) or fetch next array element (for foreach).
2. Compute soft halt indicator: a sigmoid that goes to 1 when condition
   becomes false (or tick exceeds count, or array exhausted).
3. Accumulate cumulative halt: `halted = min(halted + halt, 1)`.
4. Run the body. The body's `pass` updates the recurrent state params.
5. Soft-mux: state ← (1 − halted) · new_state + halted · old_state.
   Once `halted` saturates at 1, the state is frozen at its last
   pre-halt value.

After T steps:
- `AXIS_LOOP_DONE = halted` is set on the output (for the program-level
  completion-flag propagation, eventually).
- Each state param's final value is written back to the caller's variable.

The Python `for _t in range(T)` is meta-iteration over a compile-time-fixed
count — the substrate sees T inline cell calls, no data-dependent control
flow.

## What doesn't work yet (open sub-questions)

1. **Substrate-pure condition evaluation.** For now the condition is
   evaluated as a Python boolean expression (e.g. `x < 11` returns a
   Python bool). The substrate-pure version computes a 0-dim soft-truth
   tensor and feeds it through the sigmoid. Acceptable boundary
   compromise for the prototype; queued for cleanup.
2. **Loop functions can call other loop functions.** Allowed in principle
   (each is just a function), but recursion depth and termination are
   the responsibility of the caller for now. No mutual-recursion
   prevention in V1.
3. **Loops have NO access to outer scope.** Pure functions over their
   declared parameters only. No closure capture of caller variables.
   This is a hard rule per Emma 2026-04-30: "they do not have access
   to anything."
4. **Multi-arg `pass` ordering.** `pass` provides values for state
   params in declaration order. `pass replace, expr;` keeps first
   param's input value, updates second. No keyword-arg form yet.
5. **foreach element binding.** Open: how exactly does the body name
   the current element? Maybe the array param itself is rebound each
   tick to the current element (overloads the param name); maybe a
   separate `element` keyword. TBD when foreach implementation lands.

## Sutra-specific gotchas

- **`>=` and `<=` don't exist.** Sutra has `>` only because fuzzy
  comparison returns "unknown" at equality; `>=` would be redundant.
  Number-adder uses `x < 11` (continue while less than 11) → final
  x = 11 starting from 9.
- **Loop body cannot return** (no `return` statement allowed inside).
  Use `pass` or fall through. The function-decl form means the
  semantics of "return from this function" are different from a
  regular function.

## Implementation order

1. Lexer: add tokens for `do_while`, `while_loop`, `foreach_loop`,
   `iterative_loop`, `loop`, `pass`, `replace`.
2. AST: add `LoopFunctionDecl` (kind, name, params with optional
   defaults, body), `PassStmt` (list of `Expr | ReplaceMarker`),
   `LoopCallStmt` (function name, args, target var bindings derived
   from arg expressions).
3. Parser: parse the new top-level decl form, the `pass` stmt, the
   `loop name(...)` call form. Keep existing `do { body } while ();`
   surface form parsing only as a deprecated alias that errors.
4. Codegen: emit each loop function as a Python function with the
   T-step soft-halt cell. Loop call emits invocation + writes state
   values back to caller's slot vars.
5. Number-adder example + tests.
6. Update todo.md with "make loops idiomatic" later-this-year item.

## When this gets re-thought

If the by-reference call shape proves too painful in real programs,
the cleanup is to make loop calls return a tuple of state values that
the caller assigns:

```sutra
x = loop addNumber(x < 11, x);   // returns just x's new value
// or for multi-state:
(max, count) = loop findMax(arr, max=0, count=0);
```

This reads more naturally and avoids the by-reference surprise. Move
on it once the basic shape is shipping and a few real programs
exercise it.
