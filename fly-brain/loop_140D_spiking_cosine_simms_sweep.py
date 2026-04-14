"""
Does longer SIM_MS push the substrate-only k-ceiling above 3?

Baseline (loop_140D_spiking_cosine_ksweep.py at SIM_MS=3000): 5/5 at k=1,
5/5 at k=2, 4/5 at k=3, 0/5 at k=5, 8, 12. Ceiling at k≈3 from Poisson
decode noise accumulating multiplicatively across iterations.

This script measures SIM_MS ∈ {3000, 6000, 12000} at k ∈ {3, 5, 8} × 3
seeds to see whether integration window extends the reachable k. If the
ceiling moves up proportionally to sqrt(SIM_MS) — the expected scaling
for Poisson-counting SNR — then longer windows are the cheap fix. If
not, the ceiling is structural and needs wider substrate or cleanup
between steps.

Wall-clock note: at SIM_MS=12000 each step takes ~4x the baseline
~15s/step, so one (k=8, SIM_MS=12000) trial is ~15 iterations *
60s/step = ~15 min. Total budget for this sweep: ~1 hour.
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


def main():
    print("Building 140-D Q (det = +1)...")
    Q = build_140D_Q_so()
    orth = float(np.linalg.norm(Q.T @ Q - np.eye(len(Q)), "fro"))
    det = float(np.linalg.det(Q))
    print(f"Q: shape={Q.shape}  ||QtQ-I||_F={orth:.2e}  det={det:+.4f}\n")

    sim_ms_values = [3000.0, 6000.0, 12000.0]
    ks = [3, 5, 8]
    seeds = [0, 1, 2]
    max_iters = 15

    t0 = time.time()
    results = {}
    for sim_ms in sim_ms_values:
        neural_vsa.SIM_MS = sim_ms
        print(f"=== SIM_MS = {sim_ms} ms ===")
        for k in ks:
            row = []
            for seed in seeds:
                ts = time.time()
                r = run_counting_argmax(Q, target_k=k, seed=seed,
                                        max_iters=max_iters)
                dt = time.time() - ts
                row.append(r)
                tag = "PASS" if r["pass"] else "FAIL"
                print(f"  SIM_MS={sim_ms:>5.0f} k={k:2d} seed={seed}  "
                      f"argmax_k={r['argmax_k']}  {tag}  [{dt:.0f}s]")
            n_pass = sum(int(r["pass"]) for r in row)
            results[(sim_ms, k)] = (n_pass, row)
            print(f"  SIM_MS={sim_ms:>5.0f} k={k:2d} SUMMARY: {n_pass}/{len(seeds)}")
        print()

    print("=" * 60)
    print("SIM_MS sweep on substrate-only 140-D loop:")
    print(f"           k=3     k=5     k=8")
    for sim_ms in sim_ms_values:
        cols = []
        for k in ks:
            n, _ = results[(sim_ms, k)]
            cols.append(f"{n}/{len(seeds)}")
        print(f"  {sim_ms:>5.0f}ms: {cols[0]:>6} {cols[1]:>6} {cols[2]:>6}")
    print(f"  wall clock: {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
