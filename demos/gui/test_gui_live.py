"""Tests for the live window's substrate side (live_frame.su via live_demo.LiveFrame).

Mirrors test_gui_whole_frame.py's patterns: host-formula oracles (≤1e-6), no-feedback
RNN walks (the state-locus audit), signal-separation gaps for the click gate, plus the
per-tick latency measurement. The tkinter mainloop itself is not tested (established:
the live window can't be checked headlessly; LiveFrame is the tkinter-free layer).
"""
from __future__ import annotations

import math
import pathlib
import sys
import time

import numpy as np

DEMO_GUI = pathlib.Path(__file__).resolve().parent
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))


def _decode(vsa, v) -> float:
    r = v.real if v.is_complex() else v
    return float(r[vsa.semantic_dim + vsa.AXIS_REAL])


def test_step_phase_rotates_on_the_substrate():
    """The animation phase is a substrate-RNN: 40 step() calls with NO host arg
    follow Re(z_k) = cos(k·π/8) — a perpetual bounded sweep, wrapped by the
    complex rotation itself (no modulus)."""
    from live_demo import _compile_live

    ns = _compile_live()
    ns["_step__z_state"] = None          # fresh phase
    vsa = ns["_VSA"]
    errs = []
    for k in range(40):
        got = _decode(vsa, ns["step"]())
        errs.append(abs(got - math.cos((k + 1) * math.pi / 8)))
    assert max(errs) <= 1e-5, f"phase walk err {max(errs):.3e}"
    # the recurrence lives in the substrate slot, not a host variable
    assert ns["_step__z_state"] is not None


def test_flip_toggles_on_the_substrate():
    """The click gate is a substrate-RNN: 6 flip() calls with NO host arg
    alternate exactly 1, 0, 1, 0, 1, 0."""
    from live_demo import _compile_live

    ns = _compile_live()
    ns["_flip__state_state"] = None      # fresh gate
    vsa = ns["_VSA"]
    seq = [round(_decode(vsa, ns["flip"]()), 3) for _ in range(6)]
    assert seq == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0], seq
    assert ns["_flip__state_state"] is not None


def test_tick_renders_one_whole_frame_to_oracle():
    """One tick() = one substrate frame call; the (N, N) field matches the host
    oracle gate·(1 − (x − cx)² − y²) to 1e-6 at every pixel."""
    from live_demo import LiveFrame

    size = 16
    live = LiveFrame(size=size)
    live.click()                          # gate on
    field = live.tick()
    assert field.shape == (size, size)
    cx = live.centre                      # decoded from the same tick
    max_err = 0.0
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            x = 2.0 * i / (size - 1) - 1.0
            oracle = 1.0 * (1.0 - (x - cx) ** 2 - cy ** 2)
            max_err = max(max_err, abs(field[j, i] - oracle))
    assert max_err <= 1e-6, f"oracle err {max_err:.3e}"


def test_tick_animates_and_click_gates():
    """The event-loop behaviors, headless: ticks sweep the glow's brightest column
    with the substrate phase; a click blanks the frame (≤1e-6), another restores
    it (≥0.99) — the signal-separation gap for the gate."""
    from live_demo import LiveFrame

    live = LiveFrame(size=64)
    live.click()                          # gate on
    # cos(kπ/8) decreases over the first 8 ticks: the brightest column moves left
    cols = []
    for _ in range(4):
        field = live.tick()
        cols.append(int(np.argmax(np.max(field, axis=0))))
    assert cols == sorted(cols, reverse=True), f"glow not sweeping left: {cols}"

    live.click()                          # gate off on the substrate
    blank = live.tick()
    assert float(np.abs(blank).max()) <= 1e-6, "gate=0 frame not blank"

    live.click()                          # gate back on
    lit = live.tick()
    assert float(lit.max()) >= 0.99, f"gate=1 frame max {lit.max():.4f}"


def test_fresh_liveframe_resets_substrate_state():
    """A second LiveFrame starts from phase 1+0i and gate 0 (the compiled module is
    memoized; the recur slots must be re-zeroed per instance)."""
    from live_demo import LiveFrame

    a = LiveFrame(size=8)
    a.click()
    a.tick()
    a.tick()
    b = LiveFrame(size=8)
    assert b.gate == 0.0
    b.tick()
    assert abs(b.centre - math.cos(math.pi / 8)) <= 1e-5


def test_tick_latency_under_budget():
    """Per-tick cost (substrate advance + one-op whole-frame render + display read)
    stays far under the 100 ms tick budget at N=64. Prints the measured numbers."""
    from live_demo import LiveFrame

    live = LiveFrame(size=64)
    live.click()
    live.tick()                           # warm-up
    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        live.tick()
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    mean = sum(times) / len(times)
    print(f"\n[latency] 50 ticks N=64: mean {mean:.2f} ms, "
          f"p95 {times[int(0.95 * 49)]:.2f} ms, max {times[-1]:.2f} ms")
    assert mean < 100.0, f"mean tick {mean:.1f} ms exceeds the 100 ms budget"
