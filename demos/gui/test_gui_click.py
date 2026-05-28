"""Test the interactive GUI's click toggle (apps/gui/click_demo.py + toggle.su).

The red<->blue toggle's state transition is a substrate computation: toggle.su's
flip(s) = 1 - s. This guards that the flip runs on the substrate and that the
host tint maps state 0 -> red, state 1 -> blue. No window/click is exercised
(headless-safe); the live click is verified by hand via `python
apps/gui/click_demo.py`. Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="toggle.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _load_click_demo():
    spec = importlib.util.spec_from_file_location("click_demo", DEMO_GUI / "click_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flip_toggles_state_on_substrate() -> None:
    """toggle.su's flip(s) = 1 - s, computed on the substrate: 0<->1."""
    cd = _load_click_demo()
    ns = cd._compile("toggle.su")
    flip, vsa = ns["flip"], ns["_VSA"]
    assert abs(float(vsa.real(flip(0.0))) - 1.0) < 1e-6
    assert abs(float(vsa.real(flip(1.0))) - 0.0) < 1e-6
    # Two flips return to the start (a true toggle).
    once = float(vsa.real(flip(0.0)))
    twice = float(vsa.real(flip(once)))
    assert abs(twice - 0.0) < 1e-6


def test_tint_maps_state_to_red_and_blue() -> None:
    """State 0 -> red-dominant glow; state 1 -> blue-dominant glow."""
    import numpy as np

    cd = _load_click_demo()
    field = cd.render_field(16)
    red = cd.tint(field, 0.0)
    blue = cd.tint(field, 1.0)
    assert red.shape == (16, 16, 3) and red.dtype == np.uint8
    # Off-centre (mid-glow) the hue is unambiguous (centre whitens).
    r, c = 16 // 2, 16 // 4
    assert int(red[r, c][0]) > int(red[r, c][2]), f"red frame not red-dominant: {red[r,c]}"
    assert int(blue[r, c][2]) > int(blue[r, c][0]), f"blue frame not blue-dominant: {blue[r,c]}"
