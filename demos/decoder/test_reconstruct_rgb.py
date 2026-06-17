"""D5 — the learned decoder reconstructs an arbitrary COLOUR image.

A 3-output coordinate decoder (render returns (size,size,3)) trained to reconstruct a colour
target the analytic render can't make. Same substrate forward (matmul + hadamard cubic), host
Adam; now per-channel. Confirms the decoder generalises from grayscale (D4) to RGB.
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


def _colour_target(size, dt, dev):
    """Two blobs in different colours, normalised to [0,1]^3 — not analytically renderable."""
    import torch
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    b1 = torch.exp(-8.0 * ((xx + 0.3) ** 2 + (yy + 0.3) ** 2))
    b2 = torch.exp(-14.0 * ((xx - 0.4) ** 2 + (yy - 0.2) ** 2))
    R, G, B = b1, 0.5 * b2, 0.9 * b2 + 0.2 * b1
    return torch.clamp(torch.stack([R, G, B], dim=-1), 0.0, 1.0).detach()


def test_decoder_reconstructs_a_colour_image():
    import math
    pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    size, nf = 24, 4
    target = _colour_target(size, dt, dev)
    params = nn.init_mlp([nn.decoder_input_dim(nf), 64, 64, 3], dt, dev, seed=0)

    rendered = nn.render_decoder_torch(params, size, nf)
    assert tuple(rendered.shape) == (size, size, 3), f"expected RGB frame, got {rendered.shape}"

    losses = nn.fit_decoder(params, target, size, num_freqs=nf, steps=800, lr=0.01)
    assert all(math.isfinite(v) for v in losses), "RGB reconstruction went non-finite"
    final = losses[-1]
    # Measured ~0.0087 (PSNR ~20.6 dB); assert comfortably below.
    assert final < 0.02, f"RGB decoder did not reconstruct: final MSE {final:.4f}"
    assert nn.psnr(final) > 16.0, f"RGB reconstruction PSNR too low: {nn.psnr(final):.1f} dB"
    assert final < losses[0] * 0.01, f"training did not do the work: {losses[0]:.2f} -> {final:.4f}"
