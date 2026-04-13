"""
140-D real-wiring Q + real hemibrain MB readout (queue item 2).

Closes the caveat from `planning/findings/2026-04-13-jaccard-on-KC-
5-of-5.md`: the prior Jaccard runs used `use_hemibrain=False`
(random PN->KC at matched dim) because hemibrain's PN count is 140
and embedding a 51-D `Q` as `block_diag(Q, I_{89})` failed trivially.

Fix: build a 140-D real-wiring `Q` that tiles to exactly hemibrain's
PN count. EPG contributes 51 dims; an 89-D hDelta subset (types J,
K, A, D, E = 30+31+12+8+8 = 89 neurons) contributes the other 89.
Both blocks come from real FlyWire v783 wiring via polar decomposition.

Then run the loop with `use_hemibrain=True`: rotation is real FlyWire
(EPG + hDelta), readout is real hemibrain PN->KC (1882 KCs, APL
sparsification). End-to-end real wiring on both sides.

Note on biological interpretation: the 140 dimensions of the state
vector are labeled by the composition (51 EPG + 89 hDelta), not by
hemibrain's actual olfactory PN identities. The hemibrain PN->KC
matrix is used as a real sparse expander projection at the matching
dimension, not as a biologically-coherent PN->KC mapping. The point
is: it is a real connectome-derived projection, not a synthetic random
one, and the MB's anti-correlation / sparse-categorical properties
come from real wiring.
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
from scipy.linalg import block_diag

from flywire_loader import load_flywire
from real_rotation_epg import build_epg_to_epg, nearest_rotation
from real_rotation_composed import build_square_motif
from vsa_operations import FlyBrainVSA


def build_140D_Q():
    fw = load_flywire(verbose=False)

    W_epg = build_epg_to_epg(fw)
    Q_epg, _ = nearest_rotation(W_epg)
    print(f"  EPG: shape={Q_epg.shape}, "
          f"||QtQ-I||_F={np.linalg.norm(Q_epg.T@Q_epg-np.eye(len(Q_epg)), 'fro'):.2e}")

    hd_types = ["hDeltaJ", "hDeltaK", "hDeltaA", "hDeltaD", "hDeltaE"]
    W_hd = build_square_motif(fw, hd_types, hd_types, "hDelta-89 subset")
    Q_hd, _ = nearest_rotation(W_hd)
    print(f"  hDelta subset: shape={Q_hd.shape}, "
          f"||QtQ-I||_F={np.linalg.norm(Q_hd.T@Q_hd-np.eye(len(Q_hd)), 'fro'):.2e}")

    Q = block_diag(Q_epg, Q_hd)
    return Q


def run_counting(vsa, Q, target_k, seed, max_iters=8, threshold=0.5):
    rng = np.random.RandomState(seed)
    start = rng.randn(vsa.dim); start /= np.linalg.norm(start)
    proto = np.linalg.matrix_power(Q, target_k) @ start
    compiled = vsa.compile_prototypes({"TARGET": proto}, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=Q, compiled_prototypes=compiled,
        target_name="TARGET", threshold=threshold, max_iters=max_iters,
        frame_seed=seed,
    )
    return {"matched": matched, "n_iters": n_iters,
            "pass": matched == "TARGET" and n_iters == target_k}


def run_ordering(vsa, Q, seed, max_iters=15, threshold=0.5):
    rng = np.random.RandomState(seed + 13)
    start = rng.randn(vsa.dim); start /= np.linalg.norm(start)
    protos = {
        "EARLY":  np.linalg.matrix_power(Q, 2) @ start,
        "MIDDLE": np.linalg.matrix_power(Q, 5) @ start,
        "LATE":   np.linalg.matrix_power(Q, 8) @ start,
    }
    compiled = vsa.compile_prototypes(protos, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=Q, compiled_prototypes=compiled,
        target_name=None, threshold=threshold, max_iters=max_iters,
        frame_seed=seed,
    )
    return {"matched": matched, "n_iters": n_iters, "pass": matched == "EARLY"}


def main():
    print("Building 140-D real-wiring Q (EPG 51 + hDelta subset 89)...")
    Q = build_140D_Q()
    print(f"Composed 140-D Q: shape={Q.shape}, "
          f"||QtQ-I||_F={np.linalg.norm(Q.T@Q-np.eye(len(Q)),'fro'):.2e}, "
          f"det={np.linalg.det(Q):+.4f}\n")

    seeds = [0, 1, 2, 3, 4]
    threshold = 0.5

    # Verify hemibrain PN count matches our Q
    vsa_probe = FlyBrainVSA(seed=0, use_hemibrain=True, snap_duration_ms=200)
    if vsa_probe.dim != Q.shape[0]:
        print(f"!! hemibrain PN count ({vsa_probe.dim}) != Q dim ({Q.shape[0]}); aborting")
        sys.exit(1)
    print(f"  hemibrain PN dim matches Q dim: {vsa_probe.dim}\n")

    # Gap probe
    print(f"Jaccard gap probe (seed=0, target k=3, real hemibrain MB):")
    rng = np.random.RandomState(0)
    start = rng.randn(vsa_probe.dim); start /= np.linalg.norm(start)
    proto = np.linalg.matrix_power(Q, 3) @ start
    compiled = vsa_probe.compile_prototypes({"TARGET": proto}, frame_seed=0)
    proto_pat = compiled["TARGET"]
    for k in range(1, 7):
        st = np.linalg.matrix_power(Q, k) @ start
        bridge = vsa_probe._make_bridge(fixed_seed=0)
        kc = bridge.snap_to_kc_pattern(st, vsa_probe.snap_duration_ms)
        inter = float(np.sum(kc * proto_pat))
        union = float(np.sum(np.clip(kc + proto_pat, 0, 1)))
        jac = inter / max(union, 1.0)
        print(f"  k={k}  jaccard={jac:.3f}")
    print()

    t0 = time.time()

    print(f"Counting k=3 (real hemibrain MB, {len(seeds)} seeds)")
    c_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=200)
        ts = time.time()
        r = run_counting(vsa, Q, target_k=3, seed=seed, threshold=threshold)
        dt = time.time() - ts
        c_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_c = sum(int(r["pass"]) for r in c_results)

    print(f"\nOrdering (EARLY@2 first, real hemibrain MB, {len(seeds)} seeds)")
    o_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=200)
        ts = time.time()
        r = run_ordering(vsa, Q, seed=seed, threshold=threshold)
        dt = time.time() - ts
        o_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_o = sum(int(r["pass"]) for r in o_results)

    print()
    print("=" * 60)
    print(f"140-D real-wiring Q + real hemibrain MB Jaccard readout:")
    print(f"  counting k=3: {n_c}/{len(seeds)}")
    print(f"  ordering:     {n_o}/{len(seeds)}")
    print(f"  wall clock:   {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
