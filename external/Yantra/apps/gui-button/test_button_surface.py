"""Y2 — the Yantra gui-button host surface (spawns the Sutra button substrate-server).

Verifies the surface drives the spawned substrate-server protocol end-to-end: it renders the
current/variant button on the substrate, forwards owner preferences and visitor clicks, and
reads state. Runs a real subprocess (not in Sutra's demos-ci, which is `pytest demos/`; run
directly: `pytest external/Yantra/apps/gui-button`).
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _surface(**kw):
    spec = importlib.util.spec_from_file_location("yantra_button_surface", _DIR / "button_surface.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.YantraButtonSurface(size=16, seed=0, **kw)


def test_surface_renders_substrate_button_frames():
    pytest.importorskip("torch")
    with _surface() as s:
        cur = s.frame("current")
        var = s.frame("variant")
        assert cur.shape == (16, 16, 3) and var.shape == (16, 16, 3)
        assert np.isfinite(cur).all() and np.isfinite(var).all()
        assert (cur >= 0).all() and (cur <= 1).all(), "frame not in displayed [0,1]"


def test_surface_owner_prefer_advances_round():
    pytest.importorskip("torch")
    with _surface() as s:
        assert s.prefer(variant=True) == 1
        assert s.prefer(variant=False) == 2


def test_surface_click_and_state():
    pytest.importorskip("torch")
    with _surface(live_ctr=True) as s:
        s.frame("current")
        s.click("variant")
        st = s.state()
        assert st["clicks"] >= 1
        assert set(("round", "clicks", "ctr_observed", "copy", "theta")) <= set(st)
        assert "fr" in st["theta"]
