"""
Jaccard-on-KC readout on 713-D composed real-wiring Q.

Direct test of the dimension-independence claim in
`planning/sutra-spec/23-loop-readout-theory.md`: KC-Jaccard has a
bimodal distribution whose gap (chance ~s/2 vs match ~1) does not
depend on the PN dimension, because APL sparsification normalizes the
active-KC count regardless of D. Cosine SNR scales ~1/sqrt(D) and the
cosine spiking test at D=713 collapsed to peak cos ~0.1 (3/5 seeds).
If the theory is right, Jaccard should hit 5/5 at D=713 just as it
did at D=51.

Substrate: `FlyBrainVSA(dim=713, use_hemibrain=False)`. Random PN->KC
at matched dim (same synthetic-MB caveat as the 51-D Jaccard test —
hemibrain is 140 PN so cannot host a 713-D state without the block-
diag-identity-padding problem, which is queue item 2).
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
from real_rotation_epg import nearest_rotation
from real_rotation_composed import build_square_motif
from vsa_operations import FlyBrainVSA


def build_composed_Q():
    fw = load_flywire(verbose=False)
    motifs = [
        ("CX EPG->EPG",       ["EPG", "EPGt"], ["EPG", "EPGt"]),
        ("LH LH->LH",         [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                   "PV5a1", "PV5b1", "PV5b2",
                                                   "PV5b3", "PV5c1"]],
                              [f"LH{t}" for t in ["AV4a4", "AV5a3", "AV6a4",
                                                   "PV5a1", "PV5b1", "PV5b2",
                                                   "PV5b3", "PV5c1"]]),
        ("FB vDelta->vDelta", [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                               ["vDeltaA_a", "vDeltaA_b"],
                              [f"vDelta{c}" for c in "ABCDEFGHIJKLMN"] +
                               ["vDeltaA_a", "vDeltaA_b"]),
        ("FB hDelta->hDelta", [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"],
                              [f"hDelta{c}" for c in "ABCDEFGHIJKLMN"]),
    ]
    Qs = []
    for name, pre, post in motifs:
        W = build_square_motif(fw, pre, post, name)
        if W.size == 0 or np.linalg.norm(W) < 1e-8:
            continue
        Q, _ = nearest_rotation(W)
        Qs.append(Q)
    return block_diag(*Qs)


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
    print("Building composed 713-D Q from 4 FlyWire motifs...")
    Q = build_composed_Q()
    print(f"  shape={Q.shape}  "
          f"||QtQ-I||_F={np.linalg.norm(Q.T@Q - np.eye(len(Q)), 'fro'):.2e}  "
          f"det={np.linalg.det(Q):+.4f}\n")

    seeds = [0, 1, 2, 3, 4]
    threshold = 0.5

    # Gap probe for seed 0, target k=3 — proves the bimodal theory prediction
    print("Jaccard gap probe (seed=0, target k=3, D=713):")
    vsa_probe = FlyBrainVSA(dim=Q.shape[0], n_kc=2000, seed=0,
                             use_hemibrain=False, snap_duration_ms=200)
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

    # Counting k=3
    print(f"Counting k=3 (D=713, threshold={threshold}, {len(seeds)} seeds)")
    c_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(dim=Q.shape[0], n_kc=2000, seed=seed,
                           use_hemibrain=False, snap_duration_ms=200)
        ts = time.time()
        r = run_counting(vsa, Q, target_k=3, seed=seed, threshold=threshold)
        dt = time.time() - ts
        c_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_c = sum(int(r["pass"]) for r in c_results)

    # Ordering
    print(f"\nOrdering (EARLY@2 first, D=713, {len(seeds)} seeds)")
    o_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(dim=Q.shape[0], n_kc=2000, seed=seed,
                           use_hemibrain=False, snap_duration_ms=200)
        ts = time.time()
        r = run_ordering(vsa, Q, seed=seed, threshold=threshold)
        dt = time.time() - ts
        o_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_o = sum(int(r["pass"]) for r in o_results)

    print()
    print("=" * 60)
    print(f"Composed 713-D real-wiring Q + tier-3 Jaccard-on-KC readout:")
    print(f"  counting k=3: {n_c}/{len(seeds)}")
    print(f"  ordering:     {n_o}/{len(seeds)}")
    print(f"  wall clock:   {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
