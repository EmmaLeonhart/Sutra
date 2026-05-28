"""Test the GUI counter (apps/gui/counter_demo.py + count.su).

Per-click substrate-dispatch demo (current shape: host-state-shuttle, NOT a
substrate RNN — see planning/findings/2026-05-28-demos-gui-substrate-audit.md
and CLAUDE.md "Subtler substrate breaches" #2). Each click invokes
count.su's step(n) = n + 1 on the substrate; the resulting count is read
back and stored in a host variable as the next state. pixel(x, y, n)
positions the displayed glow's centre from the current count. This test
guards both substrate computations. No window/click is exercised
(headless-safe); the live click is verified by hand via `python
apps/gui/counter_demo.py`. Target shape (queued, Emma 2026-05-28): rewrite
count.su to use `loop (cond)` with substrate-held state across iterations
so the recurrence lives on the substrate, not the host. Torch-gated like
the other real-Sutra tests.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="count.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _load_counter_demo():
    spec = importlib.util.spec_from_file_location(
        "counter_demo", DEMO_GUI / "counter_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_step_increments_on_substrate() -> None:
    """count.su's step(n) = n + 1 on the substrate: 0 -> 1 -> ... -> 10, exact.

    The host holds the decoded value and feeds it back (the register in the
    recurrent loop); the +1 is the substrate's, not a host n += 1.
    """
    cd = _load_counter_demo()
    ns = cd._compile("count.su")
    step, vsa = ns["step"], ns["_VSA"]
    n = 0.0
    seen = []
    for _ in range(10):
        n = float(vsa.real(step(n)))  # SUBSTRATE increment, fed back
        seen.append(round(n))
    assert seen == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # Each step is an exact integer (substrate increment, no drift).
    assert abs(float(vsa.real(step(4.0))) - 5.0) < 1e-9


def test_counter_class_increments_on_substrate() -> None:
    """_Counter.click() walks 0 -> 1 -> 2 -> 3 via the substrate step."""
    cd = _load_counter_demo()
    counter = cd._Counter()
    assert counter.state == 0.0
    assert round(counter.click()) == 1
    assert round(counter.click()) == 2
    assert round(counter.click()) == 3


def test_glow_steps_right_with_count() -> None:
    """The glow's centre is chosen FROM the count on the substrate: it moves
    left (n=0) -> right (n=9) as the count rises."""
    import numpy as np

    cd = _load_counter_demo()
    size = 32
    cols = []
    for n in (0.0, 4.0, 9.0):
        field = cd.render_field(n, size)
        # brightest column (where the glow centre sits)
        cols.append(int(np.argmax(field.sum(axis=0))))
    # strictly increasing column index — the glow steps rightward
    assert cols[0] < cols[1] < cols[2], f"glow did not step right: {cols}"
    assert cols[0] < size // 2, f"n=0 glow not on the left: col {cols[0]}"
    assert cols[2] > size // 2, f"n=9 glow not on the right: col {cols[2]}"


def test_render_field_shape_and_dtype() -> None:
    import numpy as np

    cd = _load_counter_demo()
    field = cd.render_field(3.0, 16)
    assert field.shape == (16, 16)
    assert field.dtype == np.float64
    rgb = cd.colormap(field)
    assert rgb.shape == (16, 16, 3) and rgb.dtype == np.uint8
