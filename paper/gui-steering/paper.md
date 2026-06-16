# Painting and Steering on a Frozen-Embedding Substrate: a differentiable whole-frame renderer and gradient-based human-in-the-loop steering in Sutra

**Status:** working draft (GUI track). The demo is built and the method sections,
render-fidelity table (§6), no-recompile measurement (§2), and the gradient-steering
results (§7) are grounded in shipped code and measured runs. This paper cites only
measured numbers.

## Abstract

Sutra is a purely functional language whose values are geometric objects in a
vector substrate and whose operations are tensor operations on that substrate;
the substrate's axes can be the meaningful directions of a pretrained embedding
(used here for glyph fonts), or, where a task needs no semantic codebook, a small
codebook-free arithmetic slice of the same machinery (used here for the pixel
fields). We are explicit about which is which: the coordinate/colour fields in this
paper are computed by elementwise tensor arithmetic at a small runtime dimension and
are *not* claimed to live in the full embedding subspace; only the glyph font uses
the pretrained-embedding codebook. We use this substrate to render a graphical
interface: the whole image is computed by a single substrate operation that returns
the frame as one buffer vector, with the host acting only as I/O (it builds
coordinate buffers and paints the returned pixels). On top of this we build a
parameterized "hero" graphic whose layout, scale, colour, and headline are driven by
a parameter vector θ supplied as per-call broadcast buffers, so changing θ changes the
picture with no recompilation. Because the render compiles to differentiable tensor
operations, **gradients flow through it**: we steer the rendered output by human
preference with a *gradient-based* loop — each warmer/colder choice trains a small
differentiable reward model (online RLHF, pairwise Bradley-Terry), and an Adam
optimizer ascends that reward by backpropagating **through the substrate render** to
θ. We report the render fidelity (the one-operation frame matches a per-pixel host
oracle to within ~4×10⁻⁷, holding across a 28× range of grid sizes), the no-recompile
cost (compile once, then thousands of θ updates at zero recompiles), and the steering
result (a brighter-preferring rater drives the substrate-rendered brightness to the
top of its range, a darker-preferring rater to the bottom; the direction flips with
the preference, with no non-finite frames); the same gradient loop also steers the hero's
position, size, and — on the differentiable colour render — its colour, each measured to
move in the rater's preferred direction and to flip with it. Throughout we keep an explicit
account of which work runs on the substrate (the render — and the gradients now pass through
it) and which is host-side (the composition, the reward model, and Adam); we do not claim
a single end-to-end substrate program.

## 1. Introduction

Sutra represents data as vectors in a frozen embedding space and computation as
geometry on that space. The motivating observation — that pretrained embedding
spaces carry reusable linear/relational structure — is the authors' own prior
open-source analysis (*latent-space-cartography*, a code repository, not a
peer-reviewed paper; we cite it as the project's empirical starting point, not as
an external authority). This paper does not depend on that analysis for any number
reported here; every measurement below is from the demo itself. A natural question
is whether something as concrete as a pixel grid can be produced *by* the substrate
rather than around it. This paper answers yes for a useful case — a rendered,
interactive interface — and is explicit about the boundary between the substrate
work and the host work.

**Why render on the substrate at all (scope of the claim).** We are *not* claiming
this is faster or better than a GPU shader or a CPU rasterizer; for raw pixel
throughput it is neither. The point is *uniformity*: in a system where application
logic already runs as tensor operations on this substrate (the direction of the
Sutra/Yantra work), rendering the interface on the *same* fabric removes a host
boundary rather than adding one. The contribution is the demonstration that the
interface — frame, parameters, text, and a live preference loop — can live on that
fabric with a measured account of fidelity and of exactly which parts remain
host-side, not a performance result against conventional renderers.

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
4. **Gradient steering through the substrate render.** Because the render is
   differentiable, a warmer/colder preference loop trains a small reward model and an
   Adam optimizer backpropagates **through the substrate render** to θ, morphing the
   substrate-rendered hero (§5). Gradients passing through the render — not a
   zeroth-order black box — is the load-bearing fact; we measure that they do (§7).

The render fidelity (§6) and the steering soak (§7) are both measured on the built
demo; §8 states what we are *not* claiming.

## 2. Whole-frame substrate rendering

**The renderer is a Sutra program.** Sutra is a purely functional language whose only
value type in this demo is `vector` (a tensor on the substrate) and whose operations are
tensor operations; a program is a set of typed functions. The hero renderer is the
following Sutra source (`demos/gui/frame_hero.su`), reproduced verbatim:

```
function vector hero(vector x, vector y, vector ones,
                     vector cx, vector cy, vector invs,
                     vector bright, vector radius, vector accent, vector bg) {
    vector dx = x - cx;
    vector dy = y - cy;
    vector r2 = hadamard(dx, dx) + hadamard(dy, dy);
    vector glow = ones - hadamard(invs, r2);
    vector rr = hadamard(x, x) + hadamard(y, y) - radius;
    vector ring = ones - hadamard(rr, rr);
    return bg + hadamard(bright, glow) + hadamard(accent, ring);
}
```

The surface is small and total: `function <type> name(params) { … }` declares a function;
`vector v = expr;` binds a local; `hadamard(a, b)` is the elementwise (Hadamard) product;
infix `+`/`-` are elementwise add/subtract; there is no control flow, no mutation, and no
host escape in this program. Each construct compiles to one PyTorch tensor operation
(`a*b`, `a+b`, `a-b`) over length-(N·N) buffers, so the whole function is one fused
sequence of tensor ops with no Python-level loop over pixels. Because every operation is a
differentiable tensor op, the compiled function is differentiable in its `vector`
arguments end-to-end — the property §5 and §7 use. (The full language has more — `map`/
`dict` codebooks, `bind`/`unbind`/`bundle`, `loop`, defuzzification — but the renderer uses
only this fragment; the substrate font in §3 is where the pretrained-embedding codebook
enters.)

The host builds, at compile time, the coordinate geometry of the grid: for an
N×N frame it produces length-(N·N) buffers `x`, `y`, and `ones`. The substrate
program consumes these and returns one length-(N·N) vector that *is* the frame.
For example, the base field `1 − x² − y²` is computed elementwise over the whole
grid by the `hadamard` (elementwise/buffer) product in a single operation
(`demos/gui/frame_whole.su`). The host reshapes the returned buffer to N×N and
paints it. This is the same host-is-I/O split as a per-pixel renderer, but one
substrate operation replaces N² calls. The per-pixel arithmetic is deliberately
elementary — the claim is not that `1 − x² − y²` is hard, but that the *entire
frame* is produced by one parameterized operation that runs on the substrate, which
is what makes the no-recompile steering in §5 possible.

**Runtime parameters as broadcast buffers.** A movable, scalable variant supplies
additional length-(N·N) buffers — e.g. a glow centre `(cx, cy)` and an inverse
scale — each a scalar broadcast to every pixel. Because these are *arguments*, not
constants compiled into the program, the same compiled operation renders any θ; no
recompilation occurs when θ changes. This is the load-bearing fact for §5: the
optimizer perturbs θ thousands of times and pays the compile cost once.

We measured this directly (`experiments/gui_norecompile_cost.py`, 64×64): the hero
program compiles once in ~3.6 s, after which 200 renders at *distinct* θ run at a
mean **1.3 ms/frame** with **0 recompiles** (the compiled module is identical across
all 200 calls). This is the concrete content of the "uniformity" claim of §1 — not a
throughput result against a GPU shader, but the fact that morphing the picture during
steering is a per-call argument change, not a rebuild. The compile cost is host-side
and one-time; it amortizes to nothing over a steering session, and the per-frame cost
is the substrate render itself.

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
background level, composed in one substrate operation (`frame_hero.su`,
`hero`), plus a headline (§3). The parameter vector θ has continuous axes
`cx, cy, invs, bright, radius, accent, bg` and colour axes `cr, cg, cb`, together
with a per-headline mixture weight vector. Colour is produced as three whole-frame
substrate fields: the same composed hero tinted by a per-channel weight in one
operation each (`hero_channel`), stacked by the host into an RGB image (the
channel fields are substrate; only the three-way stack is host display assembly).
This colour render is **differentiable** as well (`render_hero_rgb_torch`): the tints
`cr,cg,cb` are differentiable θ axes broadcast grad-preservingly, so the colour-steering
result in §7 backpropagates through the same `hero_channel` substrate op. The
headline is chosen by a host-side argmax over the mixture weights; the glyph
pixels are substrate (§3).

## 5. Gradient steering through the differentiable render (Adam + online RLHF)

The render compiles to differentiable tensor operations, so the rendered frame is a
tensor whose autograd graph reaches θ: a scalar loss on the frame backpropagates
**through the substrate render** to the parameters. This is what lets us steer with a
*gradient-based* loop rather than a zeroth-order one, and it is the central object of
§7. Concretely, with θ supplied as differentiable per-pixel broadcast buffers
(`val · ones`, not a detached constant), `∂loss/∂θ` is well defined for any scalar
function of the rendered frame (`whole_frame.render_hero_torch`).

We turn human warmer/colder preferences into that scalar with a small **online
reward model** trained in the loop (`demos/gui/hero_adam.py`). We use the **pairwise**
(Bradley-Terry) formulation that reward models are normally trained with — it is
contrastive by construction and therefore stable in any preference direction, where a
single-frame thumbs-up/down proved unstable (we measured it inverting the steer
direction; see §7). Each round:

1. **Propose.** Render the current θ and a perturbed variant θ′ — two frames.
2. **Prefer.** The person prefers one (warmer = the variant, colder = the current).
   One step trains a differentiable reward head R (a 4×4 average-pool of the frame
   then a linear layer) on the comparison: `loss = −log σ(R(preferred) − R(rejected))`.
3. **Policy.** A few **Adam** steps ascend `R(render(θ))` — backprop runs through the
   reward head *and* the compiled Sutra render — then θ is clamped into the render's
   healthy box.

The render is the substrate; the reward model and both optimizers are host-side and
named as such (§8). The earlier zeroth-order SPSA optimizer is retained as a baseline
(`demos/gui/hero_spsa.py`), but the headline loop is gradient-based: Adam updating θ by
gradients that pass *through* the substrate render is precisely the property a
frozen-embedding "everything is a tensor op" substrate is supposed to provide.

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

**Fidelity holds as the frame scales.** The single-operation render is not a
small-grid artifact: re-running the same check at larger grids, the worst-case
error across all modes stays in float32-rounding territory and grows only as the
slow accumulation expected from more pixels, while the glyph banner remains exact
at every size.

| Grid | overall max \|substrate − host oracle\| | glyph banner |
|---|---|---|
| 24 × 24 | 4.0 × 10⁻⁷ | 0 (exact) |
| 64 × 64 | 5.2 × 10⁻⁷ | 0 (exact) |
| 128 × 128 | 7.0 × 10⁻⁷ | 0 (exact) |

Across a 28× increase in pixel count (576 → 16,384) the error rises by under 2×
and never leaves the rounding floor; the whole-frame substrate render is the same
operation at any resolution (`python experiments/gui_render_fidelity.py --size N`).

## 7. Steering results

**Gradients flow through the substrate render (the load-bearing fact).** With θ
entries as differentiable parameters and the render not detached, the rendered frame
is a tensor with an autograd graph (`grad_fn` set), and a scalar loss on it produces
non-zero `∂loss/∂θ` *through* the compiled Sutra `hero` op. Measured at the neutral θ
for a "make it brighter" loss (`−mean(frame)`): the background axis gives exactly
`−1.0` (it shifts every pixel by 1), brightness a strictly negative gradient, and the
spread/accent axes non-trivial gradients; cx/cy/radius are 0 by the symmetry of a
centred glow. Ten Adam steps on that loss reduce it monotonically
(`demos/gui/test_hero_differentiable.py`). This is what distinguishes the loop from a
black-box optimizer: Adam steers θ by gradients the substrate render actually carries.

**Steering by preference (directional consistency).** We drive the online-RLHF loop of
§5 with a synthetic fixed-preference rater (the live window uses real button presses;
tests use a scripted rater so the result is deterministic). Over 50 rounds at a 16×16
grid, across seeds 0–2 (`demos/gui/test_hero_adam.py`):

- A rater that **prefers brighter** frames drives the displayed mean brightness from
  the neutral **0.465 to 1.000** (the top of the displayed range).
- A rater that **prefers darker** frames drives it from **0.465 to 0.000** (the bottom).
- The steer direction **flips with the preference**, and **every** proposed and
  rendered frame is finite (0 NaN/inf) across the session.

The earlier single-frame thumbs-up/down reward was measured to be unstable — a
zero-initialised head fed single-class labels learned the wrong sign and drove a
brighter-preferring rater's image *dark* — which is why §5 uses the pairwise
Bradley-Terry formulation; the numbers above are with that formulation.

**Steering more than brightness: position, size, and colour.** Brightness is a single
scalar; the same gradient loop steers the hero's spatial and colour axes, which the
gradient reaches through the same substrate render. We measured each with a synthetic rater
scoring frames on that one property (`demos/gui/test_hero_steering_axes.py`,
`test_hero_adam_rgb.py`, 16×16):

- **Position.** Scoring frames by a bottom-right-minus-top-left mass, a rater preferring the
  bright mass top-left drives that measure to ≈ **−0.99** and one preferring bottom-right to
  ≈ **+0.99** from a centred ≈ 0 start; the direction flips and the result is robust across
  seeds 0–4. (We deliberately use this *linear* mass measure rather than a normalised
  centroid: a normalised centroid is scale-invariant, so the optimiser can satisfy it by
  collapsing the frame to black — a degenerate win we observed and removed.)
- **Size.** A rater preferring a wider glow raises the rendered frame's intensity-weighted
  spatial spread from **0.607 to 0.869**; a tighter preference drives it lower; the
  direction flips.
- **Colour.** On the **differentiable** RGB render (`render_hero_rgb_torch`, where each
  channel is the composed hero tinted on the substrate and the colour tints `cr,cg,cb` are
  differentiable θ axes), a rater preferring a redder frame raises its relative redness from
  **+0.106 to ≈ +0.50–0.62** while a less-red preference drives it to **−1.0**; the
  direction flips, with 0 non-finite frames.

These reuse the §5 loop unchanged — only the rater's scored property and (for colour) the
differentiable render path differ — so the steering claim is not specific to brightness: the
preference gradient moves whichever rendered property the reward head learns to read.

**Figures.** `experiments/gui_figures.py` renders figures from these same substrate
paths: the θ hero (mono and RGB), a substrate glyph banner, the four-quadrant layout,
and a before/after steering pair (neutral start vs after a steered session). The PNGs
are build artifacts (regenerated locally; git-ignored).

## 8. What we are not claiming

- **The composition is host-side.** Assembling glyphs into a banner, placing the
  banner in the frame, and stacking RGB channels are host operations over
  substrate-produced fields. We do not claim a single end-to-end substrate program.
- **Gradients pass *through* the substrate render, but the reward model and the
  optimizer are host-side.** Backprop reaches θ through the compiled render (that is
  the §7 result), and that is what makes the steering gradient-based rather than
  zeroth-order. But the differentiable reward head and Adam themselves run host-side;
  we do not claim the *learning* runs on the substrate, only that the render the
  gradient passes through does.
- **The reward is a preference signal**, not behaviour from real traffic — a live
  human's button in the window, a scripted fixed-preference rater in the measured
  tests. The demo shows steerability by a present rater, not learning from usage.
- **Render fidelity is agreement with a host oracle**, i.e. the substrate computes
  the intended field; it is not a claim that the field is the "right" graphic in
  any aesthetic sense.

## 9. Related work

**Vector-symbolic architectures and hyperdimensional computing.** The
bind/bundle/unbind algebra Sutra uses for glyph fonts and composite frames comes
from the VSA / hyperdimensional-computing (HD) tradition — Plate's Holographic
Reduced Representations (binding by circular convolution) and Kanerva's
hyperdimensional computing. As the Torchhd library (Heddes et al., JMLR 2023)
states the framework, HD/VSA computes "with distributed representations by
exploiting properties of *random* high-dimensional vector spaces." Sutra inverts
that premise: its axes are the *meaningful* directions of a frozen pretrained
embedding, not random roles, and a rendered frame is a deterministic geometric
function of those axes rather than a similarity search over random codes. Practical
HD/VSA tooling — the Torchhd library and the HDCC compiler (Pale et al. 2023) — and
the closest neuro-symbolic *language*, Scallop (Li et al. 2023, Datalog-like with
PyTorch integration), target classification and reasoning workloads; rendering an
interactive pixel interface on the substrate is, to our knowledge, not a use case
they pursue.

**Computation in frozen embedding spaces.** That pretrained embedding spaces carry
linear/geometric structure usable for computation is long-observed (the word-analogy
displacements of word2vec-style models). Sutra's own empirical foundation is the
relational-displacement analysis of frozen embedding spaces in
*latent-space-cartography*, which showed displacement vectors exist in those spaces.
This paper extends "compute in the frozen space" from analogy and retrieval to
*rendering*: producing a full pixel buffer as one operation on the substrate.

**Differentiable rendering.** A rendering function whose output is differentiable in
its parameters lets gradient methods optimize what is drawn — the principle behind
differentiable rasterizers and renderers in vision/graphics. Our renderer is
differentiable for the same structural reason every Sutra operation is a tensor op: the
frame is a composition of elementwise tensor arithmetic, so `∂frame/∂θ` exists and
backprop reaches θ through it (§7). The novelty here is not a new differentiable
rasterizer but that the *substrate* render — a program in a frozen-embedding tensor
language — is itself the differentiable function the optimizer descends.

**Preference optimization / RLHF, and pairwise reward models.** Steering output by a
warmer/colder signal is a small instance of learning from human preference comparisons,
the pattern behind reinforcement learning from human feedback (Christiano et al. 2017;
Ouyang et al. 2022). We use the **Bradley-Terry** pairwise-comparison model those
systems train their reward models with (`−log σ(R(better) − R(worse))`); the difference
from full RLHF is scale and locus — a single live rater, an online reward head over a
handful of render parameters rather than a frozen reward model over network weights —
but the shape (a preference signal training a differentiable reward, a gradient
optimizer ascending it) is the same. The earlier zeroth-order baseline is Spall's
Simultaneous Perturbation Stochastic Approximation (SPSA), which estimates a gradient
from two evaluations with one random perturbation at a cost independent of dimension;
we retain it (`hero_spsa.py`) but the headline loop is gradient-based because, unlike a
black-box reward, our learned reward composed with the differentiable render *does* have
a usable gradient w.r.t. θ.

### References

- T. A. Plate. *Holographic Reduced Representations.* IEEE Transactions on Neural
  Networks, 1995.
- P. Kanerva. *Hyperdimensional Computing: An Introduction to Computing in
  Distributed Representation with High-Dimensional Random Vectors.* Cognitive
  Computation, 2009.
- M. Heddes et al. *Torchhd: An Open Source Python Library to Support Research on
  Hyperdimensional Computing and Vector Symbolic Architectures.* JMLR 24, 2023.
- J. M. Pale et al. *HDCC: A Hyperdimensional Computing Compiler for Classification
  on Embedded Systems and High-Performance Computing.* 2023.
- Z. Li et al. *Scallop: A Language for Neurosymbolic Programming.* PLDI, 2023.
- T. Mikolov et al. *Efficient Estimation of Word Representations in Vector Space.*
  2013. (Word-analogy displacements in embedding spaces.)
- E. Leonhart. *latent-space-cartography: relational-displacement analysis of frozen
  embedding spaces.* Open-source code repository (not peer-reviewed).
  https://github.com/EmmaLeonhart/latent-space-cartography
- J. C. Spall. *Multivariate Stochastic Approximation Using a Simultaneous
  Perturbation Gradient Approximation.* IEEE Transactions on Automatic Control, 1992.
- P. Christiano et al. *Deep Reinforcement Learning from Human Preferences.*
  NeurIPS, 2017.
- L. Ouyang et al. *Training Language Models to Follow Instructions with Human
  Feedback.* NeurIPS, 2022.
- R. A. Bradley and M. E. Terry. *Rank Analysis of Incomplete Block Designs: I. The
  Method of Paired Comparisons.* Biometrika, 1952. (The pairwise preference model.)
- D. P. Kingma and J. Ba. *Adam: A Method for Stochastic Optimization.* ICLR, 2015.

## 10. Reproducibility

The differentiable renderer and the Adam steering loop are in `demos/gui/`
(`frame_*.su`, `whole_frame.py` — `render_hero_torch` / `render_hero_rgb_torch` are the
differentiable mono / colour paths — `hero_adam.py` with its `color=True` multi-axis mode,
`adam_window.py`, `adam_window_rgb.py`, `run_adam_gui.bat`, `run_adam_rgb_gui.bat`), with
the SPSA baseline in `hero_spsa.py`/`steering_window.py` and the substrate font in
`demos/font/`. The regression tests are `demos/gui/test_hero_differentiable.py` and
`test_hero_rgb_differentiable.py` (gradients through the mono / colour render),
`test_hero_adam.py`, `test_hero_adam_rgb.py`, and `test_hero_steering_axes.py` (the
brightness / colour / position / size steering directions), and `test_gui_whole_frame.py`
(render fidelity). The measured numbers come from:

```
python experiments/gui_render_fidelity.py --size 24      # §6 render-fidelity table
python experiments/gui_norecompile_cost.py --frames 200  # §2 no-recompile cost (0 recompiles)
pytest demos/gui/test_hero_differentiable.py             # §7 gradients through the render
pytest demos/gui/test_hero_rgb_differentiable.py         # §7 gradients through the RGB render
pytest demos/gui/test_hero_adam.py                       # §7 steering directions (bright/dark)
pytest demos/gui/test_hero_adam_rgb.py                   # §7 colour steering (redder/less-red)
pytest demos/gui/test_hero_steering_axes.py              # §7 position + size steering
python demos/gui/adam_window.py                          # the live Adam warmer/colder window
python demos/gui/adam_window_rgb.py                      # the live colour A/B steering window
```

The full demo and steering suites are run with `pytest demos/gui/`.

## 11. Conclusion

A frozen-embedding substrate can render an interactive interface a frame at a time —
and because the render is a composition of tensor operations, it is *differentiable*,
so a person can steer it by gradient descent: warmer/colder preferences train a small
reward model and Adam backpropagates through the substrate render to morph the picture.
The contribution is as much the bookkeeping as the demo — a clear line between the
substrate render (which the gradients now pass through) and the host-side composition,
reward model, and optimizer — backed by measured render fidelity, a measured
no-recompile cost, and a measured, direction-flipping steering result.
