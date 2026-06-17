"""Live RGB / multi-axis Adam steering window for the substrate hero (GUI rebuild G4).

A thin tkinter driver over `hero_adam.HeroAdam(color=True)` — the colour version of the
real-time-RL demo: a COLOUR pixel image generated entirely by the Sutra substrate
(`whole_frame.render_hero_rgb_torch`), steered by your A / B preferences, where Adam
backpropagates your preference THROUGH the differentiable Sutra render to morph the picture
across position, size, brightness AND colour (cr/cg/cb tints are steerable axes now).

Each round shows two substrate-rendered colour frames — A (current, left) and B (proposed
variant, right). Press:
  • A (key A) — you prefer the LEFT frame (keep current)
  • B (key B) — you prefer the RIGHT frame (take the variant)
One Bradley-Terry step trains the differentiable reward head on your choice, then a couple
of Adam steps ascend that reward through the Sutra render; the next pair is drawn and the
hero visibly morphs toward what you reward.

All compute is the controller's: the frames are the Sutra substrate render; the reward head
and Adam are host-side. This file is only I/O — a window, two images, two buttons. It is
intentionally untested (no display in CI); the steering logic is covered headless in
test_hero_adam_rgb.py and test_hero_steering_axes.py.

    python demos/gui/adam_window_rgb.py             # open the window
    python demos/gui/adam_window_rgb.py --size 96   # bigger frame (slower)
    python demos/gui/adam_window_rgb.py --cell 6    # display pixels per cell
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _to_uint8(img: np.ndarray) -> np.ndarray:
    """Clamp the substrate colour frame to [0,1] and scale to 8-bit RGB for display."""
    return (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)


def _mean_rgb(frame: np.ndarray) -> tuple[float, float, float]:
    return (float(frame[..., 0].mean()),
            float(frame[..., 1].mean()),
            float(frame[..., 2].mean()))


def main() -> None:
    ap = argparse.ArgumentParser(description="RGB Adam steering of the substrate hero (RLHF).")
    ap.add_argument("--size", type=int, default=64, help="frame grid resolution")
    ap.add_argument("--cell", type=int, default=5, help="display pixels per cell")
    ap.add_argument("--seed", type=int, default=0, help="controller seed")
    args = ap.parse_args()

    ha = _load("gui_hero_adam", "hero_adam.py")
    ctl = ha.HeroAdam(size=args.size, seed=args.seed, color=True)

    import tkinter as tk
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("Sutra hero — RGB Adam RLHF (A / B preference)")
    root.configure(bg="black")

    state = {"photos": [None, None], "round": 0}

    def _photo(frame):
        big = Image.fromarray(_to_uint8(frame)).resize(
            (args.size * args.cell, args.size * args.cell), Image.NEAREST)
        return ImageTk.PhotoImage(big)

    def draw_pair():
        cur, var = ctl.propose()
        pc, pv = _photo(cur), _photo(var)
        state["photos"] = [pc, pv]                 # keep refs so they aren't GC'd
        a_label.configure(image=pc); a_label.image = pc
        b_label.configure(image=pv); b_label.image = pv
        r, g, b = _mean_rgb(cur)
        th = ctl.current_theta()
        caption.configure(
            text=f"round {state['round']}   ·   A mean RGB "
                 f"({r:.2f}, {g:.2f}, {b:.2f})   ·   pos ({th['cx']:+.2f}, {th['cy']:+.2f})  "
                 f"spread invs {th['invs']:.2f}   ·   Adam through the substrate render")

    def choose(prefer_variant: bool):
        ctl.choose(prefer_variant=prefer_variant)
        state["round"] += 1
        draw_pair()

    tk.Label(root, text="A — current               B — proposed", fg="white", bg="black",
             font=("TkDefaultFont", 11)).pack(pady=(8, 0))
    frames = tk.Frame(root, bg="black")
    frames.pack(padx=args.cell, pady=args.cell)
    a_label = tk.Label(frames, bg="black", borderwidth=0)
    a_label.pack(side="left", padx=args.cell)
    b_label = tk.Label(frames, bg="black", borderwidth=0)
    b_label.pack(side="left", padx=args.cell)

    caption = tk.Label(root, fg="white", bg="black", font=("TkDefaultFont", 12))
    caption.pack(pady=4)

    btns = tk.Frame(root, bg="black")
    btns.pack(pady=(0, args.cell))
    tk.Button(btns, text="PREFER A (key A) — keep current", width=28,
              command=lambda: choose(False)).pack(side="left", padx=6)
    tk.Button(btns, text="PREFER B (key B) — take proposed", width=28,
              command=lambda: choose(True)).pack(side="left", padx=6)
    root.bind("a", lambda e: choose(False))
    root.bind("b", lambda e: choose(True))

    draw_pair()
    root.mainloop()


if __name__ == "__main__":
    main()
