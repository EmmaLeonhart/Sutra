# Loops

Sutra has two loop forms:

1. **`loop (N) { body }`** — bounded compile-time unroll. The body is emitted N times in sequence; no runtime iteration; `iterator` inside the body is the per-copy compile-time constant. This is the **preferred** form for any loop with a known iteration count.

2. **Loop function declarations** (`do_while`, `while_loop`, `iterative_loop`, `foreach_loop`) — first-class declared functions whose parameters are the recurrent state. The body uses `pass` to yield the next iteration's values. Call sites use the `loop` prefix. This is the form for loops with runtime data dependence.

The retired form is the **C-style imperative loop** — `while(cond) { body }`, `do { body } while(cond)`, `for(init; cond; step) { body }`. Those compiled to host-side branches and didn't survive the 2026-04-30 substrate-purity audit. They're neither a counter loop nor a tail-recursive cell, which is why they didn't fit.

The two forms above DO fit, for different reasons: `loop (N)` runs at compile time (no host branches needed), and the declared-function loops compile to substrate-pure RNN cells (no host counter, soft-halt mask freezes state on the substrate).

| Form | When to use |
|---|---|
| `loop (N) { body }` | Compile-time-known iteration count. Body is emitted N times; `iterator` substitutes in. |
| `do_while NAME(...)` | Body runs once before the condition check; condition re-evaluated each tick. |
| `while_loop NAME(...)` | Condition checked before each tick; body skipped if false at entry. |
| `iterative_loop NAME(...)` | Run N times, body sees `iterator` (N can be runtime). |
| `foreach_loop NAME(...)` | Walk a Sutra binding-array; body sees `element`. |

---

## `do_while`

Body runs once before the first condition check. Re-evaluates after each tick.

```sutra
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;     // 11
}
```

- `do_while addNumber(...)` — declaration. First param is the condition expression; remaining params are the recurrent state vars.
- `pass x + 1;` — tail-recursive yield. Provides one value per recurrent state param, in declaration order. The condition is re-evaluated automatically against the new state, not passed.
- `loop addNumber(x < 11, x)` — call site. Mutates the caller's `x` by reference on completion.

Two equivalent body forms — the compiler accepts both:

```sutra
// Form A: pass an expression directly.
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

// Form B: mutate then pass.
do_while addNumber(x < 11, int x) {
    x = x + 1;
    pass x;
}
```

### `replace` keeps the input value

When a state param shouldn't update on an iteration, use `replace` in its `pass` slot — that keeps whatever value the loop was called with for that param.

---

## `while_loop`

Same as `do_while` but the condition is checked before each tick. Body is skipped entirely if the condition is false at entry.

```sutra
while_loop drainQueue(count > 0, int count) {
    pass count - 1;
}
```

---

## `iterative_loop`

Runs N times. Body sees the `iterator` keyword, which is 1-indexed and ranges from 1 to N.

```sutra
iterative_loop sumToN(5, int n) {
    pass n + iterator;
}

function int main() {
    slot int n = 0;
    loop sumToN(5, n);
    return n;     // 0 + 1 + 2 + 3 + 4 + 5 == 15
}
```

`iterator` is contextual — only meaningful inside an `iterative_loop` body. It is **never a runtime variable** in the host sense; the substrate sees it as part of the cell's per-tick state.

---

## `foreach_loop`

Walks a binding-array (Sutra's array form: `arr[0]` is the length, `arr[1..length]` are the elements). Body sees the `element` keyword bound to the current item.

```sutra
foreach_loop applySteps(steps, vector x) {
    pass element(x);
}
```

The array has to be a Sutra binding-array (constructed via `array_from_literal` or read from another binding-array operation). See [Memory](memory.md) for binding-array semantics.

---

## Call-site shape

```sutra
loop NAME(cond_or_count_or_array, state1, state2, ...);
```

- `loop` is the call prefix; the named function `NAME` must be a declared loop function.
- The call site mutates the caller's named variables for each state param. The state vars must be `slot`-declared at the caller.
- Loop functions have **no outer-scope access** — they're pure functions over their declared parameters only.

The by-reference call shape is acknowledged non-idiomatic; the cleanup direction (return tuples, no by-ref mutation) is in `todo.md` § "Make loops idiomatic" for later.

---

## Substrate execution

Under the hood, each loop kind compiles to a fixed-T tensor-op unroll where T is the runtime compute budget. Each "tick" is one cell evaluation:

- The cell function takes the current state and emits the next state plus a `done` flag derived from the condition (or array exhaustion, or iteration count).
- Soft-halt sigmoid + monotone cumulative + soft-mux freeze: once `done` crosses the threshold, subsequent ticks copy the current state forward, so the final output is the state at the moment of completion.
- `AXIS_LOOP_DONE` (a reserved synthetic axis) carries the completion flag through the unroll.

Result: the host runs the unroll once; the substrate sees T inline cell evaluations regardless of when the logical loop terminated. No counter lives on the host. See `planning/findings/2026-04-30-rnn-loop-architecture.md` for the design rationale.

---

## Choosing between them

| you want | use |
|---|---|
| body must run at least once, then check | `do_while` |
| check first, possibly skip the body | `while_loop` |
| run N times | `iterative_loop` |
| iterate a Sutra binding-array | `foreach_loop` |

The common theme: every Sutra loop is a substrate-resident RNN cell. Termination is on the substrate (a soft-halt mask), not a host counter.
