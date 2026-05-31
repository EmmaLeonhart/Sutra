# weight→code follow-up #2: the coefficient wall — ~½ decodable, three levers exhausted (NEGATIVE ×3)

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
- **The aux-loss integration is the wrong lever. Two paths were named; #1 is now
  also closed (negative); #2 is the indicated direction:**
  1. *Post-hoc substitution — TRIED, NEGATIVE (see "Lever 1 result" below).*
  2. *Richer input features — TRIED, NULL (see "Lever 2 result" below).* Both
     output-side levers (aux loss, post-hoc substitution) AND this input-side
     lever failed, so coefficient recovery is a measured wall for this
     architecture; the next moves are bigger bets (readout redesign, regression
     head, bigger model) — a research-direction call surfaced to Emma.

## Lever 1 result — post-hoc substitution does NOT help (NEGATIVE)

To get a good decoder *and* a trained head in one run (the aux loss couples them
negatively), the head was trained with a **stop-gradient on the encoder memory**
(`--coeff-detach`): it probes the decoder-shaped representation without
perturbing it. This worked as designed — decoder exact-match stayed at baseline
**0.667** (vs 0.508 for the coupled aux_w=0.5), and the probe reached **coeff_a
0.615 / coeff_b 0.556**, even slightly *higher* than the coupled head.

Then `eval_substrate.py` overwrites the decoder's coefficient literal(s) with the
probe's prediction (positional 1st→a / 2nd→b), gated to slot-carrying programs
(corpus label as slot-presence oracle), and recompiles + reruns on the substrate.
Measured on the 96 coeff-slot val programs:

| | IO-reproduction |
|---|---|
| decoder source as-is (`io_base`) | 28 / 96 = **0.292** |
| with post-hoc head substitution (`io_subst`) | 27 / 96 = **0.281** |

**Substitution did not lift coeff-family IO — it was a slight wash-to-worse.** A
0.61-accurate head is *below* the decoder's own coefficient quality on the cases
it already gets right: blanket substitution overwrites the decoder's correct
coefficients with the head's wrong predictions about as often as it fixes wrong
ones, so there is no net gain (and for two-slot families it needs *both* a and b
right, ≈0.61·0.56 ≈ 0.34 from the head alone). Output-side coefficient injection
needs a head materially more accurate than ~0.6; the head can't get there because
the coefficient is only ~½ decodable from the encoder rep (finding #1 above).
**Conclusion: the bottleneck is representational — lever 2 (input features) is the
path; output-side tricks are exhausted.**

## Lever 2 result — matmul input feature does NOT move it (NULL/marginal)

The coefficient is a *relationship* `y ≈ a·(M@x) + …`, so the natural input-side
fix is to feed the matmul partial-products `M_s @ x` directly (a new `TYPE_MM`
token stream in `build_enc`, computed host-side — feature prep for the host
weight→code model, not a substrate op), making `y`-vs-`M@x` visible instead of
something the per-token encoder must synthesize. Retrained the same detached
config with the feature on:

| metric | without feature (lever 1 run) | with `M@x` feature |
|---|---|---|
| decoder exact-match | 0.667 | 0.689 |
| probe coeff_a / coeff_b | 0.615 / 0.556 | **0.604 / 0.597** |
| coeff-slot IO (`io_base`, n=96) | 28 | 30 |
| post-hoc substitution (`io_subst`) | 27 | 27 |

**The feature did not move coefficient recovery** — probe accuracy stays ~0.60,
decoder and coeff-family IO move only within retrain noise (a few programs).
Feeding `M@x` explicitly was supposed to make the coefficient linearly readable;
it didn't. The most likely reason is the head's **mean-pool readout**: the
coefficient is a *per-component* ratio `a = (yᵢ−…)/(M@x)ᵢ`, and mean-pooling the
encoder memory over all tokens dilutes exactly that per-component signal. So the
limit may be the readout, not the input — but that is now a *fourth* speculative
lever, and three have already returned the same ~0.60.

**Verdict: three levers exhausted (aux loss, post-hoc substitution, input
feature), all converging on a ~0.60 probe / ~0.30 coeff-family-IO wall.** This is
a genuine, measured result: weight→code recovers program *structure* near-
perfectly (chain4 = 1.0) but *scalar coefficients* are a wall for this
architecture. Whether to keep investing (readout redesign, regression head,
bigger model) or document the wall and move on is a research-direction call —
surfaced to Emma (queue.md A.0), not decided autonomously.

## Capacity test (Emma 2026-05-31: "bigger model / corpus") — NOT capacity-bound

Emma's call on the wall: test whether it's capacity-bound before concluding it's
architectural. Step 1 (bigger model): retrained at `--d-model 256 --layers 6`
(≈4–8× the params of the d128/L3 baseline), same detached-probe setup.

| metric | d128 / L3 (baseline) | d256 / L6 |
|---|---|---|
| decoder exact-match | 0.689 | 0.658 |
| canonical exact = IO | 0.714 | 0.678 |
| probe coeff_a / coeff_b | 0.604 / 0.597 | 0.615 / 0.569 |
| coeff-slot IO (`io_base`, n=96) | 30 (0.31) | 22 (0.23) |

**Quadrupling-to-octupling the model did not move the wall** — probe accuracy
stays ~0.60, coeff-family IO is flat-to-noisily-lower, decoder exact unchanged-
to-down. So the wall is **not capacity-bound** (model side). This is consistent
with the lever-2 read that the bottleneck is the **readout architecture** (the
mean-pool head can't extract a per-component ratio), not the parameter budget.
Step 2 (bigger *corpus*) is the remaining half of Emma's test — but the flat
probe across a 4–8× model-size change already makes a data-starvation explanation
unlikely (a model that structurally can't represent the ratio won't learn it from
more examples). Corpus-scaling is being measured to scratch (no HF push) to
confirm before drawing the architectural conclusion.

## Honesty caveats

- **Single seed per config, single greedy decode.** The finding's robust signal
  is the *monotone trade-off* and the *~0.5–0.6 head ceiling*, not any third
  decimal. coeff_b is noisier (n=72, and 0.5→0.47 is within noise of flat).
- **Small-K (4…16) plain-numeric regime**, as before.
- The ablation numbers are read from each run's `final_val` stdout, not one
  checkpoint; `data/model.pt` now holds the detached-head run (lever 1).
  Gitignored `data/` is not committed.
- **Lever-1 caveat:** the 28→27 is the aggregate over the 96 slot programs; the
  per-program overlap (how many base-correct got *corrupted* vs how many
  base-wrong got *fixed*) was not separately logged — the mechanism (0.61 head
  corrupts ≈ as often as it fixes) is the consistent interpretation, not a
  separately-measured decomposition. Substitution is gated by the corpus
  slot-presence label (a ceiling assumption — a real decompiler wouldn't know
  which programs have coeff slots), so 0.281 is already optimistic.
- This is a **double negative** (aux loss *and* post-hoc substitution), logged as
  required rather than buried. It does not close coefficient recovery — it
  exhausts the output-side levers and points to input features (lever 2).
