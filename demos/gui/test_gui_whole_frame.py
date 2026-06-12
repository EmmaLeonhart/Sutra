"""Test the whole-frame substrate render (GUI item #3).

frame_whole.su computes the WHOLE frame in ONE substrate op and returns it as a
single flat buffer vector (Emma's model: the returned vector IS the pixels). This
guards two things:
  1. the one-op buffer reproduces the per-pixel render_field() exactly (1e-6);
  2. the returned buffer length is N·N (it really is the whole frame, one vector).

Both run on the real Sutra substrate (the new `hadamard` elementwise/buffer
primitive). Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="frame_whole.su runs through real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DEMO_GUI / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_whole_frame_matches_per_pixel_render() -> None:
    """One-op whole-frame buffer == per-pixel render_field() to 1e-6, and the
    buffer length is N·N (the returned vector is the whole frame)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    window = _load("gui_window", "window.py")

    size = 16
    got = whole.render_field_whole(size)          # ONE substrate op -> N×N
    ref = window.render_field(size)                # per-pixel oracle

    assert got.shape == (size, size)
    assert got.size == size * size                 # the buffer really is the whole frame
    worst = float(abs(got - ref).max())
    assert worst < 1e-6, f"whole-frame vs per-pixel max error {worst} >= 1e-6"


def test_moving_glow_tracks_center_on_the_substrate() -> None:
    """frame_moving.su renders a glow centred at a movable x; the rendered field
    matches `1 - (x - cx)² - y²` (1e-6) and the brightest column TRACKS cx as it
    moves — the animation property, computed one-op-per-frame on the substrate."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size = 16
    for center in (0.0, 0.5):
        got = whole.render_field_moving(size, center)
        ref = [[1.0 - (2.0 * i / (size - 1) - 1.0 - center) ** 2
                - (2.0 * j / (size - 1) - 1.0) ** 2
                for i in range(size)] for j in range(size)]
        worst = max(abs(got[j][i] - ref[j][i])
                    for j in range(size) for i in range(size))
        assert worst < 1e-6, f"moving glow center={center}: max error {worst} >= 1e-6"
        # brightest pixel's column maps to ~center (the glow moved with cx).
        flat = int(got.argmax())
        col_x = 2.0 * (flat % size) / (size - 1) - 1.0
        assert abs(col_x - center) <= 2.0 / (size - 1) + 1e-6


def test_animation_centre_is_a_substrate_rnn() -> None:
    """moving_glow.su drives the animation from a SUBSTRATE-RNN: `step()` advances
    the glow centre on the substrate (no host arg, no host feedback between ticks),
    and the rendered frame's brightest column tracks that advancing centre."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    step, _frame_at, vsa = whole._compile_moving_glow()

    def read(v):
        v = v.real if v.is_complex() else v
        return float(v[vsa.semantic_dim + vsa.AXIS_REAL])

    seq = [round(read(step()), 3) for _ in range(6)]   # walk the recurrence, no host arg
    # centre advances by +0.25 each tick, held on the substrate slot across calls.
    assert all(abs(seq[i + 1] - seq[i] - 0.25) < 1e-5 for i in range(len(seq) - 1)), seq

    # The animation renders track the advancing centre (state drives the picture).
    size = 16
    frames = whole.animate_moving_glow(size, frames=4)
    assert len(frames) == 4
    cols = [2.0 * (int(f.argmax()) % size) / (size - 1) - 1.0 for f in frames]
    # brightest column moves right across frames (the glow slides with the substrate centre).
    assert cols == sorted(cols) and cols[-1] > cols[0]


def test_ring_widget_matches_oracle_and_is_a_ring() -> None:
    """frame_ring.su renders a concentric ring `1 - (x²+y² - R)²` in one substrate op:
    matches the host oracle (1e-6), and the bright locus is a RING — the peak is on
    the circle, brighter than the centre (not a centred blob)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size, R = 16, 0.5
    got = whole.render_field_ring(size, R)
    ref = [[1.0 - ((2.0 * i / (size - 1) - 1.0) ** 2
                   + (2.0 * j / (size - 1) - 1.0) ** 2 - R) ** 2
            for i in range(size)] for j in range(size)]
    worst = max(abs(got[j][i] - ref[j][i])
                for j in range(size) for i in range(size))
    assert worst < 1e-6, f"ring vs oracle max error {worst} >= 1e-6"
    centre = float(got[size // 2][size // 2])
    peak = float(got.max())
    assert peak > centre + 1e-3, f"expected a ring (peak {peak} > centre {centre})"


def test_click_interaction_gates_render_via_substrate_state() -> None:
    """click_frame.su: a click flips a 0/1 state on the SUBSTRATE (no host feedback
    between clicks) and the rendered frame is the glow GATED by that state — visible
    when 1, blank when 0. Verifies the substrate-state toggle and that clicking
    alternates the frame between glow and blank (interaction → visible change)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    flip, _frame_gated, vsa = whole._compile_click_frame()

    def read(v):
        v = v.real if v.is_complex() else v
        return float(v[vsa.semantic_dim + vsa.AXIS_REAL])

    seq = [round(read(flip()), 3) for _ in range(6)]   # no host arg
    assert seq == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0], seq  # substrate-state toggle

    size = 16
    frames = whole.click_frames(size, clicks=4)        # glow, blank, glow, blank
    assert len(frames) == 4
    brights = [float(f.max()) for f in frames]
    assert brights[0] > 0.9 and brights[2] > 0.9       # state 1 -> glow visible
    assert brights[1] < 1e-6 and brights[3] < 1e-6     # state 0 -> blank


def test_rgb_colour_channels_match_host() -> None:
    """frame_rgb.su: three substrate-computed colour channels (R=glow, G=ring,
    B=gradient), each a whole-frame field, stacked into an N×N×3 image. Each channel
    matches its host oracle (1e-6); B is a left→right ramp (0→1)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size, R = 16, 0.5
    img = whole.render_rgb(size, R)
    assert img.shape == (size, size, 3)

    def at(i, j):
        return (2.0 * i / (size - 1) - 1.0, 2.0 * j / (size - 1) - 1.0)

    worst = 0.0
    for j in range(size):
        for i in range(size):
            x, y = at(i, j)
            refR = 1.0 - x * x - y * y
            refG = 1.0 - (x * x + y * y - R) ** 2
            refB = (x + 1.0) / 2.0
            worst = max(worst,
                        abs(img[j, i, 0] - refR),
                        abs(img[j, i, 1] - refG),
                        abs(img[j, i, 2] - refB))
    assert worst < 1e-6, f"RGB channel vs host max error {worst} >= 1e-6"
    # B channel ramps left (dark) to right (bright)
    assert img[0, 0, 2] < 0.01 and img[0, size - 1, 2] > 0.99


def test_layout_composes_two_widgets_into_regions() -> None:
    """frame_layout.su composes two whole-frame widgets via a region mask in one
    substrate op: the left half shows the glow, the right half the ring. The composed
    frame matches the region-selected host oracle (1e-6)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size, R = 16, 0.5
    got = whole.render_layout(size, R)
    worst = 0.0
    for j in range(size):
        for i in range(size):
            x = 2.0 * i / (size - 1) - 1.0
            y = 2.0 * j / (size - 1) - 1.0
            want = (1.0 - x * x - y * y) if x < 0.0 else (1.0 - (x * x + y * y - R) ** 2)
            worst = max(worst, abs(float(got[j, i]) - want))
    assert worst < 1e-6, f"layout vs region-selected host max error {worst} >= 1e-6"


def test_checker_matches_oracle_with_crisp_gap() -> None:
    """frame_checker.su: `0.5 * (1 + px*py)` over host-built cell-parity buffers
    (grid geometry, the layout-mask precedent) renders a checkerboard in one
    substrate op. Matches the host oracle (1e-6), and the on/off separation is the
    full 1.0 gap (min(on) − max(off)) — a crisp binary pattern, no ambiguity."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size, block = 16, 4
    got = whole.render_checker(size, block)
    on, off, worst = [], [], 0.0
    for j in range(size):
        for i in range(size):
            want = 1.0 if ((i // block) % 2) == ((j // block) % 2) else 0.0
            worst = max(worst, abs(float(got[j, i]) - want))
            (on if want == 1.0 else off).append(float(got[j, i]))
    assert worst < 1e-6, f"checker vs oracle max error {worst} >= 1e-6"
    gap = min(on) - max(off)
    assert gap > 1.0 - 1e-6, f"checker on/off gap {gap} (expected 1.0)"
    # block structure: cell (0,0) on, the next block over differs
    assert float(got[0, 0]) > 0.99 and float(got[0, block]) < 1e-6


def test_diag_gradient_matches_oracle_and_ramps() -> None:
    """frame_diag.su: the diagonal ramp `0.5 * (1 + 0.5*(x + y))` in one substrate
    op. Matches the host oracle (1e-6); 0 at top-left, 1 at bottom-right, 0.5 on
    the anti-diagonal."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size = 16
    got = whole.render_diag(size)
    worst = 0.0
    for j in range(size):
        for i in range(size):
            x = 2.0 * i / (size - 1) - 1.0
            y = 2.0 * j / (size - 1) - 1.0
            worst = max(worst, abs(float(got[j, i]) - 0.5 * (1.0 + 0.5 * (x + y))))
    assert worst < 1e-6, f"diag vs oracle max error {worst} >= 1e-6"
    assert float(got[0, 0]) < 1e-6                        # top-left corner = 0
    assert float(got[size - 1, size - 1]) > 1.0 - 1e-6    # bottom-right corner = 1
    assert abs(float(got[0, size - 1]) - 0.5) < 1e-6      # anti-diagonal = 0.5


def test_quad_layout_composes_four_widgets() -> None:
    """frame_quad.su: FOUR whole-frame widgets (glow / ring / diag / checker)
    composed into quadrants in one substrate op — three host masks + the
    substrate-derived complement. The frame matches the quadrant-selected host
    oracle (1e-6) at every pixel, so the masks tile exactly (no overlap, no gap)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    size, R, block = 16, 0.5, 4
    got = whole.render_quad(size, R, block)
    worst = 0.0
    for j in range(size):
        for i in range(size):
            x = 2.0 * i / (size - 1) - 1.0
            y = 2.0 * j / (size - 1) - 1.0
            if x < 0.0 and y < 0.0:                       # top-left: glow
                want = 1.0 - x * x - y * y
            elif x >= 0.0 and y < 0.0:                    # top-right: ring
                want = 1.0 - (x * x + y * y - R) ** 2
            elif x < 0.0 and y >= 0.0:                    # bottom-left: diag
                want = 0.5 * (1.0 + 0.5 * (x + y))
            else:                                         # bottom-right: checker
                want = 1.0 if ((i // block) % 2) == ((j // block) % 2) else 0.0
            worst = max(worst, abs(float(got[j, i]) - want))
    assert worst < 1e-6, f"quad vs quadrant-selected host max error {worst} >= 1e-6"


def test_hadamard_is_elementwise_on_the_substrate() -> None:
    """The new primitive: hadamard squares a buffer elementwise (unlike `*`,
    which is the single-number complex product)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    _frame, vsa = whole._compile_frame_whole()
    a = torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=vsa.dtype, device=vsa.device)
    got = vsa.hadamard(a, a)
    got = got.real if got.is_complex() else got
    assert [round(float(got[i]), 4) for i in range(4)] == [1.0, 4.0, 9.0, 16.0]
