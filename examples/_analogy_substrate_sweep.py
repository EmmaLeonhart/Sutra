"""Run the capital-country analogy on three substrates via the
@embedding directive.

Exercises the per-program embedding-space override (STATUS #1,
landed 2026-04-22). The harness compiles three different .su files,
each of which declares its substrate in a `// @embedding:` directive
at the top of the source. No Python-side substrate override needed;
the directive is parsed by `_su_harness.compile_to_module`.

Each program runs the same 5-pair capital-country associative memory
and queries `country_of(paris)`, `country_of(tokyo)`, etc. Report
the winner per substrate, plus the cosine margin to the runner-up —
correctness alone doesn't tell you how comfortably the substrate is
discriminating.

The three files are:

- `examples/analogy.su`         (no directive -> default: nomic-embed-text)
- `examples/analogy_mxbai.su`   (@embedding: mxbai-embed-large)
- `examples/analogy_minilm.su`  (@embedding: all-minilm)

Usage: python examples/_analogy_substrate_sweep.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _su_harness import compile_to_module  # noqa: E402


PAIRS = [
    ("paris",  "france"),
    ("tokyo",  "japan"),
    ("london", "uk"),
    ("rome",   "italy"),
    ("cairo",  "egypt"),
]
COUNTRIES = [c for _, c in PAIRS]


def query_ranking(mod, capital_name: str) -> list[tuple[str, float]]:
    """Re-run the unbind + 5-country cosine explicitly in Python so we
    can see the full ranking and compute margin, not just the winner.
    """
    vsa = mod._VSA
    capital = getattr(mod, capital_name)
    memory = mod.memory
    recovered = vsa.unbind(capital, memory)
    rec_n = np.linalg.norm(recovered) + 1e-12
    ranked = []
    for country in COUNTRIES:
        cv = getattr(mod, country)
        cvn = np.linalg.norm(cv) + 1e-12
        cos = float(np.dot(recovered, cv) / (rec_n * cvn))
        ranked.append((country, cos))
    ranked.sort(key=lambda x: -x[1])
    return ranked


def run_one(path: str, label: str) -> dict:
    print("-" * 72)
    print(f"{label}  [{os.path.basename(path)}]")
    print("-" * 72)
    mod = compile_to_module(path)

    correct = 0
    margins = []
    print(f"  {'capital':<8} -> {'target':<8}  "
          f"{'winner':<8}  cos     runner    cos     margin  ok")
    print(f"  {'-' * 70}")
    for capital, target in PAIRS:
        ranked = query_ranking(mod, capital)
        winner, winner_cos = ranked[0]
        runner, runner_cos = ranked[1]
        margin = winner_cos - runner_cos
        ok = winner == target
        if ok:
            correct += 1
        margins.append(margin)
        mark = "OK " if ok else "NO "
        print(f"  {capital:<8} -> {target:<8}  "
              f"{winner:<8}  {winner_cos:+.3f}  "
              f"{runner:<8}  {runner_cos:+.3f}  "
              f"{margin:+.3f}  {mark}")
    mean_m = float(np.mean(margins))
    min_m = float(np.min(margins))
    max_m = float(np.max(margins))
    print(f"  {correct}/5 correct   "
          f"margin mean={mean_m:+.3f}  min={min_m:+.3f}  max={max_m:+.3f}")
    return dict(label=label, correct=correct, total=len(PAIRS),
                mean_margin=mean_m, min_margin=min_m, max_margin=max_m)


def main() -> int:
    print("=" * 72)
    print("Capital-country analogy across substrates (via @embedding directive)")
    print("=" * 72)

    programs = [
        ("examples/analogy.su",        "nomic-embed-text (default, no directive)"),
        ("examples/analogy_mxbai.su",  "mxbai-embed-large (@embedding directive)"),
        ("examples/analogy_minilm.su", "all-minilm (@embedding directive)"),
    ]
    results = []
    for rel, label in programs:
        path = os.path.join(os.path.dirname(HERE), rel)
        results.append(run_one(path, label))

    print()
    print("=" * 72)
    print("Side-by-side summary")
    print("=" * 72)
    print(f"  {'substrate':<48}  {'acc':<5}  mean    min")
    print(f"  {'-' * 70}")
    for r in results:
        print(f"  {r['label']:<48}  "
              f"{r['correct']}/{r['total']}    "
              f"{r['mean_margin']:+.3f}  {r['min_margin']:+.3f}")
    print()
    print("Interpretation:")
    print("  acc = correct winners / 5 queries.")
    print("  mean / min margin: cosine gap to runner-up. >0.1 comfortable,")
    print("  <0.02 fragile (a small perturbation could flip the result).")
    return 0 if all(r["correct"] == 5 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
