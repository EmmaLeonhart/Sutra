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
