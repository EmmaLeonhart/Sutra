"""Yantra's first INTERACTIVE GUI — click to toggle the glow red <-> blue.

Two substrate computations drive it:
  - frame.su's pixel(x, y) computes the glow field (brightness 1 - x^2 - y^2),
  - toggle.su's flip(s) flips the 0/1 colour state on the substrate (1 - s).

On every click the host calls flip(state) on the substrate to get the new state,
then recolours: state 0 -> red glow, state 1 -> blue glow. The host does only
event delivery (the click) and painting; the field and the state transition are
substrate computations — the same host-is-I/O split as the calculator.

Usage:
    python apps/gui/click_demo.py                  # open the window; click to toggle
    python apps/gui/click_demo.py --render out      # save out_red.png + out_blue.png
    python apps/gui/click_demo.py --size 64

This is the first interactive GUI proof of concept (planning/24-first-gui.md).
The live window + click can't be checked headlessly; --render verifies the two
substrate-coloured frames.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Migrated to Sutra 2026-05-28; _REPO_ROOT is Sutra root, not Yantra.
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _compile(su_name: str) -> dict:
    """Compile a .su under apps/gui and return its namespace (functions + _VSA).

    Returns a dict view on the compiled module (kept for source-compat with
    the prior subscript access pattern `ns["pixel"]`). Caching happens
    inside `sutra_compiler.compile_su` so the second call on the same .su
    skips codegen entirely.
    """
    from sutra_compiler import compile_su
    # dim=8 — toggle.su + frame.su use only make_real + arithmetic; measured
    # exact at dim=8 (2026-05-27 audit, planning/27-substrate-honesty-audit-2026-05-27.md).
    mod = compile_su(DEMO_GUI / su_name,
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.__dict__


def render_field(size: int = 64) -> np.ndarray:
    """(size, size) brightness field, each cell a substrate pixel(x, y) call."""
    ns = _compile("frame.su")
    pixel, vsa = ns["pixel"], ns["_VSA"]
    field = np.empty((size, size), dtype=np.float64)
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            field[j, i] = float(vsa.real(pixel(cx, cy)))
    return field


def tint(field: np.ndarray, state: float) -> np.ndarray:
    """Colour the glow by the substrate STATE: 0 -> red, 1 -> blue.

    Brightness comes from the (substrate) field; which channel it lights comes
    from the (substrate) state. black -> hue -> white ramp.
    """
    v = np.clip(field, 0.0, 1.0)
    hot = np.clip(2.0 * v, 0, 1)        # primary hue channel
    rest = np.clip(2.0 * v - 1.0, 0, 1)  # whitens toward the centre
    if round(float(state)) == 0:  # red
        rgb = np.stack([hot, rest, rest], axis=-1)
    else:  # blue
        rgb = np.stack([rest, rest, hot], axis=-1)
    return (rgb * 255).astype(np.uint8)


class _Flip:
    """Substrate-backed 0/1 state: each step is toggle.su's flip() on the substrate."""

    def __init__(self) -> None:
        ns = _compile("toggle.su")
        self._flip, self._vsa = ns["flip"], ns["_VSA"]
        self.state = 0.0

    def toggle(self) -> float:
        self.state = float(self._vsa.real(self._flip(self.state)))  # SUBSTRATE flip
        return self.state


def main() -> None:
    ap = argparse.ArgumentParser(description="Yantra first interactive GUI (click toggles red/blue)")
    ap.add_argument("--render", metavar="PREFIX", help="save PREFIX_red.png + PREFIX_blue.png and exit")
    ap.add_argument("--size", type=int, default=64)
    args = ap.parse_args()

    field = render_field(args.size)

    if args.render:
        from PIL import Image
        for state, name in ((0.0, "red"), (1.0, "blue")):
            img = Image.fromarray(tint(field, state)).resize(
                (args.size * 8, args.size * 8), Image.NEAREST)
            img.save(f"{args.render}_{name}.png")
            print(f"[gui] saved {args.render}_{name}.png (state={state})")
        return

    import tkinter as tk
    from PIL import Image, ImageTk

    flipper = _Flip()

    def make_photo(state: float):
        img = Image.fromarray(tint(field, state)).resize(
            (args.size * 8, args.size * 8), Image.NEAREST)
        return ImageTk.PhotoImage(img)

    root = tk.Tk()
    root.title("Yantra — click to toggle red/blue (state flips on the substrate)")
    label = tk.Label(root, image=make_photo(flipper.state))
    label.pack()
    status = tk.Label(
        root, text="click anywhere — the colour state flips on the Sutra substrate")
    status.pack()

    def on_click(_event):
        state = flipper.toggle()  # substrate flip
        photo = make_photo(state)
        label.configure(image=photo)
        label.image = photo  # keep a ref
        colour = "red" if round(float(state)) == 0 else "blue"
        status.configure(
            text=f"state = {round(float(state))} ({colour}) — flipped on the substrate")
        print(f"[gui] click -> substrate flip -> state {round(float(state))} ({colour})",
              flush=True)

    # Bind ONCE, on the toplevel only. A widget's bindtags already include
    # its toplevel, so a click anywhere in the window (image, text, or empty
    # area) fires this exactly once. Binding BOTH the image label AND the
    # toplevel fired on_click TWICE per click (label tag + toplevel tag),
    # double-flipping the state (0->1->0) so the colour never appeared to
    # change. This was the "clicking does nothing" bug.
    root.bind("<Button-1>", on_click)
    root.mainloop()


if __name__ == "__main__":
    main()
