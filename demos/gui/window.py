"""Yantra's first GUI — a window of substrate-computed pixels.

The image FIELD is computed on the Sutra substrate: `apps/gui/frame.su` exposes
`pixel(x, y)`, and this host walks the pixel grid, calls `pixel` per pixel on the
substrate (mapping each pixel to centred coordinates in [-1, 1]), reads the
brightness, then clamps, colour-maps, and paints. The host does assembly + I/O
only — the picture's content comes from the substrate, the same split as the
calculator (host reads/writes; the substrate computes the value).

Usage:
    python apps/gui/window.py                 # render + open a window
    python apps/gui/window.py --render out.png # render to a PNG only (no window)
    python apps/gui/window.py --size 96        # grid resolution (default 64)

This is the first-GUI proof of concept; planning/24-first-gui.md describes the
path from here (a single returned vector decoded to a frame; the window living in
the Rust orchestrator rather than host tkinter).
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


def _compile_frame():
    """Compile frame.su and return its `pixel` function + the _VSA runtime."""
    from sutra_compiler import compile_su
    # dim=8 — frame.su uses only make_real + arithmetic; measured exact at
    # dim=8 (2026-05-27 audit, planning/27-substrate-honesty-audit-2026-05-27.md).
    mod = compile_su(DEMO_GUI / "frame.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.pixel, mod._VSA


def render_field(size: int = 64) -> np.ndarray:
    """Return a (size, size) float array of substrate-computed brightness.

    Each cell is one real call to frame.su's `pixel(x, y)` on the substrate,
    with x, y mapped to centred coordinates in [-1, 1].
    """
    pixel, vsa = _compile_frame()
    field = np.empty((size, size), dtype=np.float64)
    for j in range(size):  # row -> y
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):  # col -> x
            cx = 2.0 * i / (size - 1) - 1.0
            field[j, i] = float(vsa.real(pixel(cx, cy)))  # SUBSTRATE value
    return field


def colormap(field: np.ndarray) -> np.ndarray:
    """Map a brightness field to an (H, W, 3) uint8 heat image.

    Normalisation + colour are display only; the field values are the
    substrate's. Clamp to [0, 1] (the glow goes negative past the unit disc),
    then a black -> red -> yellow -> white ramp.
    """
    v = np.clip(field, 0.0, 1.0)
    r = np.clip(2.0 * v, 0, 1)
    g = np.clip(2.0 * v - 1.0, 0, 1)
    b = np.clip(4.0 * v - 3.0, 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def to_image(field: np.ndarray, upscale: int = 8):
    from PIL import Image

    img = Image.fromarray(colormap(field), mode="RGB")
    if upscale > 1:
        img = img.resize((img.width * upscale, img.height * upscale), Image.NEAREST)
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="Yantra first GUI (substrate pixels)")
    ap.add_argument("--render", metavar="PNG", help="render to a PNG and exit (no window)")
    ap.add_argument("--size", type=int, default=64, help="grid resolution (default 64)")
    args = ap.parse_args()

    print(f"[gui] computing a {args.size}x{args.size} field on the substrate "
          f"({args.size * args.size} pixel calls)...")
    field = render_field(args.size)
    print(f"[gui] field: centre={field[args.size//2, args.size//2]:.4f} "
          f"corner={field[0, 0]:.4f} min={field.min():.4f} max={field.max():.4f}")
    img = to_image(field)

    if args.render:
        img.save(args.render)
        print(f"[gui] saved {args.render} ({img.width}x{img.height})")
        return

    import tkinter as tk
    from PIL import ImageTk

    root = tk.Tk()
    root.title("Yantra — first GUI (substrate-computed pixels)")
    tkimg = ImageTk.PhotoImage(img)
    tk.Label(root, image=tkimg).pack()
    tk.Label(root, text="every pixel computed by frame.su on the Sutra substrate").pack()
    root.mainloop()


if __name__ == "__main__":
    main()
