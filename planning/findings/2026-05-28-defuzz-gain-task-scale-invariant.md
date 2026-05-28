# 2026-05-28 — Defuzz β harness: training task is scale-invariant in `gain`, not just saturated

Follow-up to `planning/findings/2026-05-28-defuzz-gain-grad-fixed-eq-substrate-leak.md`. The `eq()` autograd leak was fixed in `e2b8ee7a`; the queue's documented next step was "rewrite harness to use `loop (2)`/`loop (3)` or non-saturated inputs, then run 3-seed end-to-end." Tried that; it doesn't help — the task is **algebraically degenerate w.r.t. the `gain` parameter**, not just over-saturated.

## What we tested

Threaded an `--iters` CLI flag through `experiments/defuzz_gain_adjustment.py` to control the loop count inside `gated_polarize`. Ran end-to-end with `iters=2`, N=16, epochs=30, 3 seeds.

Result:

```
seed 0: baseline loss = 0.0000  ->  trained loss = 0.0000  gain*=1.0000
seed 1: baseline loss = 0.0000  ->  trained loss = 0.0000  gain*=1.0000
seed 2: baseline loss = 0.0000  ->  trained loss = 0.0000  gain*=1.0000
```

`gain` did not move from its 1.0 initialization. Loss was zero at baseline AND at the trained value.

## Why — the math

The .su body is `v = (gain * v) == true;` repeated. For an input `v = make_truth(x)` (real-axis = 0, truth-axis = x, others 0):

- `gain * v` is element-wise scaling: truth-axis becomes `gain * x`, others stay 0.
- `(gain * v) == true` is `eq` — cosine similarity against `make_truth(1.0)`:

```
cos(gain*v, true) = (gain*v · true) / (|gain*v| · |true|)
                  = (gain * x) / (|gain*x| · 1)
                  = sign(gain * x)
                  = sign(x)         (for gain > 0)
```

**Cosine similarity normalizes out the scale.** Whatever `gain` is (positive), the result is `sign(x)` — the polarization target. Loss is zero at every gain > 0; gradient is zero everywhere.

The `loop (10)` was a red herring. Even `loop (1)` saturates because the first iteration already outputs sign(x). Iterating doesn't change anything either — once you're at sign(x), you stay at sign(x).

## What the precedent (equality_cosine_adjustment) does differently

`experiments/equality_cosine_adjustment.py` (the shipped rank-1 constrain-train instance) trains `T` inside a softmax over `T * sim(x, prototype)`. **Softmax IS scale-sensitive** — higher T sharpens the distribution. Cross-entropy loss against the correct class then has a real gradient w.r.t. T. That harness ships because the parameter is used in a scale-sensitive context (softmax + CE), not in a scale-invariant context (cosine).

The defuzz harness chose the wrong context for `gain` — applying it before a cosine `eq` cancels it. The autograd works (`gain.grad` is non-zero in principle; the chain is connected); the *task* doesn't differentiate the parameter.

## What would unblock this

A real defuzz β experiment needs a task where β meaningfully shifts the OUTPUT distribution. Options:

1. **Apply β to a non-cosine operator.** The original `defuzzify_trit(v, iters=10, beta=2.0)` β IS scale-sensitive — it's the exponent in `w_neg = exp(-β * (x+1)²)` style polarization, where β sharpens the polarization. If we expose `defuzzify_trit`'s β as a Sutra-level `number` parameter and train *that*, the gradient is meaningful (higher β = sharper polarization = different output for non-saturated inputs).

2. **Switch the eq operator to a scale-sensitive variant.** `eq_synthetic` (Euclidean distance + tanh) is scale-sensitive in its input magnitude. A version with the form `tanh(β * (1 - dist))` would have β meaningfully shift the polarization curve.

3. **Train a different scalar in the same .su.** E.g., a per-step weight on the polarized output rather than a pre-multiplier on the input. The post-step weight isn't cancelled by cosine.

Option 1 is the cleanest — it goes back to the `defuzzify_trit` β that the experiment was originally named for (the file is `defuzz_gain_adjustment.py`, but the body actually uses `==`, not `defuzzify_trit`). The naming was off; the implementation drifted from the original intent.

## What landed in this commit

- `--iters` CLI flag for future task-redesign experiments (default 10, matches original). Exposed but documented as not-a-fix.
- This finding doc names the real issue (scale-invariance, not saturation) so the next session doesn't repeat the "try fewer iterations" attempt.

## Update 2026-05-28 (later in session): `defuzzify_trit` exposed as Sutra intrinsic; loss surface is STILL mostly flat

Followed Option 1's path. Added an intrinsic declaration in `sdk/sutra-compiler/sutra_compiler/stdlib/logic.su`:

```sutra
intrinsic function fuzzy defuzzify_trit(fuzzy v, number iters, number beta);
```

This compiles to `_VSA.defuzzify_trit(v, iters, beta)` at runtime. Verified: the .su `function fuzzy gated_polarize(fuzzy v, number beta) { return defuzzify_trit(v, 10, beta); }` compiles, runs, and produces β-sensitive outputs at the polarization boundary (table below). The harness now has a `--body trit` CLI option that switches to this path.

### β-sensitivity table (iters=10, hardcoded in runtime)

| input x | β=0.01 | β=0.1 | β=1.0 | β=10.0 |
|---:|:---:|:---:|:---:|:---:|
| 0.05 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0.30 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0.50 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0.70 | 0.0 | 0.0 | +0.9999 | +0.9999 |
| 0.90 | 0.0 | 0.0 | +0.9999 | +0.9999 |

β has a STEP behavior — the transition is between 0.1 and 1.0 for inputs > 0.5. Within saturation regions the gradient is ~0. Adam training at β=0.5 with inputs in (0.55, 0.85) stays stuck at β=0.5 over 30 epochs (loss=1.0 throughout — all outputs collapse to 0).

### What's still blocking real β-training

1. **Runtime hardcodes iters=10** inside `defuzzify_trit` (codegen-time unroll). The intrinsic accepts an `iters` argument but the runtime ignores it. For real β-sensitivity, iters=1 or 2 keeps β-changes visible across the whole input range. v2 work: make iters runtime-variable.

2. **The 3-way polarizer's loss landscape is step-shaped at iters=10**, not smooth. Even with Adam, the gradient flowing through the saturation regions is negligible. Real β-training needs either (a) iters<3, or (b) a different loss design that pulls β toward the active boundary (e.g., a regularizer on the polarization-strength rather than direct MSE on outputs).

3. **The 3-way polarizer target doesn't match the harness's sign(x) target.** For x ∈ (0.1, 0.5), the polarizer correctly outputs 0 (the nearest trit), but the harness's target is sign(x) = +1 — unrecoverable loss=1 from that input bucket regardless of β. Either the harness needs to use 3-way targets (sign(x) only if |x| > 0.5, else 0) or the input distribution needs to be concentrated in |x| > 0.5.

Tracked as the v2 follow-on under task #19 (originally "expose defuzzy 2-arg"; renamed to "implement runtime-variable iters in defuzzify_trit + redesign harness loss + verify β trains end-to-end").

## Update 2026-05-28 (third pass): input-distribution fix lands; β STILL doesn't move

Targeted blocker #3 (target-vs-polarizer mismatch) by changing `build_fuzzy_data` to sample magnitudes in `[0.55, 0.85]` (and `[-0.85, -0.55]`) instead of `[0.1, 0.9]`. Default args `mag_lo=0.55, mag_hi=0.85` exposed.

Measured (`--body trit`, 3 seeds × 30 epochs × N=20 × lr=0.2):

```
seed 0: baseline loss = 0.4500  ->  trained loss = 0.4500  gain*=0.9999
seed 1: baseline loss = 0.1500  ->  trained loss = 0.1500  gain*=0.9998
seed 2: baseline loss = 0.2000  ->  trained loss = 0.2000  gain*=0.9998
```

**Progress:** baseline loss is now non-trivial (0.27 ± 0.16 mean) — the polarizer at β=1.0 doesn't perfectly polarize all inputs in [0.55, 0.85]; some closer to 0.55 collapse to 0 (the polarizer's "x=0.55 → 0.44 → 0.42 → 0.34 → ..." trajectory under β-doubling).

**No progress on training:** β still stuck at ~1.0. The gradient at β=1.0 is still ~0 because:
- For x ≈ 0.75, β=1.0 already saturates to +1 (no gradient there).
- For x ≈ 0.55, β=1.0 pulls toward 0 across iterations (no gradient there either — the polarization trajectory is locked into the 0-attractor at this β).
- The transition happens at some β-value between 1.0 and 10.0 where the 0.55 input flips from 0-attractor to +1-attractor — that's the kink that Adam needs to cross, and the gradient on either side of the kink is too small.

This confirms blocker #1 (runtime-hardcoded iters=10) is the real bottleneck. Real β-training needs iters≤2 so β-changes affect ONE polarization step (not 10 compound doublings), keeping the gradient surface smooth.

The input-distribution fix is committed because (a) it makes the baseline loss non-trivial — a measurable improvement over the prior zero-loss-everywhere state, (b) `mag_lo`/`mag_hi` parameters are exposed so future experiments can sweep, (c) the default range is now correctly aligned with the polarizer's natural output range.

## Update 2026-05-28 (fourth pass): RESOLVED — β trains end-to-end at iters=1

Per Emma's `AskUserQuestion` decision (Option 1: "Change defuzzify_trit to runtime-variable iters"), the codegen-time 10-iter unroll in `_VSA.defuzzify_trit` was replaced with a runtime `for _t in range(int(iters))` over the structural iters parameter. Per Audit #4's 2026-05-17 reclassification, range() over a structural index (no host scalar branch on data) is substrate-pure — comment in the codegen explicitly cites it.

Default behavior preserved: callers without an explicit iters arg still get iters=10. The harness's `--body trit --iters 1` mode now polarizes in one step, giving a smooth β-gradient surface.

### 3-seed end-to-end training result (`--body trit --iters 1 --N 20 --epochs 40 --lr 0.3`)

```
seed 0: baseline loss = 0.2255  ->  trained loss = 0.0201  gain*=6.7792
seed 1: baseline loss = 0.2040  ->  trained loss = 0.0104  gain*=6.4532
seed 2: baseline loss = 0.2082  ->  trained loss = 0.0133  gain*=6.5188

baseline loss (gain=1): 0.2126 ± 0.0114  (n=3)
trained  loss (gain*):  0.0146 ± 0.0050  (n=3)
trained gain*: 6.5837 ± 0.1724
round_trip_ok(all): True  max|Δ| over all seeds: 1.19e-07
```

**Loss decreased ~15× across all seeds.** β converged consistently to ~6.58 (low variance: 0.17), suggesting a real task-optimum. Bake-back round-trip is bit-exact within float32 precision (max|Δ| = 1.19e-7). The full compiler suite (437 passed / 7 skipped) is green on the codegen change.

This closes task #19 as functionally discharged: defuzz β IS the second-shipped constrain-train instance (after equality-cosine T from 2026-05-26). It expands the trainable surface to a SECOND operator (`defuzzify_trit`'s β), per Emma's "every operation trainable" vision (memory `feedback-constrain-train-vision-is-every-op`).

The bake-back round-trip works at numerical precision (1.19e-7 < 1e-4 threshold) — `defuzzify_trit(v, 1, β=6.5837)` compiles to the same emitted graph whether β is a runtime tensor (param form) or a baked literal (`(6.58370018)`). The trained β IS the model in source.

## Cross-refs

- `experiments/defuzz_gain_adjustment.py` — the harness (autograd works; task is scale-invariant)
- `experiments/equality_cosine_adjustment.py` — the working precedent (softmax + CE)
- `planning/findings/2026-05-28-defuzz-gain-grad-fixed-eq-substrate-leak.md` — the autograd fix (still load-bearing for any future trainable-through-`==` task)
- `Audit.md` REAL LEAK #2 — the `defuzzify_trit` substrate-purity fix that exposed the operator the harness was named for
- queue.md State Inventory A.4
