"""B2 — the simulated audience (CTR) model.

`button_audience.SimulatedAudience.ctr(frame, copy)` is a DETERMINISTIC, DIFFERENTIABLE
host-side proxy for a click-through rate: it reads a rendered button frame and a discrete
copy choice and returns a click probability in [0,1]. It rewards salience (button vs page
contrast), warm call-to-action colour, and punchier preset copy. It is the synthetic signal
that drives the trainable-button training/CI loop (B3); it is explicitly *simulated*, not
real traffic (real clicks arrive only in the live browser, B4). Differentiability in the
frame is load-bearing: B3's Adam ascends CTR THROUGH the differentiable substrate render.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wf():
    return _load("gui_whole_frame", "whole_frame.py")


def _aud():
    return _load("gui_button_audience", "button_audience.py")


def _frame(wf, **overrides):
    th = dict(wf.BUTTON_THETA_DEFAULT)
    th.update(overrides)
    return wf.render_button_torch(24, th).clamp(0.0, 1.0)


def test_ctr_in_unit_interval():
    torch = pytest.importorskip("torch")
    wf, aud = _wf(), _aud()
    a = aud.SimulatedAudience()
    p = a.ctr(_frame(wf), copy=0)
    v = float(p.detach())
    assert 0.0 <= v <= 1.0, f"CTR not a probability: {v}"
    assert v == v, "CTR is NaN"


def test_higher_contrast_gives_higher_ctr():
    torch = pytest.importorskip("torch")
    wf, aud = _wf(), _aud()
    a = aud.SimulatedAudience()
    # High contrast: a vivid button on the light page. Low contrast: button ≈ page colour.
    high = a.ctr(_frame(wf, fr=0.95, fg=0.25, fb=0.10), copy=0)
    low = a.ctr(_frame(wf, fr=0.92, fg=0.92, fb=0.92), copy=0)
    assert float(high.detach()) > float(low.detach()) + 0.05, \
        f"contrast did not raise CTR: high={float(high):.3f} low={float(low):.3f}"


def test_punchier_copy_gives_higher_ctr():
    torch = pytest.importorskip("torch")
    wf, aud = _wf(), _aud()
    a = aud.SimulatedAudience()
    f = _frame(wf)
    punchy = a.ctr(f, copy=0)        # "Buy now"
    bland = a.ctr(f, copy=len(aud.PRESET_COPY) - 1)   # "Learn more"
    assert float(punchy.detach()) > float(bland.detach()) + 0.02, \
        f"punchier copy did not raise CTR: punchy={float(punchy):.3f} bland={float(bland):.3f}"


def test_ctr_is_deterministic():
    torch = pytest.importorskip("torch")
    wf, aud = _wf(), _aud()
    a = aud.SimulatedAudience()
    f = _frame(wf)
    assert float(a.ctr(f, copy=1).detach()) == float(a.ctr(f, copy=1).detach())


def test_ctr_differentiable_through_render_to_theta():
    torch = pytest.importorskip("torch")
    wf, aud = _wf(), _aud()
    _, vsa = wf._compile_button()
    dt, dev = vsa.dtype, vsa.device
    a = aud.SimulatedAudience()
    fr = torch.tensor(0.5, dtype=dt, device=dev, requires_grad=True)
    frame = wf.render_button_torch(16, {"fr": fr}).clamp(0.0, 1.0)
    p = a.ctr(frame, copy=0)
    p.backward()
    assert fr.grad is not None and abs(fr.grad.item()) > 1e-6, \
        f"CTR gradient did not reach the fill colour through the render: {fr.grad}"
