"""D14 — the decoder reconstructs HIGH-FREQUENCY arbitrary content (not just smooth blobs).

D4/D5 used smooth gaussian blobs. This trains the substrate decoder on a sharp CHECKERBOARD —
genuinely high-frequency arbitrary content — and confirms (a) it reconstructs it well, and (b)
the number of Fourier-feature bands sets the achievable frequency: more bands → higher PSNR on
the same high-frequency target (the encoding earns its bands). Same substrate forward
(matmul + hadamard cubic), host Adam.
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


def _checker(nn, k, size, dt, dev):
    import torch
    lin = torch.linspace(-1, 1, size, dtype=dt, device=dev)
    yy, xx = torch.meshgrid(lin, lin, indexing="ij")
    return ((torch.sin(k * math.pi * xx) * torch.sin(k * math.pi * yy)) > 0).to(dt).detach()


def _fit_checker(nn, k, num_freqs, size=24, steps=1000):
    import torch
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    target = _checker(nn, k, size, dt, dev)
    params = nn.init_mlp([nn.decoder_input_dim(num_freqs), 96, 96, 1], dt, dev, seed=0)
    losses = nn.fit_decoder(params, target, size, num_freqs=num_freqs, steps=steps, lr=0.01)
    return losses[-1]


def test_decoder_reconstructs_a_high_frequency_checkerboard():
    pytest.importorskip("torch")
    nn = _nn()
    mse = _fit_checker(nn, k=3, num_freqs=6)
    assert math.isfinite(mse), "high-frequency reconstruction went non-finite"
    # measured ~0.0009 / 30.6 dB; assert comfortably above a sharp-content threshold.
    assert nn.psnr(mse) > 25.0, f"decoder failed the high-frequency target: PSNR {nn.psnr(mse):.1f} dB"


def test_more_fourier_bands_raise_the_frequency_ceiling():
    pytest.importorskip("torch")
    nn = _nn()
    few = _fit_checker(nn, k=3, num_freqs=4)
    many = _fit_checker(nn, k=3, num_freqs=6)
    assert nn.psnr(many) > nn.psnr(few) + 2.0, \
        f"more Fourier bands did not help: nf4={nn.psnr(few):.1f} dB, nf6={nn.psnr(many):.1f} dB"
