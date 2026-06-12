# 2026-06-11 — GUI whole-frame buffer needs a new grid/elementwise primitive (measured)

**Context:** GUI item #3 (Emma's model): the substrate returns **one vector that IS the
frame buffer** (pixel channel values in raster order); the host reshapes + paints. The
efficient form is computing the whole buffer in ONE vectorized substrate op over the
coordinate grid (not N² per-pixel calls).

## Finding

The existing Sutra number-arithmetic does NOT vectorize over a multi-component buffer, so
the one-op whole-frame render cannot be built on current primitives.

**Why (code):** `complex_mul` (codegen_pytorch.py) realizes a number product via fixed
d×d matrices tied to the real/imag AXES of a single number-vector:
`_cm_real_matrix() @ (a*b) + _cm_imag_matrix() @ ((_swap_ri @ a) * b)`. Those matrices
assume the value lives on the real/imag axes; values spread across other components are
mixed/zeroed.

**Measured:** built two vectors with `[1,2,3,4]` in their first four components (as if four
pixels) and called `complex_mul(a, b)`. Elementwise would give `[1,4,9,16]`; the runtime
returned `[0,0,0,0]`. So `*` (and the same goes for the matrix-based ops) treats its
operand as a single number on the real/imag axes, not an N-element buffer.

`complex_add`/`complex_sub` ARE elementwise (`av ± bv`), but multiplication — needed for
any non-trivial field like `1 − x² − y²` — is not.

## Consequence

A frame buffer (N² independent pixel values) computed in one substrate op needs a NEW
primitive: a vectorized **grid/field-render** op that evaluates a field across all pixels
at once (elementwise over a coordinate buffer), producing the buffer vector. This is the
"missing primitive to expose," not a wrong idea (CLAUDE.md). It is a runtime addition on
the substrate — its shape is a design decision for Emma (it's her substrate).

The fallbacks both fail Emma's intent: per-pixel substrate calls assembled by the host are
the inefficient shape she rejected; doing the field math host-side (numpy/torch over the
grid) is not the substrate computing the frame.

## Open: primitive shape (for Emma)

Candidate shapes for the grid-render primitive (all produce the buffer on the substrate):
- **(A) elementwise-buffer ops** — expose Hadamard `*` / square over a raw N-length buffer
  (coords as buffers), so `1 − X*X − Y*Y` composes directly. Most general; smallest concept.
- **(B) a dedicated `render(field, grid)` op** — takes a field function + coordinate grid,
  returns the buffer in one call. Higher-level; closer to "deconvolution"/CNN-decode framing.
- **(C) a fixed render matrix** — only works for linear fields (the rejected B@c shape).

Recommendation: **(A)** — it's the minimal, composable primitive; the field formula stays
ordinary `.su` arithmetic, just over a buffer. (B) can be sugar over (A) later.
