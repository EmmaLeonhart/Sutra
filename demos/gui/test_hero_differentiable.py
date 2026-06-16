"""R1 — the differentiable render path: gradients flow through the Sutra render.

`whole_frame.render_hero_torch` keeps the autograd graph, so a scalar loss on the
rendered frame backpropagates to θ THROUGH the compiled Sutra `hero` op. This is the
load-bearing fact for Adam steering (queue R2): Adam can only update θ by gradients,
and those gradients have to pass through the substrate render. These tests measure
that — `grad_fn` is set, and ∂loss/∂θ is non-zero on the axes that move the field.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _whole_frame():
    spec = importlib.util.spec_from_file_location("gui_whole_frame", _DIR / "whole_frame.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_is_differentiable_tensor():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    bright = torch.tensor(1.0, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
    img = wf.render_hero_torch(16, {"bright": bright})
    assert img.requires_grad and img.grad_fn is not None, "render severed the autograd graph"
    assert tuple(img.shape) == (16, 16)


def test_gradients_flow_to_theta_through_substrate():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    # Learnable θ on axes that demonstrably move the field.
    theta = {k: torch.tensor(v, dtype=dt, device=dev, requires_grad=True)
             for k, v in {"bright": 1.0, "bg": 0.0, "invs": 1.0, "accent": 0.0}.items()}
    img = wf.render_hero_torch(16, theta)
    loss = -img.mean()                      # "make it brighter" = maximize mean
    loss.backward()
    grads = {k: t.grad for k, t in theta.items()}
    assert all(g is not None for g in grads.values()), "no grad reached θ"
    # bg shifts every pixel by 1 -> d(-mean)/d(bg) == -1 exactly (within float tol).
    assert grads["bg"].item() == pytest.approx(-1.0, abs=1e-4)
    # bright weights the (non-negative) glow -> strictly negative grad for -mean.
    assert grads["bright"].item() < -1e-3
    # at least 3 of the 4 axes carry a non-trivial gradient through the render.
    nonzero = sum(1 for g in grads.values() if abs(g.item()) > 1e-4)
    assert nonzero >= 3, f"only {nonzero} axes carried gradient: {grads}"


def test_adam_step_reduces_loss_through_render():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    bright = torch.tensor(1.0, dtype=dt, device=dev, requires_grad=True)
    bg = torch.tensor(0.0, dtype=dt, device=dev, requires_grad=True)
    opt = torch.optim.Adam([bright, bg], lr=0.05)
    losses = []
    for _ in range(10):
        opt.zero_grad()
        loss = -wf.render_hero_torch(16, {"bright": bright, "bg": bg}).mean()
        loss.backward()
        opt.step()
        losses.append(float(loss))
    assert losses[-1] < losses[0] - 1e-3, f"Adam through the render did not reduce loss: {losses}"
