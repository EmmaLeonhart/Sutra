"""Test the GUI counter (apps/gui/counter_demo.py + count.su).

Substrate-state-RNN demo: count.su's `step()` is a non-halting-loop
function (planning/sutra-spec/non-halting-loop.md) whose `recurring vector
state` lives on the substrate as a tensor in a module-level slot, surviving
across calls without host scalar extraction. Each click invokes `step()`
with NO host arg; the substrate loads the slot, increments the real axis,
writes back via `recur(...)`, returns the new state vector. `pixel(x, y, n)`
is stateless geometry — host decodes the current count via read_real() for
display purposes only (display boundary, allowed). This test guards
both pieces. No window/click is exercised (headless-safe); the live click
is verified by hand via `python demos/gui/counter_demo.py`.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="count.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent
import sys
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))
from _display import read_real  # noqa: E402  (display/output boundary helper)


def _load_counter_demo():
    spec = importlib.util.spec_from_file_location(
        "counter_demo", DEMO_GUI / "counter_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_step_increments_on_substrate() -> None:
    """count.su's step() is a non-halting loop: 10 calls walk 1..10 on the
    substrate. The state vector lives between calls — no host scalar is fed
    back; the substrate's slot is the source of truth.
    """
    cd = _load_counter_demo()
    ns = cd._compile("count.su")
    step, vsa = ns["step"], ns["_VSA"]
    # Reset the substrate slot — see _Counter.__init__ note about
    # _compile caching the compiled module across tests.
    ns["_step__state_state"] = None
    seen = []
    for _ in range(10):
        state_vec = step()  # no host arg; substrate loads its own slot
        seen.append(round(read_real(vsa, state_vec)))  # decode for display
    assert seen == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_counter_class_increments_on_substrate() -> None:
    """_Counter.click() walks 0 -> 1 -> 2 -> 3. The host's `state` attribute
    is just a display cache; the canonical count lives on the substrate."""
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
