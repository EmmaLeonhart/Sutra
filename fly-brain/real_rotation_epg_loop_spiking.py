"""
Geometric loop driven by real-wiring Q through Brian2 spiking rotate.

Queue item 2 (STATUS.md): lift the Q loop test from numpy rotation
(real_rotation_epg_loop.py) into actual spiking dynamics. Each loop
step evolves v_{k+1} = Q @ v_k as a Brian2 LIF population using
neural_linear_map from neural_vsa.py — Q becomes a 51x51 pattern of
synaptic weights (positive excitatory, negative inhibitory), the
input vector is Poisson-rate-coded, and the steady-state membrane
voltage of the output population decodes back to the rotated vector.

The question: does the loop still pick out the correct target
iteration k when the rotation runs on spiking neurons rather than
numpy? Noise per step will reduce peak cosine below 1.0 (pure numpy
gave cos=1.000 because Q is orthogonal at machine precision), but
argmax should still be at the target k for small k — which is all
Sutra's loop(condition) needs.

Runs a small grid (counting target k=3, 3 seeds) to keep wall-clock
reasonable; each Brian2 sim is ~1-2 seconds and we need 3*4=12 per
seed for the iterated states.
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
from flywire_loader import load_flywire
from real_rotation_epg import build_epg_to_epg, nearest_rotation
import neural_vsa
from neural_vsa import neural_linear_map

# Longer averaging window per step reduces Poisson variance before it
# compounds across loop iterations. neural_vsa's rotate self-test uses
# 1500 ms for the same reason.
neural_vsa.SIM_MS = 3000.0


def spiking_counting(Q: np.ndarray, target_k: int, max_iters: int = 6,
                     seed: int = 0) -> dict:
    """Run the counting test with Q iterated through spiking rotate.

    proto = Q^target_k v0 (computed numerically — this is compile-time
    circuit specification, not the runtime rotation). At runtime we
    iterate the spiking rotate circuit and record cos(state_k, proto)
    at each step.
    """
    rng = np.random.RandomState(seed)
    dim = Q.shape[0]
    v0 = rng.randn(dim)
    v0 /= np.linalg.norm(v0)
    proto = np.linalg.matrix_power(Q, target_k) @ v0
    proto /= np.linalg.norm(proto)

    state = v0.copy()
    cos_by_k = []
    c0 = float(state @ proto / (np.linalg.norm(state) + 1e-12))
    cos_by_k.append(c0)
    for k in range(1, max_iters + 1):
        state = neural_linear_map(Q, state, seed=seed * 31 + k)
        n = np.linalg.norm(state)
        if n < 1e-9:
            break
        s_norm = state / n
        c = float(s_norm @ proto)
        cos_by_k.append(c)
        # Renormalize the state between iterations: Q is exactly
        # norm-preserving in theory, but spiking decoding has O(1/sqrt(T))
        # variance that accumulates on the magnitude otherwise.
        state = s_norm
    argmax_k = int(np.argmax(cos_by_k))
    return {
        "target_k": target_k,
        "argmax_k": argmax_k,
        "peak_cos": float(np.max(cos_by_k)),
        "cos_by_k": cos_by_k,
        "pass": argmax_k == target_k,
    }


def main():
    print("Loading FlyWire v783 + building real EPG->EPG Q...")
    fw = load_flywire(verbose=False)
    W = build_epg_to_epg(fw)
    Q, diag = nearest_rotation(W)
    print(f"  Q: shape={Q.shape}  ||Q^T Q - I||={diag['Q_orthogonality_residual']:.2e}\n")

    target = 3
    max_iters = 6
    seeds = [0, 1, 2, 3, 4]
    print(f"Spiking counting test: target k={target}, max_iters={max_iters}, "
          f"{len(seeds)} seeds.")
    print(f"Each iteration runs Q through Brian2 LIF (51 Poisson inputs -> "
          f"51 LIF outputs via 51x51 synapse matrix weighted by Q).\n")

    t_start = time.time()
    results = []
    for seed in seeds:
        t0 = time.time()
        r = spiking_counting(Q, target_k=target, max_iters=max_iters, seed=seed)
        dt = time.time() - t0
        results.append(r)
        cos_str = " ".join(f"k{i}={c:+.2f}" for i, c in enumerate(r["cos_by_k"]))
        print(f"  seed={seed}  argmax_k={r['argmax_k']}  "
              f"peak_cos={r['peak_cos']:+.3f}  {cos_str}  "
              f"{'PASS' if r['pass'] else 'FAIL'}  [{dt:.1f}s]")

    n_pass = sum(int(r["pass"]) for r in results)
    total = len(results)
    elapsed = time.time() - t_start
    print()
    print("=" * 60)
    print(f"Spiking counting at k={target}: {n_pass}/{total} seeds")
    print(f"Wall clock: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
