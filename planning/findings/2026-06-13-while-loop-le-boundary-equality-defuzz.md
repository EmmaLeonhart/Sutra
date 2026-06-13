# `<=` / `>=` loop bounds are off-by-one on the substrate (boundary-equality defuzzes false)

**Date:** 2026-06-13
**Status:** measured limitation, not a lowering bug. Use `<` / `>` for loop bounds.

## What was measured

The `sutra-from-rust` `while` lowering (Rust `while COND { BODY }` → a hoisted
Sutra `while_loop` + `slot`/`loop`/write-back, the OCaml `_lower_while` shape)
was verified end-to-end on the substrate. Two identical loops, differing only in
the comparison operator in the condition:

| Loop | Condition | Expected | Measured |
|---|---|---|---|
| `lt_sum(6)`: `i` 1→, `acc += i; i += 1` | `i < n` | 1+2+3+4+5 = 15 | **15** ✓ |
| `le_sum(5)`: `i` 1→, `acc += i; i += 1` | `i <= n` | 1+2+3+4+5 = 15 | **10** ✗ |

The `<=` loop stops one iteration early: at `i == n` the body does not run, so
the final `i == n` term is dropped (10 = 1+2+3+4, missing the i=5 term).

## Why

This is **not** a transpiler bug — the lowering faithfully emits Sutra `<=`. It
is the substrate comparison's behavior at exact equality. `<=` carries an
equality component, and equality at a loop boundary defuzzes false (the same
"literal-vs-loop-state `==` defuzz-false" behavior documented for the ISO-5
machine, finding `2026-06-06-iso5-full-machine-handedit-and-dispatch-blocker`).
When the loop variable reaches the bound exactly, the `<=` truth is not high
enough to keep the `while_loop` iterating, so it exits before the boundary
iteration.

## Consequence / what to do

- **The `while` → substrate-loop lowering is correct.** Verified with `<`
  (`sdk/sutra-from-rust/tests/fixtures/while_sum`, `sum_to(5) = 15`).
- **Write loop bounds with strict `<` / `>`, not `<=` / `>=`.** A `<=` bound
  silently loses the boundary iteration. This matches how the OCaml reference
  frontend's `while` fixtures are written (all use `<`).
- A general fix would live at the substrate comparison level (a sharper
  equality defuzz at integer lattice points), not in any frontend. Out of scope
  for the transpiler track; tracked with the broader equality-defuzz boundary
  work.
