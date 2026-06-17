"""D4 — the learned decoder reconstructs an arbitrary image (the headline milestone).

Trains the substrate coordinate decoder's weights (host-side Adam) to reconstruct a target the
analytic hero/button renders cannot produce — two off-centre gaussian blobs of different size
and intensity — by MSE through the substrate render. This is "the decoder learns an arbitrary
frame": every forward op on the substrate, only the optimizer host-side.
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


def _two_blobs(size, dt, dev):
    """A target the analytic render can't make: two off-centre gaussians, normalised to [0,1]."""
    import torch
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    g1 = torch.exp(-8.0 * ((xx + 0.3) ** 2 + (yy + 0.3) ** 2))
    g2 = 0.7 * torch.exp(-14.0 * ((xx - 0.4) ** 2 + (yy - 0.2) ** 2))
    t = g1 + g2
    return (t / t.max()).detach()


def test_decoder_reconstructs_an_arbitrary_image():
    import math
    pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    size, nf = 24, 4
    target = _two_blobs(size, dt, dev)
    params = nn.init_mlp([nn.decoder_input_dim(nf), 64, 64, 1], dt, dev, seed=0)
    losses = nn.fit_decoder(params, target, size, num_freqs=nf, steps=800, lr=0.01)

    assert all(math.isfinite(v) for v in losses), "reconstruction training went non-finite"
    final = losses[-1]
    # Measured ~0.0058 (PSNR ~22 dB); assert comfortably below that and far below the start.
    assert final < 0.02, f"decoder did not reconstruct the image: final MSE {final:.4f}"
    assert nn.psnr(final) > 17.0, f"reconstruction PSNR too low: {nn.psnr(final):.1f} dB"
    assert final < losses[0] * 0.01, f"training did not do the work: {losses[0]:.2f} -> {final:.4f}"
