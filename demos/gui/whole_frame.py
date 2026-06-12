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


def _compile_frame_moving():
    """Compile frame_moving.su and return its `frame_at` function + the _VSA."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_moving.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.frame_at, mod._VSA


def render_field_moving(size: int = 64, center_x: float = 0.0):
    """Return a (size, size) array for a glow centred at x=`center_x` — `1 - (x -
    center_x)² - y²`, computed in ONE substrate op (frame_moving.su's `frame_at`).
    Sweep `center_x` across calls to animate the glow sliding horizontally.
    """
    import torch

    frame_at, vsa = _compile_frame_moving()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    cx_buf = torch.full((size * size,), float(center_x), dtype=dt, device=dev)
    buf = frame_at(X, Y, ones, cx_buf)            # ONE substrate op -> the whole frame
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


def _compile_layout():
    """Compile frame_layout.su -> (layout, _VSA). Composes glow (left) + ring (right)
    via a region mask, one substrate pass."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_layout.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return mod.layout, mod._VSA


def render_layout(size: int = 64, radius: float = 0.5):
    """Return a (size, size) frame with the glow in the left half and the ring in the
    right half, composed via a region mask in one substrate op (frame_layout.su)."""
    import torch

    layout, vsa = _compile_layout()
    dt, dev = vsa.dtype, vsa.device
    xs, ys, mask = [], [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
            mask.append(1.0 if cx < 0.0 else 0.0)   # left region = glow
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    rad = torch.full((size * size,), float(radius), dtype=dt, device=dev)
    mL = torch.tensor(mask, dtype=dt, device=dev)
    out = layout(X, Y, ones, mL, rad)
    out = out.real if out.is_complex() else out
    return out.reshape(size, size).detach().to("cpu").numpy()


def _compile_rgb():
    """Compile frame_rgb.su -> (glow, ring, gradient, _VSA) channel fields."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_rgb.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return mod.glow, mod.ring, mod.gradient, mod._VSA


def render_rgb(size: int = 64, radius: float = 0.5):
    """Return a (size, size, 3) colour image. Each channel is a whole-frame field
    computed in one substrate op (frame_rgb.su): R=glow, G=ring, B=horizontal gradient.
    The host stacks the three substrate-computed channels (display assembly)."""
    import numpy as np
    import torch

    glow, ring, gradient, vsa = _compile_rgb()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    rad = torch.full((size * size,), float(radius), dtype=dt, device=dev)
    half = torch.full((size * size,), 0.5, dtype=dt, device=dev)

    def chan(v):
        v = v.real if v.is_complex() else v
        return v.reshape(size, size).detach().to("cpu").numpy()

    r = chan(glow(X, Y, ones))
    g = chan(ring(X, Y, ones, rad))
    b = chan(gradient(X, ones, half))
    return np.stack([r, g, b], axis=-1)


def _compile_ring():
    """Compile frame_ring.su and return its `ring` function + the _VSA."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_ring.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.ring, mod._VSA


def render_field_ring(size: int = 64, radius: float = 0.5):
    """Return a (size, size) array of a concentric ring, `1 - (x² + y² - radius)²`,
    computed in ONE substrate op (frame_ring.su's `ring`). The bright locus is the
    circle x² + y² = radius.
    """
    import torch

    ring, vsa = _compile_ring()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    rad = torch.full((size * size,), float(radius), dtype=dt, device=dev)
    buf = ring(X, Y, ones, rad)                    # ONE substrate op -> the whole frame
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


def _compile_click_frame():
    """Compile click_frame.su -> (flip, frame_gated, _VSA). `flip` toggles the 0/1
    state on the substrate; `frame_gated` renders the glow gated by that state."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "click_frame.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.flip, mod.frame_gated, mod._VSA


def click_frames(size: int = 64, clicks: int = 4):
    """Interaction driven by SUBSTRATE state: each click flips a 0/1 state on the
    substrate (click_frame.su's `flip`), then renders the glow GATED by that state
    (visible when 1, blank when 0). Returns a list of `clicks` (size, size) arrays —
    the frame the user would see after each click. The state lives in the substrate
    recur slot across clicks; the host reads it only to drive the render.
    """
    import torch

    flip, frame_gated, vsa = _compile_click_frame()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    out = []
    for _ in range(clicks):
        st = flip()                                  # substrate-state toggle
        g = float((st.real if st.is_complex() else st)[vsa.semantic_dim + vsa.AXIS_REAL])
        gate = torch.full((size * size,), g, dtype=dt, device=dev)
        buf = frame_gated(X, Y, ones, gate)          # one-op gated render
        buf = buf.real if buf.is_complex() else buf
        out.append(buf.reshape(size, size).detach().to("cpu").numpy())
    return out


def _compile_moving_glow():
    """Compile moving_glow.su -> (step, frame_at, _VSA). `step` is the substrate-RNN
    that advances the glow centre on the substrate; `frame_at` renders the whole frame
    at a centre."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "moving_glow.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.step, mod.frame_at, mod._VSA


def animate_moving_glow(size: int = 64, frames: int = 8):
    """Animation driven by a SUBSTRATE-RNN: each frame advances the glow centre on
    the substrate (moving_glow.su's `step`), then renders the whole frame at that
    centre in one op. Returns a list of `frames` (size, size) arrays. The centre
    lives in the substrate recur slot across ticks; the host reads it only to drive
    the render (display boundary), never to feed the recurrence.
    """
    import torch

    step, frame_at, vsa = _compile_moving_glow()
    dt, dev = vsa.dtype, vsa.device
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    out = []
    for _ in range(frames):
        cx_vec = step()                                  # substrate-RNN advance
        cx_val = float((cx_vec.real if cx_vec.is_complex() else cx_vec)
                       [vsa.semantic_dim + vsa.AXIS_REAL])
        cx_buf = torch.full((size * size,), cx_val, dtype=dt, device=dev)
        buf = frame_at(X, Y, ones, cx_buf)               # one-op whole-frame render
        buf = buf.real if buf.is_complex() else buf
        out.append(buf.reshape(size, size).detach().to("cpu").numpy())
    return out


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
