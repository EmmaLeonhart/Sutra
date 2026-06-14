"""Tests for the warmer/colder steering controller (a1 item 1c).

Headless — drives `HeroSteering` with a synthetic rater (no window). Verifies the
two-sided-SPSA-over-two-presses wiring, clean frames across a session (no NaN/blank),
and that a consistent brightness preference STEERS the hero brighter (the demo's
"directionally-consistent morphing" property), with the substrate render in the loop.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="HeroSteering renders on real Sutra")

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DEMO_GUI / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_two_presses_complete_one_spsa_batch() -> None:
    """Each pair of warmer/colder presses completes exactly one SPSA step: the
    batch counter and the optimizer's internal counter advance once per two
    presses, and the per-press phase alternates +perturbation / -perturbation."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    ctl = steer.HeroSteering(size=16, seed=0, render_headline=False)
    assert ctl.batches_done == 0 and ctl.opt.j == 0
    ctl.frame()
    ctl.press(steer.WARMER)            # scores +perturbation; no batch yet
    assert ctl.batches_done == 0
    ctl.press(steer.COLDER)            # scores -perturbation; one batch done
    assert ctl.batches_done == 1 and ctl.opt.j == 1
    for _ in range(3):
        ctl.press(steer.WARMER)
        ctl.press(steer.COLDER)
    assert ctl.batches_done == 4 and ctl.opt.j == 4


def test_no_nan_or_blank_frames_across_a_session() -> None:
    """Every frame across a multi-press session is finite and non-blank (the
    controller's frame guard would raise otherwise) — the soak property the demo
    needs (item 1d builds the full 100-press version with the headline on)."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    rng = np.random.default_rng(0)
    ctl = steer.HeroSteering(size=16, seed=1, render_headline=False)
    img, _ = ctl.frame()
    assert np.all(np.isfinite(img)) and float(np.abs(img).max()) > 0.0
    for _ in range(40):                # 40 presses = 20 SPSA batches
        r = steer.WARMER if rng.random() < 0.5 else steer.COLDER
        img, _ = ctl.press(r)          # press() re-renders + guards each frame
        assert np.all(np.isfinite(img))
        assert float(np.abs(img).max()) > 0.0


def test_brightness_preference_steers_the_hero_brighter() -> None:
    """A rater that consistently prefers brighter frames drives the optimizer's
    best θ brightness UP from neutral — end-to-end directional steering with the
    substrate render in the loop (not just the optimizer in isolation)."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    ctl = steer.HeroSteering(size=16, seed=2, render_headline=False)
    start_bright = ctl.best_theta()["bright"]

    # Rater: warmer if the CURRENTLY SHOWN perturbation is brighter than the
    # running best, else colder. A pure brightness preference expressed on the
    # rendered-θ the controller is presenting.
    for _ in range(160):               # 160 presses = 80 SPSA batches
        shown = ctl.current_theta()["bright"]
        ref = ctl.best_theta()["bright"]
        ctl.press(steer.WARMER if shown >= ref else steer.COLDER)

    final_bright = ctl.best_theta()["bright"]
    assert final_bright > start_bright + 0.3, (start_bright, final_bright)


def test_full_frame_with_headline_renders_clean() -> None:
    """One frame on the FULL path (RGB hero + substrate glyph headline overlay)
    renders finite and non-blank, and reports a headline from the preset set —
    covers the live-window render path (render_headline=True) without a 100-frame
    glyph-rasterization loop."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    wf = _load("gui_whole_frame_hl", "whole_frame.py")
    ctl = steer.HeroSteering(size=24, seed=0, render_headline=True)
    img, headline = ctl.frame()
    assert img.shape == (24, 24, 3)
    assert np.all(np.isfinite(img)) and float(img.max()) > 0.0
    assert headline in wf.HERO_HEADLINES
