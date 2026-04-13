"""
Target-k sweep for the 140-D real-wiring + real hemibrain Jaccard loop
(queue item 3).

The 5/5+5/5 result in `planning/findings/2026-04-13-jaccard-140D-
real-hemibrain.md` tested only target k=3. This sweep confirms the
Jaccard readout is not specific to k=3 by running counting at
k in {1, 2, 3, 5, 8, 12} across 5 seeds each. Same Q, same substrate,
same threshold (0.5); only the target varies.

Theory prediction (`planning/sutra-spec/23-loop-readout-theory.md`):
the KC-Jaccard gap is set by sparsity s and the sameness of the state
vs prototype, not by k. So pass rate should stay near 5/5 for any k
up to the point where R's spectrum puts state_k and a nearby state_k'
close enough in PN space that their KC patterns cross — which for a
well-mixed 140-D operator should not happen at small k.

The k=12 point is the real test. max_iters needs to scale with k.
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
    hd_types = ["hDeltaJ", "hDeltaK", "hDeltaA", "hDeltaD", "hDeltaE"]
    W_hd = build_square_motif(fw, hd_types, hd_types, "hDelta-89")
    Q_hd, _ = nearest_rotation(W_hd)
    return block_diag(Q_epg, Q_hd)


def run_counting(vsa, Q, target_k, seed, threshold=0.5):
    max_iters = max(8, target_k + 4)
    rng = np.random.RandomState(seed)
    start = rng.randn(vsa.dim); start /= np.linalg.norm(start)
    proto = np.linalg.matrix_power(Q, target_k) @ start
    compiled = vsa.compile_prototypes({"TARGET": proto}, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=Q, compiled_prototypes=compiled,
        target_name="TARGET", threshold=threshold, max_iters=max_iters,
        frame_seed=seed,
    )
    return matched == "TARGET" and n_iters == target_k, n_iters


def main():
    print("Building 140-D real-wiring Q...")
    Q = build_140D_Q()
    print(f"  shape={Q.shape}, det={np.linalg.det(Q):+.4f}\n")

    ks = [1, 2, 3, 5, 8, 12]
    seeds = [0, 1, 2, 3, 4]
    threshold = 0.5

    print(f"Counting target-k sweep (real hemibrain MB, threshold={threshold})")
    print(f"  {'k':>4} | {'seeds passing':<20} | {'n_iters each':<30}")
    print(f"  {'-'*4}-|-{'-'*20}-|-{'-'*30}")

    t0 = time.time()
    summary = []
    for k in ks:
        passes = []
        iters = []
        for seed in seeds:
            vsa = FlyBrainVSA(seed=seed, use_hemibrain=True,
                               snap_duration_ms=200)
            p, n = run_counting(vsa, Q, target_k=k, seed=seed,
                                 threshold=threshold)
            passes.append(p)
            iters.append(n)
        n_pass = sum(passes)
        summary.append((k, n_pass, iters))
        iters_str = " ".join(str(x) for x in iters)
        print(f"  k={k:<3}| {n_pass}/{len(seeds)} "
              f"{'PASS' if n_pass == len(seeds) else 'mixed':<13} | "
              f"{iters_str}")

    print()
    print("=" * 60)
    total_pass = sum(s[1] for s in summary)
    total_trials = len(ks) * len(seeds)
    print(f"Target-k sweep: {total_pass}/{total_trials} across k in {ks}")
    print(f"Wall clock: {time.time()-t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
