"""D9 — light smoke of the steered-generator demo orchestration.

The heavy train+steer pipeline is covered by test_latent_steer.py (3); this just confirms the
demo module imports and its pure helpers work (the full session and the tkinter window are
exercised by running them, not in CI — no display).
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_imports_and_centroid_helper_works():
    demo = _load("latent_demo", "latent_demo.py")
    assert hasattr(demo, "steer_session") and hasattr(demo, "train_generator")
    # a blob on the right has a positive centroid_x; on the left, negative.
    size = 8
    right = np.zeros((size, size)); right[:, -2:] = 1.0
    left = np.zeros((size, size)); left[:, :2] = 1.0
    assert demo._centroid_x(right) > 0.3
    assert demo._centroid_x(left) < -0.3
