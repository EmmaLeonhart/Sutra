"""B9 — the click-driven copy bandit closes the COPY half of the CTR loop.

B7's learned head optimizes the VISUAL design from clicks, but copy is discrete and not in the
rendered frame, so the learned head can't pick it — yet copy ("Buy now" vs "Learn more") is the
biggest CTR lever. In live mode `ButtonAdam` runs a per-copy click-rate bandit (UCB):
`select_copy_ucb()` chooses which copy to show (explore/exploit) and `record_copy_outcome(clicked)`
records whether the shown copy was clicked.

These tests drive it with a synthetic clicker that clicks with probability = the B2 audience CTR
for the shown copy (copy 0 "Buy now" highest). The bandit should explore every copy and
concentrate on — and select — the best one. Deterministic via a seeded clicker.
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


def test_copy_bandit_explores_and_selects_best_copy():
    import torch
    pytest.importorskip("torch")
    ba = _button_adam()
    ctl = ba.ButtonAdam(size=16, seed=0, alpha=0.0, live_ctr=True)
    aud = ctl.audience
    rng = np.random.default_rng(0)
    frame = ctl._render().detach()       # fixed frame so only the COPY varies the click prob
    for _ in range(300):
        ctl.select_copy_ucb()
        c = ctl.current_copy()
        p = float(aud.ctr(frame, c))     # B2 click probability for this copy
        ctl.record_copy_outcome(bool(rng.random() < p))
    impr = ctl.copy_impressions()
    rates = ctl.copy_click_rates()
    assert all(impr[c] > 0 for c in range(ctl.n_copy)), f"bandit left a copy unexplored: {impr}"
    # UCB concentrates pulls on the best arm — "Buy now" (copy 0) should be pulled the most...
    assert int(np.argmax(impr)) == 0, f"bandit did not favour the best copy: impressions={impr}"
    # ...and its empirical click rate should lead.
    assert int(np.argmax(rates)) == 0, f"best-rate copy is not 'Buy now': rates={[round(r,3) for r in rates]}"


def test_copy_bandit_methods_require_live_ctr():
    pytest.importorskip("torch")
    ba = _button_adam()
    ctl = ba.ButtonAdam(size=16, seed=0, alpha=0.5)   # default sim mode
    with pytest.raises(RuntimeError):
        ctl.record_copy_outcome(True)
    with pytest.raises(RuntimeError):
        ctl.select_copy_ucb()
