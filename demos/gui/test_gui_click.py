"""Test the interactive GUI's click toggle (demos/gui/click_demo.py + toggle.su).

Substrate-state-RNN demo: toggle.su's `flip()` is a non-halting-loop
function (planning/sutra-spec/non-halting-loop.md) whose `recurring vector
state` lives on the substrate as a tensor in a module-level slot, surviving
across calls without host scalar extraction. Each click invokes `flip()`
with NO host arg; the substrate loads the slot, computes `make_real(1.0)
- state`, writes back via `recur(...)`. The host decodes vsa.real(new) for
display only. This test guards the flip is on the substrate and that the
host tint maps state 0 -> red, state 1 -> blue. No window/click is
exercised (headless-safe); live click verified by hand via `python
demos/gui/click_demo.py`. Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="toggle.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent
import sys
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))
from _display import read_real  # noqa: E402  (display/output boundary helper)


def _load_click_demo():
    spec = importlib.util.spec_from_file_location("click_demo", DEMO_GUI / "click_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flip_toggles_state_on_substrate() -> None:
    """toggle.su's flip() is a non-halting loop: state vector flips 0 <-> 1
    on the substrate slot between calls; no host scalar shuttle."""
    cd = _load_click_demo()
    ns = cd._compile("toggle.su")
    flip, vsa = ns["flip"], ns["_VSA"]
    # Reset the substrate slot — _compile caches the compiled module
    # across tests; without this the slot may carry state from a prior
    # test or _Flip() instance.
    ns["_flip__state_state"] = None
    # Sequence: 0 -> 1 -> 0 -> 1 -> 0
    a = read_real(vsa, flip())
    b = read_real(vsa, flip())
    c = read_real(vsa, flip())
    d = read_real(vsa, flip())
    assert abs(a - 1.0) < 1e-6
    assert abs(b - 0.0) < 1e-6
    assert abs(c - 1.0) < 1e-6
    assert abs(d - 0.0) < 1e-6


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
