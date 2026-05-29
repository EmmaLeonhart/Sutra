# Trainable MATRIX through the compiled Sutra substrate — first instance

**Date:** 2026-05-29
**Code:** `experiments/trainable_matrix_adjustment.py`,
`sdk/sutra-compiler/tests/test_trainable_matrix.py`
**Status:** shipped, measured, regression-guarded.

## What this is

The constrain-train inventory before today trained **scalars** through
the compiled tensor-op graph (equality-cosine `T`, defuzz `β`, select
temperature, rank-k gains). This is the first trainable **matrix** — the
next tier in Emma's arc ("equality cosine first → other low-hanging
scalars → harder matrix stuff → full weight→code decompilation").

A `matrix`-typed parameter flows through the compiled Sutra program

```sutra
function vector apply(matrix M, vector x) {
    return Tensor.MatrixMul(M, x);
}
```

`Tensor.MatrixMul` lowers to `_VSA.matmul == torch.matmul`, so the whole
forward runs on the substrate. `M` is a leaf tensor with `requires_grad`;
gradient descent updates it through the compiled matmul. This is the
natural downstream consumer of the 2026-05-28 matrix-literal work:
training produces a matrix, and the **bake-back** re-expresses the
trained matrix as a `matrix_literal(...)` `.su` source — a weight → code
round-trip.

## Task

Learn a target permutation of K=8 one-hot glyph states. `M` is
initialised at the frozen `font.su` cyclic-shift-by-1 permutation `P`
and trained toward a different target permutation — literally *shifting
the matrix around* under gradient descent. Two objectives, two
outcomes:

| loss | what it learns | Frobenius to canonical target |
|------|----------------|-------------------------------|
| **CE** (cross-entropy on the matmul output) | the permutation **function** — `argmax(M @ e_i) == perm(i)` | **rises** 4.00 → 8.61 |
| **MSE** (regress `M @ e_i` to the target one-hot) | the **exact canonical** permutation matrix | **collapses** 4.00 → 0.00 |

## Measured (3 seeds, K=8, 400 epochs, lr=0.05, RTX 4070 / cuda / fp32)

**CE — learn the function (`--target shift3 --loss ce`):**
- transform accuracy 0% → **100%**
- separation gap −1.000 → **+1.472** (`min_i (M@e_i)[perm(i)] −
  max_{j≠perm(i)} (M@e_i)[j]`; >0 ⇒ the substrate matmul cleanly
  separates every input)
- Frobenius to canonical target **4.00 → 8.61** (rises)
- first-step `‖dL/dM‖` = 2.436 (nonzero ⇒ backprop reaches the matrix
  through the substrate matmul)
- bake-back max|Δ| = **0.00** (bit-exact)

**MSE — shift the matrix to the target (`--target shift3 --loss mse`):**
- transform accuracy 0% → **100%**; separation gap −1.000 → **+1.000**
- Frobenius to canonical target **4.00 → 0.00** (collapses)
- bake-back max|Δ| = **3.2e-10**

**Arbitrary (non-shift) permutation (`--target random --loss mse`):**
- Frobenius 3.91 → **0.00**, accuracy 4% → **100%** across 3 seeds —
  it learns an arbitrary permutation, not just a shift.

## The finding worth not-misreading

Under **cross-entropy**, the matrix learns the permutation *function*
perfectly (100% accuracy, clean +1.47 separation) **while its Frobenius
distance to the canonical 0/1 permutation matrix grows**. CE only
constrains the argmax; the matrix entries grow large to sharpen the
softmax, so the learned matrix *implements* the permutation without
*being* the canonical permutation matrix. The naive success metric
"matrix converged to the target" is wrong for CE — the right metrics are
functional (transform accuracy + separation gap). **MSE** additionally
pins the canonical representation (Frobenius → 0), which is what you want
when the goal is to *shift a known matrix to a known target* rather than
*learn an unknown transform*. Pick the objective by which you mean.

## Integrity / substrate-honesty checklist

- **Substrate matmul:** asserted `_torch.matmul` appears in the emitted
  source; the op M flows through IS the substrate op, not a host shim.
- **Gradient locus:** `‖dL/dM‖ > 0` measured at the first step — the
  recurrence/parameter lives in the compiled graph, not in a host
  variable shuttled around it.
- **Dim audit (CLAUDE.md breach #1):** `apply.su` makes ZERO
  `basis_vector` calls — the LLM codebook is unused — so `runtime_dim`
  is pinned to the task size K, not the 768 default. No silent 96×
  over-dimensioning.
- **Signal-separation table (breach #3):** the `gap` column above is the
  measured `min(correct) − max(wrong)` per the rule; positive after
  training for both losses.
- **Equivalence guard:** vmap-batched `apply` == per-sample `apply`
  (max|Δ| = 0) before training begins.
- **Bake-back:** trained matrix → `matrix_literal(...)` `.su` →
  recompile → reproduces the param-M transform within 1e-4 (bit-exact
  for CE, 3e-10 for MSE).

## Related dark-code probes (discharges queue B.1)

Two loose exploratory scripts probed the *upstream* question — does a
learned role-matrix even exist on this embedding substrate? They are
documented here so they are no longer undocumented "dark code":

- **`planning/exploratory/object_matrix_probe.py`** — host-side numpy
  `lstsq` fit of a `d×d` matrix `M` with `M @ sentence_emb ≈ object_emb`
  over 30 SVO sentences, 5-fold CV, vs identity / mean-object / random
  baselines, plus SVD structure of the fitted `M`. (Matrix *fitting* is
  a legitimate compile-time role — numpy here is allowed; it is not a
  runtime op.) Its docstring records the result: **the identity baseline
  wins**, because the object word is lexically present in the sentence
  embedding, so a learned linear "object-of" operator buys little over
  reading the sentence embedding directly.
- **`planning/exploratory/subject_object_matrix_probe.py`** — the
  sharper follow-up: fit *separate* `M_subject` and `M_object` and test
  whether each recovers its role better than the wrong matrix does
  (cross-role degradation), i.e. whether nomic distinguishes subject
  from object linearly.

These are host **least-squares** probes of *whether* a role matrix
exists. Today's experiment is the complementary **substrate gradient-
descent** demonstration of *training* a matrix through the compiled
Sutra graph on a task with clean ground truth (permutations). The
least-squares probes motivate the eventual semantic target; the
permutation task proves the trainable-matrix mechanism end to end first.

## Next

- Semantic variant: train `M` (init identity) so
  `Tensor.MatrixMul(M, sentence_emb) ≈ object_emb` through the compiled
  graph — the substrate version of `object_matrix_probe.py`, with the
  host lstsq fit as the baseline. Needs live Ollama embeddings.
- Constrain `M` to the orthogonal/permutation manifold during CE
  training (so the function-learner also yields a canonical matrix).
- Wire a trainable binding matrix (semantic `bind` = learned matrix) —
  the long-standing learned-matrix-binding target, now mechanically
  unblocked by trainable matrices + matrix literals.
