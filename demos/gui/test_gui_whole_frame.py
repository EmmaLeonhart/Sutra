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


def test_hadamard_is_elementwise_on_the_substrate() -> None:
    """The new primitive: hadamard squares a buffer elementwise (unlike `*`,
    which is the single-number complex product)."""
    whole = _load("gui_whole_frame", "whole_frame.py")
    _frame, vsa = whole._compile_frame_whole()
    a = torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=vsa.dtype, device=vsa.device)
    got = vsa.hadamard(a, a)
    got = got.real if got.is_complex() else got
    assert [round(float(got[i]), 4) for i in range(4)] == [1.0, 4.0, 9.0, 16.0]
