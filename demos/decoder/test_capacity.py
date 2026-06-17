"""D6 — capacity / scaling of the learned substrate decoder.

Wider decoders reconstruct better: this sweeps the hidden width on a fixed target and confirms
the reconstruction error falls monotonically with capacity (the expected scaling for an
implicit neural representation). Measured, deterministic (seed 0). Same substrate forward
(matmul + hadamard cubic), host Adam.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _nn():
    spec = importlib.util.spec_from_file_location("substrate_nn", _DIR / "substrate_nn.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _target(nn, size, dt, dev):
    import torch
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    b1 = torch.exp(-8.0 * ((xx + 0.3) ** 2 + (yy + 0.3) ** 2))
    b2 = 0.7 * torch.exp(-14.0 * ((xx - 0.4) ** 2 + (yy - 0.2) ** 2))
    t = b1 + b2
    return (t / t.max()).detach()


def test_reconstruction_improves_with_decoder_width():
    import math
    pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    size, nf = 24, 4
    target = _target(nn, size, dt, dev)

    widths = [8, 32, 64]
    mses = []
    for H in widths:
        params = nn.init_mlp([nn.decoder_input_dim(nf), H, H, 1], dt, dev, seed=0)
        losses = nn.fit_decoder(params, target, size, num_freqs=nf, steps=500, lr=0.01)
        assert all(math.isfinite(v) for v in losses), f"H={H} training went non-finite"
        mses.append(losses[-1])

    # Monotonic-ish: each wider decoder is at least as good (allow 15% numerical slack)...
    for small, big in zip(mses, mses[1:]):
        assert big <= small * 1.15, f"wider decoder not better: {mses}"
    # ...and the widest clearly beats the narrowest (≥3 dB PSNR gain).
    assert mses[-1] < mses[0] * 0.5, f"capacity gave no real gain: {mses}"
    assert nn.psnr(mses[-1]) - nn.psnr(mses[0]) > 3.0, \
        f"PSNR gain from capacity too small: {[round(nn.psnr(m),1) for m in mses]}"
