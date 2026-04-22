"""Monte-Carlo attractor search over the king - man + woman analogy.

STATUS 2026-04-22: WIP / DEFERRED. The cross-substrate sweep
(_king_queen_multi_substrate.py) answered the primary question
(which substrates give queen vs. which give king / woman under naive
arithmetic); Monte-Carlo is now about characterizing *robustness*
of the winning answer under perturbation. Per user priority,
deferred past the Anthropic grant app (~2026-04-29). See todo.md.

This script is runnable but hasn't been validated end-to-end on the
O(d) `perturb_on_sphere` replacement for the old make_small_rotation.
Expected behavior when it runs cleanly:

Companion to `king_queen_naive.su`. The naive .su program runs
argmax_cosine(king - man + woman, candidates) and returns the
top-scoring candidate. On nomic-embed-text with mean-centering the
naive result happens to be `queen`, but only by a thin margin
(~0.79 vs. king at ~0.75). This Python harness asks how *robust*
that margin is:

- Start from v0 = king - man + woman (the naive analogy vector).
- For N trials, perturb v0 by a small Haar-random rotation.
- Snap each perturbed vector to the nearest codebook entry.
- Report the histogram of winners across trials.

Interpretation: each codebook entry is an attractor with a basin of
attraction under cosine distance; Monte Carlo samples which basin v0
is closest to. A robust naive-analogy result would land on queen in
nearly every trial; a fragile one would scatter across king, queen,
and the near neighbors (princess, monarch).

Also reports the result with the three INPUT vectors (king, man,
woman) removed from the candidate pool — the word2vec-analogy-
benchmark convention. This is the version that has been published
as "showing" analogy works, and it's a useful contrast to the
honest (inputs-included) naive run.

Usage: python examples/_king_queen_attractor_search.py
"""
from __future__ import annotations

import os
import sys
import types
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SDK_PATH = os.path.join(REPO_ROOT, "sdk", "sutra-compiler")
sys.path.insert(0, SDK_PATH)

from sutra_compiler.codegen_numpy import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def compile_module(path: str) -> types.ModuleType:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module)
    mod = types.ModuleType("_kq_harness")
    mod.__file__ = path
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    return mod


def perturb_on_sphere(v: np.ndarray, angle: float, rng: np.random.RandomState) -> np.ndarray:
    """Rotate v by approximately `angle` radians toward a random direction.

    Cheap O(d) alternative to a full Haar rotation: draw a random unit
    direction orthogonal to v, then move along the arc between v and
    that direction by `angle` radians. Produces a vector of the same
    norm as v whose angular distance from v is `angle`.
    """
    d = np.random.RandomState(rng.randint(1 << 30)).randn(v.shape[0])
    # Project out the v-component so d is orthogonal to v
    d = d - (d @ v) / (v @ v + 1e-12) * v
    d = d / (np.linalg.norm(d) + 1e-12)
    # Rotate v toward d by `angle`
    return np.cos(angle) * v + np.sin(angle) * (d * np.linalg.norm(v))


def snap_to_codebook(v: np.ndarray, codebook: list[tuple[str, np.ndarray]]) -> tuple[str, float]:
    """Return (name, cosine) of the closest codebook entry to v."""
    best_name = None
    best_score = -np.inf
    for name, cv in codebook:
        s = float(np.dot(v, cv) / (np.linalg.norm(v) * np.linalg.norm(cv) + 1e-12))
        if s > best_score:
            best_score = s
            best_name = name
    return best_name, best_score


def run_trials(
    v0: np.ndarray,
    codebook: list[tuple[str, np.ndarray]],
    n_trials: int,
    perturbation_angle: float,
    seed: int = 12345,
) -> Counter:
    """N Monte-Carlo trials: perturb v0, snap, tally winners."""
    rng = np.random.RandomState(seed)
    winners: Counter = Counter()
    for _ in range(n_trials):
        v_perturbed = perturb_on_sphere(v0, perturbation_angle, rng)
        winner, _ = snap_to_codebook(v_perturbed, codebook)
        winners[winner] += 1
    return winners


def print_histogram(name: str, winners: Counter, total: int) -> None:
    print(f"\n{name}:")
    ranked = winners.most_common()
    for nm, count in ranked:
        bar = "#" * int(40 * count / total)
        pct = 100.0 * count / total
        print(f"  {nm:<10} {count:3} ({pct:5.1f}%) {bar}")


def main() -> int:
    print("=" * 72)
    print("Monte-Carlo attractor search over king - man + woman")
    print("=" * 72)

    # Compile king_queen_naive.su to get the VSA runtime, the
    # vocabulary vectors, and the naive analogy vector.
    mod = compile_module(os.path.join(HERE, "king_queen_naive.su"))
    v0 = mod.analogy  # bundle(displacement(king, man), woman), L2-normalized

    # All candidates (inputs included)
    full_codebook = [
        ("king",     mod.king),
        ("queen",    mod.queen),
        ("man",      mod.man),
        ("woman",    mod.woman),
        ("prince",   mod.prince),
        ("princess", mod.princess),
        ("boy",      mod.boy),
        ("girl",     mod.girl),
        ("ruler",    mod.ruler),
        ("monarch",  mod.monarch),
        ("husband",  mod.husband),
        ("wife",     mod.wife),
        ("father",   mod.father),
        ("mother",   mod.mother),
    ]
    # Exclude the three arithmetic inputs
    INPUTS = {"king", "man", "woman"}
    excluded_codebook = [(n, v) for n, v in full_codebook if n not in INPUTS]

    # Baseline: what does v0 snap to with zero perturbation?
    w_full, s_full = snap_to_codebook(v0, full_codebook)
    w_excl, s_excl = snap_to_codebook(v0, excluded_codebook)
    print("\nBaseline (no perturbation):")
    print(f"  argmax over all 14 candidates     : {w_full:<10}  cos={s_full:+.4f}")
    print(f"  argmax with king/man/woman excluded: {w_excl:<10}  cos={s_excl:+.4f}")

    n_trials = 300
    print(f"\nRunning {n_trials} Monte-Carlo trials at three perturbation scales.")
    print("Each trial: apply a small random Haar rotation to v0, snap to nearest codebook.")
    print("(Perturbation angle is the magnitude of the random rotation, in radians.)")

    for angle in [0.05, 0.15, 0.30]:
        print(f"\n--- Perturbation angle = {angle} rad ---")
        winners_full = run_trials(v0, full_codebook, n_trials, angle, seed=42)
        winners_excl = run_trials(v0, excluded_codebook, n_trials, angle, seed=42)
        print_histogram(
            f"  All 14 candidates (inputs included)",
            winners_full, n_trials,
        )
        print_histogram(
            f"  Inputs (king/man/woman) excluded",
            winners_excl, n_trials,
        )

    print()
    print("=" * 72)
    print("Interpretation:")
    print("- If 'queen' dominates the full-codebook histogram, the naive")
    print("  analogy is robust on this substrate — the argmax choice is")
    print("  stable under perturbation.")
    print("- If 'king' shows up substantially, the naive answer is on a")
    print("  basin boundary: a small random rotation flips which attractor")
    print("  wins. That's the 'fragile' regime, and it motivates the")
    print("  input-exclusion convention that word2vec benchmarks use.")
    print("- The exclusion variant is the conventionally-reported result:")
    print("  it's what's published as 'analogy works', and it's always")
    print("  more sharply queen-dominant than the honest version.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
