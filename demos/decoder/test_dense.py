"""D1 — the trainable dense (Linear) layer on the substrate.

`dense.su` computes `matmul(W, x) + b` on the substrate; `dense_tanh` adds a tanh. The weights
W, b arrive as parameters, so a host optimizer trains them by autograd THROUGH the compiled
substrate matmul — the load-bearing proof that the Sutra substrate can be *trained*, not just
evaluated. (The analytic hero/button renders are fixed-weight; this is the trainable cell the
learned decoder is built from.) Every op is on the substrate; the optimizer is host-side.
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


def test_dense_is_differentiable_in_weights_through_substrate():
    torch = pytest.importorskip("torch")
    nn = _nn()
    dense, _dense_tanh, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    W = torch.randn(4, 3, dtype=dt, device=dev, requires_grad=True)
    b = torch.zeros(4, dtype=dt, device=dev, requires_grad=True)
    x = torch.randn(3, dtype=dt, device=dev)
    y = dense(W, x, b)
    assert y.requires_grad and y.grad_fn is not None, "dense severed the autograd graph"
    assert tuple(y.shape) == (4,), f"expected (4,), got {tuple(y.shape)}"
    y.sum().backward()
    for name, g in (("W", W.grad), ("b", b.grad)):
        assert g is not None and torch.isfinite(g).all(), f"{name}.grad missing/non-finite"
    assert W.grad.abs().sum() > 0, "no gradient reached W through the substrate matmul"


def test_dense_matches_matmul_reference():
    torch = pytest.importorskip("torch")
    nn = _nn()
    dense, _dt, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    W = torch.randn(2, 3, dtype=dt, device=dev)
    x = torch.randn(3, dtype=dt, device=dev)
    b = torch.randn(2, dtype=dt, device=dev)
    got = dense(W, x, b).detach()
    ref = (W @ x + b).detach()
    assert torch.allclose(got, ref, atol=1e-5), f"substrate dense != W@x+b: {got} vs {ref}"


def test_dense_cube_is_nonlinear_and_differentiable():
    """The stackable nonlinearity is a hadamard cubic h³ (the substrate's tanh/sin are
    canonical-vector ops, not elementwise over activation buffers — D1 finding). It matches
    (W·x+b)³ elementwise and carries gradient to the weights."""
    torch = pytest.importorskip("torch")
    nn = _nn()
    _d, dense_cube, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    W = torch.randn(5, 4, dtype=dt, device=dev, requires_grad=True)
    b = torch.zeros(5, dtype=dt, device=dev, requires_grad=True)
    x = torch.randn(4, dtype=dt, device=dev)
    y = dense_cube(W, x, b)
    ref = (W @ x + b) ** 3
    assert torch.allclose(y.detach(), ref.detach(), atol=1e-4), "cube != (W@x+b)^3"
    y.sum().backward()
    assert W.grad is not None and torch.isfinite(W.grad).all() and W.grad.abs().sum() > 0


def test_adam_trains_the_substrate_layer_to_fit_a_linear_map():
    """Adam fits the substrate dense layer to a held linear target over a small dataset — the
    gradient through the substrate matmul actually drives learning."""
    torch = pytest.importorskip("torch")
    nn = _nn()
    dense, _dt, vsa = nn.dense_layers()
    dt, dev = vsa.dtype, vsa.device
    torch.manual_seed(0)
    in_d, out_d, n = 3, 2, 8
    W_true = torch.randn(out_d, in_d, dtype=dt, device=dev)
    b_true = torch.randn(out_d, dtype=dt, device=dev)
    Xs = torch.randn(n, in_d, dtype=dt, device=dev)
    Ys = (Xs @ W_true.T + b_true).detach()

    W = torch.zeros(out_d, in_d, dtype=dt, device=dev, requires_grad=True)
    b = torch.zeros(out_d, dtype=dt, device=dev, requires_grad=True)
    opt = torch.optim.Adam([W, b], lr=0.1)
    losses = []
    for _ in range(300):
        opt.zero_grad()
        loss = sum(((dense(W, Xs[i], b) - Ys[i]) ** 2).mean() for i in range(n)) / n
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    assert losses[-1] < losses[0] * 0.05, f"substrate layer did not train: {losses[0]:.3f} -> {losses[-1]:.4f}"
    assert losses[-1] < 1e-2, f"final fit loss too high: {losses[-1]:.4f}"
