"""Formal-verification artifact: continuous-time convergence of the energy-based
sampler (the §7 stochastic-ODE / Langevin angle), on the REAL AND-gadget energy.

`fv-lean/GibbsChain.lean` machine-checks the discrete chain's hypotheses
(irreducible, aperiodic, unique Gibbs mode) and names what it leaves open: *"the
general multi-state spectral gap and the continuous-time Langevin/SDE limit."*
This test measures exactly that, numerically, on the machine-checked AND-gadget
energy `E4` (`AndGadget.lean`): the continuous-time Glauber generator's Gibbs
measure is stationary and reversible, its spectral gap is positive (so the law
converges exponentially), the mode is the correct AND output, and the master ODE
`dp/dt = Qᵀp` decays at the rate the spectral gap predicts.

Referenced by `paper/formal-verification/paper.md` §7.
"""
from __future__ import annotations

import pytest

np = pytest.importorskip("numpy", reason="the generator analysis needs numpy")

from sutra_compiler.fv_sampler_convergence import (
    analyze_sampler_convergence,
    build_generator,
    integrate_master_equation,
    measured_decay_rate,
)


def _sp(b: int) -> int:
    # spins already in {−1, +1}; identity, kept for parity with the Lean `sp`.
    return b


def _e4_free(state):
    """The machine-checked AND-gadget energy E4 over the free state (a, b, z),
    spins in {−1,+1}. 4*E = −A − B + 2Z + A*B − 2*A*Z − 2*B*Z (AndGadget.lean)."""
    a, b, z = state
    return -a - b + 2 * z + a * b - 2 * a * z - 2 * b * z


def _e4_clamped(a_fixed: int, b_fixed: int):
    """The clamped-decode energy: a, b fixed, only z sampled (a 2-state chain) —
    the case GibbsChain proves the unique mode for."""
    def energy(state):
        (z,) = state
        return _e4_free((a_fixed, b_fixed, z))
    return energy


# --- The full 3-spin (8-state, multi-state) chain -----------------------------

def test_full_and_gadget_chain_converges() -> None:
    rep = analyze_sampler_convergence(_e4_free, n_spins=3, beta=1.0)
    print(
        f"[fv-sampler] full AND chain: states={rep.n_states} "
        f"gap={rep.spectral_gap:.6f} stat_resid={rep.stationary_residual:.2e} "
        f"db_viol={rep.detailed_balance_violation:.2e} real_eig={rep.eigenvalues_real} "
        f"mix_time(1e-3)={rep.mixing_time():.3f}"
    )
    # Gibbs measure stationary + reversible -> a unique limit law.
    assert rep.stationary_residual < 1e-9
    assert rep.detailed_balance_violation < 1e-9
    assert rep.eigenvalues_real, "reversible generator must have real spectrum"
    # Positive spectral gap = exponential convergence (the multi-state rate the
    # Lean files leave open).
    assert rep.spectral_gap > 0.0
    assert rep.converges()


# --- The clamped-decode chain mode is the correct AND output ------------------

@pytest.mark.parametrize(
    "a,b,expected_z",
    [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, -1)],  # z = a AND b (in ±1)
)
def test_clamped_decode_mode_is_and_output(a, b, expected_z) -> None:
    rep = analyze_sampler_convergence(_e4_clamped(a, b), n_spins=1, beta=2.0)
    assert rep.converges()
    assert rep.mode_state == (expected_z,), (
        f"clamped Gibbs mode {rep.mode_state} != AND output ({expected_z},) "
        f"for a={a}, b={b}"
    )


# --- The master ODE decays at the spectral-gap rate ---------------------------

def test_master_equation_decays_at_spectral_gap_rate() -> None:
    """Integrate the law's ODE dp/dt = Qᵀp from a worst-case start (point mass on
    the highest-energy state) and confirm the total-variation distance to π
    decays at the rate the spectral gap predicts — the measured continuous-time
    convergence statement."""
    beta = 1.0
    states, E, pi, Q = build_generator(_e4_free, n_spins=3, beta=beta)
    rep = analyze_sampler_convergence(_e4_free, n_spins=3, beta=beta)
    gap = rep.spectral_gap

    # Worst-case initial law: all mass on the highest-energy configuration.
    p0 = np.zeros(len(states))
    p0[int(np.argmax(E))] = 1.0

    t_max = 8.0 / gap  # several mixing times
    times, P = integrate_master_equation(Q, p0, t_max=t_max, n_steps=4000)

    # Mass conservation + nonnegativity along the trajectory (a valid law).
    assert np.allclose(P.sum(axis=1), 1.0, atol=1e-9)
    assert P.min() > -1e-9

    tv = 0.5 * np.abs(P - pi[None, :]).sum(axis=1)
    # Monotone decay to ~0.
    assert tv[-1] < 1e-3, f"law did not converge to π: TV={tv[-1]:.3e}"

    rate = measured_decay_rate(times, tv)
    print(
        f"[fv-sampler] master-ODE decay: spectral_gap={gap:.6f} "
        f"measured_rate={rate:.6f} ratio={rate / gap:.4f} TV_end={tv[-1]:.2e}"
    )
    # The measured asymptotic decay rate matches the spectral gap (the slowest
    # mode governs the tail). 5% tolerance absorbs the fit + RK4 error.
    assert abs(rate - gap) / gap < 0.05, (
        f"measured decay rate {rate:.6f} disagrees with spectral gap {gap:.6f}"
    )
