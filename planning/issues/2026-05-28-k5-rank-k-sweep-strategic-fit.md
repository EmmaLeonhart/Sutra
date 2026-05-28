# 2026-05-28 — K=5 rank-k is_X sweep: what it actually does + strategic-fit assessment

Emma 2026-05-28 surfaced a concern that the K=5 rank-k experiment may not align with strategic goals. This file lays out what the experiment is doing, plainly, and provides the materials needed to decide whether to continue, scope it down, or stop.

## What the experiment actually does

**Setup.** A K-class classification task on synthetic data:
- K = 5 classes; per_class = 5 examples per class; so N = 25 total samples
- Each example x is a 768-d frozen-LLM embedding (nomic-embed-text)
- Class labels are 0..K-1; the goal is to assign x to the right class

**The Sutra rule under training.** For each class i, the rule is:
```
is_class_i(x) = T_i_0 * sim(x, v_i_0) ⊕ T_i_1 * sim(x, v_i_1) ⊕ ... ⊕ T_i_(k-1) * sim(x, v_i_(k-1))
rule_i(x) = is_class_i(x) AND NOT(is_class_j(x))  for all j ≠ i
```

Where:
- ⊕ is the fuzzy OR (Kleene-Lagrange polynomial connective)
- AND, NOT are also Kleene connectives
- T_i_r is a scalar "temperature" for the r-th prototype of class i
- v_i_r is a 768-d "prototype vector" for the r-th prototype of class i

So the trainable parameter set is:
- K × k vectors (each 768-d) — the prototypes
- K × k scalars — the temperatures

For K=5 and k ∈ {1, 2, 4}, that's:
- k=1: 5 vectors + 5 scalars = 5·768 + 5 = 3845 trainable scalars
- k=2: 10 vectors + 10 scalars = 7690
- k=4: 20 vectors + 20 scalars = 15380

**Training.** Adam optimizer, learning rate 0.05, 20 epochs, 3 seeds per k-value. Loss is cross-entropy of the rule logits against the class labels.

**The headline measurement.** *Not* classification accuracy — at K=5 with synthetic data, accuracy saturates at 100% even at k=1. The metric of interest is the **rank-k margin**: does k=2 or k=4 widen the decision boundary compared to k=1? Bigger margin would suggest that having multiple prototypes per class lets the rule capture intra-class variation that a single prototype can't.

**Bake-back round-trip.** After training, the script writes the trained values back into a fresh .su as `vector_literal(...)` calls and numeric literals (no params, no Adam, no PyTorch graph), recompiles, and asserts that for every sample x the baked rule produces the same output as the trained-with-params rule to within 1e-4. This is the "weights compile to readable Sutra source" claim made concrete.

**Wall cost.** ~3-9h on the local machine. K=1 alone took ~4h in the prior failed run before crashing (which turned out to be a Python caller bug — `logits_per_sample_factory` was passing args in all-vectors-then-all-scalars order while the .su signature expected per-class interleaved).

## What strategic goal this is supposed to advance

The "constrain-train" thesis (per `feedback-constrain-train-vision-is-every-op.md`):

> Every operation in Sutra should be trainable. Parameters in Sutra programs can be trained via standard ML loops. The trained values then get baked back into .su source code as literals. This is the "every weight is decompilable to readable code" vision.

Shipped constrain-train instances as of 2026-05-28:
1. **Equality-cosine T** (`equality_cosine_adjustment.py`, 2026-05-26 commit `21778648`) — first SHIPPED, scalar parameter (T inside softmax)
2. **Defuzz β** (`defuzz_gain_adjustment.py`, 2026-05-28 commit `5ca1b043`) — second SHIPPED, scalar parameter inside `defuzzify_trit`
3. **Rank-k is_X** (`rank_k_is_x.py`) — mechanism exists; the K=5 sweep would be the headline "matrix-valued" demonstration but has NOT shipped a clean result yet (K=2 k=2 ran end-to-end but the K=5 sweep is the publishable finding)

If the K=5 sweep ships:
- It would be the FIRST matrix-valued constrain-train instance (prototypes are 768-d vectors; the training fits K×k matrices of weights)
- It demonstrates that the bake-back round-trip works for `vector_literal(...)`, not just numeric literals
- It demonstrates rank-k as a useful concept — does k>1 actually help?

If the K=5 sweep does NOT ship:
- The matrix-valued case stays at "mechanism only" — the scalar case (T, β) shipped, but no end-to-end matrix-valued demo
- The "every weight is decompilable" claim stays narrower (works for scalars; matrix demonstration pending)
- Rank-k as a concept stays unmeasured against rank-1 — we don't know if rank-k margin is wider, or if k=1 is already sufficient for this task

## Strategic alignment — Emma's concern

The vision is **breadth across operators**, not depth on one operator. The K=5 sweep is a specific *demonstration* of an already-shipped mechanism (the matrix-valued path), not a new trainable surface. Spending 5-9h to ship K=5 specifically (vs. say K=3, which is just as much "matrix-valued") may be polishing one demo at the cost of breadth.

Operators that are NOT YET trainable and would each ADD a new surface:
- `select` softmax temperature (currently a Sutra-internal constant)
- `bundle` weights (currently uniform; could be per-filler)
- Kleene connective coefficients per call site (the Lagrange polynomials are spec-fixed; could be per-program-trained)
- `defuzzify_trit` β SHIPPED already, but iters is structurally fixed (could become trainable)
- Bind rotation angle (currently random Haar; could be per-role-trained)

Each of those would be a NEW shipped surface that demonstrates the vision. K=5 specifically demonstrates an EXISTING surface scaling to more classes.

## Reasonable closures

The decision matrix:

1. **Let the in-flight sweep finish.** ~5–9h wall, no further attention needed; if it ships clean results, the matrix-valued case is closed and we move on to breadth. Cost: GPU time + waiting.

2. **Stop the in-flight sweep; run K=3 instead.** K=3 is the smallest K that exercises the per-class-interleaved arg layout (the bug that the 68b7ade1 fix targeted). Same matrix-valued demonstration, ~2x faster wall. Same strategic value.

3. **Stop the in-flight sweep; pivot to a new operator's first trainable instance.** Pick one of the not-yet-trainable operators above (e.g. `select` temperature) and ship the THIRD scalar-trainable instance, then return to matrix-valued later. Cost: defer the matrix-valued demo by a few sessions.

4. **Stop the in-flight sweep; run a minimal K=2 k=2 bake-back proof and move on.** A K=2 k=2 sweep already worked. If the goal is "matrix-valued bake-back is real," K=2 k=2 demonstrates it. K=5 is just bigger numbers; not qualitatively different. Cost: weaker headline (K=2 isn't as visually impressive as K=5).

## What's currently in flight (2026-05-28 ~14:30 UTC)

- Smoke test (`bhubs0ke7`): K=5 k=1, 1 seed, 1 epoch, per_class=2 — running, verifies the new `logits_per_sample_factory` fix.
- Full sweep (PID 16164): `run_rank_k_K5_sweep.py` — runs K=5 at k ∈ {1, 2, 4}, 3 seeds × 20 epochs each, sequentially. Started ~14:00 UTC; expected to finish ~17:00–23:00 UTC. Was launched by the parallel session using my new wrapper script.

The fix to `logits_per_sample_factory` (the Python caller misalignment) is live in the in-flight sweep, so if the fix is correct the sweep will produce real numbers when it finishes. If the fix is wrong, the sweep will crash at the same spot — visible in the runlogs `experiments/runlogs/2026-05-28-rank-k-K5-k{1,2,4}-n3.txt`.

## What this issue file is asking for

A decision on the four closures above. The strategic-fit concern is real: K=5 specifically may not be the right next move. The mechanism is shipped, the matrix-valued path works (K=2 k=2 demonstrated it), and the breadth-across-operators direction is the explicit vision. Tagged to the queue tail per Emma's request so it doesn't get lost.

## Cross-refs

- `feedback-constrain-train-vision-is-every-op.md` (memory) — the breadth-vs-depth principle
- `feedback-be-less-procedural-more-creative.md` (memory) — "nothing actionable" usually means "nothing in queue is the right thing"
- `experiments/rank_k_is_x.py` — the script
- `experiments/equality_cosine_adjustment.py` — the first shipped (scalar) precedent
- `experiments/defuzz_gain_adjustment.py` — the second shipped (scalar) precedent
- `experiments/run_rank_k_K5_sweep.py` — the wrapper currently in flight
- `planning/findings/2026-05-26-equality-cosine-shipped.md` (if exists) — the equality-cosine ship
