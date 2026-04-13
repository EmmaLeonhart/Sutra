"""
VSA operations (bundle, bind, rotate) backed by REAL FlyWire v783
connectivity. Sister module to neural_vsa.py, which used synthetic
one-to-one synapse matrices and arbitrary weights.

Here, every synapse weight comes from FlyWire:
  - connection count (syn_count) -> magnitude
  - predicted presynaptic neurotransmitter -> sign
      ACH                  -> +1 (excitatory)
      GABA, GLUT           -> -1 (inhibitory-ish; GLUT in Drosophila
                              is predominantly inhibitory via GluCl)
      SER, DA, OCT, ''     ->  0 (neuromodulatory / unknown — dropped)

No weight is tuned. Whatever the connectome gives us IS the circuit.
The question this module answers is NOT "can we make it work?" but
"what does the real wiring actually compute when we push a VSA-shaped
signal through it?"

Per CLAUDE.md "NO MATH SHORTCUTS":
 - If the real wiring does not implement a clean VSA operation, we
   REPORT that honestly rather than tune things until it does.
 - Rotation R is biologically fixed by anatomy. We do not pick R; we
   measure what the anatomy gives us and describe it (angle,
   orthogonality, spectrum). If it is not orthogonal, we say so.

Population choices (all from FlyWire v783 classification):
 - ALPN (685 antennal-lobe projection neurons): bundle inputs
     * 474 ACh (excitatory), 211 GABA/GLUT (inhibitory). The NT split
       is the substrate-native resource we use for sign-flip bind.
 - LHLN (517 lateral-horn local neurons): downstream target for bundle
   and rotate. ALPN->LHLN has 7,068 nonzero connections, 125k synapses.
 - Kenyon Cells (5,177): downstream target for bind (ALPN->KC has
   22,298 nonzero connections, 367k synapses — the canonical
   olfactory-to-MB projection).

Substrate status:
 - Brian2 LIF is the dev-sim. The *weights* come from FlyWire. A
   neuromorphic or biological deployment would use the same weight
   matrix with its own neuron model.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8' and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Local import — flywire_loader lives in the same directory.
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from flywire_loader import load_flywire, FlyWireConnectome  # noqa: E402


# -------------------------------------------------------------
# Encoding / rate-coding conventions (shared with neural_vsa.py)
# -------------------------------------------------------------

BASELINE_HZ = 100.0
GAIN_HZ = 80.0
SIM_MS = 500.0
W_UNIT_MV = 0.02   # millivolt PER SYNAPSE. Real FlyWire counts are 1-100;
                   # the per-synapse EPSP in fly central neurons is ~0.1-1 mV.
                   # Using 0.02 mV/synapse keeps total drive comparable to
                   # the synthetic module without rescaling the real matrix.
TAU_MS = 20.0

NT_SIGN = {
    'ACH':  +1.0,
    'GABA': -1.0,
    'GLUT': -1.0,   # Drosophila glutamate mostly inhibitory (GluCl)
    # SER, DA, OCT, '' -> 0 (modulatory / unknown)
}


def _rate_of(v: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, BASELINE_HZ + GAIN_HZ * v)


# -------------------------------------------------------------
# Substrate selection
# -------------------------------------------------------------

@dataclass
class FlyWireSubstrate:
    """Caches the populations and signed weight matrices we reuse."""
    fw: FlyWireConnectome
    alpn: np.ndarray          # row indices of ALPN
    lhln: np.ndarray          # row indices of LHLN
    kc:   np.ndarray          # row indices of Kenyon cells
    alpn_nt_sign: np.ndarray  # per-ALPN presynaptic sign in {-1, 0, +1}
    W_alpn_to_lhln: np.ndarray  # (|LHLN|, |ALPN|), signed by presyn NT, weighted by syn_count
    W_alpn_to_kc:   np.ndarray  # (|KC|,   |ALPN|)


_SUBSTRATE_CACHE: FlyWireSubstrate | None = None


def get_substrate(verbose: bool = False) -> FlyWireSubstrate:
    global _SUBSTRATE_CACHE
    if _SUBSTRATE_CACHE is not None:
        return _SUBSTRATE_CACHE
    fw = load_flywire(verbose=verbose)
    alpn = np.where(fw.cls == 'ALPN')[0]
    lhln = np.where(fw.cls == 'LHLN')[0]
    kc = np.where(fw.cls == 'Kenyon_Cell')[0]

    nt = fw.nt_type[alpn]
    signs = np.array([NT_SIGN.get(str(x), 0.0) for x in nt], dtype=np.float64)

    # Build signed weight matrices.
    # counts[pre, post] -> we want W[post, pre] so that y = W @ x is conventional.
    C_lh = fw.counts[alpn, :][:, lhln].toarray().astype(np.float64)  # (|ALPN|, |LHLN|)
    W_lh = (C_lh.T) * signs[np.newaxis, :]                            # (|LHLN|, |ALPN|)
    C_kc = fw.counts[alpn, :][:, kc].toarray().astype(np.float64)
    W_kc = (C_kc.T) * signs[np.newaxis, :]

    _SUBSTRATE_CACHE = FlyWireSubstrate(
        fw=fw, alpn=alpn, lhln=lhln, kc=kc,
        alpn_nt_sign=signs,
        W_alpn_to_lhln=W_lh,
        W_alpn_to_kc=W_kc,
    )
    return _SUBSTRATE_CACHE


# -------------------------------------------------------------
# Generic Brian2 linear-map runner
# -------------------------------------------------------------

def _run_signed_linear_map(
    W: np.ndarray, v: np.ndarray, *, seed: int = 0, sim_ms: float = SIM_MS,
    w_unit_mV: float = W_UNIT_MV, bias_v_in: np.ndarray | None = None,
) -> np.ndarray:
    """
    Push a rate-coded vector v through a signed synaptic weight matrix W
    using a Brian2 LIF-integrator network. Returns the vector read out
    from steady-state voltage at the output layer. Weights are NOT
    tuned: the caller passes W (typically from FlyWire) and we simulate.

    W: (d_out, d_in), arbitrary real, sign = synapse sign, magnitude =
       per-synapse count (so W[i,j] = +17 means 17 ACh synapses from
       input j to output i; -3 means 3 GABA synapses).
    v: (d_in,), values in [-1, +1]. Mapped to Poisson rate via _rate_of.
    bias_v_in: optional (d_in,) rate-scale bias added to every input
       (used by neural_bind_flywire to keep inhibitory channels encoding
       a rather than -a when we want to cancel the bias on a-side).

    Returns: (d_out,) estimated signal. Subtracts the connectome-baseline
    row-sum contribution, so the output encodes W @ v (up to Poisson
    noise and saturation at rate=0).
    """
    import brian2 as b2
    b2.start_scope()
    b2.seed(seed)
    d_out, d_in = W.shape
    assert v.shape == (d_in,), f"v shape {v.shape} vs d_in {d_in}"

    rates = _rate_of(v)
    in_grp = b2.PoissonGroup(d_in, rates=rates * b2.Hz)

    eqs = 'dv/dt = (v_rest - v) / tau : volt'
    out = b2.NeuronGroup(
        d_out, eqs, method='exact',
        namespace={'v_rest': 0*b2.mV, 'tau': TAU_MS*b2.ms},
    )
    out.v = 0 * b2.mV

    # Build per-synapse weighted connections from nonzero entries of W.
    out_idx, in_idx = np.nonzero(W)
    if len(out_idx) == 0:
        # Degenerate: no connections. Return zeros.
        return np.zeros(d_out)
    syn = b2.Synapses(in_grp, out, model='w : volt', on_pre='v_post += w')
    syn.connect(i=in_idx.astype(np.int64), j=out_idx.astype(np.int64))
    syn.w = (W[out_idx, in_idx] * w_unit_mV) * b2.mV

    mon = b2.StateMonitor(out, 'v', record=True)
    net = b2.Network(in_grp, out, syn, mon)
    net.run(sim_ms * b2.ms)

    t_ms = np.asarray(mon.t / b2.ms)
    mask = t_ms > 100.0
    mean_v_mV = np.mean(np.asarray(mon.v / b2.mV)[:, mask], axis=1)

    # Steady-state per output i:
    #   v_i = sum_j W[i,j] * rate_j * w_unit * tau
    #       = sum_j W[i,j] * (BASELINE + GAIN*v_j) * w_unit * tau
    #       = (row_sum_i * BASELINE + GAIN * (W@v)_i) * w_unit * tau
    # So: (W@v)_i = (v_i/(w_unit*tau) - row_sum_i * BASELINE) / GAIN
    row_sum = W.sum(axis=1)
    scale = w_unit_mV * TAU_MS * 1e-3  # mV * s
    # expected_mV(target = Wv_i) = (row_sum_i*BASELINE + GAIN*Wv_i) * scale
    # invert:
    Wv_est = (mean_v_mV / scale - row_sum * BASELINE_HZ) / GAIN_HZ
    return Wv_est


# -------------------------------------------------------------
# 1. neural_bundle_flywire
# -------------------------------------------------------------

def neural_bundle_flywire(a: np.ndarray, b: np.ndarray, *, seed: int = 0,
                          sim_ms: float = SIM_MS) -> tuple[np.ndarray, np.ndarray]:
    """
    Bundle two ALPN-shaped vectors by letting two copies of the ALPN
    population project onto LHLN using the REAL ALPN->LHLN wiring
    (signed by NT, weighted by syn_count).

    y_ref = W_alpn_to_lhln @ a  +  W_alpn_to_lhln @ b  =  W @ (a + b)

    Because the two input populations share the same downstream
    connectivity, EPSP summation at LHLN literally integrates (a + b).
    That's what bundle IS — superposition via convergent wiring. The
    honest question is how faithfully LHLN voltage encodes W(a+b) given
    the real rank and spectral structure of W.

    Args:
      a, b: shape (|ALPN|,) = (685,). Values in [-1, +1].

    Returns:
      (y_sim, y_ref) both shape (|LHLN|,) = (517,).
      y_sim: estimate from Brian2 run.
      y_ref: exact W @ (a + b).
    """
    S = get_substrate()
    assert a.shape == (len(S.alpn),)
    assert b.shape == (len(S.alpn),)
    W = S.W_alpn_to_lhln

    # Run both operand populations through the SAME W in a single
    # simulation by treating (a + b) as the input rate on a doubled-
    # synapse circuit. Concretely: two PoissonGroups, same W, summed
    # at the same LIF output. This is exactly the two-convergent-
    # populations wiring (like two olfactory hemispheres projecting to
    # LH), and it sums at the membrane by cable-equation.
    import brian2 as b2
    b2.start_scope()
    b2.seed(seed)
    d_out, d_in = W.shape

    in_a = b2.PoissonGroup(d_in, rates=_rate_of(a) * b2.Hz)
    in_b = b2.PoissonGroup(d_in, rates=_rate_of(b) * b2.Hz)

    eqs = 'dv/dt = (v_rest - v) / tau : volt'
    out = b2.NeuronGroup(
        d_out, eqs, method='exact',
        namespace={'v_rest': 0*b2.mV, 'tau': TAU_MS*b2.ms},
    )
    out.v = 0 * b2.mV

    out_idx, in_idx = np.nonzero(W)
    w_vals = (W[out_idx, in_idx] * W_UNIT_MV) * b2.mV

    syn_a = b2.Synapses(in_a, out, model='w : volt', on_pre='v_post += w')
    syn_a.connect(i=in_idx.astype(np.int64), j=out_idx.astype(np.int64))
    syn_a.w = w_vals

    syn_b = b2.Synapses(in_b, out, model='w : volt', on_pre='v_post += w')
    syn_b.connect(i=in_idx.astype(np.int64), j=out_idx.astype(np.int64))
    syn_b.w = w_vals

    mon = b2.StateMonitor(out, 'v', record=True)
    net = b2.Network(in_a, in_b, out, syn_a, syn_b, mon)
    net.run(sim_ms * b2.ms)

    t_ms = np.asarray(mon.t / b2.ms)
    mask = t_ms > 100.0
    mean_v_mV = np.mean(np.asarray(mon.v / b2.mV)[:, mask], axis=1)

    # Two convergent inputs, total gain doubled on baseline and signal.
    row_sum = W.sum(axis=1)
    scale = W_UNIT_MV * TAU_MS * 1e-3
    # v_i = (2*row_sum*BASELINE + GAIN*W@(a+b)) * scale
    Wab_est = (mean_v_mV / scale - 2 * row_sum * BASELINE_HZ) / GAIN_HZ

    y_ref = W @ (a + b)
    return Wab_est, y_ref


# -------------------------------------------------------------
# 2. neural_bind_flywire
# -------------------------------------------------------------

def neural_bind_flywire(a: np.ndarray, role: np.ndarray, *, seed: int = 0,
                        sim_ms: float = SIM_MS) -> tuple[np.ndarray, np.ndarray]:
    """
    Sign-flip bind, implemented by routing a_i through an ALPN whose
    native NT type determines the sign of its downstream effect.

    The 685 ALPNs split into 474 ACh (excitatory) and 211 GABA/GLUT
    (inhibitory) cells. That split is substrate-native — we do not set
    it. We just USE it: if role_i >= 0 we route a_i through an ACh
    ALPN; if role_i < 0 we route a_i through a GABA/GLUT ALPN. The
    sign of the downstream effect on KC voltage is then substrate-
    carried by the real neurotransmitter of the chosen cell.

    To keep the dimensionality tractable and the mapping deterministic,
    we work in the reduced dim = min(n_ach, n_inh) = 211. Each of the
    211 dimensions is assigned to one ACh ALPN (for the +role branch)
    and one GABA/GLUT ALPN (for the -role branch). At runtime, for each
    dimension i:
      - set the ACh ALPN's rate to _rate_of(a_i) if role_i >= 0 else BASELINE
      - set the inh ALPN's rate to _rate_of(a_i) if role_i <  0 else BASELINE
    Downstream target: Kenyon cells. Reference = (W_ach_slice + W_inh_slice)
    where each slice's sign is the true NT sign of those cells.

    Returns (y_sim, y_ref, y_reference_semantic):
      y_sim:                Brian2 simulated readout at KC layer
      y_ref:                W @ x  where x is the rate-structured ALPN input
      y_reference_semantic: the VSA semantic reference = a * sign(role),
                            projected through the same KC weights.
                            I.e. what the circuit SHOULD compute if the
                            bind is to be usable as a VSA bind.
    """
    S = get_substrate()
    n_pn = len(S.alpn)
    ach_ids = np.where(S.alpn_nt_sign > 0)[0]
    inh_ids = np.where(S.alpn_nt_sign < 0)[0]
    k = min(len(ach_ids), len(inh_ids))
    # Use deterministic ordering (first k) so the substrate selection is reproducible.
    ach_ids = ach_ids[:k]
    inh_ids = inh_ids[:k]

    assert a.shape == (k,), f"a must have shape ({k},), got {a.shape}"
    assert role.shape == (k,), f"role must have shape ({k},), got {role.shape}"

    # Build the ALPN-layer rate vector (length n_pn).
    # ACh channel carries a where role>=0, baseline (i.e. value=0) elsewhere.
    # Inh channel carries a where role<0, baseline elsewhere.
    v_alpn = np.zeros(n_pn)  # value = 0 => rate = BASELINE_HZ
    pos_mask = role >= 0
    neg_mask = ~pos_mask
    v_alpn[ach_ids[pos_mask]] = a[pos_mask]
    v_alpn[inh_ids[neg_mask]] = a[neg_mask]

    # Run v_alpn through the real ALPN->KC signed weight matrix.
    W = S.W_alpn_to_kc  # (|KC|, |ALPN|)
    y_sim = _run_signed_linear_map(W, v_alpn, seed=seed, sim_ms=sim_ms)
    y_ref = W @ v_alpn

    # Semantic reference: if the circuit behaved as a pure sign-flip
    # bind *at the KC projection*, y would equal W @ x_target where
    # x_target = (a * sign(role)) placed into the ACh channel on
    # positive dims and (-a * ... ) ... -- but because the sign flip is
    # carried by the ALPN NT, the semantic target at KC is:
    #   for each i:  contribution to KCs via ach_ids[i] if pos, else via inh_ids[i]
    #   with value a[i]; the NT sign then multiplies through W.
    # Which is exactly what v_alpn encodes. So y_ref == semantic target
    # already — the reference computation IS the circuit semantics,
    # because the NT sign is part of the weight matrix.
    # To compare against the pure VSA a*sign(role), we project that
    # target through an "idealized" version: use only the ACh ALPNs
    # but with role signs applied externally. This tells us how close
    # the connectome route is to a clean host-computed sign flip.
    v_ideal = np.zeros(n_pn)
    v_ideal[ach_ids] = a * np.sign(np.where(role == 0, 1, role))
    y_ideal = (S.W_alpn_to_kc[:, ach_ids]) @ (a * np.sign(np.where(role == 0, 1, role)))

    return y_sim, y_ref, y_ideal


# -------------------------------------------------------------
# 3. neural_rotate_flywire  (actually: characterize the real linear map)
# -------------------------------------------------------------

def neural_rotate_flywire(v: np.ndarray, *, seed: int = 0,
                          sim_ms: float = SIM_MS) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Apply the REAL ALPN->LHLN signed weight matrix to an ALPN-shaped
    vector v as a spiking linear map. Characterize the transformation
    the wiring actually provides.

    Per CLAUDE.md "NO MATH SHORTCUTS": this is NOT a Givens rotation.
    We do not pretend it is. The real projection ALPN(685) -> LHLN(517)
    is rectangular, rank-deficient, and non-orthogonal. We report:
      - cos(y_sim, W@v): how well the spiking run approximates W@v
      - ||W W^T - diag|| / ||W W^T||: how far from orthogonal the map is
      - condition number, effective rank, top singular values
      - "rotation angle" only in the sense of angle(v_lifted, W@v)
        between a v lifted into output space and its image — but this
        is a poor proxy and we say so.

    The user-stated constraint is that R is fixed by anatomy. This
    function measures what R the anatomy actually gives us. The honest
    answer, from the spectrum below, is that ALPN->LHLN is a heavily
    compressive projection, not a rotation.
    """
    S = get_substrate()
    W = S.W_alpn_to_lhln  # (517, 685)
    assert v.shape == (W.shape[1],)

    y_sim = _run_signed_linear_map(W, v, seed=seed, sim_ms=sim_ms)
    y_ref = W @ v

    # Characterize W geometrically (cached computation — cheap).
    U, sv, Vt = np.linalg.svd(W, full_matrices=False)
    eff_rank = int(np.sum(sv > 1e-3 * sv[0]))
    # Orthogonality check: a true rotation satisfies W^T W = I (or a
    # scaled identity). We measure how close W is to orthonormal.
    col_norms = np.linalg.norm(W, axis=0)
    # Normalize columns, then measure off-diag of W_n^T W_n.
    W_n = W / (col_norms + 1e-12)
    G = W_n.T @ W_n  # (d_in, d_in); should be I if orthonormal columns
    off = G - np.diag(np.diag(G))
    off_rms = float(np.sqrt(np.mean(off**2)))

    # Shape: W is 517x685, so rows > rank bound. Check if W has
    # orthonormal rows (semi-orthogonal):
    row_norms = np.linalg.norm(W, axis=1)
    W_rn = W / (row_norms[:, None] + 1e-12)
    Gr = W_rn @ W_rn.T
    offr = Gr - np.diag(np.diag(Gr))
    off_rms_rows = float(np.sqrt(np.mean(offr**2)))

    info = {
        'shape': W.shape,
        'top_5_singular_values': sv[:5].tolist(),
        'smallest_singular_value': float(sv[-1]),
        'condition_number': float(sv[0] / max(sv[-1], 1e-30)),
        'effective_rank': eff_rank,
        'frobenius_norm': float(np.linalg.norm(W)),
        'is_square': bool(W.shape[0] == W.shape[1]),
        'columns_orthonormal_rms_offdiag': off_rms,   # 0 if yes
        'rows_orthonormal_rms_offdiag': off_rms_rows, # 0 if yes
        'is_rotation': False,   # Concretely: no. Rectangular + non-orthogonal.
    }
    return y_sim, y_ref, info


# -------------------------------------------------------------
# Self-test
# -------------------------------------------------------------

def _cos(x, y):
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx < 1e-12 or ny < 1e-12:
        return 0.0
    return float(np.dot(x, y) / (nx * ny))


def _sign_match(x, y):
    return float((np.sign(x) == np.sign(y)).mean())


def main():
    print("="*70)
    print("FlyWire-backed VSA operations — self-test")
    print("="*70)
    print()
    print("Loading FlyWire substrate...")
    S = get_substrate(verbose=True)
    n_ach = int((S.alpn_nt_sign > 0).sum())
    n_inh = int((S.alpn_nt_sign < 0).sum())
    print(f"  ALPN: {len(S.alpn)}   (ACh: {n_ach}, GABA/GLUT: {n_inh})")
    print(f"  LHLN: {len(S.lhln)}")
    print(f"  KC:   {len(S.kc)}")
    print(f"  W_ALPN->LHLN: shape {S.W_alpn_to_lhln.shape}, "
          f"nnz={np.count_nonzero(S.W_alpn_to_lhln)}")
    print(f"  W_ALPN->KC:   shape {S.W_alpn_to_kc.shape}, "
          f"nnz={np.count_nonzero(S.W_alpn_to_kc)}")
    print()

    rng = np.random.RandomState(0)

    # --- bundle ---
    print("-"*70)
    print("[1/3] neural_bundle_flywire")
    print("-"*70)
    a = rng.uniform(-1, 1, size=len(S.alpn))
    b = rng.uniform(-1, 1, size=len(S.alpn))
    y_sim, y_ref = neural_bundle_flywire(a, b, seed=0, sim_ms=600.0)
    # Compare the Brian2 run to exact W@(a+b). This tests whether the
    # real ALPN->LHLN wiring, driven as a convergent circuit, faithfully
    # performs linear superposition at the membrane.
    cos_bundle = _cos(y_sim, y_ref)
    sign_bundle = _sign_match(y_sim, y_ref)
    # Also compare y_ref itself to W@a + W@b (should be identical; sanity).
    identity_check = _cos(y_ref, (S.W_alpn_to_lhln @ a) + (S.W_alpn_to_lhln @ b))
    print(f"  y_sim vs W@(a+b):          cos={cos_bundle:.4f}  sign_match={sign_bundle:.3f}")
    print(f"  linearity sanity (==1.00): cos={identity_check:.4f}")
    print(f"  ||y_sim||={np.linalg.norm(y_sim):.2f}  ||y_ref||={np.linalg.norm(y_ref):.2f}")
    ok_bundle = cos_bundle > 0.90
    print(f"  -> bundle: {'PASS' if ok_bundle else 'NEEDS-REVIEW'} (threshold cos>0.90)")
    print()

    # --- bind ---
    print("-"*70)
    print("[2/3] neural_bind_flywire")
    print("-"*70)
    k = min(n_ach, n_inh)
    a_small = rng.uniform(-1, 1, size=k)
    role = rng.choice([-1.0, +1.0], size=k)
    # KCs are very sparsely innervated (median ~5 ALPN synapses per KC)
    # so Poisson variance per-output is high and we need a longer
    # averaging window to measure the underlying W@v. This is a
    # measurement-SNR question, NOT a weight-tuning shortcut: at sim=600
    # we observe cos~0.75 (variance-dominated); at sim=2000 we observe
    # cos~0.93 (signal-dominated). A deployment on fewer, larger-count
    # synapses (like LHLN) converges faster.
    y_sim, y_ref, y_ideal = neural_bind_flywire(a_small, role, seed=0, sim_ms=2000.0)
    # y_ref is what the SUBSTRATE computes (ALPN with mixed NT split).
    # y_ideal is what a host-computed a*sign(role) would produce if
    # routed through ACh-only ALPNs. Compare circuit to both.
    cos_to_substrate = _cos(y_sim, y_ref)
    sign_to_substrate = _sign_match(y_sim, y_ref)
    cos_to_ideal = _cos(y_ref, y_ideal)
    print(f"  y_sim vs y_substrate_ref:  cos={cos_to_substrate:.4f}  "
          f"sign_match={sign_to_substrate:.3f}")
    print(f"     (circuit approximates what the real wiring computes)")
    print(f"  y_substrate vs y_ideal_SF: cos={cos_to_ideal:.4f}")
    print(f"     (how close real NT-split path is to a host sign-flip bind)")
    print(f"     values < 1 mean substrate bind DIFFERS from VSA sign-flip.")
    ok_bind_spike = cos_to_substrate > 0.90
    print(f"  -> bind spiking-fidelity: {'PASS' if ok_bind_spike else 'NEEDS-REVIEW'} "
          f"(threshold cos>0.90)")
    print()

    # --- rotate ---
    print("-"*70)
    print("[3/3] neural_rotate_flywire  — characterize the real projection")
    print("-"*70)
    v = rng.uniform(-1, 1, size=len(S.alpn))
    y_sim, y_ref, info = neural_rotate_flywire(v, seed=0, sim_ms=600.0)
    cos_rot = _cos(y_sim, y_ref)
    sign_rot = _sign_match(y_sim, y_ref)
    print(f"  y_sim vs W@v:              cos={cos_rot:.4f}  sign_match={sign_rot:.3f}")
    print(f"  W shape:                   {info['shape']}")
    print(f"  is_square:                 {info['is_square']}")
    print(f"  effective_rank:            {info['effective_rank']}  "
          f"(of max {min(info['shape'])})")
    print(f"  top 5 singular values:     "
          f"{[f'{s:.1f}' for s in info['top_5_singular_values']]}")
    print(f"  condition number:          {info['condition_number']:.2e}")
    print(f"  column-orthonormality RMS: {info['columns_orthonormal_rms_offdiag']:.4f} "
          f"(0 = orthonormal)")
    print(f"  row-orthonormality RMS:    {info['rows_orthonormal_rms_offdiag']:.4f}")
    print()
    print("  HONEST FINDING: ALPN->LHLN is NOT a rotation.")
    print("  It is a rectangular (685 -> 517) rank-deficient projection")
    print("  with strongly non-orthogonal columns. It implements a")
    print("  compressive linear map, which is what the olfactory system")
    print("  physically does (high-dimensional odor codes -> lower-dim")
    print("  LH representations). The user's constraint that 'R is fixed")
    print("  by anatomy' is satisfied; what the anatomy gives is NOT a")
    print("  norm-preserving rotation.")
    ok_rot_spike = cos_rot > 0.90
    print(f"  -> rotate spiking-fidelity: "
          f"{'PASS' if ok_rot_spike else 'NEEDS-REVIEW'} (threshold cos>0.90)")
    print()

    print("="*70)
    print("Summary")
    print("="*70)
    print(f"  bundle (W@(a+b)):    cos={cos_bundle:.3f}")
    print(f"  bind (substrate):    cos={cos_to_substrate:.3f}")
    print(f"  bind (vs VSA ideal): cos={cos_to_ideal:.3f}  "
          f"<- tells you whether the real NT-split circuit")
    print(f"                                        is usable as a VSA bind")
    print(f"  rotate (W@v):        cos={cos_rot:.3f}")
    print(f"  rotate is_rotation:  False (rectangular, non-orthogonal)")


if __name__ == '__main__':
    main()
