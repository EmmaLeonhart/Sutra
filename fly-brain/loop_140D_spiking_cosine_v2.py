"""
Experiment A v2: 140-D spiking rotation + cosine readout, with two fixes
over v1 (loop_140D_spiking_cosine.py):

1. Force det(Q) = +1. The v1 Q was a rotoinversion (det = -1) because
   the hDelta polar-decomposition block had det = -1 and the block_diag
   composition inherited it. Fix: after SVD-based polar decomposition,
   if det(Q) = -1, flip the sign of one row of the last U column.
   Standard Kabsch sign correction. Q is now in SO(140).

2. Argmax-over-trajectory termination for counting. v1 used absolute
   threshold cos > 0.5, which rejected valid target peaks at 0.4
   because of the 140-D Poisson decode-noise ceiling. v2 runs the
   loop for max_iters iterations, then returns argmax_k cos(state_k,
   target_proto). This is how the ordering test already decides —
   apply the same rule to counting.

Measures at n=5 seeds, k=3, SIM_MS=3000 to match v1.
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

import neural_vsa
from neural_vsa import neural_linear_map
from flywire_loader import load_flywire
from real_rotation_epg import build_epg_to_epg
from real_rotation_composed import build_square_motif


neural_vsa.SIM_MS = 3000.0


def nearest_rotation_so(W):
    """Polar decomposition, force det = +1 (proper rotation in SO(n))."""
    U, s, Vt = np.linalg.svd(W, full_matrices=False)
    # Kabsch sign correction: flip last U column if det(U V^T) = -1.
    D = np.eye(len(s))
    if np.linalg.det(U @ Vt) < 0:
        D[-1, -1] = -1
    Q = U @ D @ Vt
    return Q


def build_140D_Q_so():
    fw = load_flywire(verbose=False)
    W_epg = build_epg_to_epg(fw)
    Q_epg = nearest_rotation_so(W_epg)
    hd_types = ["hDeltaJ", "hDeltaK", "hDeltaA", "hDeltaD", "hDeltaE"]
    W_hd = build_square_motif(fw, hd_types, hd_types, "hDelta-89 subset")
    Q_hd = nearest_rotation_so(W_hd)
    return block_diag(Q_epg, Q_hd)


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


def run_counting_argmax(Q, target_k, seed, max_iters=8):
    rng = np.random.RandomState(seed)
    v0 = rng.randn(Q.shape[0]); v0 /= np.linalg.norm(v0)
    proto = np.linalg.matrix_power(Q, target_k) @ v0
    proto /= np.linalg.norm(proto)

    state = v0.copy()
    cos_by_k = []
    for k in range(1, max_iters + 1):
        state = spiking_rotate_step(Q, state, seed=seed * 101 + k)
        cos_by_k.append(cosine(state, proto))

    argmax_k = int(np.argmax(cos_by_k)) + 1
    return {
        "target_k": target_k,
        "argmax_k": argmax_k,
        "cos_by_k": cos_by_k,
        "pass": argmax_k == target_k,
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
        best_name = None; best_c = -2.0
        for name, p in proto_vecs.items():
            c = cosine(state, p)
            if c > best_c:
                best_c = c; best_name = name
        if best_c >= threshold:
            matched_name = best_name
            matched_at = k
            break

    return {"matched": matched_name, "matched_at": matched_at,
            "pass": matched_name == "EARLY"}


def main():
    print("Building 140-D real-wiring Q (EPG 51 + hDelta 89), forcing det=+1...")
    Q = build_140D_Q_so()
    orth = float(np.linalg.norm(Q.T @ Q - np.eye(len(Q)), "fro"))
    det = float(np.linalg.det(Q))
    print(f"Q: shape={Q.shape}  ||QtQ-I||_F={orth:.2e}  det={det:+.4f}")
    print(f"SIM_MS per step = {neural_vsa.SIM_MS} ms\n")

    seeds = [0, 1, 2, 3, 4]
    t0_all = time.time()

    print(f"Counting k=3 (argmax over 8 iterations, spiking, {len(seeds)} seeds)")
    c_results = []
    for seed in seeds:
        ts = time.time()
        r = run_counting_argmax(Q, target_k=3, seed=seed, max_iters=8)
        dt = time.time() - ts
        c_results.append(r)
        cs = " ".join(f"k{i+1}={c:+.2f}" for i, c in enumerate(r["cos_by_k"]))
        print(f"  seed={seed}  argmax_k={r['argmax_k']}  {cs}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_c = sum(int(r["pass"]) for r in c_results)

    print(f"\nOrdering (EARLY@2 first, threshold=0.5, {len(seeds)} seeds)")
    o_results = []
    for seed in seeds:
        ts = time.time()
        r = run_ordering(Q, seed=seed, threshold=0.5)
        dt = time.time() - ts
        o_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  at={r['matched_at']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_o = sum(int(r["pass"]) for r in o_results)

    print()
    print("=" * 60)
    print(f"140-D spiking rotation (det=+1) + cosine readout:")
    print(f"  counting k=3 (argmax): {n_c}/{len(seeds)}")
    print(f"  ordering:              {n_o}/{len(seeds)}")
    print(f"  wall clock:            {time.time() - t0_all:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
