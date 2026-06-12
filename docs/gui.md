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

## The gallery

| Demo | Source | What you see |
|---|---|---|
| Glow | [`frame.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame.su) | A radial glow, one substrate value per pixel. |
| Whole-frame glow | [`frame_whole.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_whole.su) | The same glow, the entire frame computed in one substrate op. |
| Moving glow | [`frame_moving.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_moving.su) | A glow centred at a movable point; sweep it to animate. |
| Animated glow | [`moving_glow.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/moving_glow.su) | The glow's centre advances **on the substrate** each tick — the animation's state is a recurrent value, not a host variable. |
| Ring | [`frame_ring.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/demos/gui/frame_ring.su) | A concentric ring, `1 - (x² + y² - R)²`. |
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
