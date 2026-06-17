# 24 — First GUI: substrate-computed pixels in a window

**Status: first proof of concept WORKS (2026-05-24).** `apps/gui/frame.su` +
`apps/gui/window.py` render a window of pixels whose values are computed on the
Sutra substrate. `apps/gui/first_frame.png` is the first rendered frame (a radial
glow, `1 − x² − y²`, heat-mapped).

## The idea (Emma)

A GUI for Yantra means: a Sutra program produces the screen content, and a window
in the orchestration layer displays it. Emma's framing: "it returns a vector, and
then the vector basically does the reorganisation thing to turn the information
into pixels" — a reverse-CNN-style decoder from a compact substrate vector to a
pixel grid. The window lives "in whatever framework we're using for orchestration"
(Python host for now; the Rust orchestrator eventually).

## What the first PoC actually does (honest scope)

It is the **smallest honest version**, not yet the vector-decoder above:

- `frame.su` exposes `pixel(x, y)` returning brightness `1 − x² − y²` for centred
  coordinates in [-1, 1]. Every arithmetic step runs on the substrate; `make_real`
  lifts the scalar onto the real axis (the same lift the calculator parser needed).
- `window.py` walks the pixel grid, maps each pixel to centred coordinates, calls
  `pixel` on the substrate **per pixel**, reads the value with `real()`, then
  clamps + colour-maps + displays (tkinter) or saves a PNG.
- **The substrate computes the image field; the host does assembly + I/O only** —
  the same host-is-I/O split as the calculator. Normalisation and colour are
  display-only; the field values are the substrate's.

Verified (real run): a 64×64 field, centre = 0.9995, corner = −1.0, matching
`1 − x² − y²`; saved a 512×512 PNG. The live window can't be verified headlessly;
`python apps/gui/window.py` opens it.

## Path from here

1. **Single returned vector → frame** (Emma's "reverse CNN"). Instead of one
   substrate call per pixel, a `.su` returns one vector that a decoder
   "reorganises" into the pixel grid. Open design question: how a compact
   substrate vector encodes a 2-D field (a fixed deconv/upsampling map, or a
   learned decoder at the quarantined boundary). The per-pixel field is the
   fallback that already works.
2. **Batched render.** Per-pixel host calls are fine for a static frame but slow
   for interactivity; batch the grid into one substrate forward pass.
3. **Window in the orchestrator.** Host tkinter is the stand-in. The real window
   belongs in the Rust orchestrator (planning/01 "CPU side: small, Rust"), as one
   of the piecemeal Rust units; the display server is host-side by design
   (planning/01 inversion 3: the FS/IO boundary is host, compute is substrate).
   **Shipped 2026-05-25:** `apps/gui-rust/` — a Rust window (minifb) owns the
   clicks + painting and gets each frame from the Sutra substrate over a
   subprocess bridge (`apps/gui/counter_substrate_server.py`); the count + the
   pixel field stay on the substrate. First Rust-orchestrator GUI unit (the
   counter demo). PyO3 in-process embedding is a later tightening; subprocess
   was chosen (Emma 2026-05-25) as the simplest honest bridge.
4. **Build-sequence note.** The committed sequence (planning/01, CLAUDE.md) gates
   the production browser GUI behind the kernel + CLI utilities. This is an
   exploratory first-pixels PoC, not that GUI — it demonstrates substrate→screen
   is real, ahead of the production GUI stack.

## Substrate-purity note

The picture's *content* is substrate-computed (each pixel a real `pixel(x,y)`
call decoded with `real()`). Host responsibilities — looping coordinates,
clamping to [0,1], colour-mapping, painting the window — are I/O/rendering, the
CPU orchestrator's job. No host-drawn image dressed as substrate output.
