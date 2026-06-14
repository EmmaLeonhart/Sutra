"""Tests for the host-side SPSA optimizer (a1 item 1b).

SPSA is host-side (no substrate ops), so these tests need no torch/Sutra — they
verify the optimizer MATH: the gradient estimate points the right way and θ
converges toward the reward maximizer, with the box clamp respected. The reward
here is a synthetic stand-in for the human warmer/colder signal.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

DEMO_GUI = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DEMO_GUI / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dist_to_target(render_theta, target, axes):
    return sum((render_theta[name] - target[name]) ** 2 for name, _, _ in axes)


def test_spsa_converges_toward_reward_maximizer() -> None:
    """With reward(θ) = -||θ_cont - target||² (a concave bump peaked at `target`),
    batched SPSA moves the continuous render-θ from the neutral start to near the
    target — final distance is a small fraction of the start distance, averaged
    over seeds (SPSA is stochastic)."""
    spsa = _load("hero_spsa", "hero_spsa.py")
    axes = spsa.HERO_SPSA_AXES
    # An on-screen, in-box target (each within center ± half_range).
    target = {"cx": 0.4, "cy": -0.3, "invs": 1.9, "bright": 1.4, "radius": 0.7,
              "accent": 0.5, "bg": 0.25, "cr": 0.9, "cg": 0.4, "cb": 0.3}

    def reward(th):
        return -_dist_to_target(th, target, axes)

    ratios = []
    for seed in range(5):
        opt = spsa.HeroSPSA(n_headlines=4, seed=seed)
        start_d = _dist_to_target(opt.current_render_theta(), target, axes)
        for _ in range(400):
            tp, tm = opt.propose()
            opt.update(reward(tp), reward(tm))
        final_d = _dist_to_target(opt.current_render_theta(), target, axes)
        ratios.append(final_d / start_d)
    mean_ratio = float(np.mean(ratios))
    assert mean_ratio < 0.25, f"SPSA did not converge: final/start dist = {mean_ratio}"


def test_spsa_gradient_sign_is_correct_on_a_monotonic_axis() -> None:
    """For a reward that strictly increases with one axis (`bright`), SPSA drives
    that axis UP from the neutral start — the gradient estimate has the right sign.
    Other axes have no reward signal, so they should stay near neutral."""
    spsa = _load("hero_spsa", "hero_spsa.py")

    def reward(th):
        return th["bright"]                      # maximize brightness only

    opt = spsa.HeroSPSA(n_headlines=4, seed=7)
    start_bright = opt.current_render_theta()["bright"]
    for _ in range(200):
        tp, tm = opt.propose()
        opt.update(reward(tp), reward(tm))
    final = opt.current_render_theta()
    assert final["bright"] > start_bright + 0.3, final["bright"]
    # a signal-free axis (radius) should not have wandered far from neutral (0.5)
    assert abs(final["radius"] - 0.5) < 0.35, final["radius"]


def test_spsa_respects_the_box_and_advances_batches() -> None:
    """θ stays in [-1,1]^D under a reward that pushes hard in one direction (the
    clamp holds), and the batch counter advances one per update (drives gain decay)."""
    spsa = _load("hero_spsa", "hero_spsa.py")
    opt = spsa.HeroSPSA(n_headlines=4, seed=1)

    def reward(th):
        return th["bright"] + th["cr"]           # push two axes to their max

    for _ in range(150):
        tp, tm = opt.propose()
        opt.update(reward(tp), reward(tm))
    assert opt.j == 150
    assert float(opt.theta.min()) >= -1.0 - 1e-12
    assert float(opt.theta.max()) <= 1.0 + 1e-12


def test_update_before_propose_raises() -> None:
    """The interactive contract: a perturbation must be proposed before it can be
    scored. Calling update() first is a programming error, surfaced loudly."""
    spsa = _load("hero_spsa", "hero_spsa.py")
    opt = spsa.HeroSPSA(n_headlines=4, seed=0)
    try:
        opt.update(1.0, -1.0)
    except RuntimeError:
        return
    raise AssertionError("update() before propose() should raise RuntimeError")
