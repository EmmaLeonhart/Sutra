"""B3 — the ButtonAdam dual-reward controller.

`ButtonAdam` steers the differentiable substrate button (B1) to maximize a blend of an
OWNER-PREFERENCE reward (a pairwise Bradley-Terry head trained on the owner's warmer/colder
choices) and a CTR reward (the simulated audience, B2):

    R(θ, copy) = α · owner_pref(frame) + (1 − α) · CTR(frame, copy)

Adam ascends R through the substrate render for the continuous θ; the discrete copy is
chosen by argmax of R over the preset set. These tests drive it with a synthetic owner that
prefers a BLUE button (brand colour) and the simulated audience (which prefers warm,
high-contrast buttons + punchy copy), and measure that:
  * α=0 (pure CTR) raises CTR and picks the punchiest copy,
  * α=1 (pure owner) drives the button toward the owner's blue taste,
  * the α knob trades the two off (owner-blue vs CTR-warm).
Every gradient is real autograd through the substrate render.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _button_adam():
    spec = importlib.util.spec_from_file_location("gui_button_adam", _DIR / "button_adam.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _centre_color(img):
    """Mean colour of the central (button) region of an (H,W,3) numpy frame."""
    h, w = img.shape[0], img.shape[1]
    c = img[h // 3:2 * h // 3, w // 3:2 * w // 3, :].reshape(-1, 3)
    return c.mean(axis=0)


def _blueness(img):
    """Button-centre blue minus the mean of red+green: how 'brand-blue' the button is."""
    r, g, b = _centre_color(img)
    return float(b - 0.5 * (r + g))


def _owner_prefers_bluer(cur, var):
    """Synthetic owner taste: prefer the bluer button (the brand colour)."""
    return _blueness(var) > _blueness(cur)


def _run(alpha, rounds=60, seed=0):
    ha = _button_adam()
    ctl = ha.ButtonAdam(size=24, seed=seed, alpha=alpha)
    b0 = _blueness(ctl.current_image())
    ctr0 = ctl.ctr_now()
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        for f in (cur, var):
            if not np.isfinite(f).all():
                bad += 1
        ctl.choose(prefer_variant=_owner_prefers_bluer(cur, var))
    return {
        "b0": b0, "b1": _blueness(ctl.current_image()),
        "ctr0": ctr0, "ctr1": ctl.ctr_now(),
        "copy": ctl.current_copy(), "bad": bad,
    }


def test_ctr_only_raises_ctr_and_picks_punchy_copy():
    pytest.importorskip("torch")
    r = _run(alpha=0.0)
    assert r["bad"] == 0, f"{r['bad']} non-finite frames"
    assert r["ctr1"] > r["ctr0"] + 0.1, f"CTR-only did not raise CTR: {r['ctr0']:.3f} -> {r['ctr1']:.3f}"
    assert r["copy"] == 0, f"CTR-only did not pick the punchiest copy (0): got {r['copy']}"


def test_owner_only_follows_owner_blue_taste():
    pytest.importorskip("torch")
    r = _run(alpha=1.0)
    assert r["bad"] == 0, f"{r['bad']} non-finite frames"
    assert r["b1"] > r["b0"] + 0.1, f"owner-only did not move toward blue: {r['b0']:.3f} -> {r['b1']:.3f}"


def test_alpha_knob_trades_off_owner_vs_ctr():
    pytest.importorskip("torch")
    owner = _run(alpha=1.0)
    ctr = _run(alpha=0.0)
    # Owner-driven button is bluer than the CTR-driven one...
    assert owner["b1"] > ctr["b1"] + 0.1, \
        f"owner not bluer than CTR: owner={owner['b1']:.3f} ctr={ctr['b1']:.3f}"
    # ...and the CTR-driven button has the higher CTR.
    assert ctr["ctr1"] > owner["ctr1"] + 0.05, \
        f"CTR-driven not higher CTR than owner: ctr={ctr['ctr1']:.3f} owner={owner['ctr1']:.3f}"


def test_steering_settles_over_time_like_adam():
    """The proposal exploration AND the per-round policy step shrink as preferences accumulate,
    so the design SETTLES instead of jittering forever (Emma 2026-06-17: the live demo "doesn't
    slow down over time like Adam"). We measure the actual θ movement per round under a fixed
    synthetic owner and assert late rounds move far less than early ones, while still converging."""
    pytest.importorskip("torch")
    ha = _button_adam()
    ctl = ha.ButtonAdam(size=24, seed=0, alpha=1.0)

    # current_explore() must be monotonically non-increasing round to round.
    explores = []
    early, late = [], []
    for r in range(70):
        explores.append(ctl.current_explore())
        cur, var = ctl.propose()
        before = ctl.current_theta()
        ctl.choose(prefer_variant=_owner_prefers_bluer(cur, var))
        after = ctl.current_theta()
        step = sum(abs(after[k] - before[k]) for k in after)
        (early if r < 10 else late if r >= 40 else []).append(step)

    assert all(b >= a - 1e-9 for a, b in zip(explores[1:], explores)), \
        "exploration did not monotonically anneal"
    assert explores[-1] < explores[0], "exploration never shrank"
    mean_early, mean_late = sum(early) / len(early), sum(late) / len(late)
    assert mean_late < 0.5 * mean_early, \
        f"steering did not settle: early step {mean_early:.4f} vs late {mean_late:.4f}"
    # ...and it still converged toward the owner's blue taste despite settling.
    assert _blueness(ctl.current_image()) > 0.1, "settled but never reached the owner's blue taste"
