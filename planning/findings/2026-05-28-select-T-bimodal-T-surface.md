# 2026-05-28 — Select-T CE surface is bimodal; default lr matters

**Context:** Follow-on to `planning/findings/2026-05-28-select-T-trains-but-K5-embed-task-is-flat.md`. That K=5 frozen-embed run trained T to -0.79 (sign-flipped softmax) on a task where the raw-similarity gap was too narrow for select-T's lever. The follow-on `experiments/select_temperature_orthogonal.py` uses K random orthonormal prototypes + alpha/noise mixture queries — a task with a deliberately *non-trivial* similarity gap. First K=5 run at lr=0.05 *also* trained to T<0 (T*=-0.89, margin +0.22 → -0.19). That was unexpected.

## The loss surface is bimodal in T

Probed the cross-entropy loss vs T directly for the orthogonal-protos K=5 task (K=5, per-class=10, alpha=0.7, noise=0.15, seed=0):

```
   T          CE     margin
-5.00      1.9098    -0.0418
-1.00      2.8867    -0.1728
-0.50      3.6235    -0.2751
-0.10      6.0889    -0.5858
 0.10      0.0002    +0.9992
 0.50      0.0215    +0.5087
 1.00      0.3111    +0.2245
 5.00      1.2999    +0.0361
```

Two basins:
- **Global min at small +T** (T≈0.1): CE ≈ 0, margin ≈ +1.0. Softmax sharpens onto the correct prototype.
- **Local min at moderate -T** (T ≈ -5 or further toward -∞): CE ≈ 1.9, margin ≈ -0.04. Softmax inverts; output is roughly the centroid of wrong prototypes.

These are separated by a barrier at T = 0 (where scores blow up; CE = 6.09 at T = -0.1). Adam starting at T=+1 and stepping with lr=0.05 overshoots zero in the first few epochs and ends up descending the negative-T slope. It never recovers because the negative-T basin is locally stable (gradient becomes shallow far from zero).

## Adam at lr=0.005 stays in the correct basin

Re-running the same K=5 / per-class=10 / epochs=80 / 3-seeds with lr=0.005:

```
seed 0: baseline margin = +0.2245 -> trained margin = +0.3970  T*=0.6225  round-trip 8.94e-08
seed 1: baseline margin = +0.2233 -> trained margin = +0.3955  T*=0.6222  round-trip 1.79e-07
seed 2: baseline margin = +0.2220 -> trained margin = +0.3939  T*=0.6219  round-trip 3.58e-07

baseline margin (T=1):   +0.2233 ± 0.0013  (n=3)
trained  margin (T=T*):  +0.3955 ± 0.0016  (n=3)
trained T*:               0.6222 ± 0.0002
margin ratio: +1.77x
round_trip_ok(all): True  max|Δ| over all seeds: 3.58e-07
```

T trains 1.0 → 0.62 (sharpening, not flipping); margin +0.22 → +0.40 (1.77× ratio); round-trip bit-exact within float32 (8.94e-08 .. 3.58e-07). Three seeds agree to four decimals. Clean positive constrain-train result.

T=0.62 is moving in the right direction toward the true minimum at T≈0.1 but hasn't reached it in 80 epochs at lr=0.005. Adam's effective step size shrinks as the gradient flattens near the minimum. Pushing further (more epochs, smaller lr decay, or a log-T parameterization) would close the gap. For the constrain-train ship criterion (mechanism trainable + bake-back + measurable margin gain) the 0.62 result is sufficient.

## Why this matters

The bimodal CE surface is **not specific to the orthogonal-protos task** — it's a property of the select operator itself. select takes scores / T and softmaxes; the softmax is symmetric around T=0 in the sense that T → -T inverts the weights. For ANY task where the correct class has positive raw similarity, large +T → uniform output (degrades to centroid), small +T → sharpens onto correct (low loss), small -T → sharpens onto incorrect (very high loss), large -T → uniform of wrong protos (moderate loss). The path from T=+1 to T=+0.1 *does not cross* T=0 in the gradient field, but Adam's adaptive momentum can push past it in finite-step training.

This means:
1. **The default lr in `experiments/select_temperature_adjustment.py` (lr=0.05) is wrong for select-T.** That harness mirrored `equality_cosine_adjustment.py`'s lr=0.05 default, which is fine for cosine-T (a single-basin surface) but unsafe for select-T. The original K=5 embed-protos negative finding was partially an optimizer pathology, not just task fit. (Task fit is still real — the embed-protos gap is genuinely narrow — but the wrong-basin landing was the lr.)
2. **The orthogonal-protos K=5 task at lr=0.005 is a clean positive constrain-train win** for select-T. Fourth shipped constrain-train instance: equality-cosine T, defuzz β, rank-k K=2, select-T (orthogonal).
3. **For future trainable-operator additions involving softmax, expect bimodal T-surfaces** and pick lr accordingly. The defuzz β surface was scale-invariant in the cosine case (single-basin in β once we picked the right body); the select-T surface is bimodal in T because the softmax is sign-symmetric in the temperature argument.

## What to do next

- Updated `experiments/select_temperature_orthogonal.py` default lr to 0.005 with an inline comment explaining why.
- Did NOT touch `experiments/select_temperature_adjustment.py` lr default (still 0.05) — the embed-protos task has both task-fit AND optimizer issues; the original finding stands as documented. If we wanted to retry the embed-protos task with lr=0.005 (probably still flat — the similarity gap is too narrow), that's a separate ~30-min experiment.
- The constrain-train inventory now has a 4-th clean positive instance: select-T (orthogonal-protos K=5, 3-seed, 1.77× margin gain, T*=0.62, round-trip 3.58e-07).

Next pick per the synthesis doc: target 3 (`bundle` weights), needs parser change + task design, ~4-6h.

## Substrate-purity note

The orthogonal-protos run hits the same `_select_softmax` path fixed in REAL LEAK #10 (`fe274d3c`) — autograd preserved via `_torch.stack` for tensor scores. The bimodal CE finding has nothing to do with substrate purity (it's a property of softmax's sign-symmetry in T), but it could not have been observed without #10's fix making T actually trainable.

## Cross-refs

- `experiments/select_temperature_orthogonal.py` — the experiment.
- `experiments/select_temperature_adjustment.py` — the original embed-protos harness.
- `planning/findings/2026-05-28-select-T-trains-but-K5-embed-task-is-flat.md` — the original K=5 NEGATIVE finding (now partially explained by lr).
- `Audit.md` REAL LEAK #10 — the substrate-purity fix that enables training.
- `planning/exploratory/constrain-train-next-targets.md` — the synthesis doc; next pick is target 3 `bundle` weights.
