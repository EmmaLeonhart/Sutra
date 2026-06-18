"""D2 — Fourier-feature input encoding + the substrate-MLP recipe.

D1 found the substrate's tanh/sin are canonical-vector ops, so the decoder's nonlinearity is a
hadamard polynomial (cubic) and expressivity comes from a FOURIER-FEATURE encoding of the input
coordinates — host-built input geometry, the same compile-time boundary as the X/Y grid (the
learned forward, matmul + cubic, stays on the substrate). These tests settle the recipe: the
encoding is well-formed, a batched substrate MLP over Fourier features fits a high-frequency
target NaN-free, and Fourier features beat raw coordinates (the whole point of the encoding).
"""
from __future__ import annotations

import importlib.util
import math
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _nn():
    spec = importlib.util.spec_from_file_location("substrate_nn", _DIR / "substrate_nn.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fourier_features_shape_and_bounded():
    torch = pytest.importorskip("torch")
    nn = _nn()
    coords = torch.rand(5, 2) * 2 - 1            # (N=5, d=2) in [-1,1]
    ff = nn.fourier_features(coords, num_freqs=4)
    assert tuple(ff.shape) == (5, 2 * (1 + 2 * 4)), f"unexpected feature dim: {ff.shape}"
    # the sin/cos columns (everything past the raw coords) are bounded in [-1,1]
    assert (ff[:, 2:].abs() <= 1.0 + 1e-6).all(), "sin/cos features left [-1,1]"


def _fit_wave(nn, use_fourier: bool, steps: int = 500):
    import torch
    torch.manual_seed(0)
    _dense, _cube, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    x = torch.linspace(-1, 1, 64, dtype=dt, device=dev).reshape(64, 1)
    Y = torch.sin(3.0 * math.pi * x).T.detach()                       # (1, 64) target
    if use_fourier:
        feats = nn.fourier_features(x, num_freqs=4).to(dt)            # (64, 9)
    else:
        feats = x
    X = feats.T.contiguous()                                         # (in, 64)
    params = nn.init_mlp([X.shape[0], 32, 32, 1], dt, dev, seed=0)
    flat = [t for wb in params for t in wb]
    opt = torch.optim.Adam(flat, lr=0.01)
    losses = []
    for _ in range(steps):
        opt.zero_grad()
        pred = nn.mlp_forward(params, X)                             # (1, 64)
        loss = ((pred - Y) ** 2).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    return losses


def test_substrate_mlp_fits_a_wave_with_fourier_features():
    pytest.importorskip("torch")
    import numpy as np
    nn = _nn()
    losses = _fit_wave(nn, use_fourier=True)
    assert all(np.isfinite(losses)), "training went non-finite (cubic blew up)"
    assert losses[-1] < 0.05, f"Fourier-feature substrate MLP did not fit the wave: final {losses[-1]:.4f}"


def test_fourier_features_beat_raw_coordinates():
    pytest.importorskip("torch")
    nn = _nn()
    fourier = _fit_wave(nn, use_fourier=True)[-1]
    raw = _fit_wave(nn, use_fourier=False)[-1]
    assert fourier < raw, f"Fourier features did not beat raw coords: fourier={fourier:.4f} raw={raw:.4f}"


# --- on-substrate Fourier encoding (closes the 2026-06-17 transcendentals finding) ---
# `fourier_features_substrate` runs the sin/cos on the substrate via the `sin_buf`/`cos_buf`
# compiler primitive instead of host torch.sin/cos. It must reproduce the host encoding within
# the trig-table precision, and a decoder built on it must fit the same wave.

def test_substrate_fourier_encoding_matches_host():
    torch = pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    coords = nn.coord_grid(16, vsa.dtype, vsa.device)
    host = nn.fourier_features(coords, num_freqs=6)
    sub = nn.fourier_features_substrate(coords, num_freqs=6)
    assert host.shape == sub.shape, f"shape mismatch: {host.shape} vs {sub.shape}"
    # float32 + N=4096 trig-table precision — the same bound the compiler test uses.
    err = float((host - sub).abs().max())
    assert err < 1e-3, f"on-substrate Fourier encoding diverged from host: max |Δ| {err}"


def test_substrate_fourier_encoding_is_differentiable():
    """The substrate encoding keeps autograd (sin_buf is differentiable) — so the coordinate
    encoding could itself be trained, the SIREN-style path the primitive unblocks."""
    torch = pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    coords = torch.rand(8, 2, dtype=vsa.dtype, device=vsa.device) * 2 - 1
    coords = coords.detach().requires_grad_(True)
    ff = nn.fourier_features_substrate(coords, num_freqs=4)
    assert ff.requires_grad, "substrate Fourier encoding detached the autograd graph"
    ff.sum().backward()
    assert coords.grad is not None and torch.isfinite(coords.grad).all(), "no/!finite grad through encoding"


def _fit_wave_substrate_encoding(nn, steps: int = 500):
    import torch
    torch.manual_seed(0)
    _dense, _cube, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    x = torch.linspace(-1, 1, 64, dtype=dt, device=dev).reshape(64, 1)
    Y = torch.sin(3.0 * math.pi * x).T.detach()
    feats = nn.fourier_features_substrate(x, num_freqs=4).to(dt)
    X = feats.T.contiguous()
    params = nn.init_mlp([X.shape[0], 32, 32, 1], dt, dev, seed=0)
    flat = [t for wb in params for t in wb]
    opt = torch.optim.Adam(flat, lr=0.01)
    losses = []
    for _ in range(steps):
        opt.zero_grad()
        loss = ((nn.mlp_forward(params, X) - Y) ** 2).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    return losses


def test_decoder_fits_wave_with_substrate_fourier_encoding():
    pytest.importorskip("torch")
    import numpy as np
    nn = _nn()
    losses = _fit_wave_substrate_encoding(nn)
    assert all(np.isfinite(losses)), "training went non-finite with the substrate encoding"
    assert losses[-1] < 0.05, f"decoder on the substrate encoding did not fit the wave: {losses[-1]:.4f}"
