"""G1 — the DIFFERENTIABLE colour render path: gradients flow through the 3-channel
Sutra render to BOTH geometry axes and the per-channel colour tints.

The display-only `render_hero_rgb` severs autograd (it broadcasts θ with
`torch.full(..., float(val))`), so colour preference cannot be steered through it.
`render_hero_rgb_torch` keeps the graph: a scalar loss on the (H, W, 3) colour frame
backpropagates to θ THROUGH the compiled Sutra `hero_channel` op — including to the
colour tints `cr/cg/cb`. These tests measure that, the load-bearing fact for the RGB
Adam controller (G2).
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


def test_rgb_render_is_differentiable_tensor():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    cr = torch.tensor(1.0, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
    img = wf.render_hero_rgb_torch(16, {"cr": cr})
    assert img.requires_grad and img.grad_fn is not None, "RGB render severed the autograd graph"
    assert tuple(img.shape) == (16, 16, 3), f"expected (16,16,3), got {tuple(img.shape)}"


def test_gradient_flows_to_colour_tint_through_substrate():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    # Each tint scales ONLY its own channel: dR/dcr > 0 where the field is positive,
    # and dG/dcr == dB/dcr == 0 (tints are independent across channels).
    cr = torch.tensor(1.0, dtype=dt, device=dev, requires_grad=True)
    img = wf.render_hero_rgb_torch(16, {"cr": cr})
    red_mean = img[..., 0].mean()
    red_mean.backward()
    assert cr.grad is not None, "no grad reached the cr tint"
    assert abs(cr.grad.item()) > 1e-4, f"cr tint carried no gradient: {cr.grad.item()}"


def test_colour_tints_are_channel_independent():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    cr = torch.tensor(1.0, dtype=dt, device=dev, requires_grad=True)
    img = wf.render_hero_rgb_torch(16, {"cr": cr})
    # Loss on the GREEN channel must not depend on the RED tint.
    green_mean = img[..., 1].mean()
    green_mean.backward()
    assert cr.grad is None or abs(cr.grad.item()) < 1e-9, \
        f"green-channel loss leaked gradient into the cr tint: {cr.grad}"


def test_gradient_flows_to_geometry_axis_across_all_channels():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    # bg shifts the mono field by 1 in every channel before the tint multiply, so
    # d(mean over all channels)/d(bg) == mean(cr,cg,cb) exactly (within float tol).
    bg = torch.tensor(0.0, dtype=dt, device=dev, requires_grad=True)
    img = wf.render_hero_rgb_torch(16, {"bg": bg})
    img.mean().backward()
    assert bg.grad is not None, "no grad reached the bg geometry axis"
    cr, cg, cb = (wf.HERO_THETA_DEFAULT[k] for k in ("cr", "cg", "cb"))
    expected = (cr + cg + cb) / 3.0
    assert bg.grad.item() == pytest.approx(expected, abs=1e-4), \
        f"d(mean)/d(bg) = {bg.grad.item()}, expected mean tint {expected}"


def test_adam_step_through_rgb_render_reduces_loss():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_hero()
    dt, dev = vsa.dtype, vsa.device
    # "Make it redder" = maximize the red channel mean by ascending cr.
    cr = torch.tensor(1.0, dtype=dt, device=dev, requires_grad=True)
    opt = torch.optim.Adam([cr], lr=0.05)
    losses = []
    for _ in range(10):
        opt.zero_grad()
        loss = -wf.render_hero_rgb_torch(16, {"cr": cr})[..., 0].mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    assert losses[-1] < losses[0] - 1e-3, \
        f"Adam through the RGB render did not reduce loss: {losses}"
