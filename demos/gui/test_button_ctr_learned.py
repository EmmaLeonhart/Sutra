"""B7 — the learned CTR reward head closes the real-click loop.

In live mode, `ButtonAdam(live_ctr=True)` replaces the simulated audience in the reward with a
LEARNED `CtrRewardModel` (a differentiable pooled-linear head) trained from click PREFERENCES:
a visitor clicking button A over B is a pairwise preference for A's clickability
(`record_click`). Adam then ascends `α·owner + (1−α)·ctr_head` through the substrate render.

These tests drive it with a synthetic clicker whose ground-truth click behaviour IS the B2
simulated audience (used only to GENERATE click labels and to MEASURE success — never read by
the learned head). With α=0 (pure learned-CTR), the head should recover the audience's
preference well enough that steering raises the true (B2) CTR of the rendered button — i.e.
the loop closes: real-click-like signals train a differentiable reward that, ascended, gets
more clicks. Every gradient is real autograd through the substrate render.
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


def _run_learned_ctr(rounds=70, seed=0):
    import torch
    ba = _button_adam()
    ctl = ba.ButtonAdam(size=24, seed=seed, alpha=0.0, live_ctr=True)  # pure learned-CTR
    aud = ctl.audience                       # B2 = hidden ground-truth clicker + true-CTR meter
    ctr0 = ctl.ctr_now()                     # ctr_now reports the TRUE (B2) CTR, not the head
    bad = 0
    for _ in range(rounds):
        cur, var = ctl.propose()
        for f in (cur, var):
            if not np.isfinite(f).all():
                bad += 1
        copy = ctl.current_copy()
        # the synthetic visitor clicks whichever button the ground-truth audience finds more
        # clickable — this is the only place B2 enters the loop (as the click label source).
        cur_t = torch.tensor(cur, dtype=ctl.img_dt, device=ctl.img_dev)
        var_t = torch.tensor(var, dtype=ctl.img_dt, device=ctl.img_dev)
        click_prefer = float(aud.ctr(var_t, copy)) > float(aud.ctr(cur_t, copy))
        ctl.record_click(click_prefer)       # trains the LEARNED ctr_head on the click label
        ctl.choose(prefer_variant=click_prefer)   # α=0: owner term is zero; policy ascends ctr_head
    return ctr0, ctl.ctr_now(), bad


def test_learned_ctr_head_raises_true_ctr():
    pytest.importorskip("torch")
    ctr0, ctr1, bad = _run_learned_ctr()
    assert bad == 0, f"{bad} non-finite frames"
    assert ctr1 > ctr0 + 0.1, f"learned CTR head did not raise true CTR: {ctr0:.3f} -> {ctr1:.3f}"


def test_record_click_requires_live_ctr():
    pytest.importorskip("torch")
    ba = _button_adam()
    ctl = ba.ButtonAdam(size=16, seed=0, alpha=0.5)   # default: simulated audience, no learned head
    ctl.propose()
    with pytest.raises(RuntimeError):
        ctl.record_click(True)


def test_default_mode_still_uses_simulated_audience():
    """live_ctr defaults off; the reward's CTR term is the simulated audience (B3 behaviour)."""
    pytest.importorskip("torch")
    ba = _button_adam()
    ctl = ba.ButtonAdam(size=16, seed=0, alpha=0.5)
    assert ctl.live_ctr is False
    assert not hasattr(ctl, "ctr_head"), "default mode should not build a learned CTR head"
