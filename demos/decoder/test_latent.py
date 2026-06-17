"""D7 — latent-conditioned decoder: GENERATION, not just reconstruction.

An auto-decoder trains the shared substrate decoder weights + a per-image latent z over a SET
of targets, so each latent renders its image AND the latent continuously controls the output —
interpolating between two learned latents GENERATES intermediate frames. Here: two blobs at
±0.4 in x; after training, lerping z from z_A to z_B sweeps the generated blob across the
frame. The render forward is the substrate (matmul + hadamard cubic); Adam (over weights + the
latents) is host-side.
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


def _blob(nn, cx, size, dt, dev):
    import torch
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    t = torch.exp(-10.0 * ((xx - cx) ** 2 + yy ** 2))
    return (t / t.max()).detach()


def _centroid_x(img, size, dt, dev):
    import torch
    w = img.clamp(0.0, None)
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    xx = lin.reshape(1, -1).expand(size, -1)
    return float((w * xx).sum() / (w.sum() + 1e-9))


def _train_autodecoder(nn, size=20, nf=4, ld=4, steps=1200):
    import torch
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    torch.manual_seed(0)
    A, B = _blob(nn, -0.4, size, dt, dev), _blob(nn, 0.4, size, dt, dev)
    params = nn.init_mlp([nn.latent_input_dim(nf, ld), 64, 64, 1], dt, dev, seed=0)
    zA = torch.empty(ld, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
    zB = torch.empty(ld, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
    nn.fit_autodecoder(params, [zA, zB], [A, B], size, num_freqs=nf, steps=steps)
    return params, zA, zB, A, B, (size, nf, dt, dev)


def test_autodecoder_reconstructs_each_latent():
    pytest.importorskip("torch")
    nn = _nn()
    params, zA, zB, A, B, (size, nf, dt, dev) = _train_autodecoder(nn)
    mA = float(((nn.render_decoder_latent_torch(params, zA, size, nf) - A) ** 2).mean().detach())
    mB = float(((nn.render_decoder_latent_torch(params, zB, size, nf) - B) ** 2).mean().detach())
    assert mA < 0.02 and mB < 0.02, f"per-latent reconstruction failed: A={mA:.4f} B={mB:.4f}"


def test_latent_interpolation_generates_between_images():
    """Lerping the latent z_A→z_B sweeps the generated blob from A's position to B's — the
    latent continuously controls the output (generation, not just reconstruction)."""
    import torch
    pytest.importorskip("torch")
    nn = _nn()
    params, zA, zB, A, B, (size, nf, dt, dev) = _train_autodecoder(nn)
    alphas = [0.0, 0.25, 0.5, 0.75, 1.0]
    cxs = []
    for a in alphas:
        z = zA + (zB - zA) * a
        img = nn.render_decoder_latent_torch(params, z, size, nf).detach()
        assert torch.isfinite(img).all(), f"generated frame non-finite at α={a}"
        cxs.append(_centroid_x(img, size, dt, dev))
    # endpoints land near the two training blobs (−0.4 / +0.4)...
    assert cxs[0] < -0.2 and cxs[-1] > 0.2, f"endpoints not separated by latent: {cxs}"
    # ...and the sweep is monotonic (small slack) — the latent smoothly generates between them.
    for lo, hi in zip(cxs, cxs[1:]):
        assert hi >= lo - 0.03, f"latent interpolation not monotonic: {cxs}"
    assert cxs[-1] - cxs[0] > 0.4, f"latent did not move the generated content: {cxs}"
