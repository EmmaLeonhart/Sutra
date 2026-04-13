"""
VSA operations (bundle, bind, rotation) running as Brian2 spiking dynamics.

Previously `bundle` and `bind` ran as numpy arithmetic on the host. The
v15 reviewer (and the user) correctly pointed out that this makes the
"connectome" framing thin: if the elementwise ops run on the host, the
circuit is just a pattern matcher. Per `planning/sutra-spec/02-operations.md`
every Sutra vector operation runs on the substrate at runtime; neurons
do elementwise arithmetic all the time (EPSP summation for bundle,
sign-gated synapses for bind, weighted summation for rotation).

This module implements bundle and sign-flip bind as actual spiking
circuits. Each vector dimension i corresponds to one output neuron.
The output neuron's firing rate, relative to a baseline, encodes the
value of that dimension.

Encoding (centered rate code):
    value v_i in [-1, +1]  ->  firing rate  baseline + v_i * gain

bundle(a, b):
    Two input populations (one per operand) project excitatorily onto a
    shared output population. Rate at output_i = input_a_i + input_b_i
    (minus baseline). Literal EPSP summation; the math is in the cable
    equation, not in numpy.

bind(a, role):
    Output neuron i receives input from a_i via a synapse whose sign is
    fixed by sign(role_i) — excitatory if role_i > 0, inhibitory if
    role_i < 0. Result at i: +a_i or -a_i. Matches a * sign(role).
    The role is consumed by the wiring; no host product.

Validation below compares circuit outputs against the numpy reference
in FlyBrainVSA. We don't expect bit-exact equality — spiking output has
Poisson-like variance — we expect cosine similarity close to 1 and the
correct sign on every dimension.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass

import numpy as np

if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# -------------------------------------------------------------
# Rate-coding conventions
# -------------------------------------------------------------

BASELINE_HZ = 100.0    # firing rate encoding v=0 (high enough that Poisson fluctuations average well)
GAIN_HZ = 80.0         # firing rate change for v=+-1 (range [20, 180] Hz)
SIM_MS = 500.0         # simulation window per op
W_MV = 0.5             # synaptic weight
TAU_MS = 20.0          # membrane time constant


def _rate_of(v: np.ndarray) -> np.ndarray:
    """Value in [-1, +1] -> firing rate in Hz. Clamped non-negative."""
    return np.maximum(0.0, BASELINE_HZ + GAIN_HZ * v)


def _voltage_of(v: np.ndarray) -> float:
    """Expected steady-state depolarization (mV above rest) for a neuron
    whose excitatory input rate encodes v via _rate_of."""
    return _rate_of(v) * W_MV * TAU_MS * 1e-3  # rate_Hz * w_mV * tau_s


def _value_from_voltage(depol_mV: np.ndarray, baseline_depol: float) -> np.ndarray:
    """Invert: recover v given steady-state depolarization."""
    return (depol_mV - baseline_depol) / (GAIN_HZ * W_MV * TAU_MS * 1e-3)


# -------------------------------------------------------------
# bundle
# -------------------------------------------------------------

def neural_bundle(a: np.ndarray, b: np.ndarray, *, seed: int = 0) -> np.ndarray:
    """
    Compute bundle(a, b) = a + b as spiking dynamics in Brian2.

    Two Poisson input populations (rates encoding a and b) drive
    leaky-integrator output neurons (no threshold) one-to-one. The
    steady-state membrane depolarization is exactly w*tau*(rate_a +
    rate_b), i.e. linear in a + b after baseline subtraction. We
    time-average the membrane voltage to get the readout.
    """
    import brian2 as b2
    b2.start_scope()
    b2.seed(seed)
    dim = len(a)
    assert b.shape == a.shape

    in_a = b2.PoissonGroup(dim, rates=_rate_of(a) * b2.Hz)
    in_b = b2.PoissonGroup(dim, rates=_rate_of(b) * b2.Hz)

    eqs = 'dv/dt = (v_rest - v) / tau : volt'
    out = b2.NeuronGroup(
        dim, eqs, method='exact',
        namespace={'v_rest': 0*b2.mV, 'tau': TAU_MS*b2.ms},
    )
    out.v = 0 * b2.mV

    w = W_MV * b2.mV
    syn_a = b2.Synapses(in_a, out, on_pre='v_post += w', namespace={'w': w})
    syn_a.connect(j='i')
    syn_b = b2.Synapses(in_b, out, on_pre='v_post += w', namespace={'w': w})
    syn_b.connect(j='i')

    mon = b2.StateMonitor(out, 'v', record=True)
    net = b2.Network(in_a, in_b, out, syn_a, syn_b, mon)
    net.run(SIM_MS * b2.ms)

    # Discard first 100 ms so the integrator has reached steady state.
    t_ms = np.asarray(mon.t / b2.ms)
    mask = t_ms > 100.0
    mean_v = np.mean(np.asarray(mon.v / b2.mV)[:, mask], axis=1)  # per-neuron, mV

    # Baseline = steady-state voltage when both inputs are at rate BASELINE_HZ.
    baseline = 2 * BASELINE_HZ * W_MV * TAU_MS * 1e-3
    # Each input contributes rate*w*tau; decode by subtracting 2*baseline/2 = baseline.
    # Recovered value = (mean_v - baseline) / (GAIN * w * tau * 1e-3), but with
    # two inputs the total gain is 2*GAIN. So divide accordingly.
    return (mean_v - baseline) / (GAIN_HZ * W_MV * TAU_MS * 1e-3)


# -------------------------------------------------------------
# bind (sign-flip)
# -------------------------------------------------------------

def neural_bind(a: np.ndarray, role: np.ndarray, *, seed: int = 0) -> np.ndarray:
    """
    Compute bind(a, role) = a * sign(role) as spiking dynamics.

    For each output neuron i, the synapse from its input Poisson has a
    sign fixed by sign(role_i): excitatory if role_i >= 0, inhibitory
    if < 0. The input Poisson fires at _rate_of(a_i). The role is
    consumed by the synapse wiring; no host-side elementwise product.

    To make the inhibitory case work symmetrically, we also pass every
    output through a shared excitatory bias rail at BASELINE_HZ. This
    pushes the resting voltage up so inhibition has room to push it
    back down — the same trick real cortex uses (tonic excitation +
    gated inhibition).

    Steady-state voltage at output i:
        v_i = (BASELINE + sign(role_i) * rate_a_i) * w * tau + baseline_offset
    Subtract the appropriate baseline and the result decodes to
    a_i * sign(role_i).
    """
    import brian2 as b2
    b2.start_scope()
    b2.seed(seed)
    dim = len(a)
    assert role.shape == a.shape

    in_a = b2.PoissonGroup(dim, rates=_rate_of(a) * b2.Hz)
    in_bias = b2.PoissonGroup(dim, rates=BASELINE_HZ * b2.Hz)

    eqs = 'dv/dt = (v_rest - v) / tau : volt'
    out = b2.NeuronGroup(
        dim, eqs, method='exact',
        namespace={'v_rest': 0*b2.mV, 'tau': TAU_MS*b2.ms},
    )
    out.v = 0 * b2.mV

    w_exc = W_MV * b2.mV
    w_inh = -W_MV * b2.mV

    # Shared bias rail.
    bias_syn = b2.Synapses(in_bias, out, on_pre='v_post += w', namespace={'w': w_exc})
    bias_syn.connect(j='i')

    # Role-signed input.
    pos_dims = np.where(role >= 0)[0]
    neg_dims = np.where(role < 0)[0]
    syn_pos = b2.Synapses(in_a, out, on_pre='v_post += w', namespace={'w': w_exc})
    if len(pos_dims):
        syn_pos.connect(i=pos_dims, j=pos_dims)
    syn_neg = b2.Synapses(in_a, out, on_pre='v_post += w', namespace={'w': w_inh})
    if len(neg_dims):
        syn_neg.connect(i=neg_dims, j=neg_dims)

    mon = b2.StateMonitor(out, 'v', record=True)
    net = b2.Network(in_a, in_bias, out, bias_syn, syn_pos, syn_neg, mon)
    net.run(SIM_MS * b2.ms)

    t_ms = np.asarray(mon.t / b2.ms)
    mask = t_ms > 100.0
    mean_v = np.mean(np.asarray(mon.v / b2.mV)[:, mask], axis=1)

    # Derivation of steady-state voltage with target t = a_i * sign(role_i):
    #   role >= 0:  v = (bias + rate_a) * w * tau = 2*BASELINE*w*tau + GAIN*a*w*tau
    #                 = 2*B*w*tau + GAIN*t*w*tau      (t = a when role>=0)
    #   role <  0:  v = (bias - rate_a) * w * tau = 0 + (-GAIN*a)*w*tau
    #                 = GAIN*t*w*tau                  (t = -a when role<0)
    # So: t = (v - baseline_per_dim) / (GAIN * w * tau)
    # where baseline_per_dim is 2*B*w*tau for role>=0, 0 for role<0.
    per_dim_baseline = np.where(
        role >= 0,
        2 * BASELINE_HZ * W_MV * TAU_MS * 1e-3,
        0.0,
    )
    return (mean_v - per_dim_baseline) / (GAIN_HZ * W_MV * TAU_MS * 1e-3)


# -------------------------------------------------------------
# rotation / general linear map
# -------------------------------------------------------------

def neural_linear_map(M: np.ndarray, v: np.ndarray, *, seed: int = 0) -> np.ndarray:
    """
    Compute M @ v as spiking dynamics in Brian2. Works for any real
    matrix M, including rotation matrices (orthogonal, detM=1) used
    for eigenrotation loops.

    Each input dimension j is encoded as a Poisson group at rate
    `_rate_of(v_j)`. Output neuron i receives synapses from every
    input j with weight `M[i, j] * W_MV` — excitatory if M[i, j] > 0,
    inhibitory if < 0. The leaky-integrator steady-state voltage at i
    is (sum_j M[i,j]) * BASELINE*w*tau + GAIN*w*tau * (M @ v)_i, which
    we invert to recover (M @ v).

    No host-side matmul is performed on v; M is only used to set the
    pattern of synaptic weights (i.e. the connectome of this particular
    circuit), which is exactly what a real learned linear transform is
    in biology: a pattern of synaptic weights.
    """
    import brian2 as b2
    b2.start_scope()
    b2.seed(seed)
    d_out, d_in = M.shape
    assert v.shape == (d_in,)

    in_v = b2.PoissonGroup(d_in, rates=_rate_of(v) * b2.Hz)

    eqs = 'dv/dt = (v_rest - v) / tau : volt'
    out = b2.NeuronGroup(
        d_out, eqs, method='exact',
        namespace={'v_rest': 0*b2.mV, 'tau': TAU_MS*b2.ms},
    )
    out.v = 0 * b2.mV

    # Build synapses with per-connection weight. Brian2 lets us store `w`
    # as a per-synapse variable.
    syn = b2.Synapses(in_v, out, model='w : volt', on_pre='v_post += w')
    i_idx, j_idx = np.nonzero(M)          # input dim j, output dim i — note np.nonzero(M) returns (row=out, col=in)
    out_idx, in_idx = i_idx, j_idx
    syn.connect(i=in_idx.astype(np.int64), j=out_idx.astype(np.int64))
    syn.w = (M[out_idx, in_idx] * W_MV) * b2.mV

    mon = b2.StateMonitor(out, 'v', record=True)
    net = b2.Network(in_v, out, syn, mon)
    net.run(SIM_MS * b2.ms)

    t_ms = np.asarray(mon.t / b2.ms)
    mask = t_ms > 100.0
    mean_v_mV = np.mean(np.asarray(mon.v / b2.mV)[:, mask], axis=1)

    # Baseline per output: (sum_j M[i,j]) * BASELINE * w * tau
    row_sum = M.sum(axis=1)
    baseline_mV = row_sum * BASELINE_HZ * W_MV * TAU_MS * 1e-3
    return (mean_v_mV - baseline_mV) / (GAIN_HZ * W_MV * TAU_MS * 1e-3)


def neural_rotate(v: np.ndarray, planes: list, *, seed: int = 0) -> np.ndarray:
    """
    Compute R @ v where R is a composition of Givens rotations, on
    spiking neurons. `planes` is a list of (i, j, angle_rad) triples.

    Builds the explicit rotation matrix R at compile time (this is
    circuit specification — the pattern of synaptic weights — not the
    computation itself, just as the PN->KC connectome is specified at
    compile time by FlyWire), then runs v through the spiking network.
    """
    d = len(v)
    R = np.eye(d, dtype=np.float64)
    for (i, j, alpha) in planes:
        G = np.eye(d, dtype=np.float64)
        c, s = np.cos(alpha), np.sin(alpha)
        G[i, i] = c; G[j, j] = c
        G[i, j] = -s; G[j, i] = s
        R = G @ R
    return neural_linear_map(R, v, seed=seed)


# -------------------------------------------------------------
# Self-test
# -------------------------------------------------------------

if __name__ == '__main__':
    rng = np.random.RandomState(0)
    dim = 32
    a = rng.uniform(-1, 1, size=dim)
    b = rng.uniform(-1, 1, size=dim)
    role = rng.choice([-1.0, +1.0], size=dim)

    print(f"[neural_vsa] dim={dim}, sim_ms={SIM_MS}")

    # bundle
    ref_bundle = a + b
    got_bundle = neural_bundle(a, b)
    # bundle output saturates: a+b can exceed [-1,+1]; the rate code caps
    # at 0 Hz below, so we compare direction (cosine), not magnitude.
    cos_bundle = float(
        np.dot(ref_bundle, got_bundle)
        / (np.linalg.norm(ref_bundle) * np.linalg.norm(got_bundle) + 1e-12)
    )
    sign_match_bundle = float((np.sign(ref_bundle) == np.sign(got_bundle)).mean())
    print(f"  bundle:  cos={cos_bundle:.3f}  sign_match={sign_match_bundle:.2f}")

    # bind
    ref_bind = a * np.sign(role)
    got_bind = neural_bind(a, role)
    cos_bind = float(
        np.dot(ref_bind, got_bind)
        / (np.linalg.norm(ref_bind) * np.linalg.norm(got_bind) + 1e-12)
    )
    sign_match_bind = float((np.sign(ref_bind) == np.sign(got_bind)).mean())
    print(f"  bind:    cos={cos_bind:.3f}  sign_match={sign_match_bind:.2f}")

    # rotation: four Givens rotations in random 2D planes
    planes = [
        (0, 1, 0.7), (5, 12, -0.4),
        (3, 20, 0.9), (8, 25, -1.1),
    ]
    # Build reference R the same way neural_rotate does, apply to a.
    R_ref = np.eye(dim)
    for (i, j, alpha) in planes:
        G = np.eye(dim); c, s = np.cos(alpha), np.sin(alpha)
        G[i, i] = c; G[j, j] = c; G[i, j] = -s; G[j, i] = s
        R_ref = G @ R_ref
    ref_rot = R_ref @ a
    # Rotation accumulates 32*32 synapses worth of Poisson variance, so
    # give it a longer averaging window than bundle/bind.
    import brian2 as _b2
    _save = globals()['SIM_MS']
    globals()['SIM_MS'] = 1500.0
    got_rot = neural_rotate(a, planes)
    globals()['SIM_MS'] = _save
    cos_rot = float(
        np.dot(ref_rot, got_rot)
        / (np.linalg.norm(ref_rot) * np.linalg.norm(got_rot) + 1e-12)
    )
    sign_match_rot = float((np.sign(ref_rot) == np.sign(got_rot)).mean())
    print(f"  rotate:  cos={cos_rot:.3f}  sign_match={sign_match_rot:.2f}")

    # Pass criteria: cosine > 0.85 and sign_match > 0.9.
    ok_bundle = cos_bundle > 0.85 and sign_match_bundle > 0.9
    ok_bind = cos_bind > 0.85 and sign_match_bind > 0.9
    ok_rot = cos_rot > 0.85 and sign_match_rot > 0.9
    print()
    print(f"  bundle {'PASS' if ok_bundle else 'FAIL'}")
    print(f"  bind   {'PASS' if ok_bind else 'FAIL'}")
    print(f"  rotate {'PASS' if ok_rot else 'FAIL'}")
