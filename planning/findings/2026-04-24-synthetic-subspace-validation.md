# Synthetic-subspace 2D-Givens design: 5-experiment validation

**Date:** 2026-04-24.
**Script:** `experiments/synthetic_subspace_validation.py`.
**Design under test:**
`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
**Experiment design doc:**
`planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`.

## Summary

All five experiments from the 2026-04-21 design doc pass on a clean
reference implementation of 2D-Givens-per-slot rotation binding in a
synthetic subspace. The design is **empirically validated** —
ready to move from "pending experimental validation" to committed
spec for the rotation-binding direction.

The concrete results justify the three structural claims the spec
makes (zero cross-talk, truth-axis orthogonality, reversibility)
and quantify the practical capacity curve.

## Results

### Experiment 1 — slot cross-talk at N/2 capacity

100 trials per N, 16-value 2D codebook per slot. Query-against-
codebook is argmax-cosine on the 2D recovered vector.

| N   | k = N/2 | accuracy | trials | verdict |
|-----|---------|----------|--------|---------|
| 16  | 8       | 100.00%  | 800    | PASS    |
| 32  | 16      | 100.00%  | 1600   | PASS    |
| 64  | 32      | 100.00%  | 3200   | PASS    |
| 128 | 64      | 100.00%  | 6400   | PASS    |

Zero cross-talk at the theoretical capacity, across every N tested.
The 2D-per-slot allocation gives the full N/2 clean slots the design
claims.

### Experiment 2 — capacity curve (N=64, varying k)

N=64, 100 trials per k, 16-value codebook. When k ≤ 32 every slot
gets its own plane; when k > 32 slots share planes with distinct
angles (simulates a compiler that ran out of synthetic dims).

| k  | accuracy | regime           |
|----|----------|------------------|
| 8  | 100.00%  | disjoint planes  |
| 16 | 100.00%  | disjoint planes  |
| 24 | 100.00%  | disjoint planes  |
| 32 | 100.00%  | disjoint planes  |
| 40 | 65.05%   | planes SHARED    |
| 48 | 41.75%   | planes SHARED    |
| 56 | 25.96%   | planes SHARED    |
| 64 | 11.62%   | planes SHARED    |

Clean regime ends exactly at k = N/2 = 32. First k with accuracy
<90% is k=40 — so the practical answer is: **allocate up to N/2
slots for clean retrieval; past that, accuracy drops fast but
degrades gracefully rather than catastrophically.**

### Experiment 3 — truth-axis orthogonality under semantic ops

100 trials. Block-diagonal learned-matrix bind (random dense in
semantic block, identity in synthetic block) applied to random unit
vectors in the semantic subspace (zero-padded with the synthetic
block). Measure the truth-axis coordinate (synthetic[2]) after bind
and after bundling 5 such binds.

| measurement                    | value    |
|--------------------------------|----------|
| max leak on single bind        | 0.000e+00 |
| max leak on 5-term bundle      | 0.000e+00 |
| threshold                      | 1e-14    |

Zero leak exactly — the block-diagonal structure enforces zero
mixing between semantic content and the truth axis by construction.
No "this might work out" statistical argument needed; the subspace
separation is structural. **PASS.**

### Experiment 4 — reversibility round-trip

N=32, 8 slots, 100 sequential rotations chosen at random (with
replacement from the 8 slots), then inverses applied in reverse
order. Start from a random unit vector.

| measurement         | value     |
|---------------------|-----------|
| L2 roundtrip error  | 6.057e-16 |
| threshold           | 1e-10     |

Floating-point roundoff level. A 100-operation sequence of
rotations returns to its starting vector within one order of
magnitude of machine epsilon. **PASS.**

### Experiment 5 — fuzzy composition on truth axis

Product t-norm (`a AND b = a*b`), probabilistic sum (`a OR b =
a + b - a*b`), negation (`NOT a = -a`). 13 test cases plus a
semantic-contamination test that adds arbitrary noise to the
semantic block and verifies the truth-axis result is unchanged.

| measurement                    | value     |
|--------------------------------|-----------|
| max composition error          | 0.000e+00 |
| semantic contamination error   | 0.000e+00 |
| threshold                      | 1e-10     |

Fuzzy operations read-modify-write the truth axis scalar with no
coupling to anything else. Adding semantic-subspace noise does not
change the result. **PASS.**

## What this validates and what it leaves open

**Validated.** The three structural claims the design makes — zero
cross-talk at N/2, truth-axis orthogonality under semantic ops,
reversibility of rotation sequences — hold at the numerical level
that floating-point permits. Experiment 2 quantifies the capacity
curve past N/2: accuracy drops immediately but gracefully when
planes are forced to share.

**What this does not yet touch.**

1. The current `_VSA.bind(role, filler)` in `codegen.py` is still
   Haar-on-the-semantic-block, not 2D-Givens-per-slot. The
   validation is of the *design*; the runtime migration to
   expose 2D-Givens-per-slot as a separate primitive for
   positional / variable-slot binding is task 3 of the
   Anthropic-grant-app sprint.
2. The cleanup primitive (codebook snap / argmax-cosine) in this
   experiment runs against a 16-entry 2D codebook per slot. A
   realistic program has larger, less-regular codebooks; that
   regime is what the 2026-04-22 d=768 study and 2026-04-23 d=868
   hashmap study measured, and they both stop being clean around
   k ≈ 32 — which is consistent with this doc's k = N/2 bound if
   you treat the semantic-Haar block as `N ~ 64` effective
   capacity after argmax-cosine degradation. The two studies are
   compatible.
3. Experiment 2's SHARED-plane curve uses 1 distinct angle per
   (plane, wrap_index) pair. A more adversarial allocator could
   assign adjacent angles on purpose, which would degrade faster.
   The 65% / 42% / 26% / 12% numbers at k=40/48/56/64 are for the
   "reasonable" allocator — the upper-bound curve, not the
   worst-case curve.

## Verdict for the spec

The rotation-binding-in-synthetic-subspace direction is **clear to
commit.** The spec text in
`planning/sutra-spec/binding.md` and the design note
`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`
can drop their "pending experimental validation" language.

Remaining follow-on items (runtime implementation of 2D-Givens-
per-slot as a first-class primitive, demos that exercise it,
spec-text cleanup) go back into queue.md / `todo.md`.
