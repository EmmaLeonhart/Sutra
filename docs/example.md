# Sample: a self-optimizing landing-page button

A worked example of one thing Sutra is good at: **optimizing a piece of a web page for
clicks, with the page element itself computed on the substrate.** The element is a
call-to-action button — the single highest-leverage object on most landing pages — and it
is *trained*, online, to raise its own click-through rate while still respecting what the
site owner wants it to look like.

The whole render runs on the substrate. The optimizer, the reward signal, and the event
plumbing are ordinary host-side code, and are named as such below.

## What the button is

The button is a rounded-rectangle (squircle) field with a fill colour, a page background,
and a choice of *copy* ("Buy now" / "Get started" / "Learn more"). Its visual design is a
parameter vector `θ` — centre, size, fill colour, page colour — and the render
`θ → frame` is a differentiable substrate function, so a gradient can be pushed back
through it. The copy is a discrete choice picked separately.

Source: [`button_adam.py`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/button_adam.py)
(the controller), with the audience model in
[`button_audience.py`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/button_audience.py).

## Two rewards, one knob

The button optimizes a blend of two rewards:

```
R(θ, copy) = α · owner_pref(frame) + (1 − α) · CTR(frame, copy)
```

- **Owner preference** — a small differentiable reward head trained online from the owner's
  pairwise *warmer / colder* choices (Bradley–Terry), the same preference-learning loop the
  steerable-glow demo uses. This is "what the site owner wants" — say, a button in the brand's
  blue.
- **CTR** — a click-through-rate signal. For training and the deterministic tests it is a
  *simulated audience*: a differentiable click-probability model that rewards a button
  standing out from the page, a warm call-to-action colour, and punchier copy. In a live
  browser it is replaced by **real clicks** logged from visitors; the loop is the same shape.

`α ∈ [0, 1]` is the tradeoff: `α = 1` is pure owner taste, `α = 0` is pure clicks. Adam
ascends `R` through the substrate render for the continuous `θ`; the copy is chosen by
argmax of `R` over the preset set each round. Because copy is discrete and not in the
rendered frame, it is steered by a separate per-copy click-rate bandit (UCB) — see
[`test_button_copy_bandit.py`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/test_button_copy_bandit.py).

## What it does, measured

On a 16–24-px render grid, across seeds, from a neutral grey start (simulated CTR ≈ 0.50):

- **Pure-CTR steering** (`α = 0`) drives the button warm and high-contrast, raises the
  simulated CTR to **≈ 0.95**, and auto-picks the punchiest copy ("Buy now").
- **Pure-owner steering** (`α = 1`) instead drives the button toward the owner's blue taste.
- **Intermediate `α`** sits between the two — the owner-driven button is bluer, the
  CTR-driven one clicks better.

The behaviour is exercised end-to-end by the demo's test suite (deterministic, seeded):

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python -m pytest demos/gui/test_button_adam.py \
                 demos/gui/test_button_ctr_learned.py \
                 demos/gui/test_button_copy_bandit.py
```

## It runs as a substrate service

The button isn't only a window. The same controller is exposed over a small stdin/stdout
protocol — frames out; owner preferences and visitor clicks in — so a host process (a browser
bridge, or an OS surface that owns the window) can spawn it, paint the substrate-rendered
button, and feed it real clicks:

```bash
python demos/gui/button_substrate_server.py
```

Source: [`button_substrate_server.py`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/button_substrate_server.py).
The picture, and the learning signal it chases, stay on the substrate; the host only does the
window and the events. The button's render math is also authored in TypeScript and lowered to
Sutra by [`sutra-from-ts`](https://github.com/EmmaLeonhart/Sutra/tree/main/sdk/sutra-from-ts),
the path for the browser/JS layer.

## Where the substrate boundary is

The render — every pixel of the button and the page — is substrate tensor ops. The optimizer
(Adam), the owner-preference reward head, the audience / CTR model, and the copy bandit are
host-side, and are named that way in the source. The one external edge is the display and the
click event: the host reads the finished frame to paint it and reads a click to feed it back.
That is the same boundary as every other [GUI demo](gui.md) — the computation itself stays on
the substrate.

For the broader picture of substrate-rendered, trainable interfaces — the steerable glow, the
learned image decoder — see the [GUI page](gui.md).
