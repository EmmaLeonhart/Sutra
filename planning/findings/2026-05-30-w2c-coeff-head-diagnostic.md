# weight→code follow-up #2: a coefficient head — the coeff is only ~½ decodable, and an aux loss hurts (NEGATIVE)

**Date:** 2026-05-30
**Scripts:** `experiments/w2c_seq2seq/{prepare,model}.py`
**Builds on:** `planning/findings/2026-05-30-w2c-tick3-hardened-corpus-eval.md`
(tick 3: the model recovers structure but not non-unit coefficients — non-unit
coeff-family exact-match 0.241)

## The question

Tick 3 localized the weight→code failure to the coefficient axis. Follow-up #2's
**diagnostic**: is the discrete coefficient (`{0.5,1,1.5,2,3}`) even decodable
from the encoder representation? If a head on the pooled encoder memory can
classify it, the information is *there* and the bottleneck is the decoder's
emission; if the head also fails, the encoder isn't capturing the coefficient
from weights+IO at all.

## What was built

- `prepare.py`: propagate per-program coefficient class labels (`coeff_a`,
  `coeff_b` as indices into `COEFF_CLASSES`, `-1` if a slot is absent).
- `model.py`: a **coefficient head** — masked mean-pool of the encoder memory →
  two `Linear(d, 5)` for slots a/b — as a *separate* branch (`coeff_logits`).
  `forward()` (the decoder path) is unchanged, so the overfit guard stays valid.
  Joint training adds a masked auxiliary CE loss, weight `--coeff-aux-w`. Eval
  reports val head accuracy for a/b.

Guards green: `test_model` + `test_prepare` 5/5; eval harness 6/6.

## Results — ablation over the auxiliary-loss weight (n=360 val, CUDA, 40 ep)

| `coeff_aux_w` | decoder exact-match | coeff_a head acc (n=96) | coeff_b head acc (n=72) |
|---|---|---|---|
| 0.0 (control) | **0.669** | 0.250 | 0.181 |
| 0.1 | 0.589 | 0.458 | 0.500 |
| 0.5 | 0.508 | **0.594** | 0.472 |

(5 coefficient classes → chance = 0.200. The 0.0 control's head is untrained, so
its 0.25/0.18 is chance, as expected. Decoder 0.669 ≈ the tick-3 baseline 0.678
— retrain variance; adding the head *params* alone does not hurt.)

## Two findings, both negative for this lever

**1. The coefficient is only partially decodable from the encoder rep.** Even
when we optimize hard for it (aux_w=0.5), a head on the pooled representation
reaches only **0.59 / 0.47** — well above chance (information *is* present) but
far from the ~0.9+ that would say "cleanly separable." The encoder, trained to
generate source, does not build a representation from which the coefficient is
crisply readable. So the bottleneck is partly **representational**, not purely
the decoder's emission.

**2. A representation-shaping auxiliary loss is a net negative for the end
task.** Decoder exact-match falls **monotonically** with aux weight
(0.669 → 0.589 → 0.508): the auxiliary objective competes with source
generation rather than helping it. There is no low-cost regime — even aux_w=0.1
costs 8 points of exact-match while only reaching coeff acc 0.46/0.50. Jointly
training a coefficient head to "shape the representation" **does not** improve
weight→code; it degrades it.

## Consequences

- **Default changed to `--coeff-aux-w 0.0`** so the standard training run is not
  degraded by a lever the ablation shows is harmful. The head remains available
  (`--coeff-aux-w 0.5` trains it) for diagnostics, but it is off by default.
- **The aux-loss integration is the wrong lever; two better paths remain open:**
  1. *Post-hoc substitution.* Decode source as today (structure is recovered
     well), then **overwrite** the coefficient literal with the head's
     prediction. This decouples coefficient recovery from the decoder objective
     — but is capped by the head's ~0.59 accuracy, so it would lift, not solve,
     the coeff families. Bounded; the natural next experiment.
  2. *Richer input features.* The coefficient is `a = (y − x)/(M@x)`-shaped —
     a *relationship* between IO and weights the current per-token encoder may
     not surface. Feeding a derived feature (e.g. per-IO residual `y − M@x`, or
     `y − x`) could make the coefficient linearly separable. Heavier; speculative.

## Honesty caveats

- **Single seed per config, single greedy decode.** The finding's robust signal
  is the *monotone trade-off* and the *~0.5–0.6 head ceiling*, not any third
  decimal. coeff_b is noisier (n=72, and 0.5→0.47 is within noise of flat).
- **Small-K (4…16) plain-numeric regime**, as before.
- `data/model.pt` currently holds the aux_w=0.1 rerun (last run); all numbers
  above are read from each run's `final_val` stdout, not from a single
  checkpoint. The ablation logs are not committed (gitignored `data/`).
- This is a **negative result for the coefficient-head-as-aux approach**, logged
  as required rather than buried. It does not close coefficient recovery — it
  rules out one lever and sharpens the next two.
