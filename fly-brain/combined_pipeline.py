"""
Combined pipeline: spiking rotation at 140-D + KC-Jaccard readout, end-to-end.

STATUS.md queue item #3. Closes the numpy-in-runtime caveat that currently
attaches to the paper's headline result.

Two pieces that already exist in the repo, now wired together at one
dimension:

- Spiking rotation via neural_linear_map (neural_vsa.py). Q enters as
  Brian2 synapse weights, the next state is read from membrane voltage.
  Rotation is on neurons — no numpy matmul on the state vector at
  runtime. Demonstrated separately at 51-D EPG and 713-D composed.

- KC-Jaccard readout via FlyBrainVSA with use_hemibrain=True. State goes
  through PN->KC on the real hemibrain wiring, APL sparsifies to ~5%,
  the resulting binary KC pattern is Jaccard-compared to a compiled
  prototype pattern. Readout is substrate-native. Demonstrated
  separately at 140-D with numpy rotation (5/5 counting, 30/30 k-sweep).

Here both run at the same 140-D composed Q (EPG 51 + hDelta subset 89,
matching the hemibrain PN count). The iteration loop applies Q through
neural_linear_map, then pushes the result through the MB bridge, checks
Jaccard against the compiled prototype, terminates on match.

Numpy is used only for:
  - compilation: building Q via polar decomposition of FlyWire weights,
    drawing the initial random state, computing the numerical prototype
    Q^target_k @ v0 that the substrate should converge TO (this
    prototype is then itself compiled to a KC pattern by running it
    through the substrate once)
  - monitoring: the Jaccard overlap computation on the two KC binary
    patterns is reported as a scalar; this is a report of what the
    substrate did, not a substitute for it

Expected effect: the 3/5 ceiling on real_rotation_epg_loop_spiking is
a cosine-readout artifact — direct cosine on decoded Brian2 voltage is
noisy. KC-Jaccard is a categorical match/no-match on a sparse binary
pattern and should tolerate the decode noise. If that story is right,
this pipeline passes at n>=5.
"""

from __future__ import annotations

import sys
import time

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

import neural_vsa
from neural_vsa import neural_linear_map
from real_rotation_140D_jaccard import build_140D_Q
from vsa_operations import FlyBrainVSA


# Longer Brian2 window per rotation step reduces Poisson variance that
# would otherwise accumulate on the magnitude across iterations. The
# 51-D spiking loop uses 3000 ms for the same reason.
neural_vsa.SIM_MS = 3000.0


def spiking_rotate_step(Q: np.ndarray, state: np.ndarray, seed: int) -> np.ndarray:
    """One rotation step on the substrate: state <- Q . state via Brian2.

    neural_linear_map encodes state as Poisson rates driving a 140-neuron
    LIF population whose input synapses are weighted by Q (positive
    excitatory, negative inhibitory). The next state is decoded from
    the mean membrane voltage over the post-transient window.
    """
    new_state = neural_linear_map(Q, state, seed=seed)
    n = np.linalg.norm(new_state)
    if n < 1e-9:
        return new_state
    # Renormalize between iterations. Q is orthogonal so the true next
    # state has the same norm as the previous one; drift away from that
    # is Poisson-decode noise that otherwise compounds.
    return new_state / n


def run_counting(Q: np.ndarray, target_k: int, seed: int,
                 max_iters: int = 8, threshold: float = 0.5,
                 snap_duration_ms: int = 200) -> dict:
    """Counting test: does the loop terminate exactly at iteration target_k?

    The prototype is built numerically (compile-time: the substrate is
    being told 'this is the vector you should converge to') and then
    itself run through the substrate once to get its KC pattern. After
    that, all iteration and matching happens on neurons.
    """
    rng = np.random.RandomState(seed)
    vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=snap_duration_ms)
    assert vsa.dim == Q.shape[0], \
        f"hemibrain PN count ({vsa.dim}) != Q dim ({Q.shape[0]})"

    v0 = rng.randn(vsa.dim)
    v0 /= np.linalg.norm(v0)

    # Numerical prototype used to compile the KC target pattern.
    proto_vec = np.linalg.matrix_power(Q, target_k) @ v0
    compiled = vsa.compile_prototypes({"TARGET": proto_vec}, frame_seed=seed)
    proto_pat = compiled["TARGET"]

    state = v0.copy()
    jac_by_k = []
    matched_at = None
    for k in range(1, max_iters + 1):
        # 1. Spiking rotation: state <- Q . state on neurons
        state = spiking_rotate_step(Q, state, seed=seed * 101 + k)

        # 2. Spiking readout: push state through PN->KC on the hemibrain
        bridge = vsa._make_bridge(fixed_seed=seed)
        kc = bridge.snap_to_kc_pattern(state, vsa.snap_duration_ms)

        # 3. Jaccard overlap against the compiled prototype pattern
        inter = float(np.sum(kc * proto_pat))
        union = float(np.sum(np.clip(kc + proto_pat, 0, 1)))
        jac = inter / max(union, 1.0)
        jac_by_k.append(jac)

        if jac >= threshold and matched_at is None:
            matched_at = k
            break

    return {
        "target_k": target_k,
        "matched_at": matched_at,
        "jac_by_k": jac_by_k,
        "pass": matched_at == target_k,
    }


def run_ordering(Q: np.ndarray, seed: int,
                 max_iters: int = 15, threshold: float = 0.5,
                 snap_duration_ms: int = 200) -> dict:
    """Ordering test: EARLY (k=2) must match before MIDDLE (k=5) or LATE (k=8)."""
    rng = np.random.RandomState(seed + 13)
    vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=snap_duration_ms)

    v0 = rng.randn(vsa.dim)
    v0 /= np.linalg.norm(v0)

    proto_vecs = {
        "EARLY":  np.linalg.matrix_power(Q, 2) @ v0,
        "MIDDLE": np.linalg.matrix_power(Q, 5) @ v0,
        "LATE":   np.linalg.matrix_power(Q, 8) @ v0,
    }
    compiled = vsa.compile_prototypes(proto_vecs, frame_seed=seed)

    state = v0.copy()
    matched_name = None
    matched_at = None
    for k in range(1, max_iters + 1):
        state = spiking_rotate_step(Q, state, seed=seed * 101 + k)
        bridge = vsa._make_bridge(fixed_seed=seed)
        kc = bridge.snap_to_kc_pattern(state, vsa.snap_duration_ms)

        best_name = None
        best_jac = -1.0
        for name, pat in compiled.items():
            inter = float(np.sum(kc * pat))
            union = float(np.sum(np.clip(kc + pat, 0, 1)))
            jac = inter / max(union, 1.0)
            if jac > best_jac:
                best_jac = jac
                best_name = name
        if best_jac >= threshold:
            matched_name = best_name
            matched_at = k
            break

    return {
        "matched": matched_name,
        "matched_at": matched_at,
        "pass": matched_name == "EARLY",
    }


def main():
    print("Building 140-D real-wiring Q (EPG 51 + hDelta subset 89)...")
    Q = build_140D_Q()
    orth = float(np.linalg.norm(Q.T @ Q - np.eye(len(Q)), "fro"))
    det = float(np.linalg.det(Q))
    print(f"Composed 140-D Q: shape={Q.shape}  ||QtQ-I||_F={orth:.2e}  det={det:+.4f}")
    print(f"Brian2 SIM_MS per rotation step = {neural_vsa.SIM_MS} ms\n")

    seeds = [0, 1, 2, 3, 4]
    threshold = 0.5
    snap_duration_ms = 200

    t0_all = time.time()

    print(f"Counting k=3 on the substrate ({len(seeds)} seeds)")
    print(f"  rotation = neural_linear_map(Q, state)  [Brian2 LIF]")
    print(f"  readout  = MB Jaccard on real hemibrain [Brian2 LIF]")
    c_results = []
    for seed in seeds:
        ts = time.time()
        r = run_counting(Q, target_k=3, seed=seed, threshold=threshold,
                         snap_duration_ms=snap_duration_ms)
        dt = time.time() - ts
        c_results.append(r)
        jac_str = " ".join(f"k{i+1}={j:.2f}" for i, j in enumerate(r["jac_by_k"]))
        print(f"  seed={seed}  matched_at={r['matched_at']}  {jac_str}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_c = sum(int(r["pass"]) for r in c_results)

    print(f"\nOrdering (EARLY@2 first, {len(seeds)} seeds)")
    o_results = []
    for seed in seeds:
        ts = time.time()
        r = run_ordering(Q, seed=seed, threshold=threshold,
                         snap_duration_ms=snap_duration_ms)
        dt = time.time() - ts
        o_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  matched_at={r['matched_at']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_o = sum(int(r["pass"]) for r in o_results)

    print()
    print("=" * 60)
    print(f"Combined pipeline (spiking rotation + KC-Jaccard, 140-D):")
    print(f"  counting k=3: {n_c}/{len(seeds)}")
    print(f"  ordering:     {n_o}/{len(seeds)}")
    print(f"  wall clock:   {time.time() - t0_all:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
