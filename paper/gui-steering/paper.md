# Painting and Steering on a Frozen-Embedding Substrate: a whole-frame renderer and a human-steerable interface in Sutra

**Status:** working draft (a1 / GUI track, `gui-training` branch). The demo is
built (1a–1d) and the method sections, render-fidelity table (§6), and steering
soak (§7) are grounded in shipped code and measured runs. Remaining: figures (§8),
related-work verification (§9), and the reproducibility command list (§10). This
paper cites only measured numbers.

## Abstract

Sutra is a purely functional language whose values are geometric objects in the
frozen semantic subspace of a pretrained embedding model, and whose operations are
tensor operations on that substrate. We use it to render a graphical interface:
the whole image is computed by a single substrate operation that returns the frame
as one buffer vector, with the host acting only as I/O (it builds coordinate
buffers and paints the returned pixels). On top of this we build a parameterized
"hero" graphic whose layout, scale, colour, and headline are driven by a parameter
vector θ supplied as per-call broadcast buffers, so changing θ changes the picture
with no recompilation. We then steer the rendered output by human preference: a
warmer/colder button supplies a scalar reward, and a host-side Simultaneous
Perturbation Stochastic Approximation (SPSA) optimizer adjusts θ. We report the
render fidelity (the one-operation frame matches a per-pixel host oracle to within
~4×10⁻⁷) and the steering soak (a 100-press session renders with zero NaN/blank
frames, and a consistent rater moves the parameter monotonically in the rewarded
direction). Throughout we keep an explicit account of which work runs on the
substrate (the render) and which is host-side (the composition and the optimizer),
and we do not claim substrate-native training or a single end-to-end substrate
program.

## 1. Introduction

Sutra represents data as vectors in a frozen embedding space and computation as
geometry on that space (`planning/sutra-spec/vision.md`). A natural question is
whether something as concrete as a pixel grid can be produced *by* that substrate
rather than around it. This paper answers yes for a useful case — a rendered,
interactive interface — and is explicit about the boundary between the substrate
work and the host work.

Contributions:

1. **Whole-frame substrate rendering.** A frame is computed by one substrate
   operation that returns the entire image as a single buffer vector (§2); the
   host only builds coordinate geometry and paints.
2. **Runtime-parameter rendering with no recompilation.** A parameter vector θ is
   supplied as per-call broadcast buffers, so an optimizer changes the picture by
   changing call arguments, not code (§2, §4) — the property the steering loop
   depends on.
3. **Substrate text rendering.** Glyphs are rendered on the substrate via a
   bound-vector font; a headline is the concatenation of substrate glyph fields
   (§3).
4. **Human-steerable output.** A warmer/colder reward drives a host-side SPSA
   optimizer over θ, morphing the substrate-rendered hero (§5).

The render fidelity (§6) and the steering soak (§7) are both measured on the built
demo; §8 states what we are *not* claiming.

## 2. Whole-frame substrate rendering

The host builds, at compile time, the coordinate geometry of the grid: for an
N×N frame it produces length-(N·N) buffers `x`, `y`, and `ones`. The substrate
program consumes these and returns one length-(N·N) vector that *is* the frame.
For example, the base field `1 − x² − y²` is computed elementwise over the whole
grid by the `hadamard` (elementwise/buffer) product in a single operation
(`demos/gui/frame_whole.su`). The host reshapes the returned buffer to N×N and
paints it. This is the same host-is-I/O split as a per-pixel renderer, but one
substrate operation replaces N² calls.

**Runtime parameters as broadcast buffers.** A movable, scalable variant supplies
additional length-(N·N) buffers — e.g. a glow centre `(cx, cy)` and an inverse
scale — each a scalar broadcast to every pixel. Because these are *arguments*, not
constants compiled into the program, the same compiled operation renders any θ; no
recompilation occurs when θ changes. This is the load-bearing fact for §5: the
optimizer perturbs θ thousands of times and pays the compile cost once.

**A note on dimension.** These coordinate fields use only elementwise arithmetic on
broadcast buffers — no codebook lookups — so the program compiles at a small
`runtime_dim` (8) rather than the embedding model's full width. The substrate work
is the tensor arithmetic itself, not a detour through unused semantic axes; the
pixels are not claimed to live in the full embedding subspace. The one place the
pretrained-embedding-derived codebook is used is the glyph font (§3), which
compiles at the dimension that representation needs.

## 3. Substrate text / glyph rendering

Text is rendered on the substrate. Each 5×5 glyph is produced by a bound-vector
font program (`demos/font/font_bound_antipodal.su`) that returns, per cell, a
cosine-to-lit value; the host thresholds it to a binary cell. A headline is the
horizontal concatenation of these substrate glyph fields into a banner. The banner
the renderer produces is exactly the per-glyph substrate fields concatenated —
verified cell-for-cell, so no host font table substitutes for the substrate
output. Placement of the banner into the frame (its band, centring, scale) is
host-side composition and is named as such.

## 4. The θ-parameterized hero

The demo's graphic is a "hero": a movable/scalable glow, a ring accent, and a
background level, composed in one substrate operation (`demos/gui/frame_hero.su`,
`hero`), plus a headline (§3). The parameter vector θ has continuous axes
`cx, cy, invs, bright, radius, accent, bg` and colour axes `cr, cg, cb`, together
with a per-headline mixture weight vector. Colour is produced as three whole-frame
substrate fields: the same composed hero tinted by a per-channel weight in one
operation each (`hero_channel`), stacked by the host into an RGB image (the
channel fields are substrate; only the three-way stack is host display assembly).
The headline is chosen by a host-side argmax over the mixture weights; the glyph
pixels are substrate (§3).

## 5. Host-side preference steering (SPSA)

We steer the rendered hero by human preference. A warmer press is reward +1, a
colder press −1 — one rating per shown frame (we do not smooth across presses; the
two-sided estimate already averages a ± pair). A host-side SPSA optimizer
(`demos/gui/hero_spsa.py`, `HeroSPSA`) adjusts θ. SPSA estimates a gradient from
two evaluations per step using a single random perturbation, which suits a setting
where each "evaluation" is a human rating of a rendered frame. Per batch it draws a
Rademacher perturbation `delta ∈ {−1,+1}^D`, forms `θ ± ck·delta`, collects the
two rewards, and updates

  θ ← clip( θ + ak · (r₊ − r₋)/(2·ck) · delta , −1, 1 ),

with the standard gains `ck = c0/(j+1)^0.101` and `ak = a0/(j+1+10)^0.602` (ported
verbatim from a validated dense-signal SPSA implementation). The optimizer works in
a normalized box θ ∈ [−1,1]^D and maps each continuous axis to the renderer's range
by an affine `center + half_range·norm`, so the search stays well-conditioned while
the renderer sees its own units.

This optimizer is host-side. It runs no substrate operations; it changes the
arguments that the substrate render consumes. The reward is a human button, not a
measured outcome from real usage. Both points are restated in §8.

## 6. Render-fidelity results

The one-operation render is checked against a per-pixel host oracle for every
render mode. The table below is the maximum absolute difference between the
substrate render and the host oracle, measured by
`experiments/gui_render_fidelity.py` at a 24×24 grid:

| Render mode | max \|substrate − host oracle\| |
|---|---|
| whole frame (`1 − x² − y²`) | 1.1 × 10⁻⁷ |
| moving glow | 2.4 × 10⁻⁷ |
| ring | 1.9 × 10⁻⁷ |
| diagonal ramp | 4.2 × 10⁻⁸ |
| region layout (glow ∣ ring) | 1.9 × 10⁻⁷ |
| RGB channels | 1.9 × 10⁻⁷ |
| θ hero | 4.0 × 10⁻⁷ |
| θ hero, RGB (tinted) | 3.6 × 10⁻⁷ |
| glyph banner (`"SU"`) | **0** (exact) |

The largest discrepancy across all modes is 4.0 × 10⁻⁷ — float32 rounding, not a
modelling gap; the substrate computes the intended field. The glyph banner is
bit-for-bit identical to the concatenated substrate glyph fields, so no host font
table substitutes for the substrate output. (These are the numerical maxima; the
test suite `demos/gui/test_gui_whole_frame.py` guards each mode at a 10⁻⁶
threshold.)

## 7. Steering results

**Optimizer convergence.** On a synthetic concave reward, the continuous θ moves
from the neutral start to within a small fraction of the reward maximizer over
multiple seeds (final/start squared-distance < 0.25, averaged over five seeds), and
the gradient-estimate sign is correct on a monotone axis (`demos/gui/test_hero_spsa.py`).

**Soak (the steering claim).** We run a scripted 100-press session over the live
controller with a consistent synthetic rater (`experiments/gui_steering_eval.py`).
Two results, both measured:

- *Frame health.* All 101 rendered frames are finite and non-blank — **0 NaN, 0
  blank** — with the glyph headline overlay both off and on (the full RGB + glyph
  demo frame). The per-frame substrate render survives a full session.
- *Directional consistency.* A rater that consistently prefers brighter frames
  drives the steered brightness from the neutral 1.000 to 1.800 — the top of the
  axis range (+0.800) — and a rater that consistently prefers darker frames drives
  it to 0.200, the bottom (−0.800). The steer direction flips with the preference.
  The Pearson correlation between the running-best brightness and the batch index
  is ±0.446; it is moderate rather than near-unity because the parameter saturates
  at the clamp boundary partway through the session and then plateaus — it reaches
  the rewarded extreme rather than ramping linearly to the end.

The steering signal here is a synthetic rater standing in for the human button; the
loop, render, and optimizer are exactly those a person drives in the window
(`demos/gui/steering_window.py`).

**Figures.** `experiments/gui_figures.py` renders the paper's figures from these
same substrate paths: the θ hero (mono and RGB), a substrate glyph banner, the
four-quadrant layout, and a before/after steering pair (the hero at the neutral
start vs after a 120-press brighter-preferring session). The before/after pair is
quantitative as well as visual — mean frame brightness rises from 71 to 146 (of
255) across the session, the morph the rater drove. The PNGs are build artifacts
(regenerated, not committed).

## 8. What we are not claiming

- **The composition is host-side.** Assembling glyphs into a banner, placing the
  banner in the frame, and stacking RGB channels are host operations over
  substrate-produced fields. We do not claim a single end-to-end substrate program.
- **The optimizer is host-side SPSA over substrate-rendered output.** It is not
  substrate-native training; no gradients flow through the substrate render.
- **The reward is a human button**, not behaviour from real traffic. The demo
  shows steerability by a present rater, not learning from usage.
- **Render fidelity is agreement with a host oracle**, i.e. the substrate computes
  the intended field; it is not a claim that the field is the "right" graphic in
  any aesthetic sense.

## 9. Related work

*To be written (task P10), with each cited claim verified against its source.*
Threads: holographic/VSA-style rendering and binding; computation in frozen
embedding spaces; SPSA and zeroth-order optimization; human-preference
optimization of generative output.

## 10. Reproducibility

The renderer, optimizer, and steering loop are in `demos/gui/` (`frame_*.su`,
`whole_frame.py`, `hero_spsa.py`, `hero_steering.py`, `steering_window.py`) and
`demos/font/`; the regression tests are `demos/gui/test_gui_whole_frame.py`,
`demos/gui/test_hero_spsa.py`, and `demos/gui/test_hero_steering.py`. The §6 and §7
tables come from:

```
python experiments/gui_render_fidelity.py --size 24      # §6 render-fidelity table
python experiments/gui_steering_eval.py --presses 100    # §7 steering soak
python experiments/gui_figures.py --size 96              # §7 figures (PNGs, uncommitted)
python demos/gui/steering_window.py                      # the live warmer/colder window
```

The full demo and steering suites are run with `pytest demos/gui/`.

## 11. Conclusion

A frozen-embedding substrate can render an interactive interface a frame at a time
and, with a host-side preference optimizer over its runtime parameters, can be
steered by a person in real time. The contribution is as much the bookkeeping as
the demo: a clear line between the substrate render and the host-side composition
and optimization, with measured fidelity on one side and an explicitly gated
steering result on the other.
