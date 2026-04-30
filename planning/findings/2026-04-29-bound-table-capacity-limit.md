# Bound-table-via-binding for transcendentals: 2-scalar capacity limit

**Date:** 2026-04-29
**Author:** Claude (Sonnet) under Emma's direction
**Experiment:** `experiments/bound_table_transcendentals.py`
**Context:** Implementing exp/ln/sin/cos in Sutra per the design in
`chats/implementing-transcendental-functions.md` (2026-04-29).

## What was tested

The user-described architecture: a "lookup table" implemented as a
single bundled vector in synthetic space, where each table entry
`f(x_i)` is bound at a unique angle `θ_i` via rotation. Lookup at
arbitrary `x` rotates the bundle back by `R(θ(x))^T` and reads the
result at synthetic[0].

The mathematical form:
```
T = sum_i  R(θ_i) @ make_real(f(x_i))
  = ( sum_i f(x_i) cos θ_i,  sum_i f(x_i) sin θ_i )

lookup(x) = (R(θ(x))^T @ T)[0]
         = sum_i f(x_i) cos(θ(x) - θ_i)
```

Tested with `cos`, `exp`, `ln` over various domains and table sizes
(N = 64, 256, 1024, 4096). Also swept the angular range of the
bindings (full circle, half, quarter, eighth, π/16) to test the
hypothesis that wrap-around crosstalk past 90° was the source of
errors.

## Results

| Function | Domain | N | Arc | Rel error |
|---|---|---|---|---|
| cos | [-π, π] | 1024 | 2π | **4.6e-16** (FP roundoff — exact) |
| exp | [-2, 2] | 64 | 2π | 87% |
| exp | [-2, 2] | 1024 | 2π | 85% |
| exp | [-2, 2] | 4096 | 2π | 85% |
| exp | [-2, 2] | 1024 | π | 68% |
| exp | [-2, 2] | 1024 | π/2 | 56% |
| exp | [-2, 2] | 1024 | π/4 | 52% |
| exp | [-2, 2] | 1024 | π/16 | 51% |
| ln | [0.1, 10] | 1024 | 2π | 117% |

## What's actually happening

**Two distinct issues, both fundamental to this architecture:**

### Issue 1: 2-scalar capacity

The bundle `T` is a single 2D vector — two scalars. By pigeonhole, N
samples cannot be losslessly compressed into 2 scalars. The lookup
recovers exactly *the first DFT coefficient* of f's periodic extension
— specifically, the projection of f onto `cos(θ)` and `sin(θ)`.

For `cos(x)` the first DFT coefficient *is* cos(x), so the lookup is
exact (it's tautological — `R(θ)^T @ R(θ) = I`).

For `exp(x)` the first DFT coefficient is whatever periodic component
of exp aligns with the fundamental frequency, which is a small
fraction of the function. Result: ~85% relative error, not improvable
with more samples.

### Issue 2: full-circle wrap-around (Gibbs)

Even if the bundle had higher capacity (more axes), the Fourier-style
basis assumes the function is periodic over `[0, 2π)`. Periodically
extending `exp` from `[-2, 2]` creates a discontinuity at the boundary
(jump from e²≈7.4 to e⁻²≈0.14). Fourier reconstruction can't
represent that jump cleanly — Gibbs phenomenon.

Restricting the binding angles to a sub-arc (so the basis cos doesn't
wrap into negative regions) reduces but doesn't eliminate this. With
a sub-arc the basis is even MORE redundant (cos(δ) ≈ 1 for all sample
pairs, so every sample contributes positively to every readout).
Result: with tiny arcs the recall converges to roughly the *average*
of f over the domain — constant regardless of x.

## What this rules out

- ❌ "Bind N samples, bundle into a 2D vector, look up by inverse rotation."
  Won't give accurate non-periodic function values. Doesn't matter what
  arc you choose.
- ❌ "Adjacent samples interpolate naturally because of crosstalk."
  Crosstalk *is* present, but it's not localized — far samples
  contribute too, and for non-periodic functions they don't cancel.

## What still works

- ✅ `cos(θ)` and `sin(θ)` via the **eigenrotation primitive**
  directly: `R(θ)` applied to (1, 0) yields `(cos θ, sin θ)` as the
  first/second elements. No "table" needed at all — cos and sin are
  literally the matrix entries of R(θ). This was actually the user's
  understanding ("they're eigenrotations") — the bound-table framing
  in this experiment was a misreading.
- ✅ `imaginaryExp(θ) = (cos θ, sin θ)` follows directly from the same
  rotation primitive.

## What still needs an approach

- `realExp(x) = e^x` for real x — non-periodic function on a bounded
  domain. Cannot be done via the binding architecture as described.
- `realLog(x) = ln(x)` for real x>0 — same.

## Plausible alternatives (not validated, not implemented)

1. **High-dim bundle.** Instead of binding into a single 2D plane,
   bind into a 2K-dim subspace with K orthogonal Givens rotations.
   Each pair stores one Fourier coefficient. With K large enough you
   can represent K-term truncated Fourier series of f. Still has
   Gibbs at the periodic boundary unless f is mirror-extendable
   (which exp is not).

2. **Polynomial expansion (Taylor / Chebyshev).** Truncated polynomial
   evaluated at runtime as `c_0 + c_1·x + c_2·x² + ...`. Pure tensor
   ops (multiply, add). Coefficients precomputed at compile time.
   For exp on [-2, 2] with degree 20: ~1e-13 precision. **Not a
   "lookup table" or "binding" pattern, but it is substrate-native.**

3. **Iterated narrow-range exp.** `exp(x) = exp(x/k)^k`. For small
   x/k the bound-table or Taylor works on a small range, then raise
   to the k-th power via repeated multiplication. Not constant-time,
   contradicts the design goal.

## Decision (2026-04-29)

Ship the parts that work as described:
- `cos`, `sin`, `imaginaryExp` via the eigenrotation primitive
  (`R(θ)` applied to the unit vector).

For `realExp`, `realLog`, ship a polynomial-expansion implementation
as the pragmatic substrate-native alternative. The bound-table
architecture for these specific functions is a known-limitation
finding; if a future session finds a high-dim-bundle version that
pencils out, that's an upgrade path.

## What to read if revisiting

- `chats/implementing-transcendental-functions.md` — original chat
  where the architecture was sketched.
- This file — what was tested, what didn't work, why.
- `experiments/bound_table_transcendentals.py` — reproducer.
- `feedback_no_libm_shortcuts_in_math_intrinsics.md` (in memory) —
  the prior session's failure mode that produced the original
  pushback. **Note**: that memory's specific recipe ("decompose to
  lookup-table + eigenrotation + matrix multiplication composition")
  works for cos/sin but not for non-periodic functions like exp/ln —
  the lookup-table portion of that recipe doesn't deliver for those.
