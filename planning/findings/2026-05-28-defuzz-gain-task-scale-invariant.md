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

## Cross-refs

- `experiments/defuzz_gain_adjustment.py` — the harness (autograd works; task is scale-invariant)
- `experiments/equality_cosine_adjustment.py` — the working precedent (softmax + CE)
- `planning/findings/2026-05-28-defuzz-gain-grad-fixed-eq-substrate-leak.md` — the autograd fix (still load-bearing for any future trainable-through-`==` task)
- `Audit.md` REAL LEAK #2 — the `defuzzify_trit` substrate-purity fix that exposed the operator the harness was named for
- queue.md State Inventory A.4
