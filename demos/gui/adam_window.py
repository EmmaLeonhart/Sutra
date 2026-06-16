"""Live Adam steering window for the substrate hero (GUI rebuild R4).

A thin tkinter driver over `hero_adam.HeroAdam` — the real-time-RL demo: a pixel image
generated entirely by the Sutra substrate, steered by your WARMER / COLDER preferences,
where Adam backpropagates your preference THROUGH the differentiable Sutra render to morph
the picture (not the old zeroth-order SPSA black box).

Each round shows two substrate-rendered frames — the CURRENT hero (left) and a PROPOSED
variant (right). Press:
  • WARMER (W) — you like the proposed variant more
  • COLDER (K) — you prefer the current
One Bradley-Terry step trains the differentiable reward head on your choice, then a couple
of Adam steps ascend that reward through the Sutra render; the next pair is drawn and the
hero visibly morphs toward what you reward.

All compute is the controller's: the frames are the Sutra substrate render; the reward head
and Adam are host-side. This file is only I/O — a window, two images, two buttons. It is
intentionally untested (no display in CI); the steering logic is covered headless in
test_hero_adam.py.

    python demos/gui/adam_window.py             # open the window
    python demos/gui/adam_window.py --size 96   # bigger frame (slower)
    python demos/gui/adam_window.py --cell 6    # display pixels per cell
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
    """Clamp the substrate frame to [0,1] and scale to 8-bit grayscale for display."""
    return (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser(description="Adam steering of the substrate hero (RLHF).")
    ap.add_argument("--size", type=int, default=64, help="frame grid resolution")
    ap.add_argument("--cell", type=int, default=5, help="display pixels per cell")
    ap.add_argument("--seed", type=int, default=0, help="controller seed")
    args = ap.parse_args()

    ha = _load("gui_hero_adam", "hero_adam.py")
    ctl = ha.HeroAdam(size=args.size, seed=args.seed)

    import tkinter as tk
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("Sutra hero — Adam RLHF (warmer / colder)")
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
        cur_label.configure(image=pc); cur_label.image = pc
        var_label.configure(image=pv); var_label.image = pv
        caption.configure(
            text=f"round {state['round']}   ·   current brightness "
                 f"{float(cur.mean()):.2f}   ·   Adam through the substrate render")

    def choose(prefer_variant: bool):
        ctl.choose(prefer_variant=prefer_variant)
        state["round"] += 1
        draw_pair()

    tk.Label(root, text="CURRENT            PROPOSED", fg="white", bg="black",
             font=("TkDefaultFont", 11)).pack(pady=(8, 0))
    frames = tk.Frame(root, bg="black")
    frames.pack(padx=args.cell, pady=args.cell)
    cur_label = tk.Label(frames, bg="black", borderwidth=0)
    cur_label.pack(side="left", padx=args.cell)
    var_label = tk.Label(frames, bg="black", borderwidth=0)
    var_label.pack(side="left", padx=args.cell)

    caption = tk.Label(root, fg="white", bg="black", font=("TkDefaultFont", 12))
    caption.pack(pady=4)

    btns = tk.Frame(root, bg="black")
    btns.pack(pady=(0, args.cell))
    tk.Button(btns, text="WARMER (W) — like proposed", width=24,
              command=lambda: choose(True)).pack(side="left", padx=6)
    tk.Button(btns, text="COLDER (K) — keep current", width=24,
              command=lambda: choose(False)).pack(side="left", padx=6)
    root.bind("w", lambda e: choose(True))
    root.bind("k", lambda e: choose(False))

    draw_pair()
    root.mainloop()


if __name__ == "__main__":
    main()
