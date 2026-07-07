# `<=` / `>=` return NEUTRAL (0) at exact ties — deliberate, but newcomer-hostile (2026-07-06)

Found by a real-program-reach usability drive (PINNED TAIL): a newcomer's `2 <= 2` does not evaluate to
true.

## Measured

Reading the truth axis of a `bool`/`fuzzy` comparison result (runtime_dim 16, model-free):

| expr | result | expected |
|---|---|---|
| `5 > 3` | +1 | +1 ✓ |
| `3 > 5` | -1 | -1 ✓ |
| `5 == 5` | +1 | +1 ✓ |
| `2 <= 3` | +1 | +1 ✓ |
| `3 <= 2` | -1 | -1 ✓ |
| **`2 <= 2`** | **0.0** | **+1 (true)** ✗ |
| **`2 >= 2`** | **0.0** | **+1 (true)** ✗ |

So `<`, `>`, `==`, and the non-tie `<=`/`>=` are correct; ONLY the exact-tie case of `<=`/`>=` is wrong —
it returns the truth-axis NEUTRAL (0), not true.

## Why (it is deliberate)

`stdlib/logic.su` defines them as the strict operators, with an explicit comment:

```
// ge / le — on the differentiable-tanh scheme, `>=` and `<=` collapse
// to `>` and `<`: both give tanh(0) = 0 on exact ties. Programs that
// need to distinguish strict from tie compose with `==`.
function fuzzy ge(complex a, complex b) { return a > b; }
function fuzzy le(complex a, complex b) { return a < b; }
```

So `a <= b` is literally `a < b` (the "or equal" is dropped), and at `a == b` the tanh comparison is 0.
This is intentional, and the stated reason is the **differentiable-tanh scheme** — the smooth comparison
used for gradients/training.

## The tension

Mathematically and for a newcomer this is wrong: `2 <= 2` must be true. A loop guard `i <= n` silently
misbehaves at the boundary. The obvious fix keeps it fuzzy and composable:

```
function fuzzy le(complex a, complex b) { return or(a < b, a == b); }   // ge symmetric
```

Measured: `or(2<2, 2==2)` = +1 (tie → true, fixed), `or(2<3, 2==3)` = +1, `or(3<2, 3==2)` = −0.52 (false).
So it restores tie-correctness while staying fuzzy for the strict part.

**But the tradeoff is real:** `==` is cosine equality (crisp on identical operands), and folding it into
`<=`/`>=` may cost the smooth differentiability the current strict-only form was chosen to protect. That
is a language-semantics decision with a training-vs-newcomer-correctness tradeoff — **Emma's call**, not a
unilateral change. Not touched.

## Disposition (NEEDS-DECISION)

- **(a)** keep the strict-only `<=`/`>=` (differentiable), and instead make the tie-at-boundary behaviour
  discoverable (doc it on the operators page + a note that ties need `==`); or
- **(b)** adopt `or(<, ==)` (tie-correct, possibly less smooth) — verify no fuzzy/training program regresses.
No test asserts the current tie=0 behaviour (grep clean), so either way is test-open.
