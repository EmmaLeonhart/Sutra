"""Substrate neural-net building blocks for the learned decoder (D1+).

Compiles the trainable substrate layers (`dense.su`) and exposes them as differentiable torch
callables: a `dense`/`dense_tanh` layer whose weights are trained by a host optimizer via
autograd THROUGH the compiled substrate `matmul`. The forward pass is the substrate; the
optimizer is host-side (named so). The learned coordinate-MLP decoder (D3) stacks these.
"""
from __future__ import annotations

import pathlib
import sys

_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

_CACHE = {}


def compile_dense():
    """Compile dense.su once and cache it. Returns the compiled module (mod.dense,
    mod.dense_tanh, mod._VSA)."""
    if "dense" not in _CACHE:
        from sutra_compiler import compile_su
        _CACHE["dense"] = compile_su(_DIR / "dense.su",
                                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                                     verbose=False)
    return _CACHE["dense"]


def dense_layers():
    """Return (dense, dense_cube, _VSA): the substrate Linear layer, its cubic-activated
    variant, and the runtime (for dtype/device). `dense(W, x, b) = matmul(W, x) + b` with the
    autograd graph intact, so `W,b` are trainable by a host optimizer. `dense_cube` applies an
    elementwise cubic (hadamard) nonlinearity — the substrate's tanh/sin are canonical-vector
    ops, not elementwise over activation buffers (D1 finding)."""
    mod = compile_dense()
    return mod.dense, mod.dense_cube, mod._VSA


# --- D2: Fourier-feature input encoding + the substrate-MLP recipe ---
#
# The decoder's expressivity comes from a Fourier-feature encoding of the input coordinates
# (Tancik et al.): the substrate's tanh/sin can't run elementwise over activation buffers
# (D1), so instead of SIREN sin-activations we feed sin/cos of the coordinates as INPUT. That
# encoding is host-built input geometry — the same compile-time boundary as the X/Y grid; the
# LEARNED forward (matmul + cubic) stays on the substrate.

def fourier_features(coords, num_freqs: int = 4):
    """Encode `coords` (N, d) in [-1,1] as `[coords, sin(πf·coords), cos(πf·coords)]` for
    f ∈ {2^0..2^(num_freqs-1)} → (N, d·(1+2·num_freqs)). Host-built input geometry (not a
    substrate computation; the trainable decoder forward is the substrate part)."""
    import math
    import torch
    feats = [coords]
    for k in range(num_freqs):
        f = float(2 ** k) * math.pi
        feats.append(torch.sin(f * coords))
        feats.append(torch.cos(f * coords))
    return torch.cat(feats, dim=-1)


def init_mlp(sizes, dtype, device, seed: int = 0):
    """Initialise MLP params: a list of (W (out,in), b (out,1)) leaf tensors with
    requires_grad. Kaiming-ish scale (1/√in) keeps the cubic activation from blowing up."""
    import math
    import torch
    torch.manual_seed(seed)
    params = []
    for i in range(len(sizes) - 1):
        in_d, out_d = sizes[i], sizes[i + 1]
        W = (torch.randn(out_d, in_d, dtype=dtype, device=device) / math.sqrt(in_d))
        W = W.detach().requires_grad_(True)
        b = torch.zeros(out_d, 1, dtype=dtype, device=device, requires_grad=True)
        params.append((W, b))
    return params


def mlp_forward(params, X):
    """Batched substrate MLP forward. `X` is (in, N); `params` = [(W,b), …] with W (out,in),
    b (out,1). Hidden layers use the cubic activation; the final layer is linear. The forward
    is substrate ops (compiled `matmul` + hadamard cube); the host only chains the layers
    (named orchestration, the button-render pattern). Returns (out, N)."""
    dense, dense_cube, _vsa = dense_layers()
    h = X
    for W, b in params[:-1]:
        h = dense_cube(W, h, b)
    W, b = params[-1]
    return dense(W, h, b)


# --- D3: the whole-frame coordinate decoder ---

def coord_grid(size: int, dtype, device):
    """The coordinate geometry the decoder consumes: a (size*size, 2) grid of (x, y) in
    [-1,1]^2, raster order (row → y, col → x) — the same mapping the hero/button renders use.
    Host-side compile-time geometry (the codebook-like input boundary)."""
    import torch
    lin = torch.linspace(-1.0, 1.0, size, dtype=dtype, device=device)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")          # yy: row→y, xx: col→x
    return torch.stack([xx.reshape(-1), yy.reshape(-1)], dim=-1)   # (N², 2): (x, y)


def decoder_input_dim(num_freqs: int = 4, coord_dim: int = 2) -> int:
    """Input feature dimension after Fourier encoding (the decoder's first-layer in-size)."""
    return coord_dim * (1 + 2 * num_freqs)


def render_decoder_torch(params, size: int = 32, num_freqs: int = 4):
    """DIFFERENTIABLE whole-frame render of the LEARNED coordinate decoder: build the grid,
    Fourier-encode it (host input geometry), run the substrate MLP per pixel, reshape to the
    frame. Returns (size, size) for a 1-output decoder, or (size, size, C) for C>1 (RGB, D5).
    Keeps the autograd graph, so the weights `params` train by Adam through the substrate
    forward — the learned analogue of `render_button_torch`."""
    dt, dev = params[0][0].dtype, params[0][0].device
    coords = coord_grid(size, dt, dev)                        # (N², 2)
    feats = fourier_features(coords, num_freqs).to(dt)        # (N², F)
    X = feats.T.contiguous()                                  # (F, N²)
    out = mlp_forward(params, X)                              # (C, N²)
    if out.shape[0] == 1:
        return out.reshape(size, size)
    return out.T.reshape(size, size, out.shape[0])


# --- D4: train the decoder to reconstruct a target image ---

def fit_decoder(params, target, size: int, num_freqs: int = 4, steps: int = 800,
                lr: float = 0.01):
    """Train the substrate decoder's weights (host-side Adam) to reconstruct `target` (a
    (size,size) or (size,size,C) field) by MSE, via autograd through the substrate render.
    Returns the per-step loss list. The render is the substrate; Adam is host-side."""
    import torch
    flat = [t for wb in params for t in wb]
    opt = torch.optim.Adam(flat, lr=lr)
    losses = []
    for _ in range(steps):
        opt.zero_grad()
        pred = render_decoder_torch(params, size, num_freqs)
        loss = ((pred - target) ** 2).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    return losses


def psnr(mse: float) -> float:
    """Peak signal-to-noise ratio (dB) for a [0,1] image at the given MSE."""
    import math
    return float("inf") if mse <= 0 else 10.0 * math.log10(1.0 / mse)
