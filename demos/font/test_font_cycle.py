"""Test cycle_step -- Emma's recurrent character-code step (added 2026-05-27).

cycle_step(prev_code, typed_code, has_typed) -> next char_code vector. By
default (has_typed=0.0), the substrate advances prev_code one step in the
36-glyph cycle (A->B->...->Y->Z->Z->0->...->9->A). With has_typed=1.0, the
typed code "takes the place" of the advanced one -- substrate weighted sum,
not a host if.

These tests exercise:
1. The 36 single-step advances (every code in the cycle goes to the right next code).
2. The two wraps (Z=90 -> 0=48, 9=57 -> A=65).
3. The override: typed code wins regardless of prev_code.
4. A full 36-tick loop returns to the starting code.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="font.su runs through real Sutra")

DEMO_FONT = pathlib.Path(__file__).resolve().parent

CYCLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _load_font_demo():
    spec = importlib.util.spec_from_file_location(
        "font_demo", DEMO_FONT / "font_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fontmod():
    return _load_font_demo()


@pytest.mark.parametrize("i", range(len(CYCLE)))
def test_cycle_step_advances_each_code(i: int, fontmod) -> None:
    """Without override, prev_code at cycle position i should advance to
    cycle position (i+1) mod 36."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    prev = float(ord(CYCLE[i]))
    expected = float(ord(CYCLE[(i + 1) % len(CYCLE)]))
    got = float(vsa.real(cycle_step(prev, 0.0, 0.0)))
    # Defuzzified select with -1000*delta^2 saturation underflows in float64,
    # so the result should be exact to within rounding.
    assert abs(got - expected) < 1e-9, (
        f"cycle from {CYCLE[i]!r} (code {prev}): got {got}, want {expected} "
        f"-- substrate 36-way select didn't one-hot"
    )


def test_cycle_step_wraps_Z_to_0(fontmod) -> None:
    """Z=90 -> 0=48 (the alphabet->digit wrap, the substrate's job not the host's)."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    got = float(vsa.real(cycle_step(90.0, 0.0, 0.0)))
    assert abs(got - 48.0) < 1e-9, f"Z->0 wrap: got {got}, want 48.0"


def test_cycle_step_wraps_9_to_A(fontmod) -> None:
    """9=57 -> A=65 (the digit->alphabet wrap, closes the cycle)."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    got = float(vsa.real(cycle_step(57.0, 0.0, 0.0)))
    assert abs(got - 65.0) < 1e-9, f"9->A wrap: got {got}, want 65.0"


def test_cycle_step_typed_overrides_advance(fontmod) -> None:
    """has_typed=1.0 -> the typed code wins, not the would-be advance."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    # prev=A (would advance to B), typed=Q -> result is Q.
    prev = float(ord("A"))
    typed = float(ord("Q"))
    got = float(vsa.real(cycle_step(prev, typed, 1.0)))
    assert abs(got - typed) < 1e-9, (
        f"typed override from A with typed=Q: got {got}, want {typed} "
        f"-- substrate weighted sum didn't pick the typed branch"
    )


def test_cycle_step_no_typed_with_typed_arg_ignored(fontmod) -> None:
    """has_typed=0.0 -> typed_code is ignored even if non-zero (the gate is the
    substrate's, not the host's)."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    # prev=A, typed=Q, but has_typed=0.0 -> advance still wins (B).
    prev = float(ord("A"))
    typed = float(ord("Q"))
    got = float(vsa.real(cycle_step(prev, typed, 0.0)))
    expected = float(ord("B"))
    assert abs(got - expected) < 1e-9, (
        f"has_typed=0 with typed=Q: got {got}, want {expected} (B) -- "
        f"substrate let typed leak through"
    )


def test_cycle_step_full_loop_returns_to_start(fontmod) -> None:
    """36 ticks of pure advance starting from A return to A. End-to-end check
    that the cycle is closed and the state-shuttle pattern (host extracts
    real(), feeds back next tick) preserves the substrate's decision."""
    ns = fontmod._compile()
    cycle_step, vsa = ns["cycle_step"], ns["_VSA"]
    code = float(ord("A"))
    for _ in range(len(CYCLE)):
        code = float(vsa.real(cycle_step(code, 0.0, 0.0)))
    assert abs(code - float(ord("A"))) < 1e-9, (
        f"36-tick loop from A: got code {code}, want {float(ord('A'))} (A)"
    )
