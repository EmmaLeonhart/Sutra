# `while_loop` halt supports only a SINGLE condition — compound `&&` / `||` halts are ignored past the first conjunct

**Date:** 2026-06-17
**Context:** extending the Haskell frontend to >2-guard TAIL recursion (multiple non-recursive bases
+ one `otherwise`-recursive step, e.g. `f acc n | n <= 0 = acc | n == 1 = acc+100 | otherwise =
f (acc+n) (n-1)`). The natural lowering is one `while_loop` that continues while NO base matches —
i.e. a continue condition `neg(c1) && neg(c2)` (`(n > 0) && (n != 1)`). It compiled and ran, but
returned the WRONG answer.

## Measured

A minimal `while_loop` with a compound `&&` halt:

```
while_loop _l((i < 5) && (i != 3), int i = 0) { i = i + 1; }
function int main() { int i = 0; slot int _i = i; loop _l((i < 5) && (i != 3), _i); return _i; }
```

| expected (if `&&` halt worked) | measured |
|---|---|
| **3** (stop at `i == 3`: `(3<5) && (3!=3)` = false) | **5** (ran to `i == 5` — only the first conjunct `i < 5` gated the loop; `i != 3` was ignored) |

The 3-guard tail recursion above returned **6** instead of **105** for `f 0 3`: the loop ran past
`n == 1` down to `n == 0` (continue `(n>0) && (n!=1)` behaved as just `n > 0`), then the post-loop
base blend selected `acc = 6` (the `n <= 0` base).

So the substrate `loop(cond)` halt evaluates a **single comparison only**; a compound boolean
(`&&`, and by the same mechanism `||`) is not honored past the first conjunct. This is consistent
with the loop lowering being an eigenrotation + a single match/threshold test, not a boolean circuit.

## Consequence

- **>2-guard guarded TAIL recursion is BLOCKED** when the multiple base conditions cannot be merged
  into ONE comparison. Some cases merge by algebra — `n <= 0 || n == 1` is `n <= 1` for integers — but
  that is case-specific, not a general transform. The general multi-base shape needs a compound halt,
  which the substrate does not provide. The Haskell extension was written, measured wrong, and
  **reverted** (kept at the existing 2-guard scope) rather than shipped.
- 2-guard guarded recursion (one base + one recursive guard) is unaffected — it halts on the single
  base condition.

## Options for a later attempt

1. **Algebraic merge** of mergeable base sets into one comparison (`n<=0 || n==1` → `n<=1`); detect
   the narrow mergeable cases only, leave the rest UNSUPPORTED.
2. **A derived single-flag halt** — carry a loop-state variable that is the substrate `||` of the base
   conditions and halt on `flag`. Needs the loop to halt on a carried boolean computed in the body;
   whether the halt can read a body-computed flag cleanly (vs. re-evaluating `cond(state)`) is itself
   unverified.
3. **Accept the limit** — document >2-guard tail recursion as out of scope; it is rare.

Repro: `/tmp/andcond.su` in the session transcript; `python -m sutra_compiler --run`.

## RESOLVED 2026-06-18 (queue §0.3) — TWO root causes, both fixed

The "compound halt ignored past the first conjunct" framing turned out to be TWO bugs the repro
`(i<5) && (i!=3)` happened to combine. Both are fixed; the substrate now honors a general compound
halt (verified `(i<5)&&(i!=3)=3`, `(i<5)&&(i<4)=4`, `(i<5)||(i<2)=5`, single `(i!=3)=3`, and the
multibase shape `(n>0)&&(n!=1)` counting down).

**Root cause 1 — `&&`/`||` composed on the wrong truth domain.** The comparison primitives (`gt`,
`eq_synthetic`, `neq_synthetic`) return SIGNED truth in `[-1, 1]` (positive = true), and the loop halt
thresholds that at 0 (`heaviside`). But the general `&&`/`||` operator inlines the Zadeh POLYNOMIAL,
which is only correct on `[0, 1]` truth — on signed truth it gives the wrong sign, so the compound
condition's truth axis didn't reflect the conjunction. On signed truth, Zadeh AND/OR ARE min/max
(`min(a,b) > 0 ⇔ both > 0`). Fix: the while_loop / do_while condition keeps `&&`/`||`/`!` un-inlined
(inliner `_lower_loop_condition_ops`) and codegen lowers them to `_VSA.truth_and`/`truth_or`/`truth_not`
(min/max/negate) via `_translate_loop_condition`. (`truth_axis` was also made 0-d-safe so the scalar
these return passes through to `heaviside`.)

**Root cause 2 — equality halts NEVER fired, because of a `_as_any_vector` 0-d-tensor bug.** The loop
soft-mux `i = (1-_halted)·i + _halted·_pre_i` turns the loop counter into a 0-d TENSOR after the first
tick. `_as_any_vector` (used by `eq_synthetic`) returned a 0-d tensor as-is instead of lifting it onto
the real axis (the way `_as_complex_vector`, used by `gt`, already did). So `diff = counter − make_real(k)`
broadcast the scalar across every axis and the distance was never 0 even when equal → `eq_synthetic`
read "not equal" at the matching value → the equality halt never fired (the loop ran away). This is why
`gt`-based loops always worked but `==`/`!=` loops hung. Fix: `_as_any_vector` now scatters a 0-d
tensor onto the real axis, on-device (no `float()` readout), mirroring `_as_complex_vector`. This was
the real content behind the loop-desugar docstring's "equality/negation bounds may not terminate
crisply" caveat — not inherent fuzziness, a representation bug.

Regression tests: `sdk/sutra-compiler/tests/test_loop_function_decl.py::TestCompoundAndEqualityHalt`.
