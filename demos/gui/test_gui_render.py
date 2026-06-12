"""Test the first GUI's render pipeline (apps/gui).

The GUI's content is computed on the Sutra substrate: frame.su's pixel(x, y)
returns brightness 1 - x^2 - y^2. This test guards that the substrate computes
the field correctly and that window.py assembles it into an image — the pieces
that were only verified by a manual render when the GUI first landed.

No display is opened (headless-safe); we check the substrate values and the
host-side assembly only. Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="frame.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent
import sys
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))
from _display import read_real  # noqa: E402  (display/output boundary helper)


def _load_window():
    """Load apps/gui/window.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("gui_window", DEMO_GUI / "window.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_frame_su_computes_brightness_on_substrate() -> None:
    """frame.su's pixel(x, y) returns 1 - x^2 - y^2, computed on the substrate."""
    win = _load_window()
    pixel, vsa = win._compile_frame()
    cases = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (1.0, 1.0, -1.0),
             (0.5, 0.5, 0.5), (-0.5, 0.25, 1.0 - 0.25 - 0.0625)]
    worst = 0.0
    for x, y, expect in cases:
        got = read_real(vsa, pixel(x, y))
        worst = max(worst, abs(got - expect))
        assert abs(got - expect) < 1e-6, (
            f"pixel({x},{y}) = {got}, expected {expect} (1 - x^2 - y^2)"
        )
    print(f"\n[gui] frame.su substrate brightness worst |err| = {worst:.3e}")


def test_render_field_shape_and_extremes() -> None:
    """render_field returns a (size, size) field with the glow's centre brightest
    and corners darkest — i.e. the substrate field, assembled by the host."""
    win = _load_window()
    size = 9  # odd -> a true centre cell; 81 substrate calls
    field = win.render_field(size)
    assert field.shape == (size, size)
    centre = field[size // 2, size // 2]
    corner = field[0, 0]
    assert abs(centre - 1.0) < 1e-6, f"centre brightness {centre} != 1.0"
    assert corner < centre, f"corner {corner} should be darker than centre {centre}"
    # corner is (x,y)=(-1,-1): 1 - 1 - 1 = -1
    assert abs(corner - (-1.0)) < 1e-6, f"corner brightness {corner} != -1.0"


def test_colormap_output_is_uint8_rgb() -> None:
    """colormap turns a brightness field into a displayable (H, W, 3) uint8 image
    (host-side rendering; clamps the out-of-disc negatives to black)."""
    import numpy as np

    win = _load_window()
    field = np.array([[1.0, 0.5], [0.0, -1.0]])
    img = win.colormap(field)
    assert img.shape == (2, 2, 3)
    assert img.dtype == np.uint8
    # brightness 1.0 -> white-ish (all channels high); -1.0 -> black (clamped)
    assert img[0, 0].min() > 200, f"bright pixel too dark: {img[0,0]}"
    assert int(img[1, 1].max()) == 0, f"dark pixel not black: {img[1,1]}"
