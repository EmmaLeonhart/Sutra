"""Whole-frame GUI render — the substrate returns ONE vector that IS the frame.

Emma's model (2026-06-11): instead of calling `pixel(x, y)` once per pixel (N²
substrate calls, see window.py), the substrate computes the whole frame in a SINGLE
op and returns it as one flat buffer vector; the host just reshapes it to N×N and
paints. No decoder, no learning.

`frame_whole.su`'s `frame(x, y, ones) = ones - hadamard(x,x) - hadamard(y,y)` is
`1 - x² - y²` evaluated ELEMENTWISE over the whole coordinate grid at once, via the
`hadamard` (elementwise/buffer) product. `x`, `y`, `ones` are length-(N·N) coordinate
buffers this host builds — compile-time grid geometry, the codebook-like boundary.
The substrate computes the frame; the host reads the finished buffer at the display
boundary, reshapes, and paints — the same host-is-I/O split as window.py, but one
substrate op instead of N².
"""
from __future__ import annotations

import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _compile_frame_whole():
    """Compile frame_whole.su and return its `frame` function + the _VSA runtime."""
    from sutra_compiler import compile_su
    # dim=8 — frame_whole.su uses only make_real + hadamard + arithmetic, no
    # basis_vector; the coordinate BUFFERS are length N·N regardless of runtime_dim
    # (hadamard/sub are elementwise over whatever length they're given).
    mod = compile_su(DEMO_GUI / "frame_whole.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.frame, mod._VSA


def render_field_whole(size: int = 64):
    """Return a (size, size) array of substrate-computed brightness, produced by a
    SINGLE call to frame_whole.su's `frame` over the whole coordinate grid.

    The coordinate mapping matches window.render_field: pixel (j, i) → centred
    (cx, cy) in [-1, 1], raster order (j = row → y, i = col → x).
    """
    import torch

    frame, vsa = _compile_frame_whole()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):          # row -> y
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):      # col -> x
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    buf = frame(X, Y, ones)                       # ONE substrate op -> the whole frame
    buf = buf.real if buf.is_complex() else buf   # display boundary: read the real field
    return buf.reshape(size, size).detach().to("cpu").numpy()


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Whole-frame substrate render.")
    ap.add_argument("--size", type=int, default=64, help="grid resolution")
    ap.add_argument("--render", metavar="OUT.png", help="render to PNG (needs Pillow)")
    args = ap.parse_args()

    field = render_field_whole(args.size)
    print(f"rendered {args.size}x{args.size} whole-frame buffer on the substrate "
          f"(centre={field[args.size // 2, args.size // 2]:.3f}, "
          f"corner={field[0, 0]:.3f})")
    if args.render:
        try:
            from PIL import Image
        except ImportError:
            print("Pillow not installed; skipping PNG render.", file=sys.stderr)
            return
        import numpy as np

        norm = np.clip((field + 1.0) / 2.0, 0.0, 1.0)
        Image.fromarray((norm * 255).astype("uint8")).save(args.render)
        print(f"wrote {args.render}")


if __name__ == "__main__":
    main()
