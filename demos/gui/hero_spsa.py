"""Host-side batched SPSA optimizer for the warmer/colder hero (a1 item 1b).

This is the optimizer of the a1 steering demo. It is **host-side** — Simultaneous
Perturbation Stochastic Approximation over the hero's parameter vector θ, scoring
the SUBSTRATE-rendered hero by a scalar reward (warmer/colder). The optimizer
itself runs no Sutra ops; it nudges the call arguments that `whole_frame.render_*`
feeds the substrate (the a1 spec is explicit: the optimizer is host-side SPSA over
substrate-rendered output, NOT substrate-native training — do not claim otherwise).

Ported from the validated `spsa_dense` in the private founder hub
(`analysis/g1_simulation.py`), keeping its math verbatim:
  - Rademacher perturbation `delta ∈ {-1,+1}^D`
  - perturbation-gain decay `ck = c0 / (j+1)^0.101`   (SPSA gamma)
  - step-size decay        `ak = a0 / (j+1+10)^0.602`  (SPSA alpha, +10 offset)
  - two-sided gradient est. `ghat = (r_plus - r_minus) / (2*ck) * delta`
  - clamp θ to the box [-1,1]^D after every step

SPSA optimizes a NORMALIZED θ in [-1,1]^D (neutral start 0 — no expert prior, the
source's conservative default). Each continuous render axis maps from [-1,1] by an
affine `center + half_range * norm` so SPSA stays in its natural box while the
renderer sees its own ranges; the per-headline mixture weights map straight through
(`whole_frame.select_headline` takes the argmax).
"""
from __future__ import annotations

import numpy as np

# (render-axis name, center, half_range): norm ∈ [-1,1] -> center + half_range*norm.
# Ranges chosen so the neutral θ=0 lands on a clean on-screen hero and the box edges
# stay well-defined (no NaN/blank): e.g. invs ∈ [0.1, 2.5], bright ∈ [0.2, 1.8].
HERO_SPSA_AXES = (
    ("cx",     0.0, 0.8),    # glow centre x   ∈ [-0.8, 0.8]
    ("cy",     0.0, 0.8),    # glow centre y   ∈ [-0.8, 0.8]
    ("invs",   1.3, 1.2),    # glow spread     ∈ [ 0.1, 2.5]
    ("bright", 1.0, 0.8),    # glow brightness ∈ [ 0.2, 1.8]
    ("radius", 0.5, 0.4),    # ring radius     ∈ [ 0.1, 0.9]
    ("accent", 0.3, 0.3),    # ring brightness ∈ [ 0.0, 0.6]
    ("bg",     0.1, 0.3),    # background      ∈ [-0.2, 0.4]
    ("cr",     0.6, 0.4),    # red tint        ∈ [ 0.2, 1.0]
    ("cg",     0.6, 0.4),    # green tint      ∈ [ 0.2, 1.0]
    ("cb",     0.6, 0.4),    # blue tint       ∈ [ 0.2, 1.0]
)


class HeroSPSA:
    """Batched two-sided SPSA over the hero θ. Interactive flow per batch:

        tp, tm = opt.propose()          # two perturbed render-θ dicts to score
        ...render+show tp, read reward r_plus; render+show tm, read reward r_minus...
        opt.update(r_plus, r_minus)     # one SPSA step; advances the batch counter

    `current_render_theta()` is the current best θ as a render dict (what the live
    window paints between perturbations)."""

    def __init__(self, n_headlines: int, seed: int = 0,
                 a0: float = 0.25, c0: float = 0.25):
        self.cont = HERO_SPSA_AXES
        self.n_headlines = int(n_headlines)
        self.D = len(self.cont) + self.n_headlines
        self.theta = np.zeros(self.D)          # neutral start in [-1,1]^D
        self.rng = np.random.default_rng(seed)
        self.a0, self.c0 = float(a0), float(c0)
        self.j = 0                             # batch counter (drives the gain decay)
        self._pending = None                   # (delta, ck) carried propose -> update

    # --- SPSA gain schedule (verbatim from spsa_dense) ---
    def _ck(self) -> float:
        return self.c0 / (self.j + 1) ** 0.101

    def _ak(self) -> float:
        return self.a0 / (self.j + 1 + 10) ** 0.602

    # --- normalized θ -> render θ dict ---
    def to_render_theta(self, norm: np.ndarray) -> dict:
        th = {name: center + hr * float(norm[i])
              for i, (name, center, hr) in enumerate(self.cont)}
        base = len(self.cont)
        th["headline_w"] = [float(norm[base + k]) for k in range(self.n_headlines)]
        return th

    def current_render_theta(self) -> dict:
        return self.to_render_theta(self.theta)

    # --- the two-sided SPSA step, split for interactive scoring ---
    def propose(self):
        """Draw a Rademacher perturbation and return the two perturbed render-θ
        dicts (θ+ck·delta, θ−ck·delta), each clamped into the box. The caller
        renders + scores both; the perturbation is stashed for `update`."""
        ck = self._ck()
        delta = self.rng.choice([-1.0, 1.0], self.D)
        tp = np.clip(self.theta + ck * delta, -1, 1)
        tm = np.clip(self.theta - ck * delta, -1, 1)
        self._pending = (delta, ck)
        return self.to_render_theta(tp), self.to_render_theta(tm)

    def update(self, reward_plus: float, reward_minus: float) -> np.ndarray:
        """One SPSA gradient ascent step from the two scored rewards (reward is to
        be MAXIMIZED — warmer is +). Advances the batch counter. Returns the new θ."""
        if self._pending is None:
            raise RuntimeError("update() called before propose()")
        delta, ck = self._pending
        ghat = (float(reward_plus) - float(reward_minus)) / (2.0 * ck) * delta
        self.theta = np.clip(self.theta + self._ak() * ghat, -1, 1)
        self.j += 1
        self._pending = None
        return self.theta.copy()
