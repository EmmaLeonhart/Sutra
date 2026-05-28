"""Yantra font demo -- character cycler / pixel renderer (NOT an RNN).

Honest framing, corrected 2026-05-27 after Emma called the previous header
out: this is a *counter* with substrate function calls inside it, not a
recurrent neural network. Specifically:

  - The "hidden state" of this task is 2-dimensional at most: (input, current
    character-on-screen). One scalar in, one scalar out per tick.
  - The substrate's word width is 768-d (fixed by nomic-embed-text, the LLM
    backing the runtime). Every substrate value is therefore 768-d regardless
    of how much information it carries. For this 2-d-state task, 766 of those
    768 dims are dead weight; the substrate adds no semantic structure.
  - The pixels are 25 bits (5x5 black/white). Each cell is computed as one
    768-d substrate vector with the bit on the real axis. 767 dims of dead
    weight per pixel.
  - Across ticks, the host extracts the scalar char_code via vsa.real() and
    feeds it back next tick (apps/font/font_demo.py:tick()). That host-scalar-
    shuttle is what makes the loop a counter, not a recurrent network --
    state lives on the host, not on the substrate.

The substrate operations DO run on real PyTorch tensors. The cycle decision
(which char comes next) and the pixel decision (lit / unlit per cell) are
computed by real substrate ops. What this demo is NOT is "an RNN" or
"substrate-pure end-to-end" -- those framings would require state to live as
a substrate vector across ticks AND for the substrate's 768-d capacity to be
load-bearing on the task, neither of which is true here.

Substrate computations (apps/font/font.su):

  cycle_step(prev_code, typed_code, has_typed)
      Counter step. 36-way defuzzified select picks (prev -> next) in cycle
      order; override gate replaces with typed_code when has_typed=1.0.
      Decision is on the substrate; state is on the host (real() between ticks).

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

    # State the host shuttles between substrate ticks:
    #   char_code    -- the current scalar code (the RNN's hidden state, decoded
    #                   from the substrate vector each tick via vsa.real()).
    #   field        -- the rendered 5x5 pixel field for that code.
    #   pending_typed -- the last typed code, or None. Set by on_key, cleared
    #                   by tick. The tick passes it to cycle_step as the
    #                   typed-code branch.
    state = {
        "char_code": float(ord("A")),
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
        # Substrate-recurrent step on the char_code. Without a key, the
        # 36-way defuzzified select advances the code one step in cycle order.
        # With a pending key, has_typed=1.0 and the typed code wins via the
        # weighted-sum gate -- no host if.
        has_typed = 1.0 if state["pending_typed"] is not None else 0.0
        typed = float(state["pending_typed"]) if has_typed else 0.0
        next_code_vec = cycle_step(state["char_code"], typed, has_typed)
        next_code = float(cycle_ns["_VSA"].real(next_code_vec))
        state["pending_typed"] = None
        # Round to the nearest integer codepoint -- the defuzzified select is
        # exact in float64, but a defensive round() guards against any drift
        # from the typed override (typed_vec * 1.0 is exact, but be careful).
        state["char_code"] = float(round(next_code))

        # Render the 25-cell pixel field for the new code. This is the expensive
        # part (22500 substrate branches via the existing glyph_pixel design);
        # the cycle_step itself is one 36-way select on top.
        new_field = render_glyph(state["char_code"], prev_field=state["field"])
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
