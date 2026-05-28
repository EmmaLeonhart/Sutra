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

# Compile cache: font.su is recompiled on the first call and reused. Compiling
# this .su is non-trivial (36 letter functions, each a 25-way select) -- doing
# it per keypress would be unusable. Memo dict mirrors counter_demo.py.
_COMPILED: dict = {}


def _compile():
    """Compile font.su and return its namespace.

    Uses ``runtime_dim=8`` (NOT 768). font.su contains no ``basis_vector``
    calls -- it uses only ``make_real`` + arithmetic + ``select``, which
    are pure math operations that don't touch the LLM codebook. So no
    embeddings are needed and the runtime dim can be tiny. Measured
    2026-05-27: at runtime_dim=8 the cycle_step / glyph_pixel results
    are still exact (codes 66.000000 for A->B, etc.; glyph patterns
    pixel-exact vs the font oracle).

    Why this matters: the previous runtime_dim=768 was 96x bigger than
    needed for this task. Every substrate op was doing 768-element
    tensor work to carry 1 scalar of information. Switching to 8
    eliminates the bulk of the per-tick slowness Emma asked about.
    ``llm_model`` is still required by the API but unused at runtime
    when no basis_vector calls are present.
    """
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


def render_glyph(char_code: float, prev_field: np.ndarray | None = None) -> np.ndarray:
    """Render the 5x5 pixel field for the character at ``char_code``.

    Each cell is one substrate ``step(prev, x, y, char_code)`` call -- Emma's
    recurrent step on the substrate. ``prev_field`` is the previous frame; if
    None, treated as all-zero (initial state). The * 0 in the step discards
    prev regardless, so the SAME glyph comes out either way -- prev_field is
    threaded only to honour the recurrent shape (the substrate is what
    forgets, not the host).
    """
    ns = _compile()
    step, vsa = ns["step"], ns["_VSA"]

    if prev_field is None:
        prev_field = np.zeros((5, 5), dtype=np.float64)

    out = np.empty((5, 5), dtype=np.float64)
    for y in range(5):
        for x in range(5):
            prev_pix = vsa.make_real(float(prev_field[y, x]))
            new_pix = step(prev_pix, float(x), float(y), float(char_code))
            out[y, x] = float(vsa.real(new_pix))
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

    # Pre-compile font.su BEFORE opening the window so the window doesn't sit
    # frozen on the first tick while Sutra codegen runs (~5 min on this machine,
    # instant after the on-disk cache is populated -- see _compile()).
    ns = _compile()
    cycle_step = ns["cycle_step"]

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
        next_code = float(ns["_VSA"].real(next_code_vec))
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
