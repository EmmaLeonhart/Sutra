"""Live warmer/colder steering window for the a1 hero demo (item 1c, the shell).

A thin tkinter driver over the headless `hero_steering.HeroSteering` controller:
it paints the current substrate-rendered hero and offers WARMER / COLDER buttons
(and the W / K keys). Each press calls `controller.press(±1)`, which scores the
shown perturbation and re-renders the next frame; every two presses complete one
host-side SPSA step, so the hero visibly morphs toward what the rater prefers.

All compute is the controller's: the frame is the substrate render (colour
channels + glyph headline) and the optimizer is host-side SPSA. This file is only
I/O — a window, two buttons, a paint loop. It is intentionally untested (no display
in CI); the steering logic is covered headless in test_hero_steering.py.

    python demos/gui/steering_window.py            # open the window
    python demos/gui/steering_window.py --size 96  # bigger frame (slower)
    python demos/gui/steering_window.py --cell 6   # pixels per cell
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
    """Clamp the substrate frame to [0,1] and scale to 8-bit RGB for display."""
    return (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser(description="Warmer/colder substrate-hero steering.")
    ap.add_argument("--size", type=int, default=64, help="frame grid resolution")
    ap.add_argument("--cell", type=int, default=6, help="display pixels per cell")
    ap.add_argument("--seed", type=int, default=0, help="SPSA seed")
    args = ap.parse_args()

    steer = _load("gui_hero_steering", "hero_steering.py")
    ctl = steer.HeroSteering(size=args.size, seed=args.seed, render_headline=True)

    import tkinter as tk
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("hero — warmer / colder")
    root.configure(bg="black")

    state = {"photo": None, "headline": ""}

    def paint(frame_headline):
        img, headline = frame_headline
        big = Image.fromarray(_to_uint8(img)).resize(
            (args.size * args.cell, args.size * args.cell), Image.NEAREST)
        photo = ImageTk.PhotoImage(big)
        state["photo"] = photo                       # keep a ref so it isn't GC'd
        state["headline"] = headline
        label.configure(image=photo)
        label.image = photo
        caption.configure(text=f"{headline}   ·   SPSA steps: {ctl.batches_done}")

    label = tk.Label(root, bg="black", borderwidth=0)
    label.pack(padx=args.cell, pady=(args.cell, 0))
    caption = tk.Label(root, fg="white", bg="black", font=("TkDefaultFont", 12))
    caption.pack(pady=4)

    def rate(reward):
        paint(ctl.press(reward))

    btns = tk.Frame(root, bg="black")
    btns.pack(pady=(0, args.cell))
    tk.Button(btns, text="WARMER (W)", width=12,
              command=lambda: rate(steer.WARMER)).pack(side="left", padx=6)
    tk.Button(btns, text="COLDER (K)", width=12,
              command=lambda: rate(steer.COLDER)).pack(side="left", padx=6)
    root.bind("w", lambda e: rate(steer.WARMER))
    root.bind("k", lambda e: rate(steer.COLDER))

    paint(ctl.frame())
    root.mainloop()


if __name__ == "__main__":
    main()
