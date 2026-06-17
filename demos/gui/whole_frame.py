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


def _compile_checker():
    """Compile frame_checker.su and return its `checker` function + the _VSA."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_checker.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.checker, mod._VSA


def render_checker(size: int = 64, block: int = 8):
    """Return a (size, size) checkerboard, `0.5 * (1 + px*py)`, computed in ONE
    substrate op (frame_checker.su). px/py are host-built cell-parity buffers
    (coordinate-derived grid geometry, the frame_layout mask precedent): +1/-1 by
    `(col // block) % 2` / `(row // block) % 2`."""
    import torch

    checker, vsa = _compile_checker()
    dt, dev = vsa.dtype, vsa.device
    pxs, pys = [], []
    for j in range(size):
        py = 1.0 if (j // block) % 2 == 0 else -1.0
        for i in range(size):
            px = 1.0 if (i // block) % 2 == 0 else -1.0
            pxs.append(px)
            pys.append(py)
    PX = torch.tensor(pxs, dtype=dt, device=dev)
    PY = torch.tensor(pys, dtype=dt, device=dev)
    ones = torch.ones(size * size, dtype=dt, device=dev)
    half = torch.full((size * size,), 0.5, dtype=dt, device=dev)
    buf = checker(ones, PX, PY, half)              # ONE substrate op -> the whole frame
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


def _compile_diag():
    """Compile frame_diag.su and return its `diag` function + the _VSA."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_diag.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.diag, mod._VSA


def render_diag(size: int = 64):
    """Return a (size, size) diagonal gradient, `0.5 * (1 + 0.5*(x + y))`, computed
    in ONE substrate op (frame_diag.su): 0 at top-left, 1 at bottom-right."""
    import torch

    diag, vsa = _compile_diag()
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
    half = torch.full((size * size,), 0.5, dtype=dt, device=dev)
    buf = diag(X, Y, ones, half)                   # ONE substrate op -> the whole frame
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


def _compile_quad():
    """Compile frame_quad.su and return its `quad` function + the _VSA."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "frame_quad.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    return mod.quad, mod._VSA


def render_quad(size: int = 64, radius: float = 0.5, block: int = 8):
    """Return a (size, size) FOUR-region frame: glow (top-left), ring (top-right),
    diagonal gradient (bottom-left), checker (bottom-right), composed via three
    host-provided quadrant masks + the substrate-derived fourth complement, in ONE
    substrate op (frame_quad.su)."""
    import torch

    quad, vsa = _compile_quad()
    dt, dev = vsa.dtype, vsa.device
    xs, ys, m0s, m1s, m2s, pxs, pys = [], [], [], [], [], [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        py = 1.0 if (j // block) % 2 == 0 else -1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
            m0s.append(1.0 if (cx < 0.0 and cy < 0.0) else 0.0)   # top-left
            m1s.append(1.0 if (cx >= 0.0 and cy < 0.0) else 0.0)  # top-right
            m2s.append(1.0 if (cx < 0.0 and cy >= 0.0) else 0.0)  # bottom-left
            pxs.append(1.0 if (i // block) % 2 == 0 else -1.0)
            pys.append(py)
    n2 = size * size
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(n2, dtype=dt, device=dev)
    M0 = torch.tensor(m0s, dtype=dt, device=dev)
    M1 = torch.tensor(m1s, dtype=dt, device=dev)
    M2 = torch.tensor(m2s, dtype=dt, device=dev)
    rad = torch.full((n2,), float(radius), dtype=dt, device=dev)
    half = torch.full((n2,), 0.5, dtype=dt, device=dev)
    PX = torch.tensor(pxs, dtype=dt, device=dev)
    PY = torch.tensor(pys, dtype=dt, device=dev)
    buf = quad(X, Y, ones, M0, M1, M2, rad, half, PX, PY)  # ONE substrate op
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


_HERO_MOD = None


def _hero_module():
    """Compile frame_hero.su ONCE and cache the module in-process. The steering
    loop (item 1c) and the soak (1d) render hundreds of frames; recompiling each
    time would dominate the wall clock, so the compiled module is reused."""
    global _HERO_MOD
    if _HERO_MOD is None:
        from sutra_compiler import compile_su
        _HERO_MOD = compile_su(DEMO_GUI / "frame_hero.su",
                               llm_model="unused-no-basis-vectors",
                               runtime_dim=8, verbose=False)
    return _HERO_MOD


def _compile_hero():
    """Return (hero, _VSA). The θ-parameterized hero render core for the
    warmer/colder a1 steering demo (queue item 1a)."""
    mod = _hero_module()
    return mod.hero, mod._VSA


# θ axis order — the single source of truth the host compositor and the SPSA
# optimizer (item 1b) share. Each value is broadcast to every pixel as a buffer;
# changing θ never recompiles (a1 spec: runtime parameters, no recompile).
HERO_THETA_AXES = ("cx", "cy", "invs", "bright", "radius", "accent", "bg",
                   "cr", "cg", "cb")

# A neutral, on-screen default θ: centred glow, unit scale/brightness, a faint
# ring accent, mid background, warm-white tint (cr,cg,cb). The SPSA loop perturbs
# around a θ like this.
HERO_THETA_DEFAULT = {
    "cx": 0.0, "cy": 0.0, "invs": 1.0, "bright": 1.0,
    "radius": 0.5, "accent": 0.25, "bg": 0.0,
    "cr": 1.0, "cg": 0.85, "cb": 0.6,
}


def render_hero(size: int = 64, theta: dict | None = None):
    """Return a (size, size) hero field driven by the parameter vector `theta`,
    computed in ONE substrate op (frame_hero.su's `hero`). `theta` maps each axis
    in HERO_THETA_AXES to a scalar; missing axes fall back to HERO_THETA_DEFAULT.
    The scalars become per-pixel broadcast buffers — so the optimizer morphs the
    hero by changing these call arguments, with no recompile."""
    import torch

    hero, vsa = _compile_hero()
    dt, dev = vsa.dtype, vsa.device
    th = dict(HERO_THETA_DEFAULT)
    if theta:
        th.update(theta)
    xs, ys = [], []
    for j in range(size):              # row -> y
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):          # col -> x
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    n2 = size * size
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(n2, dtype=dt, device=dev)

    def bcast(name):
        return torch.full((n2,), float(th[name]), dtype=dt, device=dev)

    buf = hero(X, Y, ones, bcast("cx"), bcast("cy"), bcast("invs"),
               bcast("bright"), bcast("radius"), bcast("accent"), bcast("bg"))
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size).detach().to("cpu").numpy()


def hero_grid(size, dt, dev):
    """The coordinate geometry the substrate render consumes: flat length-(size*size)
    `(X, Y, ones)` buffers for an `size x size` grid over [-1, 1]^2. Host-side I/O
    (compile-time geometry), shared by the numpy and the differentiable render paths."""
    import torch

    xs, ys = [], []
    for j in range(size):              # row -> y
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):          # col -> x
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    n2 = size * size
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(n2, dtype=dt, device=dev)
    return X, Y, ones


def render_hero_torch(size: int = 64, theta: dict | None = None):
    """DIFFERENTIABLE hero render: return the (size, size) hero field as a TORCH
    TENSOR that KEEPS its autograd graph — the load-bearing path for Adam steering
    (queue R1/R2). Unlike `render_hero` (which `.detach().numpy()`s for display),
    this keeps gradients flowing to θ THROUGH the compiled Sutra `hero` op.

    `theta` maps each axis in HERO_THETA_AXES to either a 0-d torch tensor (typically
    a `requires_grad=True` parameter the optimizer updates) or a Python float; missing
    axes fall back to HERO_THETA_DEFAULT as plain (grad-free) constants. The broadcast
    to per-pixel buffers is grad-preserving (`val * ones`, NOT `torch.full(..., float(val))`
    which would sever the graph). The returned tensor is `(size, size)`, real-valued,
    with `grad_fn` set when any θ entry requires grad — call `.backward()` on a scalar
    loss of it to get ∂loss/∂θ through the substrate render. No `.detach()` here: this
    is the differentiable boundary, not the display boundary."""
    import torch

    hero, vsa = _compile_hero()
    dt, dev = vsa.dtype, vsa.device
    th = dict(HERO_THETA_DEFAULT)
    if theta:
        th.update(theta)
    X, Y, ones = hero_grid(size, dt, dev)

    def bcast(name):
        v = th[name]
        if isinstance(v, torch.Tensor):
            # 0-d (or broadcastable) tensor -> grad-preserving per-pixel buffer.
            return v.to(dtype=dt, device=dev) * ones
        return torch.full((ones.shape[0],), float(v), dtype=dt, device=dev)

    buf = hero(X, Y, ones, bcast("cx"), bcast("cy"), bcast("invs"),
               bcast("bright"), bcast("radius"), bcast("accent"), bcast("bg"))
    buf = buf.real if buf.is_complex() else buf
    return buf.reshape(size, size)


def render_hero_rgb(size: int = 64, theta: dict | None = None):
    """Return a (size, size, 3) COLOUR hero driven by θ, computed as THREE
    whole-frame substrate ops (frame_hero.su's `hero_channel`): R, G, B are the
    same composed hero tinted on the substrate by θ's (cr, cg, cb) weights. The
    host stacks the three substrate-computed channels (display assembly, the
    frame_rgb precedent) — no host colour arithmetic touches the field. θ changing
    needs no recompile (the tints are broadcast buffers)."""
    import numpy as np
    import torch

    mod = _hero_module()
    hero_channel, vsa = mod.hero_channel, mod._VSA
    dt, dev = vsa.dtype, vsa.device

    th = dict(HERO_THETA_DEFAULT)
    if theta:
        th.update(theta)
    xs, ys = [], []
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            xs.append(cx)
            ys.append(cy)
    n2 = size * size
    X = torch.tensor(xs, dtype=dt, device=dev)
    Y = torch.tensor(ys, dtype=dt, device=dev)
    ones = torch.ones(n2, dtype=dt, device=dev)

    def bcast(val):
        return torch.full((n2,), float(val), dtype=dt, device=dev)

    base = (X, Y, ones, bcast(th["cx"]), bcast(th["cy"]), bcast(th["invs"]),
            bcast(th["bright"]), bcast(th["radius"]), bcast(th["accent"]), bcast(th["bg"]))

    def chan(tint_name):
        buf = hero_channel(*base, bcast(th[tint_name]))   # ONE substrate op -> channel
        buf = buf.real if buf.is_complex() else buf
        return buf.reshape(size, size).detach().to("cpu").numpy()

    return np.stack([chan("cr"), chan("cg"), chan("cb")], axis=-1)


def render_hero_rgb_torch(size: int = 64, theta: dict | None = None):
    """DIFFERENTIABLE colour render: return the (size, size, 3) RGB hero as a TORCH
    TENSOR that KEEPS its autograd graph — the load-bearing path for RGB Adam steering
    (queue G1/G2). Unlike `render_hero_rgb` (which `.detach().numpy()`s each channel for
    display), this keeps gradients flowing to θ THROUGH the compiled Sutra `hero_channel`
    op, including to the per-channel colour tints `cr/cg/cb`.

    Each channel is the SAME composed mono hero tinted on the substrate by its tint
    (R←cr, G←cg, B←cb), so geometry axes (cx/cy/invs/bright/radius/accent/bg) carry grad
    through all three channels and each tint carries grad through only its own channel.
    `theta` maps each axis in HERO_THETA_AXES to a 0-d torch tensor (typically a
    `requires_grad=True` parameter) or a Python float; missing axes fall back to
    HERO_THETA_DEFAULT as grad-free constants. The broadcast is grad-preserving
    (`val * ones`, NOT `torch.full(..., float(val))` which severs the graph). The returned
    tensor is `(size, size, 3)`, real-valued, with `grad_fn` set when any θ entry requires
    grad. No `.detach()` here: this is the differentiable boundary, not the display one."""
    import torch

    mod = _hero_module()
    hero_channel, vsa = mod.hero_channel, mod._VSA
    dt, dev = vsa.dtype, vsa.device
    th = dict(HERO_THETA_DEFAULT)
    if theta:
        th.update(theta)
    X, Y, ones = hero_grid(size, dt, dev)

    def bcast(name):
        v = th[name]
        if isinstance(v, torch.Tensor):
            # 0-d (or broadcastable) tensor -> grad-preserving per-pixel buffer.
            return v.to(dtype=dt, device=dev) * ones
        return torch.full((ones.shape[0],), float(v), dtype=dt, device=dev)

    base = (X, Y, ones, bcast("cx"), bcast("cy"), bcast("invs"),
            bcast("bright"), bcast("radius"), bcast("accent"), bcast("bg"))

    def chan(tint_name):
        buf = hero_channel(*base, bcast(tint_name))   # ONE substrate op -> channel
        buf = buf.real if buf.is_complex() else buf
        return buf.reshape(size, size)

    return torch.stack([chan("cr"), chan("cg"), chan("cb")], dim=-1)


# --- Trainable click-button render (queue B1) ----------------------------------
#
# A clickable BUTTON as an (H, W, 3) colour frame: a quartic-squircle mask
# (button_frame.su's `button_channel`) composites a page-background colour and a
# button-fill colour per channel on the substrate. Continuous θ (colours, inverse
# size, centre) is differentiable through the compiled op — the render half of the
# trainable-button demo (owner-preference + CTR steering, B2/B3).
def _compile_button():
    """Compile button_frame.su and return its `button_channel` op + the _VSA runtime."""
    from sutra_compiler import compile_su
    mod = compile_su(DEMO_GUI / "button_frame.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8, verbose=False)
    return mod.button_channel, mod._VSA


# θ axis order — the continuous parameters the host compositor and the ButtonAdam
# optimizer (B3) share. cx,cy = centre; inv_w,inv_h = inverse half-extents (size,
# larger ⇒ smaller button); pr/pg/pb = page colour; fr/fg/fb = button-fill colour.
BUTTON_THETA_AXES = ("cx", "cy", "inv_w", "inv_h",
                     "pr", "pg", "pb", "fr", "fg", "fb")

# A neutral default: a wide, centred blue button on a light page.
BUTTON_THETA_DEFAULT = {
    "cx": 0.0, "cy": 0.0, "inv_w": 1.7, "inv_h": 3.5,
    "pr": 0.95, "pg": 0.95, "pb": 0.95,
    "fr": 0.20, "fg": 0.45, "fb": 0.90,
}


def render_button_torch(size: int = 64, theta: dict | None = None):
    """DIFFERENTIABLE button render: return the (size, size, 3) RGB button as a TORCH
    TENSOR that KEEPS its autograd graph, so a scalar loss on the button backpropagates to
    the continuous θ THROUGH the compiled Sutra `button_channel` op (the load-bearing fact
    for the ButtonAdam controller, B3).

    Each channel composites the page colour and the button-fill colour by the squircle mask
    in ONE substrate op; the host stacks the three channels (display assembly, the
    hero_channel/frame_rgb precedent). `theta` maps each axis in BUTTON_THETA_AXES to a 0-d
    torch tensor (typically `requires_grad=True`) or a float; missing axes fall back to
    BUTTON_THETA_DEFAULT. The broadcast is grad-preserving (`val * ones`, NOT
    `torch.full(float(val))` which severs the graph). No `.detach()`: this is the
    differentiable boundary, not the display boundary."""
    import torch

    button_channel, vsa = _compile_button()
    dt, dev = vsa.dtype, vsa.device
    th = dict(BUTTON_THETA_DEFAULT)
    if theta:
        th.update(theta)
    X, Y, ones = hero_grid(size, dt, dev)

    def bcast(name):
        v = th[name]
        if isinstance(v, torch.Tensor):
            return v.to(dtype=dt, device=dev) * ones
        return torch.full((ones.shape[0],), float(v), dtype=dt, device=dev)

    geom = (X, Y, ones, bcast("cx"), bcast("cy"), bcast("inv_w"), bcast("inv_h"))

    def chan(page_name, fill_name):
        buf = button_channel(*geom, bcast(page_name), bcast(fill_name))
        buf = buf.real if buf.is_complex() else buf
        return buf.reshape(size, size)

    return torch.stack([chan("pr", "fr"), chan("pg", "fg"), chan("pb", "fb")], dim=-1)


# --- Headline-glyph selector (a1 item 1a, discrete "copy" axis) ----------------
#
# The hero's headline is chosen from a small preset set by an argmax over θ's
# per-headline mixture weights (HOST-SIDE selection — the discrete copy axis; the
# SPSA optimizer nudges the weights, the host renders the winner). The glyph
# PIXELS are substrate output (render_glyph / font_bound_antipodal.su); only the
# which-headline choice and the banner placement are host-side composition (a1
# spec: the compositor is host-side — do not claim "one substrate program").

# Preset UPPERCASE headlines (A-Z / 0-9 only — the 36-glyph renderer's alphabet).
HERO_HEADLINES = ("SUTRA", "LEARN", "STEER", "WARMER")

_BANNER_CACHE: dict = {}


def _render_glyph(code: float):
    """Render one 5x5 glyph on the substrate via demos/font's render_glyph
    (font_bound_antipodal.su). Imported lazily so the gui module doesn't pull the
    font compile unless a headline is actually rasterized."""
    import pathlib as _pl
    import sys as _sys
    font_dir = _pl.Path(__file__).resolve().parent.parent / "font"
    if str(font_dir) not in _sys.path:
        _sys.path.insert(0, str(font_dir))
    import font_demo
    return font_demo.render_glyph(code)


def select_headline(theta: dict | None = None) -> str:
    """HOST-SIDE argmax over θ['headline_w'] (one weight per HERO_HEADLINES entry)
    → the headline string to render. The discrete copy axis of the a1 demo. With
    no weights, returns the first headline."""
    if not theta:
        return HERO_HEADLINES[0]
    w = theta.get("headline_w")
    if not w:
        return HERO_HEADLINES[0]
    n = len(HERO_HEADLINES)
    return HERO_HEADLINES[max(range(n),
                              key=lambda i: w[i] if i < len(w) else float("-inf"))]


def render_headline_banner(headline: str):
    """Rasterize `headline` into a binary banner field of shape (5, 5*len) by
    rendering each glyph ON THE SUBSTRATE (render_glyph). Cached per headline — the
    banner only changes when the discrete argmax headline changes, not per frame,
    so the per-frame render path stays cheap."""
    import numpy as np

    if headline in _BANNER_CACHE:
        return _BANNER_CACHE[headline]
    cols = [_render_glyph(float(ord(ch))) for ch in headline]
    banner = (np.concatenate(cols, axis=1) if cols
              else np.zeros((5, 0), dtype=np.float64))
    _BANNER_CACHE[headline] = banner
    return banner


def _banner_placement(banner, size: int, band: tuple):
    """Yield (frame_row, frame_col, banner_row, banner_col) for each frame cell the
    banner maps onto: the banner is centred horizontally in the top `band`, scaled
    nearest-neighbour keeping glyph aspect. Host-side placement geometry, shared by
    the field overlay and the RGB overlay."""
    hb, wb = banner.shape
    if hb == 0 or wb == 0:
        return
    r0, r1 = int(band[0] * size), int(band[1] * size)
    rows = max(1, r1 - r0)
    cols = max(1, min(size, int(rows * wb / hb)))
    c0 = (size - cols) // 2
    for j in range(rows):
        by = min(hb - 1, int(j * hb / rows))
        for i in range(cols):
            bx = min(wb - 1, int(i * wb / cols))
            yield r0 + j, c0 + i, by, bx


def render_hero_with_headline(size: int = 64, theta: dict | None = None,
                              band: tuple = (0.08, 0.30)):
    """The θ-parameterized hero field (render_hero) with the selected headline
    banner overlaid into a horizontal band near the top. Returns (field, headline).

    Substrate: the hero field (frame_hero.su) AND every glyph pixel (render_glyph).
    Host-side composition (named, per the a1 spec): the argmax headline choice and
    nearest-neighbour placement of the banner into the frame band. Lit banner cells
    are painted at full brightness over the hero field."""
    field = render_hero(size, theta)
    headline = select_headline(theta)
    banner = render_headline_banner(headline)            # (5, 5*n) binary, substrate
    for fr, fc, by, bx in _banner_placement(banner, size, band):
        if banner[by, bx] > 0.5:                         # lit glyph cell
            field[fr, fc] = 1.0                          # host paints the overlay
    return field, headline


def render_hero_full(size: int = 64, theta: dict | None = None,
                     band: tuple = (0.08, 0.30)):
    """The full demo frame: the θ-driven RGB hero (render_hero_rgb) with the
    selected headline banner overlaid white into the top band. Returns
    (rgb_image (size,size,3), headline).

    Substrate: the three colour channels (hero_channel) AND every glyph pixel.
    Host-side composition (named): the RGB stack, the argmax headline choice, and
    the banner placement. This is what the live steering window paints (item 1c)."""
    import numpy as np

    img = render_hero_rgb(size, theta)                   # (size,size,3) substrate channels
    headline = select_headline(theta)
    banner = render_headline_banner(headline)
    for fr, fc, by, bx in _banner_placement(banner, size, band):
        if banner[by, bx] > 0.5:
            img[fr, fc, :] = 1.0                          # white headline over all channels
    return img, headline


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
