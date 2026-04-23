# Defuzzify: what does the polarization rule look like?

**Opened:** 2026-04-23.
**Status:** Known divergence between user's stated vision and the
currently-shipped `defuzzify_trit` implementation. Surfacing the
gap rather than quietly picking one.

## User's vision

Per 2026-04-23 session:

> And our defuzzy was just applying this operation n times (default 10)
>
>     fuzzy f = "cat" == "tiger";
>     // manual defuzzification
>     Loop (10){
>       f = f == true;
>     }
>
> And so from there we have it polarize to 1 or -1

So `defuzzify(f)` is definitionally `iterate N times: f = f == true`.
The inner operator is the same `==` the language already uses for
equality — no new primitive.

## What actually happens under the current `==` semantics

Now that `==` is implemented (commit c7d380d's successor: vector
cosine similarity projected onto the truth axis), we can trace the
iteration:

- Let `f = make_truth(x)` for some `x ∈ [-1, +1]`.
- Let `true = make_truth(+1)`.
- `f == true`: cosine similarity of two vectors that live entirely
  on the truth axis. Both have zero in every other coordinate and
  nonzero only at `synthetic[AXIS_TRUTH]`. Cosine of two colinear
  vectors is `sign(x·1) = sign(x)`. So `f == true` snaps to
  `make_truth(+1)` (if `x > 0`) or `make_truth(-1)` (if `x < 0`).

**One iteration is enough to polarize.** The default `N=10` does
nothing after the first pass, because `cos(make_truth(±1), make_truth(+1)) = ±1`
is already at the fixed point.

For a fuzzy value that came from a generic vector comparison (like
`"cat" == "tiger"`), the result already lives purely on the truth
axis with a scalar cosine as its truth coordinate. So the same
snap-in-one-iteration behavior applies.

## The implementation that actually shipped

`codegen_numpy.py:_NumpyVSA.defuzzify_trit(v, iters=10, beta=2.0)`
implements a three-way exp-weighted softmax polarizer:

```
for _ in range(iters):
    w_neg  = exp(-β · (x + 1)²)
    w_zero = exp(-β · x²)
    w_pos  = exp(-β · (x - 1)²)
    x'     = (-w_neg + w_pos) / (w_neg + w_zero + w_pos)
    β      *= 2
```

This is *gradual* polarization: `x=0.3` with β=2 moves to ~0.27 in
one iter, then further each pass as β doubles. It also preserves
the neutral — a value near zero stays near zero, because the
`w_zero` weight dominates when both `(x+1)²` and `(x-1)²` are
large.

This has very different behavior from `iterate f = f == true`:

| input `x` | `iterate f==true` (cos eq) | `defuzzify_trit` (softmax poles) |
|---|---|---|
| +0.7      | snap to +1 in 1 iter        | gradual toward +1                |
| +0.3      | snap to +1 in 1 iter        | stays near 0 (closer to zero pole) |
| +0.05     | snap to +1 in 1 iter        | stays near 0                      |
| 0.0       | stays 0 (cos undefined, guarded to 0) | stays at 0              |
| -0.5      | snap to -1 in 1 iter        | gradual toward -1                |

The three-way polarizer treats 0 as a first-class attractor with its
own basin of attraction. The `f == true` iteration treats 0 as a
discontinuity — any nonzero value snaps to the nearest pole in one
step, regardless of magnitude.

## What the user probably meant

The user's description of `iterate f = f == true` collapsing `f` to
`±1` is consistent with cos-based equality: after one iteration any
nonzero truth snaps to its sign. So the user's mental model is
correct — iteration just needs N ≥ 1. The "default 10" is a safety
margin.

But this is also *not* a three-way polarizer. It's a two-way one.
There is no "preserve the neutral" property under `f == true` iteration;
instead, the rule is "snap to the nearest binary pole, with `0` as
the sharp discontinuity between the basins."

That directly contradicts the `trit` design, which specifically wants
a three-way polarizer that preserves the neutral.

## Two compatible spec paths

### Path A: one defuzzify, two behaviors via class

- `defuzzify(fuzzy f)` = `iterate N: f = f == true`. Binary poles,
  neutral is a discontinuity.
- `defuzzify(trit t)` = the softmax three-way polarizer. Ternary
  poles, neutral is preserved.
- Two different classes → two different defuzzification rules, both
  following the same iterated-sharpening shape but with different
  fixed-point sets.

The current implementation ships `defuzzify_trit` under the trit
path. `defuzzify(fuzzy)` hasn't been written; it would be a thin
wrapper around the iteration-of-`eq` formula.

### Path B: one defuzzify, softmax always

- Both fuzzy and trit use the softmax polarizer with a pole-set
  parameter:
  - fuzzy: poles `{-1, +1}` (w_zero drops out)
  - trit:  poles `{-1, 0, +1}`
- Iteration count and β control sharpness uniformly.
- The user's `iterate f == true` framing is *an approximation* —
  nominally the same idea, but not the rule the compiler emits.

This is the cheat-adjacent path: the user writes one formula,
the compiler emits a different one. Not honest unless we're
explicit about it.

### Path C: drop `defuzzify_trit` entirely, implement the user's formula

- `defuzzify(x) = iterate N: x = x == true`
- Two-pole behavior for all truth-axis types.
- The "preserve the neutral" property that motivates `trit` has to
  come from somewhere else — maybe: `trit t` defuzzifies by
  comparing to `unknown` not `true`, i.e. `iterate: t = t == unknown`
  and see which pole stabilizes.

Under cos-equality, `t == unknown` where `unknown = make_truth(0)` is
undefined (zero norm on one side, guarded to truth=0). So `iterate: t = t == unknown`
always returns 0. That's not right either.

Option C would need a different rule for the trit case.

## Recommendation

Path A is the honest minimum: implement `defuzzify(fuzzy)` per the
user's stated formula, keep `defuzzify_trit` as the three-way rule
it already is, and call out in the spec that the two types
intentionally have different defuzzification semantics matching
their different pole sets.

Not implemented in the commit that opened this doc — the divergence
is captured here so a future session can close it with an explicit
design choice rather than a quiet pick.

## Pointers

- `==` implementation: `codegen_numpy.py:_NumpyVSA.eq` (lands with
  this commit series).
- Current trit polarizer: `codegen_numpy.py:_NumpyVSA.defuzzify_trit`.
- Fuzzy primitive-class design: `docs/primitive-classes.md`.
- Related: `planning/open-questions/zero-as-explicit-neutrality.md`.
