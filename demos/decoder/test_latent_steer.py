"""D8 — preference steers the generative decoder's latent (the convergence milestone).

A trained latent-conditioned decoder (D7) has its weights FROZEN; `LatentSteer` then moves the
latent `z` by pairwise preference — a reward head trained on the choices, Adam ascending it
THROUGH the substrate decoder render. A synthetic rater preferring the generated blob further
right drives the latent so the decoder generates a rightward blob; the leftward rater drives it
left; the direction flips. The learned generator meets the GUI preference-steering loop.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

_DIR = pathlib.Path(__file__).resolve().parent
_SIZE, _NF, _LD = 16, 4, 4
_TRAINED = {}


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _centroid_x(img):
    w = np.clip(img, 0.0, None)
    lin = np.linspace(-1, 1, img.shape[1])
    xx = np.tile(lin, (img.shape[0], 1))
    return float((w * xx).sum() / (w.sum() + 1e-9))


def _trained_decoder():
    """Train (once, cached) an auto-decoder on two blob-position targets so the latent controls
    the generated blob's x. Returns (substrate_nn module, params, z_mid)."""
    if not _TRAINED:
        import torch
        nn = _load("substrate_nn", "substrate_nn.py")
        _d, _c, vsa = nn.dense_layers()
        dt, dev = vsa.dtype, vsa.device

        def blob(cx):
            lin = torch.linspace(-1, 1, _SIZE, dtype=dt, device=dev)
            yy, xx = torch.meshgrid(lin, lin, indexing="ij")
            t = torch.exp(-10.0 * ((xx - cx) ** 2 + yy ** 2))
            return (t / t.max()).detach()

        torch.manual_seed(0)
        params = nn.init_mlp([nn.latent_input_dim(_NF, _LD), 64, 64, 1], dt, dev, seed=0)
        zA = torch.empty(_LD, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
        zB = torch.empty(_LD, dtype=dt, device=dev).normal_(0, 0.5).requires_grad_(True)
        nn.fit_autodecoder(params, [zA, zB], [blob(-0.4), blob(0.4)], _SIZE, num_freqs=_NF, steps=900)
        _TRAINED["v"] = (nn, params, (0.5 * (zA + zB)).detach())
    return _TRAINED["v"]


def _steer(prefer, rounds=40, seed=0):
    nn, params, z_mid = _trained_decoder()
    ls = _load("latent_steer", "latent_steer.py")
    st = ls.LatentSteer(params, z_mid, size=_SIZE, num_freqs=_NF, seed=seed)
    start = _centroid_x(st.current_image())
    for _ in range(rounds):
        cur, var = st.propose()
        var_more_right = _centroid_x(var) > _centroid_x(cur)
        st.choose(prefer_variant=(var_more_right if prefer == "right" else not var_more_right))
    return start, _centroid_x(st.current_image())


def test_preference_steers_the_generated_blob_right():
    pytest.importorskip("torch")
    start, final = _steer("right")
    assert final > start + 0.05, f"rightward preference did not move the generated blob: {start:.3f} -> {final:.3f}"


def test_preference_steers_the_generated_blob_left():
    pytest.importorskip("torch")
    start, final = _steer("left")
    assert final < start - 0.1, f"leftward preference did not move the generated blob: {start:.3f} -> {final:.3f}"


def test_latent_steer_flips_with_preference():
    pytest.importorskip("torch")
    _, right = _steer("right")
    _, left = _steer("left")
    assert right > left + 0.2, f"latent steer did not flip with preference: right={right:.3f} left={left:.3f}"
