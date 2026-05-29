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

## Semantic role matrix at real scale — substrate reproduction of the probe

`experiments/trainable_role_matrix.py` runs the trainable-matrix
mechanism on the dark-code probe's actual task: train `M` (d×d, init
identity) so `Tensor.MatrixMul(M, sentence_emb) ≈ object_emb` over the
30 SVO pairs, by gradient descent **through the compiled substrate
matmul**, with the host `torch.linalg.lstsq` fit and the identity matrix
as baselines (5-fold CV, real d=768 nomic embeddings, cuda/fp32).

**Mechanism (asserted, true regardless of task learnability):**
- the matmul the program runs IS `torch.matmul` (substrate);
- first-step `‖dL/dM‖` = 0.27 > 0 — backprop reaches the d×d matrix
  through the compiled matmul at full scale;
- GD drives train `cos(M@s, o)` **0.733 → 0.994** — the substrate
  trainer fits the training pairs.

**Held-out (reported, the probe's open question):**

| | held-out cos | held-out top-1 (chance 3%) |
|---|---|---|
| identity `M = I` | **+0.733** | **100%** |
| host lstsq fit | +0.674 | 0% |
| GD-trained (substrate) | +0.668 | 0% |

This **reproduces the probe's "identity wins" conclusion through the
substrate path.** A learned linear role matrix — whether fit by host
closed-form least-squares or by gradient descent through the compiled
graph — *overfits* (train 0.99, held-out 0.67) and is beaten outright by
the identity matrix, which retrieves the held-out object every time
because the object word is lexically present in the sentence embedding
(so `cos(I@s, o) = cos(s, o)` already points at it). A negative result,
and the expected one: this embedding substrate does not support a
generalising linear "object-of" operator on this task. The value here is
that the **trainable-matrix mechanism is now validated at real d=768
scale on real embeddings**, not just toy permutations, and it lands on
the same answer the host probe did.

## Next

- Constrain `M` to the orthogonal/permutation manifold during CE
  training (so the function-learner also yields a canonical matrix).
- A task where a generalising linear operator plausibly *does* exist
  (analogy/displacement: capital-of, plural-of) to see GD-through-the-
  substrate beat identity on held-out — the role-matrix probe's task is
  degenerate (object word lexically present).
- Wire a trainable binding matrix (semantic `bind` = learned matrix) —
  the long-standing learned-matrix-binding target, now mechanically
  unblocked by trainable matrices + matrix literals. (Kept deferred as a
  headline per Emma; the mechanism is ready when she wants it.)
