"""D3 — the whole-frame coordinate decoder (learned, on the substrate).

`render_decoder_torch(params, size)` renders a full frame by running the trainable substrate
MLP (Fourier-encoded coordinates → matmul/cubic layers → output) over the coordinate grid —
the learned analogue of `render_button_torch`. These tests verify the render is a
differentiable frame whose every weight carries gradient through the substrate forward (the
prerequisite for training it to reconstruct an image, D4).
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


def _decoder(nn, size_hidden=32, num_freqs=4, out=1, seed=0):
    _d, _c, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    fin = nn.decoder_input_dim(num_freqs)
    params = nn.init_mlp([fin, size_hidden, size_hidden, out], dt, dev, seed=seed)
    return params, num_freqs


def test_decoder_renders_a_field_of_the_right_shape():
    pytest.importorskip("torch")
    nn = _nn()
    params, nf = _decoder(nn)
    img = nn.render_decoder_torch(params, size=16, num_freqs=nf)
    assert tuple(img.shape) == (16, 16), f"expected (16,16), got {tuple(img.shape)}"


def test_decoder_render_is_finite_and_differentiable_in_all_weights():
    import torch
    pytest.importorskip("torch")
    nn = _nn()
    params, nf = _decoder(nn)
    img = nn.render_decoder_torch(params, size=16, num_freqs=nf)
    assert img.requires_grad and img.grad_fn is not None, "decoder render severed autograd"
    assert torch.isfinite(img).all(), "decoder render produced non-finite pixels"
    img.mean().backward()
    grads = [t.grad for wb in params for t in wb]
    assert all(g is not None and torch.isfinite(g).all() for g in grads), "weight grad missing/non-finite"
    assert sum(float(g.abs().sum()) for g in grads) > 0, "no gradient reached the decoder weights"


def test_decoder_grid_matches_render_resolution_independence():
    """The same decoder renders at any resolution (it's a coordinate function) — a 16² and a
    24² render are both finite and shaped correctly from the identical weights."""
    import torch
    pytest.importorskip("torch")
    nn = _nn()
    params, nf = _decoder(nn)
    a = nn.render_decoder_torch(params, size=16, num_freqs=nf)
    b = nn.render_decoder_torch(params, size=24, num_freqs=nf)
    assert a.shape == (16, 16) and b.shape == (24, 24)
    assert torch.isfinite(a).all() and torch.isfinite(b).all()
