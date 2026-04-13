"""
Experiment A: 140-D spiking rotation with direct cosine readout.

Question: if we skip the MB's anti-correlator entirely and just compare
the rotated state to the target prototype by cosine on decoded voltage,
does the loop terminate correctly?

Combined pipeline (combined_pipeline.py) was 0/5 because the MB PN->KC
path is a decorrelator by design — small vector-space noise on the
spiking-rotated state maps to a *different* KC mask than the
prototype's, and Jaccard cannot rescue that. This script removes the
MB entirely: rotation runs on spiking neurons (neural_linear_map), the
decoded voltage is compared to a stored prototype voltage by cosine.

51-D and 713-D versions of this configuration existed in the repo
(real_rotation_epg_loop_spiking.py, real_rotation_composed_spiking.py)
and both hit 3/5 seeds at k=3 with cosine. 140-D with cosine is the
combination that has never been measured. This closes that gap.

Numpy usage: Q construction (compile), initial state draw (compile),
prototype computation `Q^k v0` (compile — the substrate is being told
what to converge to), and cosine similarity as a post-run scalar
(monitoring). Rotation itself runs on neurons every iteration.
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


neural_vsa.SIM_MS = 3000.0


def spiking_rotate_step(Q, state, seed):
    new_state = neural_linear_map(Q, state, seed=seed)
    n = np.linalg.norm(new_state)
    if n < 1e-9:
        return new_state
    return new_state / n


def cosine(a, b):
    na = np.linalg.norm(a); nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def run_counting(Q, target_k, seed, max_iters=8, threshold=0.5):
    rng = np.random.RandomState(seed)
    v0 = rng.randn(Q.shape[0]); v0 /= np.linalg.norm(v0)

    # Prototype is compiled numerically once; same role as in the
    # combined pipeline. It is what the substrate is being told to
    # converge to.
    proto = np.linalg.matrix_power(Q, target_k) @ v0
    proto /= np.linalg.norm(proto)

    state = v0.copy()
    cos_by_k = []
    matched_at = None
    for k in range(1, max_iters + 1):
        state = spiking_rotate_step(Q, state, seed=seed * 101 + k)
        c = cosine(state, proto)
        cos_by_k.append(c)
        if c >= threshold and matched_at is None:
            matched_at = k
            break

    return {
        "target_k": target_k,
        "matched_at": matched_at,
        "cos_by_k": cos_by_k,
        "pass": matched_at == target_k,
    }


def run_ordering(Q, seed, max_iters=15, threshold=0.5):
    rng = np.random.RandomState(seed + 13)
    v0 = rng.randn(Q.shape[0]); v0 /= np.linalg.norm(v0)

    proto_vecs = {}
    for name, k in [("EARLY", 2), ("MIDDLE", 5), ("LATE", 8)]:
        p = np.linalg.matrix_power(Q, k) @ v0
        p /= np.linalg.norm(p)
        proto_vecs[name] = p

    state = v0.copy()
    matched_name = None
    matched_at = None
    for k in range(1, max_iters + 1):
        state = spiking_rotate_step(Q, state, seed=seed * 101 + k)
        best_name = None
        best_c = -2.0
        for name, p in proto_vecs.items():
            c = cosine(state, p)
            if c > best_c:
                best_c = c
                best_name = name
        if best_c >= threshold:
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
    print(f"Q: shape={Q.shape}  ||QtQ-I||_F={orth:.2e}  det={det:+.4f}")
    print(f"Brian2 SIM_MS per rotation step = {neural_vsa.SIM_MS} ms\n")

    seeds = [0, 1, 2, 3, 4]
    threshold = 0.5
    t0_all = time.time()

    print(f"Counting k=3 (spiking rotation + cosine readout, {len(seeds)} seeds)")
    c_results = []
    for seed in seeds:
        ts = time.time()
        r = run_counting(Q, target_k=3, seed=seed, threshold=threshold)
        dt = time.time() - ts
        c_results.append(r)
        cs = " ".join(f"k{i+1}={c:+.2f}" for i, c in enumerate(r["cos_by_k"]))
        print(f"  seed={seed}  matched_at={r['matched_at']}  {cs}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_c = sum(int(r["pass"]) for r in c_results)

    print(f"\nOrdering (EARLY@2 first, {len(seeds)} seeds)")
    o_results = []
    for seed in seeds:
        ts = time.time()
        r = run_ordering(Q, seed=seed, threshold=threshold)
        dt = time.time() - ts
        o_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  matched_at={r['matched_at']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_o = sum(int(r["pass"]) for r in o_results)

    print()
    print("=" * 60)
    print(f"140-D spiking rotation + cosine readout:")
    print(f"  counting k=3: {n_c}/{len(seeds)}")
    print(f"  ordering:     {n_o}/{len(seeds)}")
    print(f"  wall clock:   {time.time() - t0_all:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
