"""SIREN-style sin-activation decoder, on the substrate (unblocked by the `sin_buf` primitive).

Until 2026-06-17 the decoder's nonlinearity was a hadamard cubic ONLY because the substrate
could not run sin elementwise over an activation buffer (D1 finding). The `sin_buf` compiler
primitive removed that constraint, so a SIREN (Sitzmann et al. 2020) sin-activation MLP is now
expressible with the sin running ON THE SUBSTRATE. These tests confirm the SIREN forward (a)
runs NaN-free on the substrate, (b) is differentiable end-to-end (the host optimizer trains the
weights through the compiled substrate sin/matmul), and (c) fits a 1D wave well — in fact beats
the cubic+Fourier decoder on that smooth signal (the measured comparison is in
`planning/findings/2026-06-17-siren-sin-activation-decoder.md`; on a 2D separable-frequency
checkerboard the Fourier-matched cubic decoder wins instead — an honest, target-dependent split).
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


def _psnr(mse):
    return -10.0 * math.log10(max(mse, 1e-12))


def _fit_wave_siren(nn, steps: int = 800):
    import torch
    torch.manual_seed(0)
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    x = torch.linspace(-1, 1, 64, dtype=dt, device=dev).reshape(64, 1)
    Y = torch.sin(3.0 * math.pi * x).T.detach()
    params = nn.init_siren([1, 32, 32, 1], dt, dev, seed=0, omega0=30.0)
    flat = [t for wb in params for t in wb]
    opt = torch.optim.Adam(flat, lr=1e-3)
    losses = []
    for _ in range(steps):
        opt.zero_grad()
        loss = ((nn.siren_forward(params, x.T.contiguous()) - Y) ** 2).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    return losses


def test_siren_forward_runs_on_substrate_nan_free():
    pytest.importorskip("torch")
    import numpy as np
    nn = _nn()
    losses = _fit_wave_siren(nn, steps=100)
    assert all(np.isfinite(losses)), "SIREN training went non-finite (sin activation blew up)"


def test_siren_fits_the_wave():
    pytest.importorskip("torch")
    nn = _nn()
    mse = _fit_wave_siren(nn)[-1]
    # measured ~1.3e-5 / ~49 dB; assert a comfortable margin (PSNR > 35) to stay CPU/CUDA-robust.
    assert _psnr(mse) > 35.0, f"SIREN decoder failed to fit the wave: {_psnr(mse):.1f} dB (mse {mse:.2e})"


#  NOTE: there is deliberately NO "SIREN beats cubic+Fourier" regression test. The head-to-head
#  is NOT a robust fact — it reverses between hardware: on CUDA SIREN won the wave (~49 vs ~35 dB),
#  on CPU cubic+Fourier won it (~50 vs ~45 dB). Asserting a winner would encode a non-reproducible
#  claim. The robust, asserted facts are: SIREN runs on the substrate, fits the wave well, and is
#  differentiable. The hardware/target sensitivity is documented in the finding, not tested.


def test_siren_activation_is_differentiable_end_to_end():
    """The sin activation keeps autograd: gradients flow through `dense_sin` (sin_buf) to the
    weights — the property that makes the SIREN trainable on the substrate at all."""
    import torch
    pytest.importorskip("torch")
    nn = _nn()
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    params = nn.init_siren([2, 16, 1], dt, dev, seed=0)
    X = (torch.rand(2, 12, dtype=dt, device=dev) * 2 - 1)
    out = nn.siren_forward(params, X)
    out.sum().backward()
    for i, (W, b) in enumerate(params):
        assert W.grad is not None and torch.isfinite(W.grad).all(), f"no/!finite grad on layer {i} W"


if __name__ == "__main__":
    import unittest
    unittest.main()
