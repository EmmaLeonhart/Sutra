"""G3 — multi-axis steering beyond brightness/colour: POSITION and SIZE.

Brightness (test_hero_adam.py) and colour (test_hero_adam_rgb.py) already show the
controller steers a 1-D scalar. These tests show it steers SPATIAL preferences too —
WHERE the glow sits and HOW WIDE it is — by driving the geometry axes through the
substrate render:

  * POSITION  — a synthetic rater preferring the glow toward a corner moves the
    intensity-weighted centroid of the rendered frame that way (axes cx, cy).
  * SIZE/SPREAD — a rater preferring a WIDER glow lowers `invs` (inverse scale), so the
    intensity-weighted spatial spread of the rendered frame grows.

Each rater scores frames with the SAME measure the assertion checks, every frame is
finite, and the steered direction flips when the preference flips. Mono mode (the 7
geometry axes); every gradient is real autograd through the substrate render.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _hero_adam():
    spec = importlib.util.spec_from_file_location("gui_hero_adam", _DIR / "hero_adam.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _corner_bias(img):
    """Bottom-right mean intensity minus top-left mean intensity, on the clipped frame.
    > 0 = bright mass sits bottom-right; < 0 = top-left. A LINEAR functional of the pixels
    (so the pooled-linear reward head can represent it directly), and NOT scale-invariant —
    an all-black frame scores 0, beaten by any cornered glow, so there is no degenerate
    'go black' optimum (the trap a normalized centroid would have admitted)."""
    w = np.clip(np.asarray(img), 0.0, None)
    n = w.shape[0]
    h = n // 2
    tl = w[:h, :h].mean()
    br = w[h:, h:].mean()
    return float(br - tl)


def _spread(img):
    """Intensity-weighted spatial standard deviation of a mono frame: larger = the bright
    region is more spread out across the frame."""
    w = np.clip(np.asarray(img), 0.0, None)
    n = w.shape[0]
    lin = np.linspace(-1.0, 1.0, n)
    xs, ys = np.meshgrid(lin, lin)
    t = w.sum() + 1e-9
    mx = (w * xs).sum() / t
    my = (w * ys).sum() / t
    var = (w * ((xs - mx) ** 2 + (ys - my) ** 2)).sum() / t
    return float(np.sqrt(var))


def _run_position(corner: str, rounds: int = 90, seed: int = 0):
    """Prefer the bright mass toward `corner` ('topleft' = high TL−BR, 'bottomright' = high
    BR−TL). Returns (initial_corner_bias, final_corner_bias, nan_count) where corner_bias is
    BR−TL (positive = bottom-right heavy)."""
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=seed)

    def score(img):
        b = _corner_bias(img)
        return -b if corner == "topleft" else b

    b0 = _corner_bias(ctl.current_image())
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        for frame in (cur, var):
            if not np.isfinite(frame).all():
                bad += 1
        ctl.choose(prefer_variant=(score(var) > score(cur)))
    b1 = _corner_bias(ctl.current_image())
    return b0, b1, bad


def _run_size(prefer: str, rounds: int = 80, seed: int = 0):
    """Prefer a 'wider' or 'tighter' glow (by intensity-weighted spread).
    Returns (initial_spread, final_spread, nan_count)."""
    ha = _hero_adam()
    ctl = ha.HeroAdam(size=16, seed=seed)

    def score(img):
        sp = _spread(img)
        return sp if prefer == "wide" else -sp

    sp0 = _spread(ctl.current_image())
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        for frame in (cur, var):
            if not np.isfinite(frame).all():
                bad += 1
        ctl.choose(prefer_variant=(score(var) > score(cur)))
    sp1 = _spread(ctl.current_image())
    return sp0, sp1, bad


# --- POSITION (cx, cy) ---------------------------------------------------------

def test_topleft_preference_moves_mass_topleft():
    pytest.importorskip("torch")
    b0, b1, bad = _run_position("topleft")
    assert bad == 0, f"{bad} NaN/blank frames during position steering"
    # top-left preference drives BR−TL more NEGATIVE (mass moves to the top-left).
    assert b1 < b0 - 0.05, f"top-left preference did not move mass top-left: {b0:.3f} -> {b1:.3f}"


def test_bottomright_preference_moves_mass_bottomright():
    pytest.importorskip("torch")
    b0, b1, bad = _run_position("bottomright")
    assert bad == 0, f"{bad} NaN/blank frames during position steering"
    # bottom-right preference drives BR−TL more POSITIVE (mass moves to the bottom-right).
    assert b1 > b0 + 0.05, f"bottom-right preference did not move mass bottom-right: {b0:.3f} -> {b1:.3f}"


def test_position_steer_flips_with_preference():
    pytest.importorskip("torch")
    _, tl, _ = _run_position("topleft")
    _, br, _ = _run_position("bottomright")
    assert tl < br, f"position steer did not flip with preference: topleft->{tl:.3f}, bottomright->{br:.3f}"


# --- SIZE / SPREAD (invs) ------------------------------------------------------

def test_wide_preference_widens_glow():
    pytest.importorskip("torch")
    sp0, sp1, bad = _run_size("wide")
    assert bad == 0, f"{bad} NaN/blank frames during size steering"
    assert sp1 > sp0 + 0.02, f"wider preference did not widen the glow: {sp0:.3f} -> {sp1:.3f}"


def test_size_steer_flips_with_preference():
    pytest.importorskip("torch")
    _, wide, _ = _run_size("wide")
    _, tight, _ = _run_size("tight")
    assert wide > tight, f"size steer did not flip with preference: wide->{wide:.3f}, tight->{tight:.3f}"
