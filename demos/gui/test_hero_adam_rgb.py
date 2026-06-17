"""G2 — RGB / multi-axis Adam steering of the substrate hero.

`HeroAdam(color=True)` steers the DIFFERENTIABLE colour render (`render_hero_rgb_torch`):
θ now includes the per-channel tints cr/cg/cb, and the reward head consumes per-channel
pooled features. These tests drive it with a synthetic rater that prefers REDDER frames
(red relative to green+blue) and measure that the substrate-rendered colour image moves in
the rater's preferred direction — the colour-steering claim — while brightness steering
still works in colour mode. Every gradient is real autograd through the substrate render.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _hero_adam():
    spec = importlib.util.spec_from_file_location("gui_hero_adam", _DIR / "hero_adam.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _redness(img):
    """Relative redness: red mean minus the mean of the other two channels. Rises only
    when the frame gets redder RELATIVE to its overall brightness (not just brighter)."""
    r = float(img[..., 0].mean())
    g = float(img[..., 1].mean())
    b = float(img[..., 2].mean())
    return r - 0.5 * (g + b)


def _run(prefer: str, rounds: int = 60, seed: int = 0):
    """Drive HeroAdam(color=True) with a synthetic rater preferring redder (or less-red)
    frames. Returns (initial_redness, final_redness, nan_count)."""
    import numpy as np
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=seed, color=True)
    r0 = _redness(ctl.current_image())
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        for frame in (cur, var):
            if not np.isfinite(frame).all():
                bad += 1
        var_redder = _redness(var) > _redness(cur)
        prefer_variant = var_redder if prefer == "red" else (not var_redder)
        ctl.choose(prefer_variant=prefer_variant)
    r1 = _redness(ctl.current_image())
    return r0, r1, bad


def test_color_mode_renders_rgb_frames():
    pytest.importorskip("torch")
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=0, color=True)
    cur, var = ctl.propose()
    assert cur.shape == (16, 16, 3), f"expected (16,16,3) colour frame, got {cur.shape}"
    assert var.shape == (16, 16, 3)
    # cr/cg/cb are now steerable axes.
    th = ctl.current_theta()
    for k in ("cr", "cg", "cb"):
        assert k in th, f"colour axis {k} missing from steerable θ"


def test_redder_preference_increases_redness():
    pytest.importorskip("torch")
    r0, r1, bad = _run("red")
    assert bad == 0, f"{bad} NaN/blank frames during colour steering"
    assert r1 > r0 + 0.03, f"redder-preferring rater did not redden: {r0:.3f} -> {r1:.3f}"


def test_less_red_preference_decreases_redness():
    pytest.importorskip("torch")
    r0, r1, bad = _run("notred")
    assert bad == 0, f"{bad} NaN/blank frames during colour steering"
    assert r1 < r0 - 0.03, f"less-red-preferring rater did not de-redden: {r0:.3f} -> {r1:.3f}"


def test_color_steer_direction_flips_with_preference():
    pytest.importorskip("torch")
    _, r1_red, _ = _run("red")
    _, r1_not, _ = _run("notred")
    assert r1_red > r1_not, \
        f"colour steer did not flip with preference: red->{r1_red:.3f}, notred->{r1_not:.3f}"


def test_brightness_steering_still_works_in_color_mode():
    """Brightness preference must still steer in colour mode (the geometry axes still
    carry gradient through all three channels)."""
    import numpy as np
    pytest.importorskip("torch")
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=0, color=True)
    b0 = float(np.asarray(ctl.current_image()).mean())
    for _ in range(60):
        cur, var = ctl.propose()
        prefer_variant = float(var.mean()) > float(cur.mean())   # prefer brighter
        ctl.choose(prefer_variant=prefer_variant)
    b1 = float(np.asarray(ctl.current_image()).mean())
    assert b1 > b0 + 0.05, f"brighter preference did not brighten in colour mode: {b0:.3f} -> {b1:.3f}"
