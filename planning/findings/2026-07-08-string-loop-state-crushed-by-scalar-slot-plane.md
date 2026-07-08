# String/vector loop state through `slot` + `loop NAME(...)` is crushed to a scalar (2026-07-08)

Round-26 composition drive: FizzBuzz 1..15 via `iterative_loop` with a String accumulator —
loops + strings + comparisons in one program.

## Measured

```sutra
iterative_loop build(15, String acc) {
    pass string_concat(string_concat(acc, fizzbuzz(iterator)), make_string(" "));
}
function string main() {
    slot String acc = make_string("");
    loop build(15, acc);
    return acc;
}
```

compiles cleanly, then dies at runtime:
`RuntimeError: index_select(): Index to scalar can have only 1 value, got 97 value(s)`
(string_concat receiving a 0-d `acc`).

## Root cause

The `slot` state plane stores ONE SCALAR per slot by design — `slot_store` projects any
incoming value to its 0-d real-axis reading (`_slot_cell` / `_re`). A String (or any
vector-valued) state threaded through the `loop NAME(state...)` by-reference machinery is
silently reduced to its real-axis scalar on the first store; the crash only surfaces when a
String op later demands the full vector. Scalar loop state (the documented `do_while_adder`
shape) is fine; vector state has a DIFFERENT mechanism (`recurring TYPE name = ...`, the
substrate-resident tensor slots the ntm/NFA work uses).

## Follow-ups (queued)

1. **Diagnostic (bounded):** a compile-time error when a `slot`-declared variable's type is
   in the text/vector family and it is passed as `loop` state — steering to `recurring`
   (inside non-halting loops) or scalar state. Today's face is an opaque torch shape error.
2. **Design question (Emma-shaped):** should `iterative_loop`/`while_loop` state params
   support vector-valued state directly (per-slot planes sized d instead of 1)? The loops.md
   "planned cleanup" (return tuples instead of by-reference mutation) intersects this.
