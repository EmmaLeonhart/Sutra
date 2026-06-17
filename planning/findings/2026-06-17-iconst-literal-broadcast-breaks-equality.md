# Bare source literals as pushed values broadcast across all axes and silently break `==`

**Date:** 2026-06-17
**Where:** `experiments/iso5_substrate_dispatch/jvm_core.su` (JVM core, step 2d-final), found while
running the real `javac`-emitted iterative-factorial method byte-for-byte.
**Status:** root-caused and fixed; the fix is verified on the substrate (`fact(0..5) =
1,1,2,6,24,120`).

## Symptom

The real `javac` factorial method returned **`(n−1)!`**: `fact(4) → 6`, `fact(5) → 24`. A clean
one-iteration-early exit. The loop guard `if_icmpgt` (exit if `i > n`) was firing at `i == n`.

## What it was NOT

The obvious hypothesis — the equality boundary of the strict comparison is fuzzy — was **wrong**,
and measuring it is what redirected the investigation:

- `if_icmpgt 4>4` and `5>5` with **literal** operands → clean fall-through (no branch). Correct.
- `if_icmpgt` with a **computed** `i=4` (built via `iconst_1` + repeated `iadd`) vs a literal `n=4`
  → clean fall-through. Correct.
- `if_icmpge 5>=5` at the equality boundary → clean branch-taken. Correct.

So both the strict-`<` gate `(1 − v_eq)` and the equality `v_eq` are clean at the boundary, even
between a computed and a literal value. The comparison machinery was never the problem.

## Actual root cause

Instrumenting the failing guard and dumping the **full vectors** (not the rounded real-axis
readout) showed the computed `i = 4` was `[4, 4, 4, …, 4]` — **4.0 in every component** — while a
proper `make_real(4)` is `[0, 0, 4, 0, …]` (the value on the real axis only). `eq_synthetic`
correctly returned "not equal" (truth `−1`): the two vectors differ on every non-real axis. The
rounded real-axis readout was `4` for both, so arithmetic and the final answer's magnitude looked
fine — the contamination is invisible to a real-axis-only readout and only surfaces in `==`.

The contamination entered through `iconst_N`. It pushed the **bare source literal** `N`:

```
int hi_ic1 = (((1 + is_iconst1) * (1)) + ((1 - is_iconst1) * (hi_ic0))) / 2;
```

A bare integer literal in Sutra lowers to a Python scalar (`ndim == 0`). When `is_iconst1` fires,
the second term `(1 − is_iconst1) * hi_ic0` becomes a **zeroed vector**, and `scalar 1 +
zero-vector` **broadcasts** the scalar across all axes → `[1, 1, 1, …]`. The factorial built `i`
by `iconst_1` then repeated `iadd`, so `[1,1,1] → [2,2,2] → [4,4,4]`. (A scalar lifts to
`make_real` only at the `ramWrite` I/O boundary or inside ops like `complex_mul` — but here the
broadcast happens *before* any such boundary.)

`bipush`/`iload` never hit this: their pushed value comes from `ramRead`, which returns a proper
real-axis `make_real` vector. `iconst` is the first op that materializes an opcode-embedded literal
as a value, so it's the first place a bare scalar enters a blend.

## Fix

Materialize the constant as a **real-axis vector**, not a scalar. A complex literal `1 + 0i` folds
to `make_complex(1.0, 0.0)` = a real-axis unit vector `one`; scaling it preserves the axis
structure (vector × scalar scales each component; it does not broadcast):

```
complex one = 1 + 0i;
int hi_ic1 = (((1 + is_iconst1) * (1 * one)) + ((1 - is_iconst1) * (hi_ic0))) / 2;
```

`N * one == make_real(N)` (verified componentwise), and `make_real(N) + zero-vector` stays
real-axis-only. With the fix `fact(0..5) = 1,1,2,6,24,120`.

## The general rule (for any future substrate op)

**A pushed/stored value must be a real-axis VECTOR, never a bare scalar literal.** Use `N * one`
(with `one = 1 + 0i`) or read it from RAM. A scalar that survives into a blend with a zeroed vector
term broadcasts across every axis; the magnitude reads correct on the real axis but the off-axis
contamination silently breaks every downstream `==` / `eq_synthetic`. This is the
signal-separation failure mode from CLAUDE.md in a new guise: the numbers look right, but they fail
to *distinguish* the values they must distinguish. Always measure the full vector, not the rounded
real axis, when an op reads "correct" but a comparison built on it misbehaves.
