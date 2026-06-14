# Painting and Steering on a Frozen-Embedding Substrate: a whole-frame renderer and a human-steerable interface in Sutra

**Status:** working draft (a1 / GUI track, `gui-training` branch). Method sections
and render-fidelity results are grounded in shipped code; the live-steering soak
results (§7) are gated on the demo's 1c/1d measurements and are marked as such.
This paper cites only measured numbers; sections awaiting measurement say so
explicitly rather than carrying a placeholder figure.

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
render fidelity (the one-operation frame matches a per-pixel host oracle within the
regression threshold the test suite enforces) and the optimizer's convergence on a
synthetic reward; the live human-in-the-loop soak is reported separately once
measured. Throughout we keep an explicit account of which work runs on the
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

We separate what is measured now (§6) from what awaits the live demo (§7), and we
state what we are *not* claiming (§8).

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
colder press −1 (smoothed over recent presses). A host-side SPSA optimizer
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
render mode (whole frame, moving glow, ring, RGB channels, region layout, four-way
quadrant layout, the θ hero, the tinted RGB hero, and the glyph banner). Each
mode's substrate output matches the oracle within the regression threshold the
suite enforces (`demos/gui/test_gui_whole_frame.py`), and the glyph banner matches
the concatenated substrate glyph fields exactly. The full per-mode max-error table
is emitted by `experiments/gui_render_fidelity.py` (task P6); this section will
quote the exact measured maxima from that script rather than the threshold bound.

## 7. Steering results — GATED on the live demo (1c/1d)

*Awaiting measurement.* The optimizer's convergence on a synthetic concave reward
is already measured (the continuous θ moves from neutral to within a small fraction
of the reward maximizer over multiple seeds; the gradient-estimate sign is correct
on a monotone axis — `demos/gui/test_hero_spsa.py`). The human-in-the-loop result —
a scripted 100-press soak reporting NaN/blank-frame count (target zero) and a
directional-consistency metric — is produced by demo steps 1c (window wiring) and
1d (soak), and will be reported here from `experiments/gui_steering_eval.py`. No
soak figure is stated until that script has run.

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

The renderer and optimizer are in `demos/gui/` (`frame_*.su`, `whole_frame.py`,
`hero_spsa.py`) and `demos/font/`; the regression tests are
`demos/gui/test_gui_whole_frame.py` and `demos/gui/test_hero_spsa.py`. The
fidelity and steering tables (§6, §7) come from `experiments/gui_render_fidelity.py`
and `experiments/gui_steering_eval.py`. Exact commands will be listed here (task
P11).

## 11. Conclusion

A frozen-embedding substrate can render an interactive interface a frame at a time
and, with a host-side preference optimizer over its runtime parameters, can be
steered by a person in real time. The contribution is as much the bookkeeping as
the demo: a clear line between the substrate render and the host-side composition
and optimization, with measured fidelity on one side and an explicitly gated
steering result on the other.
