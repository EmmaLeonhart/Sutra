"""
Scaled evaluation of the permutation-conditional branching test.

The paper currently reports 13/16 correct on a single run of
`permutation_conditional.py`. Reviewer v19 flagged this as statistically
insignificant. This harness runs the same 16-trial suite N times against
the hemibrain substrate and reports the full distribution of per-trial
accuracy, so we can report a real mean +/- stdev instead of one sample.

Each run re-instantiates the Brian2 bridge, so the stochasticity comes
from actual Poisson input variance, not seed choice. Everything else
(prototype table, primitives, expected mapping) is fixed across runs.
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
from fuzzy_conditional import (
    FixedFrameFlyBrainVSA,
    build_primitives,
    build_behavior_vecs,
    compile_prototypes,
    run_decision,
)


EXPECTED = {
    "A": ["approach", "ignore",   "search",   "idle"],
    "B": ["search",   "idle",     "approach", "ignore"],
    "C": ["ignore",   "approach", "idle",     "search"],
    "D": ["idle",     "search",   "ignore",   "approach"],
}


def one_run(seed):
    vsa = FixedFrameFlyBrainVSA(seed=seed, use_hemibrain=True)
    rng = np.random.RandomState(seed)
    prims = build_primitives(vsa, rng)
    behavior_vecs = build_behavior_vecs(vsa, rng)
    prototypes = compile_prototypes(vsa, prims)
    inputs = [
        ("vinegar",   "hungry", prims["smell_present"], prims["hunger_hungry"]),
        ("vinegar",   "fed",    prims["smell_present"], prims["hunger_fed"]),
        ("clean_air", "hungry", prims["smell_absent"],  prims["hunger_hungry"]),
        ("clean_air", "fed",    prims["smell_absent"],  prims["hunger_fed"]),
    ]
    correct = 0
    total = 0
    per_program = {}
    mappings = {}
    for prog_id in ["A", "B", "C", "D"]:
        prog_got = []
        prog_correct = 0
        for i, (_, _, s_vec, h_vec) in enumerate(inputs):
            behavior, _, _, _ = run_decision(
                vsa, prototypes, behavior_vecs, s_vec, h_vec, prog_id,
            )
            exp = EXPECTED[prog_id][i]
            prog_got.append(behavior)
            if behavior == exp:
                prog_correct += 1
                correct += 1
            total += 1
        per_program[prog_id] = prog_correct
        mappings[prog_id] = tuple(prog_got)
    distinct = len(set(mappings.values())) == 4
    return correct, total, per_program, distinct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-runs', type=int, default=20,
                        help='Number of independent runs of the 16-trial suite')
    parser.add_argument('--base-seed', type=int, default=1000)
    args = parser.parse_args()

    print(f"Scaled eval: {args.n_runs} runs x 16 trials = {args.n_runs * 16} trials")
    print(f"Substrate: hemibrain v1.2.1 (140 PN -> 1882 KC -> APL -> 20 MBON)")
    print(f"Base seed: {args.base_seed}\n")

    t_start = time.time()
    accs = []
    per_prog_accs = {p: [] for p in "ABCD"}
    distinct_count = 0
    for run_idx in range(args.n_runs):
        seed = args.base_seed + run_idx
        correct, total, per_program, distinct = one_run(seed)
        acc = correct / total
        accs.append(acc)
        for p in "ABCD":
            per_prog_accs[p].append(per_program[p] / 4)
        if distinct:
            distinct_count += 1
        elapsed = time.time() - t_start
        print(f"  run {run_idx+1:2d}/{args.n_runs} seed={seed} "
              f"correct={correct:2d}/{total} acc={acc:.3f} distinct={distinct} "
              f"[{elapsed:.0f}s]")

    accs = np.array(accs)
    print(f"\n{'=' * 60}")
    print(f"AGGREGATE OVER {args.n_runs} RUNS ({args.n_runs * 16} TRIALS)")
    print(f"{'=' * 60}")
    print(f"Per-trial accuracy: mean={accs.mean():.3f}  stdev={accs.std():.3f}  "
          f"min={accs.min():.3f}  max={accs.max():.3f}")
    total_correct = int(accs.sum() * 16)
    total_trials = args.n_runs * 16
    print(f"Total: {total_correct}/{total_trials} "
          f"({100*total_correct/total_trials:.1f}%)")
    print(f"Runs producing 4 distinct program mappings: "
          f"{distinct_count}/{args.n_runs}")
    print(f"\nPer-program accuracy (mean +/- stdev):")
    for p in "ABCD":
        arr = np.array(per_prog_accs[p])
        print(f"  Program {p}: {arr.mean():.3f} +/- {arr.std():.3f}")


if __name__ == '__main__':
    main()
