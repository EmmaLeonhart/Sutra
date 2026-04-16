# 2026-04-15: Nomic has no learnable "object-of" matrix; identity wins

## What was measured

On 30 simple SVO sentences, a linear map `M` fit by least-squares to
map `sentence_emb → object_emb` in nomic-embed-text achieves **0%
top-1 retrieval** under 5-fold CV — strictly worse than the identity
baseline (100% top-1) and comparable to the constant-mean-object
baseline (0% top-1, mean cosine 0.67).

## Setup

- Script: `planning/exploratory/object_matrix_probe.py`
- Model: `nomic-embed-text` via Ollama, 768-dim
- Embedding transform: scalar mean-center then L2-normalize, matching
  `sdk/sutra-compiler/sutra_compiler/codegen_numpy.py` `embed()`
- 30 (sentence, object) pairs, manually curated SVO sentences
  ("The cat chased the mouse." → "mouse", etc.)
- 5-fold CV: 24 train / 6 test per fold; `M = lstsq(S_train, O_train)`
- Evaluation: mean cosine `(M @ s_test, o_test)`; top-1 retrieval
  against the full 30-object codebook; mean rank
- Baselines: identity (`M = I`); constant mean-object prediction;
  random Gaussian `M` with `std = 1/√d`

## Raw numbers

```
Baseline 0 — raw cosine(sentence, its own object), no fit:
  mean=+0.733  min=+0.618  max=+0.808

Learned M (5-fold CV, aggregated):
  mean cos(M@s, o_true) = +0.678
  top-1 accuracy        = 0.0%   (chance = 3.3%)
  mean rank             = 12.10  (chance = 15.5)

Comparison baselines (averaged across folds):
  identity I             mean_cos=+0.733   top1=100.0%
  mean-object const      mean_cos=+0.669   top1=  0.0%
  random Gaussian        mean_cos=+0.000   top1=  0.0%

Structure of M fit on all 30 pairs:
  Frobenius norm = 5.923
  singular values top-5: [1.55, 1.50, 1.46, 1.41, 1.33]
  condition number = 1.6e12  (effectively singular)
  distance to nearest orthogonal = 27.2
```

## Interpretation

The headline — "learned M beats chance" — is technically true (top-1
0% vs 3.3% chance is because of small-sample variance; mean rank
12.1 vs chance 15.5 is a weak-but-positive signal) but the
**identity baseline crushes it at 100% top-1**. This means in
nomic's space, the sentence embedding is already nearest to its own
object embedding by cosine. The object word appears literally in the
sentence ("The cat chased the mouse." contains "mouse"), and nomic's
semantic compression puts them close in embedding space — so "which
object is this sentence about" is solved by bag-of-words nearest-
neighbor, not by any learned linear role.

This is a **confound in the experiment**, not a success of the
matrix. When the object word is literally in the sentence, there's
no work for a role-extractor to do. A real "object of" matrix test
would need sentences whose object is **not** lexically present:
"The cat chased something small and furry" → "mouse", where the
sentence embedding alone cannot pick "mouse" out.

The learned M's structure reinforces this. Condition number 1.6e12
means the system is severely underdetermined (24 samples for a
768×768 matrix = 589,824 parameters). The singular value spectrum
is flat-ish but the matrix is effectively singular, so the fit is
mostly noise aligned along the mean-object direction — which is why
the learned-M cosine (0.68) is indistinguishable from the constant-
mean-object baseline cosine (0.67). The matrix isn't learning
"object of sentence"; it's learning "the average object embedding"
with some noise riding on top.

## Implications

**For Sutra's "roles are learned matrices" position:** this run does
not falsify the position, but it does not support it either. It
demonstrates two things:

1. **A naive probe is inadequate.** Fitting a full d×d matrix with
   30 samples for a role like "object of sentence" in nomic fails
   for the boring reason that you can't fit 590k parameters from 24
   examples — plus, on this curated dataset the identity is already
   optimal because the object word is lexically present. Any real
   evaluation needs (a) more data, (b) sentences whose object is
   lexically absent, and (c) rank-constrained fitting.

2. **Not every role admits a clean matrix in every substrate.**
   Even with better data, "object of sentence" might genuinely not
   be a linear operation in nomic — it might be non-linear, or it
   might be partially non-compositional (attention-head style
   dynamics that the sentence embedding has already integrated
   away). The spec should not assume all learned role matrices will
   turn out clean.

**What this changes in the spec:** `planning/sutra-spec/operations.md`
should flag that the "roles are learned matrices" framing is a
design hypothesis with strong conceptual support (unifies with
`is_cat`, defuzz matrix, cartography displacements) but the naive
empirical probe on this substrate gave a null result. The honest
position is: matrix roles are the design target; implementations
that turn out to require more data, more structure, or non-linear
roles for some cases are expected, not failures.

**Follow-up experiments worth running:**

- Larger corpus (1000+ SVO pairs from a parsed corpus) with
  lexically-absent objects
- Low-rank regression (fit M as `U @ V.T` with rank 10-50) to handle
  the data/parameter ratio
- Orthogonal Procrustes (restrict M to rotations) and see if the
  rotation story from the spec holds
- Test the rank-0 special case (displacement vector) the cartography
  paper validated — does `sentence_emb + d ≈ object_emb` for a
  learned `d`? If that works and the full matrix doesn't, we learn
  that nomic's role structure is affine-only, not fully linear.
- Repeat on other substrates (mxbai is known-broken; maybe a larger
  embedding like `text-embedding-3-large` behaves differently)

**What this does not mean:** this result does **not** rescue sign-flip
binding. Sign-flip is still rejected (the user's 2026-04-15 position
is independent of this experiment). If the "learned matrix" framing
turns out to need more care than naively-fit lstsq, the replacement
for sign-flip is still a structured linear operation — just one that
respects the substrate's data/dimension ratio.
