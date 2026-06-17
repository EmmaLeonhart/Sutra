"""D9 — live window for the preference-steered generative decoder (thin I/O wrapper).

A tkinter driver over `LatentSteer`: it trains the latent-conditioned substrate decoder, then
shows the CURRENT generated frame and a PROPOSED latent-variant; press WARMER (W, prefer the
variant) / COLDER (K, prefer the current) and Adam moves the latent up the learned reward
through the substrate render — the generated picture morphs toward what you reward.

I/O only — the generation + steering are the substrate/host split proven headless
(test_latent_steer.py, latent_demo.py). Not exercised in CI (no display). Smoke by running it.

    python demos/decoder/latent_window.py
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _u8(img):
    return (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Live preference-steering of the substrate generator.")
    ap.add_argument("--size", type=int, default=24)
    ap.add_argument("--cell", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    demo = _load("latent_demo", "latent_demo.py")
    ls = _load("latent_steer", "latent_steer.py")
    print("Training the latent-conditioned generator (substrate decoder) ...")
    nn, params, z_mid, (size, nf) = demo.train_generator(size=args.size, seed=args.seed)
    ctl = ls.LatentSteer(params, z_mid, size=size, num_freqs=nf, seed=args.seed)

    import tkinter as tk
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("Sutra — preference-steered generator (warmer / colder)")
    root.configure(bg="black")
    state = {"photos": [None, None]}

    def _photo(frame):
        big = Image.fromarray(_u8(frame)).resize((size * args.cell, size * args.cell), Image.NEAREST)
        return ImageTk.PhotoImage(big)

    def draw():
        cur, var = ctl.propose()
        pc, pv = _photo(cur), _photo(var)
        state["photos"] = [pc, pv]
        cur_lbl.configure(image=pc); cur_lbl.image = pc
        var_lbl.configure(image=pv); var_lbl.image = pv

    def choose(prefer_variant):
        ctl.choose(prefer_variant=prefer_variant)
        draw()

    tk.Label(root, text="CURRENT            PROPOSED", fg="white", bg="black").pack(pady=(8, 0))
    frames = tk.Frame(root, bg="black"); frames.pack(padx=args.cell, pady=args.cell)
    cur_lbl = tk.Label(frames, bg="black"); cur_lbl.pack(side="left", padx=args.cell)
    var_lbl = tk.Label(frames, bg="black"); var_lbl.pack(side="left", padx=args.cell)
    btns = tk.Frame(root, bg="black"); btns.pack(pady=(0, args.cell))
    tk.Button(btns, text="WARMER (W)", width=16, command=lambda: choose(True)).pack(side="left", padx=6)
    tk.Button(btns, text="COLDER (K)", width=16, command=lambda: choose(False)).pack(side="left", padx=6)
    root.bind("w", lambda e: choose(True)); root.bind("k", lambda e: choose(False))
    draw()
    root.mainloop()


if __name__ == "__main__":
    main()
