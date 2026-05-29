"""Font demo -- substrate-state-RNN glyph cycler + pixel renderer.

The cycle_step rewrite (2026-05-28, Option B) makes the glyph cursor a REAL
substrate-state RNN, fixing the host-state-shuttle shape Emma called out on
2026-05-27. Specifically:

  - The hidden state is a 36-dim ONE-HOT over the glyph cycle, held in a
    `recurring vector` slot that lives ON THE SUBSTRATE across ticks
    (non-halting-loop.md). It is NOT extracted to a host scalar and fed back
    between ticks -- the recurrence stays on the substrate. The host decodes
    the one-hot to a char only for RENDERING (a monitoring boundary, like
    count.su decoding its count vector to position the glow).
  - The advance is a single matmul `next = P @ glyph` against the frozen 36x36
    cyclic-permutation matrix P, built with the `matrix_literal` primitive.
    One-hot in, one-hot out; the state stays bit-exact one-hot across ticks
    (signal-separation gap = 1.0 - 0.0 = 1.0, measured in test_font_cycle.py).
  - The state/advance tensors are 36-dim problem-sized (no basis_vector calls),
    so cycle_step runs at runtime_dim=8 -- the old "766 of 768 dims are dead
    weight" critique does not apply; the 36-d state is fully load-bearing.

Pixel rendering is a SEPARATE substrate compile (font_bound_antipodal.su at
runtime_dim=256, 63 basis_vector calls for the position+marker codebook); see
render_glyph / _compile_render below. The two paths are independent.

Substrate computations:

  cycle_step(typed_onehot, has_typed)   [font.su, runtime_dim=8]
      Substrate-state RNN. recurring 36-dim one-hot `glyph` advances via
      next = P @ glyph (frozen cyclic-permutation matmul); has_typed=1.0 lets
      a host-provided typed one-hot replace the advance via the substrate
      weighted sum. State lives on the substrate across ticks.

  step(prev_state, x, y, char_code)
      Per-cell substrate dispatch. ``prev*0 + glyph_pixel(...)`` is host-
      framed as "forget then add" but the * 0 is structurally a no-op (any
      input zeros it). The pixel decision is real substrate work.

  glyph_pixel(x, y, char_code)
      36-way outer select over char + 25-way inner select per char's bit
      pattern. ~22,500 substrate branches per keypress; documented as bloat
      in planning/26-font-bound-vector-rewrite.md (queued).

Usage:
    python demos/font/font_demo.py              # open window; auto-cycles, keys override
    python demos/font/font_demo.py --render A   # save A.png and exit (headless)
    python demos/font/font_demo.py --cell 40    # 5x5 glyph at 40px/cell = 200x200
    python demos/font/font_demo.py --fps 2      # cycle rate (default 2 fps)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

# Migrated from Yantra/apps/font/ 2026-05-28. _REPO_ROOT here is the Sutra
# repo root (demos/font/.. = demos/; demos/.. = sutra-root).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

DEMO_FONT = pathlib.Path(__file__).resolve().parent

# TWO separate compiles:
#   font.su                  — cycle_step (the character-code counter, runtime_dim=8,
#                              no basis_vector, pure arithmetic on the real axis).
#   font_bound_antipodal.su  — glyph_pixel_antipodal (the rotation-binding pixel
#                              renderer, runtime_dim=256, MEASURED-WORKING with
#                              36/36 glyphs pixel-exact at threshold 0.0; ~28x
#                              faster than the original font.su's defuzzified-
#                              select tree at 22500 substrate branches per render).
# Each .su is compiled at the dim its task actually needs (per the substrate-
# honesty audit; see Sutra DEVLOG.md 2026-05-28).
_COMPILED: dict = {}


def _compile_cycle():
    """Compile font.su (just for cycle_step). runtime_dim=8."""
    cached = _COMPILED.get("font.su")
    if cached is not None:
        return cached
    from sutra_compiler import compile_su
    mod = compile_su(
        DEMO_FONT / "font.su",
        llm_model="unused-no-basis-vectors-in-font.su",
        runtime_dim=8,
    )
    _COMPILED["font.su"] = mod.__dict__
    return mod.__dict__


# Cosine threshold dividing lit cells (positive cosine to LIT) from unlit
# cells (negative cosine) in the antipodal-filler encoding. Measured 2026-05-28
# at runtime_dim=256: lit_min=+0.028, unlit_max=-0.024 across 900 samples.
# Anything in (-0.024, +0.028) cleanly partitions; 0.0 sits in the middle.
_ANTIPODAL_THRESHOLD = 0.0


def _compile_render():
    """Compile font_bound_antipodal.su (for glyph_pixel_antipodal). dim=256."""
    cached = _COMPILED.get("font_bound_antipodal.su")
    if cached is not None:
        return cached
    from sutra_compiler import compile_su
    mod = compile_su(
        DEMO_FONT / "font_bound_antipodal.su",
        llm_model="nomic-embed-text",
        runtime_dim=256,
    )
    _COMPILED["font_bound_antipodal.su"] = mod.__dict__
    return mod.__dict__


# Kept for source-compat with any external caller (e.g. tests/test_font.py
# loads the module and inspects `_compile()`). Routes to the cycle compile,
# which is what test_font_cycle.py needs; test_font.py's render path is now
# handled by render_glyph() below using _compile_render() directly.
_compile = _compile_cycle


def render_glyph(char_code: float, prev_field: np.ndarray | None = None) -> np.ndarray:
    """Render the 5x5 pixel field for the character at ``char_code``.

    Uses the antipodal-filler bound-vector encoding (font_bound_antipodal.su,
    runtime_dim=256). Each cell is one substrate call to
    ``glyph_pixel_antipodal(x, y, char_code)`` that returns a cosine-to-LIT
    value: positive for lit cells, negative for unlit. The host thresholds at
    0.0 to produce the binary field. Measured 2026-05-28: 36/36 glyphs
    pixel-exact at this threshold; ~93 ms/render = ~11 fps single-threaded
    (~28x faster than the original font.su defuzzified-select path).

    ``prev_field`` is accepted for source-compat with older callers but is
    not used (the encoding has no recurrence — render is stateless per cell).
    """
    del prev_field  # unused; kept for source-compat
    ns = _compile_render()
    glyph_pixel_antipodal = ns["glyph_pixel_antipodal"]
    vsa = ns["_VSA"]

    out = np.empty((5, 5), dtype=np.float64)
    for y in range(5):
        for x in range(5):
            cos_lit = float(vsa.real(
                glyph_pixel_antipodal(float(x), float(y), float(char_code))
            ))
            # Threshold to a clean 0/1 field. Substrate returns a cosine in
            # roughly [-1, +1]; host paints the binary result.
            out[y, x] = 1.0 if cos_lit > _ANTIPODAL_THRESHOLD else 0.0
    return out


def colormap(field: np.ndarray) -> np.ndarray:
    """5x5 brightness field -> uint8 RGB. White on black -- the cleanest read
    for a single-character display. Values are the substrate's; host only
    paints (clamp + scale)."""
    v = np.clip(field, 0.0, 1.0)
    g = (v * 255.0).astype(np.uint8)
    return np.stack([g, g, g], axis=-1)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Yantra font demo (auto-cycles A-Z-0-9, keypress overrides; all on the substrate)")
    ap.add_argument("--render", metavar="CHAR",
                    help="render the given character and save CHAR.png; exit")
    ap.add_argument("--cell", type=int, default=40,
                    help="pixel size per glyph cell (default 40 -> 200x200 image)")
    ap.add_argument("--fps", type=float, default=2.0,
                    help="auto-cycle rate (default 2 frames/sec)")
    args = ap.parse_args()

    if args.render:
        from PIL import Image
        ch = args.render.upper()
        if len(ch) != 1 or not (ch.isalpha() or ch.isdigit()):
            raise SystemExit(f"--render expects one A-Z/0-9 char, got {args.render!r}")
        field = render_glyph(float(ord(ch)))
        img = Image.fromarray(colormap(field)).resize(
            (5 * args.cell, 5 * args.cell), Image.NEAREST)
        out = pathlib.Path(f"{ch}.png")
        img.save(out)
        print(f"[font] saved {out} (char {ch!r}, code {ord(ch)})")
        return

    # Pre-compile BOTH .su files BEFORE opening the window so the window
    # doesn't sit frozen on the first tick while Sutra codegen runs (~5 min
    # uncached, instant after the on-disk cache is populated). Two separate
    # compiles per the substrate-honesty audit: cycle_step at runtime_dim=8
    # (no basis_vector, pure arithmetic) + glyph_pixel_antipodal at
    # runtime_dim=256 (63 basis_vector calls for the position+marker codebook).
    cycle_ns = _compile_cycle()
    cycle_step = cycle_ns["cycle_step"]
    _compile_render()  # Warm the renderer cache too.

    import tkinter as tk
    from PIL import Image, ImageTk

    # The RNN hidden state lives ON THE SUBSTRATE — cycle_step's `recurring`
    # one-hot `glyph` slot is the source of truth and survives across ticks
    # without the host carrying it (substrate-state RNN, non-halting-loop.md).
    # The host keeps only:
    #   field         -- the rendered 5x5 pixel field for the current glyph.
    #   pending_typed -- the last typed code, or None. Set by on_key, cleared
    #                   by tick; the tick turns it into a one-hot and passes it
    #                   to cycle_step with has_typed=1.0.
    import torch as _torch
    cycle_vsa = cycle_ns["_VSA"]
    CYCLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    def _typed_onehot(code_or_none):
        """Build a 36-dim one-hot for a typed char (or all-zeros when none).
        A host-side INPUT crossing the boundary — not state; the recurring
        state lives on the substrate."""
        v = _torch.zeros(len(CYCLE), dtype=cycle_vsa.dtype, device=cycle_vsa.device)
        if code_or_none is not None:
            ch = chr(int(code_or_none)).upper()
            if ch in CYCLE:
                v[CYCLE.index(ch)] = 1.0
        return v

    state = {
        "field": np.zeros((5, 5), dtype=np.float64),
        "pending_typed": None,
    }
    tick_ms = max(50, int(1000.0 / max(0.1, args.fps)))

    def make_photo(field: np.ndarray):
        img = Image.fromarray(colormap(field)).resize(
            (5 * args.cell, 5 * args.cell), Image.NEAREST)
        return ImageTk.PhotoImage(img)

    # The window is intentionally minimal — only the 5x5 pixel grid in the
    # middle is substrate output. No status label, no chatty title. Anything
    # painted by tkinter (fonts, borders, the title bar text the OS draws) is
    # host chrome; only the centre image is the substrate's product.
    root = tk.Tk()
    root.title("font")
    root.configure(bg="black")
    photo0 = make_photo(state["field"])
    label = tk.Label(root, image=photo0, bg="black", borderwidth=0)
    label.image = photo0
    label.pack(padx=args.cell, pady=args.cell)

    def tick():
        # Substrate-state-RNN step. cycle_step advances its own recurring
        # one-hot `glyph` slot ON THE SUBSTRATE (next = P @ glyph, the frozen
        # cyclic-permutation matmul); the host does NOT carry the cursor.
        # Without a key, has_typed=0.0 and the advance passes through; with a
        # pending key, has_typed=1.0 and the host-built typed one-hot wins via
        # the substrate weighted-sum gate -- no host if.
        has_typed = 1.0 if state["pending_typed"] is not None else 0.0
        typed_oh = _typed_onehot(state["pending_typed"])
        glyph_oh = cycle_step(typed_oh, has_typed)
        state["pending_typed"] = None
        # Decode the returned one-hot to a char_code for RENDERING only -- a
        # monitoring boundary (like count.su decoding its count vector), NOT
        # state feedback. The recurrence already advanced on the substrate.
        char_code = float(ord(CYCLE[int(_torch.argmax(glyph_oh))]))

        # Render the 25-cell pixel field for the new code. This is the expensive
        # part (the glyph_pixel_antipodal bound-vector design at dim=256);
        # the cycle_step advance itself is one matmul.
        new_field = render_glyph(char_code, prev_field=state["field"])
        state["field"] = new_field
        photo = make_photo(new_field)
        label.configure(image=photo)
        label.image = photo
        root.after(tick_ms, tick)

    def on_key(event):
        ch = (event.char or "").upper()
        if len(ch) != 1 or not (ch.isalpha() or ch.isdigit()):
            return
        if ch.isalpha() and ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            return
        # Stash the typed code; the next tick passes it to cycle_step with
        # has_typed=1.0 and the substrate weighted-sum gate picks it.
        state["pending_typed"] = ord(ch)

    root.bind("<Key>", on_key)
    root.after(tick_ms, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
