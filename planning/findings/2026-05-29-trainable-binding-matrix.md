# Trainable binding matrices — semantic vs non-semantic bind, measured

**Date:** 2026-05-29
**Code:** `experiments/trainable_binding_matrix.py`
**Status:** shipped, measured. Greenlit by Emma 2026-05-29 (`AskUserQuestion`).
**Builds on:** `2026-05-29-trainable-matrix-through-substrate.md` (the
trainable-matrix mechanism).

## What this tests

Emma's learned-matrix-binding vision: a **semantic** bind is a *learned*
matrix; a **non-semantic** bind is an arbitrary/random matrix; and
"objects track which learned matrices bound their fields." This makes the
per-field binding matrices trainable parameters and trains them through
the same compiled substrate path as the other matrix experiments
(`apply(matrix M, vector x){ Tensor.MatrixMul(M, x); }`,
`MatrixMul == torch.matmul`).

A VSA role-filler record: K fields, each a bind matrix `B_i` + unbind
matrix `U_i`. Store K fillers in one bundle and recover each:

```
S       = (1/sqrt(K)) * sum_i  B_i @ f_i     # bind + bundle, substrate
f_hat_j = U_j @ S                            # unbind, substrate
score   = cos(f_hat_j, f_j)                  # monitoring only
```

- **Non-semantic baseline:** `B_i` random orthogonal (Haar), `U_i = B_i^T`
  — the standard VSA rotation binding.
- **Semantic / learned:** `B_i, U_i` trained (init at the baseline) to
  maximise recovery of a KNOWN, FIXED filler set.

`d=64` (dim audit: zero `basis_vector`, codebook unused, so `runtime_dim`
is the small task size). Substrate matmul asserted `== torch.matmul`.

## Measured

**Known (trained) filler set — recovery cos:**

| K | random-orth (non-semantic) | learned (semantic) | Δ |
|---|---|---|---|
| 2 | +0.785 | **+1.000** | +0.215 |
| 4 | +0.542 | **+1.000** | +0.458 |
| 8 | +0.385 | **+1.000** | +0.615 |
| 16 | +0.246 | **+1.000** | +0.754 |
| 32 | +0.181 | **+1.000** | +0.819 |

**New random fillers (generalisation) — recovery cos:**

| K | random-orth | learned |
|---|---|---|
| 2 | +0.713 | +0.708 |
| 4 | +0.409 | **+0.242** |
| 8 | +0.332 | **+0.141** |
| 16 | +0.195 | +0.099 |
| 32 | +0.158 | +0.132 |

## What it actually means (the honest mechanics)

The learned matrices recover the **known** fillers *perfectly* (cos=1.0)
at every K, while non-semantic random-orthogonal binding degrades with K
(the standard capacity curve). But two diagnostics keep this honest:

1. **It is the UNBIND side that learns, not the bind side.** At the
   orthogonal init the first-step gradient to the bind matrices is
   `‖dL/dB‖ ≈ 6e-8` (near-stationary), while `‖dL/dU‖ ≈ 0.22` (healthy).
   The bind matrices barely move (Frobenius 8.0→8.5); the unbind matrices
   carry the optimisation. Because the filler set is FIXED, the bundle
   `S` is a single fixed vector per configuration, so each `U_j` only has
   to map that one vector to `f_j` — easily driven to cos=1. "Perfect
   known recovery" is **unbind memorisation of fixed content**, verified
   to be real optimisation (loss 0.458 → 2e-4 by epoch 50, no parameter
   blow-up), not a numerical artifact.

2. **It does not generalise.** On NEW random fillers the learned matrices
   are *no better than* — and at mid-K *worse than* — random-orthogonal
   binding (e.g. K=8: 0.332 → 0.141). It learned the specific content,
   not a generally-better binding operator. This matches VSA theory:
   perfect zero-crosstalk recovery for K>1 full-rank matrices is
   impossible (`U_j B_j = I` ⇒ `U_j = B_j^{-1}` ⇒ `U_j B_i = B_j^{-1}B_i
   ≠ 0`), so for arbitrary content random-orthogonal binding is already
   near-optimal and cannot be beaten.

## The conclusion — a crisp statement of Emma's distinction

This is exactly the **semantic vs non-semantic bind** distinction, now
measured:

- **Non-semantic bind** = random orthogonal: content-agnostic,
  generalises to any filler, capacity-limited (cos falls with K).
- **Semantic bind** = a matrix specialised to KNOWN content: recovers its
  known fields perfectly regardless of K, does NOT generalise to
  arbitrary content. This *is* "objects track which learned matrices
  bound their fields" — the learned matrix encodes knowledge of the
  specific content it binds.

The trainable-matrix mechanism is the same one proven on permutations and
the category operator; here it draws the line between the two kinds of
binding rather than beating a baseline. A negative-shaped result on
generalisation, a positive one on known-content recovery, and an exact
fit to the spec's framing.

## Next

- Tie `U_i = B_i^T` during training (enforce the inverse relationship) so
  the BIND matrices must do the work — a harder, more "honest binding"
  formulation that can't lean on unbind memorisation.
- Train one shared binding scheme over a *distribution* of fillers
  (resample each step) to see whether anything beats random-orthogonal in
  the generalising regime (theory says no; worth confirming on the
  substrate).
