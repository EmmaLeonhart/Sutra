"""
Geometric loop test driven by the real-wiring rotation Q.

Q is the nearest orthogonal matrix to the FlyWire v783 CX EPG->EPG
recurrent weight matrix (via polar decomposition, see
real_rotation_epg.py). This script runs the same counting-and-ordering
tests that scale_eval_loop.py runs with a synthetic Givens rotation,
but drives them with Q.

Specifically we ask: if we place a prototype at Q^k v_0 for chosen k
(e.g. k=3 and k=6), does cosine similarity against that prototype peak
exactly at iteration k during the loop? If yes, Q can serve as the
loop's rotation operator even though it is 51x51 and derived from the
central-complex recurrent wiring rather than an arbitrary Givens
composition.

This is a numpy rotation test in the 51-D EPG subspace. It does not
run through the mushroom-body spiking circuit; that integration is a
later step. The point here is to verify that real-wiring-derived Q
supports the three geometric-loop patterns at all.
"""

from __future__ import annotations

import sys
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from flywire_loader import load_flywire
from real_rotation_epg import build_epg_to_epg, nearest_rotation


def run_counting_test(Q: np.ndarray, target_k: int, max_iters: int = 15,
                      seed: int = 0) -> dict:
    """Place prototype at Q^target_k v0. Iterate the loop, report iteration
    of max cosine to prototype. Pass if argmax iteration == target_k."""
    rng = np.random.RandomState(seed)
    dim = Q.shape[0]
    v0 = rng.randn(dim)
    v0 /= np.linalg.norm(v0)
    proto = np.linalg.matrix_power(Q, target_k) @ v0
    proto /= np.linalg.norm(proto)

    state = v0.copy()
    cos_by_k = []
    for k in range(max_iters + 1):
        c = float(state @ proto / (np.linalg.norm(state) + 1e-12))
        cos_by_k.append(c)
        state = Q @ state

    argmax_k = int(np.argmax(cos_by_k))
    return {
        "target_k": target_k,
        "argmax_k": argmax_k,
        "peak_cos": float(np.max(cos_by_k)),
        "cos_by_k": cos_by_k,
        "pass": argmax_k == target_k,
    }


def run_ordering_test(Q: np.ndarray, proto_steps: list[int],
                      proto_names: list[str], max_iters: int = 15,
                      seed: int = 0) -> dict:
    """Place several prototypes at Q^k_i v0. Iterate, record which prototype
    is matched first (cosine first to cross 0.9 of its peak). Expect the
    smallest-k prototype to fire first."""
    rng = np.random.RandomState(seed)
    dim = Q.shape[0]
    v0 = rng.randn(dim)
    v0 /= np.linalg.norm(v0)
    protos = {
        name: np.linalg.matrix_power(Q, k) @ v0 / np.linalg.norm(
            np.linalg.matrix_power(Q, k) @ v0)
        for name, k in zip(proto_names, proto_steps)
    }
    state = v0.copy()
    peak_iter = {name: -1 for name in proto_names}
    peak_cos = {name: -np.inf for name in proto_names}
    for k in range(max_iters + 1):
        s = state / (np.linalg.norm(state) + 1e-12)
        for name in proto_names:
            c = float(s @ protos[name])
            if c > peak_cos[name]:
                peak_cos[name] = c
                peak_iter[name] = k
        state = Q @ state

    expected_first = proto_names[int(np.argmin(proto_steps))]
    got_first = min(proto_names, key=lambda n: peak_iter[n])
    return {
        "peak_iter": peak_iter,
        "peak_cos": peak_cos,
        "expected_first": expected_first,
        "got_first": got_first,
        "pass": got_first == expected_first,
    }


def main():
    print("Loading FlyWire v783...")
    fw = load_flywire(verbose=False)
    print("Building real EPG -> EPG recurrent W (51 x 51)...")
    W = build_epg_to_epg(fw)
    Q, diag = nearest_rotation(W)
    print(f"  Q is orthogonal to {diag['Q_orthogonality_residual']:.2e} "
          f"(Frob), det Q = {diag['det_Q']:+.6f}\n")

    print("Counting test: prototype at Q^target v0, iterate, argmax cos.")
    seeds = [0, 1, 2, 3, 4]
    targets = [3, 6]
    results = []
    for target in targets:
        n_pass = 0
        for seed in seeds:
            r = run_counting_test(Q, target_k=target, seed=seed)
            results.append((target, seed, r))
            n_pass += int(r["pass"])
        print(f"  target k={target}: {n_pass}/{len(seeds)} seeds matched argmax k")
        for target_shown, seed, r in results[-len(seeds):]:
            print(f"    seed={seed}  argmax_k={r['argmax_k']:2d}  "
                  f"peak_cos={r['peak_cos']:+.3f}  "
                  f"{'PASS' if r['pass'] else 'FAIL'}")
    print()

    print("Ordering test: prototypes at k=2, 5, 8. Expect EARLY first.")
    n_pass = 0
    for seed in seeds:
        r = run_ordering_test(Q, proto_steps=[2, 5, 8],
                              proto_names=["EARLY", "MIDDLE", "LATE"],
                              seed=seed + 100)
        print(f"    seed={seed+100}  "
              f"peak iters: EARLY={r['peak_iter']['EARLY']:2d} "
              f"MIDDLE={r['peak_iter']['MIDDLE']:2d} "
              f"LATE={r['peak_iter']['LATE']:2d}  "
              f"got_first={r['got_first']}  "
              f"{'PASS' if r['pass'] else 'FAIL'}")
        n_pass += int(r["pass"])
    print(f"  Ordering: {n_pass}/{len(seeds)} seeds correct\n")

    total_counting = sum(int(r["pass"]) for (_, _, r) in results)
    print("=" * 60)
    print(f"Counting (k=3 and k=6 x 5 seeds): {total_counting}/10")
    print(f"Ordering (EARLY first x 5 seeds): {n_pass}/5")
    print("=" * 60)


if __name__ == "__main__":
    main()
