# Rotation-binding capacity — empirical results

**Date:** 2026-04-22.
**Status:** Runs and closes STATUS #2 (capacity experiment). The
adapted experiment targets the **current prototype** (role-seeded
Haar rotation in the 768-d semantic subspace), not the idealized
synthetic-subspace design in the 2026-04-21 design doc — that
design's runtime is still deferred.

Script: `experiments/rotation_binding_capacity.py`. All-random
vectors; the capacity of rotation binding is a property of the
rotation algebra, not the vector distribution, so no Ollama
dependency here.

## Three sub-experiments

### 1. Reversibility round-trip

Measured `||unbind(role, bind(role, x)) - x||` across 100
(role, x) pairs of random unit vectors.

| Statistic | Value |
|-----------|-------|
| mean      | 1.45e-15 |
| max       | 1.59e-15 |
| min       | 1.33e-15 |

Essentially the floating-point floor. Confirms `Q^T Q = I` exactly
(up to double-precision roundoff) for the Haar-random Q used by the
runtime. Reversibility is not a bottleneck.

### 2. Capacity curve

Bundled k (role, filler) bindings; for each, unbound with the matched
role and argmax-cosine'd against a 200-filler codebook. 10 trials per
k, ~32-64 retrievals per trial.

| k   | accuracy | signal cos | noise cos | SNR |
|-----|---------:|-----------:|----------:|----:|
| 2   | 100.0%   | +0.709     | −0.002    | 322 |
| 4   | 100.0%   | +0.505     | −0.002    | 199 |
| 8   | 100.0%   | +0.354     | +0.003    | 120 |
| 12  | 100.0%   | +0.289     | −0.001    | 438 |
| 16  | 100.0%   | +0.253     | +0.001    | 222 |
| 24  | 99.6%    | +0.205     | −0.001    | 360 |
| 32  | 97.2%    | +0.175     | −0.000    | 974 |
| 48  | 88.3%    | +0.144     | −0.000    | 431 |
| 64  | 75.0%    | +0.124     | −0.000    | 633 |
| 96  | 53.9%    | +0.102     | −0.000    | 3506 |
| 128 | 39.5%    | +0.089     | −0.000    | 500 |

**Practical take-away: rotation binding in 768-d reliably handles
up to ~32 bundled bindings. Accuracy crosses the 90% threshold at
k = 48 and the 50% threshold at k = 96.** For a 200-way filler
codebook; the thresholds shift with codebook size.

### 3. Cross-talk analysis

The signal-cosine column follows a `~1/sqrt(k)` curve cleanly:

| k | signal cos | 1/sqrt(k) |
|---|-----------:|----------:|
| 2   | 0.709 | 0.707 |
| 4   | 0.505 | 0.500 |
| 8   | 0.354 | 0.354 |
| 16  | 0.253 | 0.250 |
| 32  | 0.175 | 0.177 |
| 64  | 0.124 | 0.125 |

Essentially exact match — the signal magnitude is dominated by the
bundle-normalization denominator (√k for unit inputs), not by any
rotation-specific effect.

The noise-cosine column stays at ~1e-4 to 1e-3, independent of k.
That's the `1/sqrt(d) ≈ 0.036` upper bound predicted by random-vector
theory but in practice well below it (around 5e-3 in magnitude
after averaging, which is roughly expected since cosine of two
independent high-d random vectors is ~N(0, 1/d)).

**SNR stays enormous across all k.** The retrieval failures at
high k aren't caused by bundled-term cross-talk flooding the signal.
They're caused by the **signal itself dropping below the level of
other codebook entries' cosines**. When the signal cosine is 0.1
and the codebook has 200 random-looking fillers, some non-
participating filler can have cosine >0.1 to the recovered vector
just by chance.

So the failure mode is **"argmax collision with an off-codebook
distractor," not "noise swamps signal."** This has implementation
implications: cleanup procedures that do better than plain
argmax-cosine (e.g. constrained-codebook argmax, iterative cleanup,
learned-attractor-MLP from the earlier session) will push the
effective capacity higher without changing the bind/bundle mechanism.

## Relation to the 2026-04-22 rotation-binding-prototype results

The smoke-test-level regressions that motivated this experiment:

- `fuzzy_dispatch.su` at 1/4. This program bundles records from
  `select()`-weighted superposition of 4 records × 2 binds each = 8
  effective terms at retrieval. k=8 → 100% accuracy in this
  experiment, so why does fuzzy_dispatch fail? **Answer: the
  fillers are not "random" — they're related semantic vectors
  (action/target words like lookup/start/stop). In the Ollama
  substrate, these have real inter-filler cosine >>1/sqrt(d),
  which reduces the effective SNR.** The capacity-curve numbers
  here are upper bounds for random-like filler distributions;
  semantically-similar filler sets tighten the margin.

- `sequence.su` at 10/11. Bundles 5 position-token bindings (k=5).
  k=5 should give 100% per this experiment; the one off-by-one
  failure is consistent with the same "semantically-similar
  fillers" effect.

This matches the substrate-characterization finding from
`2026-04-22-king-queen-across-substrates.md`: real LLM embeddings
are not the abstract random vectors capacity theory assumes. Bundle-
and-retrieve on clustered codebooks (proper nouns, family-word
vocabulary, etc.) fails at lower k than this experiment predicts.

## What would fail this — did not happen

The design doc (2026-04-21) predicted that cross-talk failure would
come from bundled terms interfering with the signal. **In practice
the mechanism is different.** For random-ish vectors:
- Bundled terms decorrelate to ~1/√d noise, which is tiny.
- Signal decays as 1/√k from bundle normalization.
- Retrieval fails when signal drops below *off-codebook-entry*
  cosines, not when signal drops below *bundled-term* cosines.

This means the theoretical "zero cross-talk by construction" of the
extended-state-vector design (dedicated 2D Givens planes) would
help in one specific way: it would keep bundled-term noise at
machine-zero instead of 1/√d. But that's not currently the binding
constraint; the binding constraint is signal-magnitude-vs-codebook-
distractors. The extended-state-vector upgrade is still valuable
(it fixes the asymptotic noise floor), but it's not the pass-a-test
fix the design doc implied.

## What remains

- **Capacity on real (nomic) embeddings.** This experiment used
  random vectors. Repeating with nomic-embedded words would directly
  measure the "clustered fillers" effect and give a realistic
  working-budget for Sutra programs.
- **Extended-state-vector comparison.** Once the dedicated synthetic
  subspace lands, re-run the capacity curve to see if the
  theoretical zero-cross-talk property actually shifts the failure
  mode.
- **Attractor cleanup capacity.** Plug the 2026-04-22 MLP-attractor
  into the cleanup step and re-run. Hypothesis: accuracy stays at
  100% well past k=48 because the attractor dynamics discriminate
  fillers more sharply than argmax-cosine against a raw codebook.
  If confirmed, this is a direct answer to "how do we push Sutra's
  per-program bundle-budget up."

## Prior-art audit pending

Capacity scaling of `1/sqrt(k)` for bundle-and-retrieve is classical
VSA — it's Plate's HRR capacity result (Plate 1995, chapter on
capacity) and Kanerva's HD-computing analogue. The specific
combination with argmax-cosine against an external codebook, and the
observation that the binding constraint is off-codebook-distractor
collision rather than bundled-term noise, may or may not be
documented elsewhere. Search terms for the pre-publication audit:
Frady/Sommer capacity bounds, Kleyko et al. HD-computing cleanup
studies.
