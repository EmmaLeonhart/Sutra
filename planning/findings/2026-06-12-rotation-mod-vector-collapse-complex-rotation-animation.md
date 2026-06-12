# `Math.mod` collapses number-vectors; complex rotation is the substrate wrap for animation phase

**Date:** 2026-06-12 · **Context:** GUI #8 live-window event loop — the animated glow
centre needed to wrap around instead of sliding off-screen (moving_glow.su's `cx + 0.25`
never returns, so a live window goes blank after 8 ticks).

## What was measured

Probe: a `recurring vector cx = make_real(-0.875)` recurrence stepping
`Math.mod(cx + 1.25, 2.0) - 1.0` at `runtime_dim=8`, walked 20 ticks, decoded at the
display boundary, compared to the host lattice oracle.

1. **`Math.mod(vector, vector)` → all-NaN.** With both arguments `make_real`
   number-vectors, `rotation_mod` computes `θ = 2π·x/m` elementwise; every axis other
   than the real axis is `0/0 = NaN`, and the NaN propagates through the trig readout to
   the whole result vector — including the real axis. Measured: all 20 ticks NaN.
2. **`Math.mod(vector, literal)` → 0-d collapse.** With the modulus as a bare literal
   (the `demos/calc/digits.su` shape) the division is safe, but `rotation_mod`'s
   sin/cos table readout is scalar-shaped: feeding a full number-vector returns a
   **0-d tensor** (`torch.Size([])`), not a number-vector. The recurrence then
   degenerates (every tick decoded −1.0). Measured directly:
   `rotation_mod(make_real(0.375), 2.0).shape == ()`.

So `Math.mod` (= `rotation_mod`) operates on the **scalar realm** (0-d / scalar-typed
values, as digits.su uses it) and cannot wrap a vector-typed recurrence. This is a
shape limitation of the trig-table readout, not of the eigenrotation idea.

## What works instead — the rotation IS the wrap

Carry the animation phase as a **complex number** and advance it by a fixed rotation:

```
recurring vector z = make_real(1.0);                       // 1 + 0i
vector next = z * (0.9238795325112867 + 0.3826834323650898i);  // z · e^{iπ/8}
```

`*` is `complex_mul` (three cached matrices + elementwise multiply — pure tensor ops),
the complex literal folds at compile time, and the glow centre is `Re(z) = cos(kπ/8)`:
a smooth perpetual sweep of [−1, 1], period 16 ticks, **no modulus needed** — the
rotation is inherently periodic. Bonus: the sweep eases at the edges (sinusoidal)
instead of teleporting like a sawtooth wrap.

**Measured** (40-tick walk at runtime_dim=8, no host feedback): max error vs
`cos((k+1)·π/8)` = **1.13e-6**, drift growing ≈2.8e-8/tick (unit-modulus float drift of
the rotation constant; ~3e-4 after 10k ticks — irrelevant for a demo window, worth a
renormalising step if anything long-running ever needs it).

## Consequence

`demos/gui/live_frame.su` uses the complex-rotation phase for its animation RNN.

**Emma's ruling (2026-06-12, mid-session): do not use `Math.mod` at all — anywhere,
even where a modulus seems necessary.** It is the worst-implemented function in the
language. For periodic/wrap behavior the complex rotation above is the pattern;
existing `Math.mod` call sites (digits.su, the `%` dispatch) are legacy, not
precedent.
