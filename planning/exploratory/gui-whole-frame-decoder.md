# GUI: whole-frame render in one substrate call (frame-buffer vector)

**Status:** exploratory design for GUI queue item #3. Corrected to Emma's model
2026-06-11 (the earlier polynomial-basis `B @ c` "decoder" framing was overcomplicated
and is dropped; there is NO learned decoder and NO deconvolution).

## The model (Emma 2026-06-11)

The substrate returns **one vector that IS the frame buffer**. Its entries are the
pixel channel values in raster order:

```
[ px0_R, px0_G, px0_B,  px1_R, px1_G, px1_B,  …,  px(N²−1)_R, _G, _B ]
```

"Rendering" is just **reshaping that flat vector to `N×N×3` and blitting it** — host
display assembly, the same role `window.py` already plays. There is no decoder matrix,
no basis reconstruction, no learning: the returned vector already holds the pixels.

This replaces today's `frame.su` path, which calls `pixel(x, y)` **once per pixel**
(`N²` separate substrate invocations). The whole point is **one** substrate result
carrying the whole frame.

## The efficient computation (the one piece to get right)

To produce that buffer in one shot rather than `N²` per-pixel calls, the substrate
evaluates the field over the **whole coordinate grid at once** — a single vectorized
tensor op. For the radial glow:

```
buffer = 1 − X² − Y²      # X, Y are the N×N coordinate grids; one elementwise op → N² values
```

(RGB = map the field to three channels, or three fields, interleaved R,G,B per pixel.)

`X`, `Y` (the grid geometry) are compile-time constants — the orchestrator boundary,
like the codebook. The field evaluation runs on the substrate. The host reads the
finished buffer at the display boundary, reshapes, and paints.

**If Sutra can't yet map a field over a grid in a single op**, that vectorized
"render-the-grid → buffer" is the one small **primitive to expose** (per CLAUDE.md:
the gap is usually a missing primitive, not a wrong idea) — NOT a decoder. The fallback
(assemble the buffer from per-pixel results) is correct but is the inefficient shape
Emma flagged; expose the vectorized op instead.

## The oracle (verify, not "it ran")

The buffer reshaped must equal today's per-pixel field, measured:

```
max_ij | buffer.reshape(N,N)[i,j]  −  window.render_field()[i,j] |  <  1e-6
```

i.e. the one-shot frame buffer reproduces `render_field()` exactly — a
`test_gui_whole_frame.py` guard, not a visual glance.

## What this does NOT need (explicitly dropped)

- **No learned decoder** (Emma: overkill — we just have the pixels).
- **No `B @ c` basis matrix / "reverse-CNN" reconstruction** (the indirection that made
  the earlier description inefficient).
- **No deconvolution** unless a vectorized grid-render genuinely needs one internally;
  the render is conceptually just "compute the field over the grid → reshape".

## Open follow-ons (not blocking the first cut)

1. **Colour.** Glow is single-channel today; RGB is interleaving three channel values
   per pixel (trivial once the grayscale buffer lands).
2. **Dynamic frames / animation.** A substrate-computed, time-varying buffer (the field
   parameters carried/updated by a `recur` loop) — overlaps GUI item #4.
3. **Bulk display read.** Read the whole buffer once at the boundary (not N² component
   reads) — still terminal I/O, done once.

## Build order (when item #3 is worked)

1. Decide the buffer mechanism: a single vectorized substrate op over the grid →
   `frame_whole.su` (or expose the grid-render primitive if `.su` can't express it yet).
2. Host driver: run the field op on the substrate, read the buffer at the display
   boundary, reshape to `N×N`(×3), paint (extend `window.py` or a sibling).
3. `test_gui_whole_frame.py` — assert buffer.reshape == `render_field()` to 1e-6.
4. Then colour + the dynamic/animated buffer (ties to item #4).
