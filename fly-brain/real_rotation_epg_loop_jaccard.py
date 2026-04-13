"""
Jaccard-on-KC termination test for real-wiring EPG rotation.

Hypothesis: the 3/5 spiking result with cosine readout
(`real_rotation_epg_loop_spiking.py`) and the 3/5 composed result
(`real_rotation_composed_spiking.py`, peak cos ~0.1) both fail because
cosine readout in high-D has a per-dim Poisson noise floor that scales
with sqrt(N). Routing iterated state through the mushroom-body PN->KC
sparse projection and terminating on KC-pattern Jaccard overlap against
a compiled prototype should suppress Gaussian cosine noise — the MB's
~5% sparsity + ~2000-D KC code is the entire point of the readout, and
`scale_eval_loop.py` already shows 20/20 convergence at SIM_MS=200ms
with synthetic Givens R.

If this brings real-wiring EPG to 5/5, the pipeline has:
- Rotation operator: polar decomposition of real FlyWire EPG->EPG
- Rotation step: host numpy matmul (NOT substrate-compliant per the
  current spec — numpy at runtime is forbidden for vector ops, only
  compile+monitor are allowed. This file measures the readout in
  isolation, so the rotation half's substrate non-compliance is a
  known caveat, not a resolved question.)
- Termination readout: hemibrain MB Jaccard overlap (substrate, spiking)

Dimension: EPG Q is 51-D. The initial attempt embedded Q in the 140-D
hemibrain PN vector as block_diag(Q, I_89), but that failed immediately:
89/140 dims are unchanged each iteration, so the KC projection of
R^k v_0 looks nearly identical to the projection of R^k' v_0 for any
k, k' — every loop terminated at iter 1 with a spurious above-threshold
match against whatever prototype happened to be closest. The identity
padding destroys the discriminability the MB readout is supposed to
provide.

So we drop hemibrain and run `FlyBrainVSA(dim=51, use_hemibrain=False)`:
Q fills the whole PN space, and the PN->KC projection is random (2000
KCs, 10% sparsity) instead of the real hemibrain wiring. Real wiring
for rotation (numpy), synthetic spiking circuit for readout.
This is strictly weaker than "both sides real" but isolates the
question of whether KC-Jaccard readout breaks the Poisson SNR problem.
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
from vsa_operations import FlyBrainVSA


def build_epg_Q():
    fw = load_flywire(verbose=False)
    W = build_epg_to_epg(fw)
    Q, _ = nearest_rotation(W)
    return Q


def run_counting(vsa: FlyBrainVSA, Q_full: np.ndarray, target_k: int,
                 seed: int, max_iters: int = 10, threshold: float = 0.2) -> dict:
    rng = np.random.RandomState(seed)
    start = rng.randn(vsa.dim)
    start /= np.linalg.norm(start)
    proto = np.linalg.matrix_power(Q_full, target_k) @ start
    compiled = vsa.compile_prototypes({"TARGET": proto}, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=Q_full,
        compiled_prototypes=compiled,
        target_name="TARGET", threshold=threshold, max_iters=max_iters,
        frame_seed=seed,
    )
    return {"matched": matched, "n_iters": n_iters,
            "pass": matched == "TARGET" and n_iters == target_k}


def run_ordering(vsa: FlyBrainVSA, Q_full: np.ndarray, seed: int,
                 max_iters: int = 15, threshold: float = 0.2) -> dict:
    rng = np.random.RandomState(seed + 13)
    start = rng.randn(vsa.dim)
    start /= np.linalg.norm(start)
    proto_vecs = {
        "EARLY":  np.linalg.matrix_power(Q_full, 2) @ start,
        "MIDDLE": np.linalg.matrix_power(Q_full, 5) @ start,
        "LATE":   np.linalg.matrix_power(Q_full, 8) @ start,
    }
    compiled = vsa.compile_prototypes(proto_vecs, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=Q_full,
        compiled_prototypes=compiled,
        target_name=None, threshold=threshold, max_iters=max_iters,
        frame_seed=seed,
    )
    return {"matched": matched, "n_iters": n_iters,
            "pass": matched == "EARLY"}


def main():
    print("Building EPG Q from FlyWire...")
    Q = build_epg_Q()
    print(f"  EPG Q: shape={Q.shape}, "
          f"||QtQ-I||_F={np.linalg.norm(Q.T@Q - np.eye(Q.shape[0]), 'fro'):.2e}")

    Q_full = Q  # use the 51-D Q directly
    print(f"  using 51-D EPG Q directly with dim=51 FlyBrainVSA (random MB)\n")

    seeds = [0, 1, 2, 3, 4]
    max_iters = 8
    threshold = 0.5

    # Jaccard-gap probe: for seed 0, target k=3, walk the iterates
    # without a threshold and record actual KC Jaccard overlap per step.
    # We need to see there's a real gap between iter-1 (would be false
    # positive at threshold=0.2) and iter-3 (true positive), not just
    # that we tuned a threshold to pass.
    print("Jaccard gap probe (seed=0, target k=3, no threshold):")
    from spike_vsa_bridge import SpikeVSABridge
    vsa_probe = FlyBrainVSA(dim=51, n_kc=2000, seed=0,
                             use_hemibrain=False, snap_duration_ms=200)
    rng = np.random.RandomState(0)
    start = rng.randn(vsa_probe.dim); start /= np.linalg.norm(start)
    proto = np.linalg.matrix_power(Q, 3) @ start
    compiled = vsa_probe.compile_prototypes({"TARGET": proto}, frame_seed=0)
    proto_pat = compiled["TARGET"]
    for k in range(1, 7):
        state_k = np.linalg.matrix_power(Q, k) @ start
        bridge = vsa_probe._make_bridge(fixed_seed=0)
        kc_k = bridge.snap_to_kc_pattern(state_k, vsa_probe.snap_duration_ms)
        inter = float(np.sum(kc_k * proto_pat))
        union = float(np.sum(np.clip(kc_k + proto_pat, 0, 1)))
        jac = inter / max(union, 1.0)
        print(f"  k={k}  jaccard(state_k, proto)={jac:.3f}")
    print()
  # tighter than default 0.2 — EPG Q's near-identity
                      # eigenvalues make early iterates too similar to
                      # target at lenient thresholds

    # Counting k=3
    print(f"Counting to k=3 (KC-Jaccard readout, {len(seeds)} seeds, "
          f"threshold={threshold})")
    t0 = time.time()
    count_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(dim=51, n_kc=2000, seed=seed, use_hemibrain=False, snap_duration_ms=200)
        ts = time.time()
        r = run_counting(vsa, Q_full, target_k=3, seed=seed,
                         max_iters=max_iters, threshold=threshold)
        dt = time.time() - ts
        count_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_pass_c = sum(int(r["pass"]) for r in count_results)
    print(f"  COUNTING k=3: {n_pass_c}/{len(seeds)}\n")

    # Ordering (EARLY@2, MIDDLE@5, LATE@8 — should match EARLY first)
    print(f"Ordering (EARLY@2 first, {len(seeds)} seeds)")
    order_results = []
    for seed in seeds:
        vsa = FlyBrainVSA(dim=51, n_kc=2000, seed=seed, use_hemibrain=False, snap_duration_ms=200)
        ts = time.time()
        r = run_ordering(vsa, Q_full, seed=seed, max_iters=15,
                         threshold=threshold)
        dt = time.time() - ts
        order_results.append(r)
        print(f"  seed={seed}  matched={r['matched']}  n_iters={r['n_iters']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.0f}s]")
    n_pass_o = sum(int(r["pass"]) for r in order_results)
    print(f"  ORDERING: {n_pass_o}/{len(seeds)}\n")

    print("=" * 60)
    print(f"Real-wiring EPG Q + KC-Jaccard readout:")
    print(f"  counting k=3: {n_pass_c}/{len(seeds)}")
    print(f"  ordering:     {n_pass_o}/{len(seeds)}")
    print(f"  wall clock:   {time.time() - t0:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
