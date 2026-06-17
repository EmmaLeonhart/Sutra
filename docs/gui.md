# Drawing pixels

The most direct way to see Sutra run: a window whose **picture is computed on the
substrate**. A Sutra program returns a frame; the host only reshapes it and paints. The
image's content comes from the substrate — the host does assembly and display, nothing
more.

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python demos/gui/window.py            # render a glow and open a window
python demos/gui/window.py --render out.png --size 96   # render to a PNG, no window
```

## How it works

A pixel's brightness is an ordinary Sutra value. [`frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame.su)
defines a radial glow as a field over centred coordinates `x, y ∈ [-1, 1]`:

```
brightness(x, y) = 1 - x² - y²
```

Every arithmetic step runs on the substrate. The host walks the pixel grid, evaluates the
field, reads the finished brightness **at the display boundary**, then colour-maps and
paints. That boundary — the host reading a final value to show it — is the one external
edge; the computation itself stays on the substrate.

## One vector *is* the frame

Calling the field once per pixel works, but the fuller form computes the **whole frame in
a single substrate op** and returns it as one flat buffer — the returned vector *is* the
pixels. [`frame_whole.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_whole.su):

```
frame(x, y, ones) = ones - hadamard(x, x) - hadamard(y, y)
```

Here `x`, `y` are the whole coordinate grid laid out as buffers, and `hadamard` is the
elementwise (per-pixel) product, so `1 - x² - y²` is evaluated for every pixel at once.
The result is the frame buffer; the host reshapes it to the image and blits it. No
per-pixel loop, no decoder — the program produces the picture directly.

```bash
python demos/gui/whole_frame.py --size 96
```

## A live window

The whole-frame form runs in real time. [`live_frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/live_frame.su)
is one program owning a live window's whole behaviour: a timer tick advances the glow's
position **on the substrate**, a mouse click flips a gate **on the substrate**, and every
tick is a single substrate call whose returned vector is the frame on screen.

```bash
python demos/gui/live_demo.py             # open the live window; click to gate the glow
python demos/gui/live_demo.py --bench     # measure the per-tick cost, no window
```

The animation needs no modulus to loop: the glow's position is carried as a **complex
number rotated a fixed step each tick** — the rotation is inherently periodic, so the
centre sweeps back and forth forever, easing at the edges. Per tick the whole 64×64
frame costs well under a millisecond.

## Steering the picture in real time

Because the frame is a composition of tensor operations, the render is **differentiable**:
you can change the picture by *gradient descent*. The steering demo puts a person in that
loop. It paints a Sutra-rendered "hero" — a movable glow, a ring accent, colour, and a
[`SUTRA` headline rendered glyph-by-glyph on the substrate](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_hero.su) —
and a second, proposed variant beside it. You press **WARMER** (you like the variant) or
**COLDER** (keep the current).

```bash
python demos/gui/adam_window.py      # or double-click demos/gui/run_adam_gui.bat (Windows)
```

Each press trains a small preference model on your choice (the pairwise Bradley-Terry
model real preference-learning uses), and an **Adam optimizer backpropagates your
preference through the substrate render** to the picture's parameters — so the hero morphs
toward what you reward, live. It is real reinforcement-from-preference, not a scripted
animation: the gradient genuinely flows through the rendered frame.

We measured the loop end to end. A rater that consistently prefers brighter frames drives
the displayed brightness from the neutral start to the top of its range; a rater that
prefers darker frames drives it to the bottom; the direction flips with the preference,
with no broken frames across a session. The render is the substrate; the preference model
and the optimizer are ordinary host-side code, and we say so — the point is that the thing
the gradient passes *through* is a Sutra program.

The same loop steers more than brightness. The hero's parameters include **where** the glow
sits, **how wide** it is, and — in the colour version — the per-channel **tints**, all of
them axes the gradient reaches through the substrate render. We measured each direction with
a synthetic rater that scores frames on that one property:

- **Position** — preferring the bright mass toward a corner moves it there; top-left and
  bottom-right preferences drive the corner-bias measure to opposite extremes and the
  direction flips with the preference, robustly across random seeds.
- **Size** — preferring a wider glow raises the rendered frame's spatial spread.
- **Colour** — on the differentiable RGB render (each channel is the composed hero tinted
  on the substrate), preferring a redder frame raises its relative redness and flips with
  the preference.

Every case stays finite (no broken frames). The colour A/B window drives all of these at
once:

```bash
python demos/gui/adam_window_rgb.py   # or double-click demos/gui/run_adam_rgb_gui.bat (Windows)
```

(One honest detail surfaced while building this: a *normalised* position measure is
scale-invariant, so an optimiser can satisfy it by collapsing the frame to black — a
degenerate win. We score position by a plain bottom-right-minus-top-left mass instead, which
black cannot game.)

## Training a button to get clicks

The same gradient machinery powers a small product demo: a **clickable button**, rendered
entirely on the substrate, that is *trained* to optimise two things at once — **what the
site owner wants** and **what gets the biggest click-through rate**. The button is a
rounded-rectangle (squircle) field with a fill colour, page background, and a choice of
*copy* ("Buy now" / "Get started" / "Learn more"); its design is a parameter vector the
optimiser steers, and the render is differentiable, so Adam backpropagates through it.

Two reward signals are blended, `R = α·owner + (1−α)·CTR`:

- **Owner preference** — the same warmer/colder Bradley-Terry head, learning the owner's
  taste (say, a blue brand button) from their A/B choices.
- **CTR** — a *simulated audience* (a deterministic, differentiable click-probability model
  that rewards a button standing out from the page, a warm call-to-action colour, and
  punchier copy) for training and tests; **real clicks** in a live browser for the demo.

The `α` knob is the story: it trades the owner's taste against raw clicks. Measured (16–24-px
grid, across seeds): from a neutral grey start (CTR ≈ 0.50), **pure-CTR steering** drives the
button warm and high-contrast, raises the simulated CTR to **≈ 0.95**, and auto-picks the
punchiest copy ("Buy now"); **pure-owner steering** instead drives the button toward the
owner's blue taste; and intermediate `α` sits between — the owner-driven button is bluer, the
CTR-driven one clicks better. The button's render math is also authored in TypeScript and
lowered to Sutra by [`sutra-from-ts`](https://github.com/EmmaLeonhart/Sutra/tree/main/sdk/sutra-from-ts),
the path for the browser/JS layer. The render is the substrate; the reward head, the audience
model, and Adam are ordinary host-side code, and we say so.

The button isn't only a window — it's a substrate **service**. The same controller is exposed
over a tiny stdin/stdout protocol (frames out; owner preferences and visitor clicks in), so a
host process — a browser bridge, or an OS surface that "owns the window" — can spawn it, paint
the substrate-rendered button, and feed it real clicks. The picture, and the learning signal it
chases, stay on the substrate; the host only does the window and the events.

## Learning the picture, not just rendering it

Every render above is a *fixed* function — hand-written substrate arithmetic. But the substrate
is differentiable, so it can also be **trained**. We built a small **learned decoder**: a
coordinate function `f(x, y) → pixel` made of substrate `matmul` layers with a cubic
nonlinearity, fed Fourier features of the coordinates. The weights are trainable; an optimizer
descends a loss by backpropagating **through the substrate forward** (the same boundary as the
steering above — the render is the substrate, the optimizer is host-side).

What that buys, all measured on the substrate render:

- **It reconstructs an arbitrary image** the analytic renders can't make — two off-centre
  blobs — to ~22 dB PSNR (≈29 dB with more width), in colour as well as grayscale; quality
  rises with capacity, as you'd expect.
- **It generates, not just memorises.** Conditioned on a latent `z` (`f(x, y; z)`) and trained
  across a small *set* of images with a learned latent each, **interpolating `z` sweeps the
  output between them** — novel frames the model never saw, produced by moving a point in
  latent space.
- **You can steer what it generates.** Freeze the weights and put the *latent* in the same
  warmer/colder loop: a person's preferences move `z` up a learned reward through the substrate
  render, so the generated picture morphs toward what they reward.

This is the bridge from "the substrate draws a picture" to "the substrate *learns* one" — the
analytic glow is the fixed-weight base case; the decoder is the trained, generative,
steerable generalisation. The forward pass is substrate tensor ops; the optimizer, the reward
head, and the Fourier input-encoding are host-side, and we say so.

## The gallery

| Demo | Source | What you see |
|---|---|---|
| Glow | [`frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame.su) | A radial glow, one substrate value per pixel. |
| Live window | [`live_frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/live_frame.su) | A real event loop: timer ticks animate, clicks gate, every frame is one substrate call. |
| Steerable hero | [`frame_hero.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_hero.su) | Press warmer/colder; Adam backpropagates your preference **through the substrate render** and the picture morphs toward what you reward. |
| Whole-frame glow | [`frame_whole.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_whole.su) | The same glow, the entire frame computed in one substrate op. |
| Moving glow | [`frame_moving.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_moving.su) | A glow centred at a movable point; sweep it to animate. |
| Animated glow | [`moving_glow.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/moving_glow.su) | The glow's centre advances **on the substrate** each tick — the animation's state is a recurrent value, not a host variable. |
| Ring | [`frame_ring.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_ring.su) | A concentric ring, `1 - (x² + y² - R)²`. |
| Checkerboard | [`frame_checker.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_checker.su) | A crisp checkerboard from cell parities, `(1 + px·py) / 2`. |
| Diagonal gradient | [`frame_diag.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_diag.su) | A corner-to-corner ramp, `(1 + (x + y)/2) / 2`. |
| Four-region layout | [`frame_quad.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_quad.su) | Glow, ring, gradient and checker tiled into the four quadrants of one frame, composed in one substrate op. |
| Click toggle | [`click_frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/click_frame.su) | A click flips a state on the substrate; the glow appears and disappears with it. |
| Counter | [`count.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/count.su) | A click counter whose count lives on the substrate between clicks. |
| Toggle | [`toggle.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/toggle.su) | A 0/1 state flipped on the substrate. |

## State that lives on the substrate

The animated and interactive demos are recurrent: the count, the toggle, the glow's
position are **vectors carried across frames on the substrate**, advanced by the program's
own step, not shuttled in and out of a host variable between frames. The host reads the
current state only to draw it. Walk the counter ten times with no input and it returns
1, 2, …, 10 — the state persisted on the substrate the whole time.

Each demo ships with a test that runs it on the real substrate and checks the rendered
field against an independent reference, so the pictures are verified, not just plausible.
