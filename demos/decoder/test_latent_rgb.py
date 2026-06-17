"""D13 — latent-conditioned RGB GENERATION (colour, not just grayscale).

Extends D7 (grayscale latent generation) to colour: an auto-decoder trains a 3-output
latent-conditioned decoder over two COLOUR targets (a red blob and a blue blob); each latent
reconstructs its colour, and interpolating the latent shifts the generated colour red→blue —
arbitrary-colour-image generation from a latent, on the substrate render.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent
_SIZE, _NF, _LD = 16, 4, 4
_TRAINED = {}


def _nn():
    spec = importlib.util.spec_from_file_location("substrate_nn", _DIR / "substrate_nn.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _centre_rgb(img):
    import numpy as np
    if hasattr(img, "detach"):                       # torch tensor (maybe CUDA) → host numpy
        img = img.detach().to("cpu").numpy()
    c = np.asarray(img)[_SIZE // 3:2 * _SIZE // 3, _SIZE // 3:2 * _SIZE // 3].reshape(-1, 3).mean(0)
    return float(c[0]), float(c[1]), float(c[2])


def _trained():
    if not _TRAINED:
        import torch
        nn = _nn()
        _d, _c, vsa = nn.dense_layers()
        dt, dev = vsa.dtype, vsa.device
        lin = torch.linspace(-1, 1, _SIZE, dtype=dt, device=dev)
        yy, xx = torch.meshgrid(lin, lin, indexing="ij")
        blob = torch.exp(-9.0 * (xx ** 2 + yy ** 2))
        A = torch.stack([blob, 0.1 * blob, 0.1 * blob], dim=-1).clamp(0, 1).detach()   # red
        B = torch.stack([0.1 * blob, 0.1 * blob, blob], dim=-1).clamp(0, 1).detach()   # blue
        torch.manual_seed(0)
        params = nn.init_mlp([nn.latent_input_dim(_NF, _LD), 64, 64, 3], dt, dev, seed=0)
        zA = torch.empty(_LD, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
        zB = torch.empty(_LD, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
        nn.fit_autodecoder(params, [zA, zB], [A, B], _SIZE, num_freqs=_NF, steps=1200)
        _TRAINED["v"] = (nn, params, zA.detach(), zB.detach(), A, B)
    return _TRAINED["v"]


def test_each_latent_reconstructs_its_colour():
    pytest.importorskip("torch")
    nn, params, zA, zB, A, B = _trained()
    mA = float(((nn.render_decoder_latent_torch(params, zA, _SIZE, _NF) - A) ** 2).mean().detach())
    mB = float(((nn.render_decoder_latent_torch(params, zB, _SIZE, _NF) - B) ** 2).mean().detach())
    assert mA < 0.02 and mB < 0.02, f"colour reconstruction failed: red={mA:.4f} blue={mB:.4f}"


def test_latent_interpolation_shifts_colour_red_to_blue():
    pytest.importorskip("torch")
    nn, params, zA, zB, A, B = _trained()
    rednesses = []
    for a in (0.0, 0.5, 1.0):
        img = nn.render_decoder_latent_torch(params, zA + (zB - zA) * a, _SIZE, _NF).detach()
        r, _g, b = _centre_rgb(img)
        rednesses.append(r - b)                      # >0 red, <0 blue
    assert rednesses[0] > 0.1, f"latent A did not generate red: redness {rednesses[0]:.2f}"
    assert rednesses[-1] < -0.1, f"latent B did not generate blue: redness {rednesses[-1]:.2f}"
    for lo, hi in zip(rednesses, rednesses[1:]):
        assert hi <= lo + 0.03, f"colour interpolation not monotonic red→blue: {rednesses}"
