"""
Scaled evaluation of the geometric-loop tests.

Mirrors `scale_eval_conditional.py`: runs the three loop tests
(convergence, counting, ordering) across N independent hemibrain seeds
and reports the full distribution of per-test pass rates.

Each run re-instantiates the Brian2 bridge with a fresh seed, so
stochasticity comes from actual Poisson input variance plus the choice
of random rotation planes and random start vectors (everything derived
from the per-run seed).
"""

import io
import sys
import time
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import numpy as np

from vsa_operations import FlyBrainVSA
from spike_vsa_bridge import cosine_similarity


def one_convergence(seed):
    """Target at step 3; expect TARGET match within max_iters."""
    vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=200)
    R = vsa.make_random_rotation(angle=np.pi / 3, n_planes=20, seed=seed + 1000)
    rng = np.random.RandomState(seed)
    start = rng.randn(vsa.dim)
    start = start / np.linalg.norm(start)
    target = np.linalg.matrix_power(R, 3) @ start
    compiled = vsa.compile_prototypes({'TARGET': target}, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=R,
        compiled_prototypes=compiled,
        target_name='TARGET', threshold=0.2, max_iters=10,
        frame_seed=seed,
    )
    return matched == 'TARGET', n_iters


def one_counting(seed):
    """Prototypes at 3 and 6; expect THREE from target=THREE and SIX from target=SIX."""
    vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=200)
    R = vsa.make_random_rotation(angle=np.pi / 4, n_planes=20, seed=seed + 2000)
    rng = np.random.RandomState(seed + 7)
    start = rng.randn(vsa.dim)
    start = start / np.linalg.norm(start)
    proto_vecs = {
        'THREE': np.linalg.matrix_power(R, 3) @ start,
        'SIX':   np.linalg.matrix_power(R, 6) @ start,
    }
    compiled = vsa.compile_prototypes(proto_vecs, frame_seed=seed)
    m3, _, _ = vsa.loop(
        initial_state=start, rotation=R,
        compiled_prototypes=compiled,
        target_name='THREE', threshold=0.2, max_iters=15,
        frame_seed=seed,
    )
    m6, _, _ = vsa.loop(
        initial_state=start, rotation=R,
        compiled_prototypes=compiled,
        target_name='SIX', threshold=0.2, max_iters=15,
        frame_seed=seed,
    )
    return (m3 == 'THREE'), (m6 == 'SIX')


def one_ordering(seed):
    """Prototypes at 2, 5, 8; with no target, first match should be EARLY."""
    vsa = FlyBrainVSA(seed=seed, use_hemibrain=True, snap_duration_ms=200)
    R = vsa.make_random_rotation(angle=np.pi / 5, n_planes=20, seed=seed + 3000)
    rng = np.random.RandomState(seed + 13)
    start = rng.randn(vsa.dim)
    start = start / np.linalg.norm(start)
    proto_vecs = {
        'EARLY':  np.linalg.matrix_power(R, 2) @ start,
        'MIDDLE': np.linalg.matrix_power(R, 5) @ start,
        'LATE':   np.linalg.matrix_power(R, 8) @ start,
    }
    compiled = vsa.compile_prototypes(proto_vecs, frame_seed=seed)
    matched, _, n_iters = vsa.loop(
        initial_state=start, rotation=R,
        compiled_prototypes=compiled,
        target_name=None, threshold=0.2, max_iters=15,
        frame_seed=seed,
    )
    return matched == 'EARLY', matched, n_iters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-runs', type=int, default=5)
    parser.add_argument('--base-seed', type=int, default=2000)
    args = parser.parse_args()

    print(f"Scaled loop eval: {args.n_runs} runs x 4 tests = {args.n_runs * 4} trials")
    print(f"Substrate: hemibrain v1.2.1 (140 PN -> 1882 KC -> APL -> 20 MBON)")
    print(f"Base seed: {args.base_seed}\n")

    t_start = time.time()
    conv_ok = 0
    count3_ok = 0
    count6_ok = 0
    order_ok = 0
    conv_iters = []
    for run_idx in range(args.n_runs):
        seed = args.base_seed + run_idx
        c_ok, c_iters = one_convergence(seed)
        t3, t6 = one_counting(seed)
        o_ok, o_matched, o_iters = one_ordering(seed)

        conv_ok += int(c_ok)
        count3_ok += int(t3)
        count6_ok += int(t6)
        order_ok += int(o_ok)
        conv_iters.append(c_iters)

        elapsed = time.time() - t_start
        print(f"  run {run_idx+1:2d}/{args.n_runs} seed={seed} "
              f"conv={'OK' if c_ok else 'XX'}(iters={c_iters}) "
              f"count3={'OK' if t3 else 'XX'} count6={'OK' if t6 else 'XX'} "
              f"order={'OK' if o_ok else 'XX'}(got={o_matched}) "
              f"[{elapsed:.0f}s]")

    n = args.n_runs
    print(f"\n{'=' * 60}")
    print(f"AGGREGATE OVER {n} RUNS")
    print(f"{'=' * 60}")
    print(f"Convergence (target@3):  {conv_ok}/{n}  "
          f"iters mean={np.mean(conv_iters):.2f} stdev={np.std(conv_iters):.2f}")
    print(f"Counting to THREE:       {count3_ok}/{n}")
    print(f"Counting to SIX:         {count6_ok}/{n}")
    print(f"Ordering (first=EARLY):  {order_ok}/{n}")
    total = conv_ok + count3_ok + count6_ok + order_ok
    print(f"\nTotal: {total}/{4*n} ({100*total/(4*n):.1f}%)")


if __name__ == '__main__':
    main()
