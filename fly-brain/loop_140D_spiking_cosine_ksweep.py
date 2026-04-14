"""
Substrate-only k-sweep over k ∈ {1, 2, 3, 5, 8, 12} × 5 seeds.

Same architecture as loop_140D_spiking_cosine_v2.py (substrate-only
140-D spiking rotation + cosine readout, argmax termination), run
across multiple target-k values. Mirrors real_rotation_140D_jaccard_
ksweep.py which did this for the numpy-rotation + MB-Jaccard pipeline
and got 30/30. This tells us whether the v2 substrate-only result
(9/10 at k=3) generalizes past k=3.

Relies on the build_140D_Q_so variant (forces det = +1). Since
nearest_rotation in real_rotation_epg.py now forces det = +1 at
source, the v1 build_140D_Q would now be equivalent — but this
script imports v2's version to keep the bug fix local to the
substrate-only experiment series, pending the paper-harness re-run
deciding whether to adopt the fix globally.
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
from loop_140D_spiking_cosine_v2 import build_140D_Q_so, run_counting_argmax


neural_vsa.SIM_MS = 3000.0


def main():
    print("Building 140-D Q (det = +1)...")
    Q = build_140D_Q_so()
    orth = float(np.linalg.norm(Q.T @ Q - np.eye(len(Q)), "fro"))
    det = float(np.linalg.det(Q))
    print(f"Q: shape={Q.shape}  ||QtQ-I||_F={orth:.2e}  det={det:+.4f}")
    print(f"SIM_MS per step = {neural_vsa.SIM_MS} ms\n")

    ks = [1, 2, 3, 5, 8, 12]
    seeds = [0, 1, 2, 3, 4]
    max_iters = 15

    t0 = time.time()
    table = {}
    for k in ks:
        row = []
        for seed in seeds:
            ts = time.time()
            r = run_counting_argmax(Q, target_k=k, seed=seed,
                                    max_iters=max_iters)
            dt = time.time() - ts
            row.append(r)
            tag = "PASS" if r["pass"] else "FAIL"
            print(f"  k={k:2d} seed={seed}  argmax_k={r['argmax_k']}  "
                  f"{tag}  [{dt:.0f}s]")
        n_pass = sum(int(r["pass"]) for r in row)
        table[k] = (n_pass, row)
        print(f"  k={k:2d} SUMMARY: {n_pass}/{len(seeds)}\n")

    print()
    print("=" * 60)
    print(f"Substrate-only 140-D k-sweep (spiking rot + cosine + argmax):")
    total_pass = 0; total = 0
    for k in ks:
        n, _ = table[k]
        print(f"  k={k:2d}: {n}/{len(seeds)}")
        total_pass += n; total += len(seeds)
    print(f"  TOTAL: {total_pass}/{total}")
    print(f"  wall clock: {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
