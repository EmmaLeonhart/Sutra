# GUI: whole-frame render in one substrate call (reverse-CNN-style decoder)

**Status:** exploratory design for GUI queue item #3. Not yet built. (The Yantra-era
sketch `planning/24-first-gui.md` was never migrated to this repo — this is a fresh
statement of the idea, grounded in what `demos/gui/` actually does today.)

## The problem

`demos/gui/window.py` renders the radial glow by calling `frame.su`'s `pixel(x, y)`
**once per pixel** — `size²` separate substrate invocations to fill an `N×N` field.
Emma's "fuller form" (noted in `frame.su`'s own header): the substrate should return
**one vector** that encodes the whole frame, and a **reverse-CNN-style decoder**
"reorganises" that vector into the pixel grid — one substrate call, not `N²`.

## The mechanism (smallest honest version: the analytic glow)

The current field is a fixed quadratic: `brightness(x, y) = 1 − x² − y²`. Any such
field is a linear combination of a small polynomial basis evaluated at each pixel:

```
brightness(x,y) = c · b(x,y),   b(x,y) = [1, x, y, x², y², xy],   c = [1,0,0,−1,−1,0]
```

So the whole frame is a single matrix–vector product:

```
frame_flat  =  B @ c
  B : (N², K)   fixed decoder matrix — row (i·N+j) is b(x_i, y_j), the basis
                evaluated at pixel (i,j). Built once at compile time (host: it is
                a constant of the grid, not a runtime value).
  c : (K,)      the latent — the field's coefficients, a single substrate vector.
  frame_flat : (N²,)   the whole frame, one substrate vector.
```

This is the "reverse-CNN decoder" in its linear form: a fixed expansion matrix maps
a tiny latent to the full output grid (exactly what a transposed-conv / CNN decoder
does, minus the learned nonlinear stack). `B @ c` is **one substrate matmul** — every
pixel computed in a single op, no per-cell Python loop, no per-cell substrate call.

- **Substrate-pure:** `B` is a compile-time constant (the grid geometry, like a
  codebook is built before the run — sanctioned numpy-at-compile role); `c` is a
  substrate vector; `B @ c` runs on the substrate; the host reads `frame_flat` at the
  display boundary (`_display.read_real` per-component, or one bulk read) and reshapes
  to `N×N` to paint. No host arithmetic in the op.
- **The latent is the substrate state.** `c` can be produced by a substrate function
  (and, later, carried/updated by a `recur` loop for animation — ties to item #4).

## The oracle (how we verify, not "it ran")

Decoded-frame **must equal** the current per-pixel field, measured:

```
max_ij | (B @ c)[i,j]  −  frame.su.pixel(x_i, y_j) |  <  1e-6
```

i.e. the one-call decoder reproduces `window.render_field()` exactly. That equality is
the pass condition — a `test_gui_whole_frame.py` guard, not a visual glance.

## Why this is the right first cut

- It is the **smallest** version that puts the whole frame in one substrate call and is
  exactly checkable against the existing demo (no new ground truth needed).
- It introduces the decoder-matrix abstraction that the **general** reverse-CNN wants,
  without yet needing a *learned* nonlinear decoder.

## Open questions / what this does NOT yet do

1. **Arbitrary images.** A fixed polynomial basis only spans smooth analytic fields.
   A real reverse-CNN decoder is a **learned** (nonlinear, multi-stage) expansion that
   can produce arbitrary frames from a latent. That is the next step after the linear
   case — and the natural place the "constrain-train / every-op-trainable" vision meets
   GUI: fit the decoder so a learned latent → a target image.
2. **Latent semantics.** For the analytic case the latent is literally the polynomial
   coefficients. For learned decoders the latent is opaque — what carries it (a single
   hypervector vs. an axon of named fields) is the same capacity question the rest of
   Sutra has.
3. **Colour.** The glow is single-channel brightness. RGB = three latents / a `(N²,3)`
   decoder; trivial extension once the scalar case lands.
4. **Bulk display read.** Reading `N²` components one-by-one at the boundary is fine for
   correctness but slow; a single host-side bulk read of `frame_flat` is the display
   boundary done once (still terminal I/O, not in-language introspection).

## Build order (when item #3 is worked)

1. `demos/gui/frame_whole.su` — a function returning the latent `c` (substrate vector).
2. Host decoder: build `B` (compile-time grid constant), do `B @ c` on the substrate,
   reshape, paint (extend `window.py` or a sibling driver).
3. `test_gui_whole_frame.py` — assert `B @ c` == per-pixel `render_field()` to 1e-6.
4. Only then: sketch the learned-decoder generalisation (its own item).
