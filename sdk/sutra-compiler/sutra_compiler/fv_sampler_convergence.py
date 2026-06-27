"""Formal-verification tooling: continuous-time convergence of the energy-based
sampler (the stochastic-ODE / Langevin angle).

`paper/formal-verification/paper.md` §7 and `planning/sutra-spec/formal-
verification.md` (thrml target) cover Sutra's second, **probabilistic** compile
target: a Sutra value is a register of spins, an operation is an energy *factor*,
and the answer is the configuration the block-Gibbs sampler settles into. The Lean
proofs (`fv-lean/`) machine-check the *discrete-time* picture — the gadget's
ground-state is the strict energy minimum, the finite Glauber chain is irreducible
+ aperiodic with the Gibbs measure as its unique stationary mode, and the
*two-state* mixing rate (`GibbsMathlib.lean`). What those files explicitly leave
open (`GibbsChain.lean`: *"the general multi-state spectral gap and the
continuous-time Langevin/SDE limit"*) is the continuous-time convergence of the
sampler's law. This module measures it.

The continuous-time limit of single-site block-Gibbs is a **Markov jump process**
with generator `Q` (the heat-bath rates). Its law obeys the master equation — the
Kolmogorov-forward / Fokker–Planck ODE for jump processes —

    dp/dt = Qᵀ · p,

which is the distribution-level statement of the Langevin/jump stochastic
dynamics. For a generator built from heat-bath rates the chain is **reversible**
with respect to the Gibbs measure ``π(s) ∝ exp(−β·E(s))`` (detailed balance), so
``Q`` is self-adjoint in the ``π``-weighted inner product: its eigenvalues are
real and ≤ 0, the eigenvalue 0 belongs to ``π``, and the **spectral gap**
``γ = −max{Re λ : λ ≠ 0}`` is the exact continuous-time convergence rate —
``‖p(t) − π‖`` decays like ``e^{−γ t}``. A positive gap is exactly the
continuous-time analog of the discrete mixing the Lean files prove, for the
*full multi-state* chain, not only the two-state clamped decode.

This is host-side **verification analysis of the real gadget energy** (an
eigen/ODE computation on the actual energy landscape the sampler runs), the same
role as `fv_poly_bound.py` / `fv_loop_convergence.py` — compile/verify-time
tooling, not a Sutra runtime op. The energy passed in must be the gadget's true
energy (e.g. the AND gadget's machine-checked ``E4``); the module then *measures*
stationarity, reversibility, the spectral gap, and the law's decay rate.

Scope: this is the discrete-state continuous-time jump process (the faithful
limit for spin gadgets). The continuous-*space* overdamped Langevin diffusion
``dX = −∇U dt + √(2/β) dW`` on a relaxed energy is the further limit, named here
but not claimed.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np


def _states(n_spins: int) -> list[tuple[int, ...]]:
    """All spin configurations in {−1, +1}^n_spins (true = +1)."""
    return list(itertools.product((-1, 1), repeat=n_spins))


@dataclass(frozen=True)
class SamplerConvergenceReport:
    """Continuous-time convergence analysis of a gadget's Gibbs sampler.

    ``spectral_gap`` is the decisive quantity: the slowest non-stationary mode's
    decay rate, hence the rate ``e^{−gap·t}`` at which the law reaches ``π``.
    """

    beta: float
    n_states: int
    spectral_gap: float
    stationary_residual: float  # max|πᵀQ|, should be ~0 (π is stationary)
    detailed_balance_violation: float  # max|π(s)Q(s,t) − π(t)Q(t,s)|, ~0 if reversible
    eigenvalues_real: bool  # all generator eigenvalues real (reversible ⟹ true)
    mode_state: tuple  # argmax π — the configuration the sampler concentrates on
    pi_min: float
    pi_max: float

    def converges(self) -> bool:
        """True iff the sampler provably relaxes to a unique stationary law: a
        strictly positive spectral gap (with π stationary and the chain
        reversible)."""
        return (
            self.spectral_gap > 0.0
            and self.stationary_residual < 1e-9
            and self.detailed_balance_violation < 1e-9
        )

    def mixing_time(self, eps: float = 1e-3) -> float:
        """Continuous time for the slowest mode to decay to ``eps``: ln(1/eps)/γ.
        The exact continuous-time analog of a discrete mixing time."""
        return float(np.log(1.0 / eps) / self.spectral_gap)


def build_generator(energy, n_spins: int, beta: float):
    """Build the continuous-time single-site Glauber (heat-bath) generator.

    ``energy(state) -> float`` is the gadget energy on a spin tuple in
    {−1,+1}^n. Returns ``(states, E, pi, Q)`` where ``Q`` is the M×M generator:
    off-diagonal ``Q[s, s'] = 1/(1 + exp(β·(E(s') − E(s))))`` between single-spin-
    flip neighbours (heat-bath rate, detailed-balanced w.r.t. ``π``), 0 between
    non-neighbours, and ``Q[s, s] = −Σ_{s'≠s} Q[s, s']`` (rows sum to 0).
    """
    states = _states(n_spins)
    index = {s: i for i, s in enumerate(states)}
    m = len(states)
    E = np.array([float(energy(s)) for s in states], dtype=float)

    # Gibbs measure π ∝ exp(−β E), in a numerically stable form.
    logp = -beta * E
    logp -= logp.max()
    pi = np.exp(logp)
    pi /= pi.sum()

    Q = np.zeros((m, m), dtype=float)
    for i, s in enumerate(states):
        for k in range(n_spins):
            flipped = list(s)
            flipped[k] = -flipped[k]
            j = index[tuple(flipped)]
            dE = E[j] - E[i]
            Q[i, j] = 1.0 / (1.0 + np.exp(beta * dE))  # heat-bath rate s -> s'
    for i in range(m):
        Q[i, i] = -Q[i].sum()
    return states, E, pi, Q


def analyze_sampler_convergence(
    energy, n_spins: int, *, beta: float = 1.0, tol: float = 1e-9
) -> SamplerConvergenceReport:
    """Measure the continuous-time convergence of the gadget's Gibbs sampler:
    build the generator, verify ``π`` is stationary and the chain reversible, and
    return the spectral gap (the law's decay rate)."""
    states, E, pi, Q = build_generator(energy, n_spins, beta)

    stationary_residual = float(np.max(np.abs(pi @ Q)))

    # Detailed balance: π(s) Q(s,t) == π(t) Q(t,s) for all s != t.
    flux = pi[:, None] * Q
    detailed_balance_violation = float(np.max(np.abs(flux - flux.T)))

    eig = np.linalg.eigvals(Q)
    eigenvalues_real = bool(np.max(np.abs(eig.imag)) < 1e-9)
    real_parts = eig.real
    # The stationary mode has eigenvalue 0; the gap is the slowest non-zero mode.
    nonzero = real_parts[np.abs(real_parts) > tol]
    spectral_gap = float(-nonzero.max()) if nonzero.size else 0.0

    mode_idx = int(np.argmax(pi))
    return SamplerConvergenceReport(
        beta=beta,
        n_states=len(states),
        spectral_gap=spectral_gap,
        stationary_residual=stationary_residual,
        detailed_balance_violation=detailed_balance_violation,
        eigenvalues_real=eigenvalues_real,
        mode_state=states[mode_idx],
        pi_min=float(pi.min()),
        pi_max=float(pi.max()),
    )


def integrate_master_equation(
    Q: np.ndarray, p0: np.ndarray, *, t_max: float, n_steps: int
):
    """Integrate the master ODE ``dp/dt = Qᵀ p`` by RK4 from ``p0``.

    Returns ``(times, P)`` where ``P[k]`` is the law at ``times[k]``. This is the
    distribution-level trajectory of the sampler's stochastic dynamics — the
    object whose decay to ``π`` the spectral gap predicts.
    """
    A = Q.T
    dt = t_max / n_steps
    p = np.array(p0, dtype=float)
    times = np.zeros(n_steps + 1)
    P = np.zeros((n_steps + 1, p.size))
    P[0] = p
    for k in range(n_steps):
        k1 = A @ p
        k2 = A @ (p + 0.5 * dt * k1)
        k3 = A @ (p + 0.5 * dt * k2)
        k4 = A @ (p + dt * k3)
        p = p + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        times[k + 1] = (k + 1) * dt
        P[k + 1] = p
    return times, P


def measured_decay_rate(times: np.ndarray, tv: np.ndarray) -> float:
    """Estimate the asymptotic exponential decay rate of the total-variation
    distance ``tv(t)`` by a least-squares fit of ``log tv`` over its tail (where
    the slowest spectral mode dominates). This is the *measured* convergence rate
    to compare against the spectral gap."""
    # Use the tail half, with strictly-positive TV (drop the converged floor).
    n = len(times)
    sl = slice(n // 2, n)
    t, y = times[sl], tv[sl]
    good = y > 1e-12
    t, y = t[good], y[good]
    if t.size < 2:
        return float("nan")
    slope = np.polyfit(t, np.log(y), 1)[0]
    return float(-slope)
