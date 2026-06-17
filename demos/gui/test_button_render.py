"""B1 — the substrate button render: a differentiable rounded-rectangle button.

`whole_frame.render_button_torch` computes a clickable button as an (H, W, 3) colour frame
in one substrate op per channel (`button_frame.su`'s `button_channel`): a quartic-squircle
mask composites a page-background colour and a button-fill colour, all on the substrate. The
render keeps its autograd graph, so a scalar loss on the button backpropagates to the
continuous θ (fill/page colours, inverse size, centre) THROUGH the compiled Sutra op — the
load-bearing fact for the ButtonAdam controller (B3). These tests measure the render against
a host oracle and confirm gradients flow to θ.
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


def test_button_render_is_differentiable_tensor():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_button()
    fr = torch.tensor(0.2, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
    img = wf.render_button_torch(24, {"fr": fr})
    assert img.requires_grad and img.grad_fn is not None, "button render severed the autograd graph"
    assert tuple(img.shape) == (24, 24, 3), f"expected (24,24,3), got {tuple(img.shape)}"


def test_button_render_matches_host_oracle():
    """The DISPLAYED button (one-op-per-channel substrate render, clamped to [0,1]) must
    match a per-pixel host computation of the same squircle composite. We compare the
    clamped display frame — the raw field reaches magnitude ~100 OUTSIDE the button (the
    unclamped squircle), where float32 resolution is ~1e-5 and which is never shown; the
    clamped [0,1] frame is what is displayed and what the audience model reads."""
    import numpy as np
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    size = 24
    th = dict(wf.BUTTON_THETA_DEFAULT)
    sub = wf.render_button_torch(size, th).clamp(0.0, 1.0).detach().to("cpu").numpy()

    # Host oracle: the same squircle composite, computed directly per pixel, then clamped.
    lin = np.linspace(-1.0, 1.0, size)
    xs, ys = np.meshgrid(lin, lin)                       # xs along cols, ys along rows
    dx, dy = xs - th["cx"], ys - th["cy"]
    sx, sy = dx * th["inv_w"], dy * th["inv_h"]
    inside = 1.0 - ((sx ** 2) ** 2 + (sy ** 2) ** 2)
    chans = []
    for pg, fl in (("pr", "fr"), ("pg", "fg"), ("pb", "fb")):
        page, fill = th[pg], th[fl]
        chans.append(page - page * inside + fill * inside)
    oracle = np.clip(np.stack(chans, axis=-1), 0.0, 1.0).astype(np.float32)

    max_abs = float(np.max(np.abs(sub - oracle)))
    assert max_abs < 1e-6, f"displayed substrate button disagrees with host oracle by {max_abs:.2e}"


def test_centre_pixel_is_the_fill_colour():
    """At the button centre the squircle mask is ~1, so the channel ≈ the fill colour."""
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    size = 25                                            # odd ⇒ a true centre pixel
    img = wf.render_button_torch(size, wf.BUTTON_THETA_DEFAULT).detach().to("cpu").numpy()
    c = size // 2
    centre = img[c, c]
    for ci, key in enumerate(("fr", "fg", "fb")):
        assert abs(float(centre[ci]) - wf.BUTTON_THETA_DEFAULT[key]) < 1e-3, \
            f"centre {key} = {centre[ci]:.3f}, expected fill {wf.BUTTON_THETA_DEFAULT[key]}"


def test_gradient_flows_to_fill_and_geometry_through_substrate():
    torch = pytest.importorskip("torch")
    wf = _whole_frame()
    _, vsa = wf._compile_button()
    dt, dev = vsa.dtype, vsa.device
    theta = {k: torch.tensor(v, dtype=dt, device=dev, requires_grad=True)
             for k, v in {"fr": 0.2, "inv_w": 1.7, "inv_h": 3.5, "cx": 0.0}.items()}
    img = wf.render_button_torch(16, theta)
    img[..., 0].mean().backward()                        # loss on the red channel
    grads = {k: t.grad for k, t in theta.items()}
    assert all(g is not None for g in grads.values()), "no grad reached button θ"
    # The red fill colour scales the red channel inside the button -> non-zero gradient.
    assert abs(grads["fr"].item()) > 1e-4, f"fill-red carried no gradient: {grads['fr']}"
    # At least 2 of the 4 axes carry a non-trivial gradient through the render.
    nonzero = sum(1 for g in grads.values() if abs(g.item()) > 1e-5)
    assert nonzero >= 2, f"only {nonzero} axes carried gradient: {grads}"
