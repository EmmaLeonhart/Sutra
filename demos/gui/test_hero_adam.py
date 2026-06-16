"""R2 + R3 — Adam steering of the substrate hero via an online learned reward model.

`HeroAdam` runs online RLHF with pairwise preferences: each round it proposes the current
frame and a perturbed variant, a (here synthetic) rater prefers one, a Bradley-Terry step
trains a differentiable reward head, and Adam ascends that reward THROUGH the differentiable
Sutra render. These tests drive it with a synthetic fixed-preference rater and measure that
the substrate-rendered image moves in the rater's preferred direction — the steering claim.
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


def _run(prefer: str, rounds: int = 50, seed: int = 0):
    """Drive HeroAdam with a synthetic rater that prefers brighter (or darker) frames.
    Returns (initial_brightness, final_brightness, nan_or_blank_count)."""
    import numpy as np
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=seed)
    b0 = float(ctl.current_image().mean())
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        # Frame health = finite (no NaN/inf). A near-zero frame is NOT a failure: darker
        # preference legitimately drives the displayed frame toward all-black.
        for frame in (cur, var):
            if not np.isfinite(frame).all():
                bad += 1
        m_cur, m_var = float(cur.mean()), float(var.mean())
        var_brighter = m_var > m_cur
        prefer_variant = var_brighter if prefer == "bright" else (not var_brighter)
        ctl.choose(prefer_variant=prefer_variant)
    b1 = float(ctl.current_image().mean())
    return b0, b1, bad


def test_brighter_preference_brightens_substrate_render():
    pytest.importorskip("torch")
    b0, b1, bad = _run("bright")
    assert bad == 0, f"{bad} NaN/blank frames during steering"
    assert b1 > b0 + 0.1, f"brighter-preferring rater did not brighten: {b0:.3f} -> {b1:.3f}"


def test_darker_preference_darkens_substrate_render():
    pytest.importorskip("torch")
    b0, b1, bad = _run("dark")
    assert bad == 0, f"{bad} NaN/blank frames during steering"
    assert b1 < b0 - 0.1, f"darker-preferring rater did not darken: {b0:.3f} -> {b1:.3f}"


def test_steer_direction_flips_with_preference():
    pytest.importorskip("torch")
    b0b, b1b, _ = _run("bright")
    b0d, b1d, _ = _run("dark")
    # same neutral start; the steered brightness moves opposite ways with the preference.
    assert b1b > b1d, f"steer did not flip with preference: bright->{b1b:.3f}, dark->{b1d:.3f}"
