# 2026-05-28 — `select` temperature trains; K=5 embed-protos task surface is flat

**Context:** Task #21 / constrain-train target 4 in `planning/exploratory/constrain-train-next-targets.md`. The shipping criterion was "expose the softmax temperature inside `select` as a Sutra-level trainable parameter, prove the mechanism via a full training harness + bake-back + round-trip check." The harness shipped in this work-loop tick (`experiments/select_temperature_adjustment.py`).

## Two results, distinct interpretation

### (A) Mechanism: WORKS end-to-end

The smoke (`experiments/select_temperature_smoke.py`, shipped earlier in `a01184e3`) demonstrates the gradient surface is smooth and monotonic across T ∈ {0.01, 0.1, 0.5, 1.0, 5.0, 100.0} on a synthetic 3-class task with orthogonal random prototypes + a deliberately weighted query (0.7·p0 + 0.25·p1 + 0.05·p2). As T decreases, the select output concentrates monotonically on the closest prototype.

The full harness (this finding's main artifact) on a K=3 / per-class=3 / epochs=10 micro-task — orthogonal-ish embedded category words — drives T from baseline 1.0 to T*=0.0185, baseline margin +0.0039 → trained margin +0.2796 (71.6× ratio), with bake-back round-trip max|Δ| = 2.50e-06. The mechanism is trainable.

The constrain-train invariant holds: T is a `number` parameter in the .su; the trained T\* bakes back as a numeric literal in a fresh .su with no T parameter; the re-compiled-from-source baked graph is observably identical to the trained-param graph within float32 noise.

### (B) Real task: K=5 / per-class=10 / epochs=80 / 3 seeds — FLAT surface

The shipped harness's K=5 default (mirroring `experiments/equality_cosine_adjustment.py`) runs in 52.9s and produces:

```
baseline margin (T=1):   -0.0014 ± 0.0000  (n=3)
trained  margin (T=T*):  -0.0370 ± 0.0000  (n=3)
trained T*:              -0.7868 ± 0.0000
round_trip_ok(all): True  max|Δ| over all seeds: 1.79e-07
```

T moves from +1.0 through 0 to -0.79 — a sign flip that inverts the softmax. The margin metric gets slightly *worse* (more negative), not better. All three seeds land at the identical T\* (deterministic given seed-independent gradient surface from T=1.0).

**Why this happens** — the raw similarities `sim(x, p_y) - max_{j≠y} sim(x, p_j)` on the K=5 embed(category-name) prototypes are essentially zero (margin ≈ -0.001). The select-T gradient surface at T=1 from those near-degenerate scores is dominated by noise, and Adam descends a flat valley toward sign-inverted T because the cross-entropy proxy is not tightly coupled to the dot-product-margin metric I'm measuring.

This is not a mechanism failure. It is a **task-fit observation**: select-T improves classification when there is a non-degenerate similarity gap to sharpen; when the gap is essentially zero (frozen category-name embeddings used as direct prototypes for 5 noisy classes), there is nothing for the temperature lever to *do*.

## What this finding adds to the inventory

**Shipped constrain-train inventory after today:**
1. Equality-cosine T (`21778648`, 2026-05-26): +1.08× margin gain on K=5 embed-protos task.
2. Defuzz β (`5ca1b043`, 2026-05-28): ~15× loss reduction on β-sweep task.
3. Rank-k is_X K=2 smoke (`132c8925`, 2026-05-27): 3.01× margin improvement.
4. **Select T (this tick):**
   - Smoke (orthogonal 3-class): monotonic gradient surface 0.01..100.
   - Micro K=3: 71.6× margin ratio + bake-back 2.50e-06.
   - K=5 embed-protos: trains to T\*=-0.79 but FLAT margin surface, no improvement.
5. Rank-k is_X K=5 sweep: still in flight (`bwf96wgym`, last-attempt rule).

Operator surface added: **`select`** (was untrained yesterday). The "wrap the scores in a divide by T" Sutra-level surface (no parser change) is sufficient — Adam navigates it cleanly when the task carries a real similarity gap; it descends a flat valley when the task does not.

## Substrate-purity contribution

Building this harness surfaced REAL LEAK #10 in `Audit.md`: `_select_softmax`'s `_torch.as_tensor(scores, ...)` was silently detaching grad-tracked scores. Fixed in the same tick by routing tensor-scored calls through `_torch.stack`. The select primitive is now substrate-pure for autograd.

## What to ship next

Per the synthesis doc's original ranking, target 3 (**`bundle` weights**) is next — `(w_a*a + w_b*b + w_c*c)` with trained scalars per bundle term. This adds the `bundle` operator (a VSA primitive) to the trainable inventory. It needs both a parser-level extension (weighted bundle syntax) and a task design where bundle weighting demonstrably matters. ~4-6h estimated, including writing the task.

Alternative pre-bundle ship: **find the not-flat select-T task.** Concretely, the smoke proved monotonic gain on orthogonal protos + biased mixture queries; the K=5 frozen-embed task is too noisy. A task where select-T's gradient surface is non-degenerate is a small change — e.g., generate K random orthonormal prototypes (not embeddings) and use mixture-of-protos queries with controlled signal-to-noise. ~1h to construct + run; would push select-T from "mechanism shipped" to "mechanism shipped + non-trivial task win."

## Cross-refs

- `experiments/select_temperature_smoke.py` — smoke (shipped in `a01184e3`).
- `experiments/select_temperature_adjustment.py` — full harness (this tick).
- `planning/exploratory/constrain-train-next-targets.md` — the synthesis doc the next pick comes from.
- `Audit.md` REAL LEAK #10 — the substrate-purity fix surfaced building this.
- `experiments/equality_cosine_adjustment.py` — the template (same K=5 embed-protos task; equality-cosine T won +1.08× on it, marginal but positive; select-T finds the same task essentially flat for its lever).
