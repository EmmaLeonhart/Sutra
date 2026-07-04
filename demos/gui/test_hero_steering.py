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


def _load_eval():
    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    return _load("gui_steering_eval", repo / "experiments" / "gui_steering_eval.py")


def test_soak_no_nan_blank_and_directional_both_signs() -> None:
    """The 1d soak property: a 100-press session renders 0 NaN / 0 blank frames,
    and a CONSISTENT rater steers monotonically in the rewarded direction — a
    brighter-preferring rater raises brightness, a darker-preferring one lowers it
    (the sign flips with the preference). Headline overlay off for test speed; the
    full-frame path is covered separately below."""
    ev = _load_eval()
    up = ev.run_soak(presses=100, size=24, seed=0, headline=False, prefer="brighter")
    assert up["frames_rendered"] == 101
    assert up["nan_count"] == 0 and up["blank_count"] == 0
    assert up["bright_delta"] > 0.3, up

    down = ev.run_soak(presses=100, size=24, seed=0, headline=False, prefer="darker")
    assert down["nan_count"] == 0 and down["blank_count"] == 0
    assert down["bright_delta"] < -0.3, down
    # opposite preferences move brightness opposite ways (directional consistency)
    assert up["bright_delta"] > down["bright_delta"]


def test_soak_full_demo_frame_stays_clean() -> None:
    """A shorter soak on the FULL demo frame (RGB hero + substrate glyph headline)
    renders 0 NaN / 0 blank — the recordable demo path holds under repeated
    pressing (the full 100-press headline-on run lives in the eval script)."""
    ev = _load_eval()
    m = ev.run_soak(presses=20, size=24, seed=1, headline=True, prefer="brighter")
    assert m["frames_rendered"] == 21
    assert m["nan_count"] == 0 and m["blank_count"] == 0


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


def test_ema_alpha_one_is_exactly_raw() -> None:
    """`ema_alpha=1.0` (the default) is byte-for-byte the raw two-sided behaviour:
    two controllers with the same seed, one default and one explicit, land on the
    identical optimizer state after the same press sequence — the smoothing path
    is dormant unless opted into (the 1d-measured numbers stay valid)."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    a = steer.HeroSteering(size=16, seed=3, render_headline=False)
    b = steer.HeroSteering(size=16, seed=3, render_headline=False, ema_alpha=1.0)
    seq = [steer.WARMER, steer.COLDER, steer.COLDER, steer.WARMER,
           steer.WARMER, steer.WARMER]
    for r in seq:
        a.press(r)
        b.press(r)
    assert np.allclose(a.opt.theta, b.opt.theta)
    assert a.batches_done == b.batches_done == 3


def test_ema_smoothing_halves_a_contrarian_swing() -> None:
    """With `ema_alpha=0.5`, the presses (+1, −1) score the batch as
    (r₊, r₋) = (+1, 0) instead of (+1, −1): the EMA primes on the first press and
    the contrarian second press is damped to 0. Since the SPSA step is
    ∝ (r₊ − r₋)·delta with a seed-deterministic delta, the smoothed controller's
    θ moves EXACTLY half as far as the raw one — the damping is measured, not
    hand-waved."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    raw = steer.HeroSteering(size=16, seed=4, render_headline=False)
    ema = steer.HeroSteering(size=16, seed=4, render_headline=False, ema_alpha=0.5)
    for ctl in (raw, ema):
        ctl.press(steer.WARMER)
        ctl.press(steer.COLDER)
    d_raw = float(np.linalg.norm(raw.opt.theta))
    d_ema = float(np.linalg.norm(ema.opt.theta))
    assert d_raw > 0.0
    assert d_ema == pytest.approx(d_raw / 2.0, rel=1e-9), (d_raw, d_ema)


def test_ema_smoothed_steering_still_moves_brighter() -> None:
    """Smoothing must damp noise, not kill the signal: with `ema_alpha=0.5` and a
    brighter-preferring rater whose presses are 20% contrarian (seeded), the
    steered brightness still ends ABOVE its start — directional steering survives
    the smoothing and the noise."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    rng = np.random.default_rng(7)
    ctl = steer.HeroSteering(size=16, seed=5, render_headline=False, ema_alpha=0.5)
    start = ctl.best_theta()["bright"]
    for _ in range(160):
        shown = ctl.current_theta()["bright"]
        ref = ctl.best_theta()["bright"]
        r = steer.WARMER if shown >= ref else steer.COLDER
        if rng.random() < 0.2:
            r = -r                      # contrarian flip
        ctl.press(r)
    final = ctl.best_theta()["bright"]
    assert final > start + 0.15, (start, final)


def test_ema_alpha_validation() -> None:
    """Out-of-range coefficients are rejected loudly (0 < α ≤ 1)."""
    steer = _load("gui_hero_steering", "hero_steering.py")
    for bad in (0.0, -0.5, 1.5):
        with pytest.raises(ValueError):
            steer.HeroSteering(size=16, seed=0, render_headline=False,
                               ema_alpha=bad)
