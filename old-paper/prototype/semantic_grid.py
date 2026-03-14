"""Semantic Grid — isolate subject/predicate/object contributions to embedding distance.

Constructs a 3x3x3 grid of 27 propositions by crossing:
  3 subjects  ×  3 predicates  ×  3 objects

All words chosen to be concrete, unambiguous, and maximally distinct from
each other within each role. This lets us measure how much each axis
(subject, predicate, object) moves the embedding vector.

Usage:
    python prototype/semantic_grid.py
    python prototype/semantic_grid.py --save semantic_grid_results.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from itertools import product

import numpy as np

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.pillar2_mapping import embed_texts


# ── Grid definition ───────────────────────────────────────────────────────────

# Chosen for maximum unambiguity and minimum semantic overlap between items
# within each role.  All concrete nouns, clear action verbs.

SUBJECTS  = ["cats", "trucks", "children"]
PREDICATES = ["eat", "carry", "watch"]
OBJECTS   = ["fish", "rocks", "stars"]

# This gives us 27 sentences like:
#   "Cats eat fish", "Cats eat rocks", "Cats eat stars",
#   "Cats carry fish", ..., "Children watch stars"


def make_sentence(s: str, p: str, o: str) -> str:
    return f"{s.capitalize()} {p} {o}"


def build_grid() -> list[tuple[str, str, str, str]]:
    """Return [(sentence, subject, predicate, object), ...] for the full grid."""
    grid = []
    for s, p, o in product(SUBJECTS, PREDICATES, OBJECTS):
        grid.append((make_sentence(s, p, o), s, p, o))
    return grid


# ── Analysis functions ────────────────────────────────────────────────────────

def pairwise_cosine(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    normed = vecs / norms
    return normed @ normed.T


def analyze_axis(
    grid: list[tuple[str, str, str, str]],
    sim_matrix: np.ndarray,
    axis: str,  # "subject", "predicate", or "object"
) -> dict:
    """Compute mean similarity for pairs that share vs differ on the given axis."""
    axis_idx = {"subject": 1, "predicate": 2, "object": 3}[axis]
    n = len(grid)

    same_scores = []
    diff_scores = []

    for i in range(n):
        for j in range(i + 1, n):
            if i == j:
                continue
            if grid[i][axis_idx] == grid[j][axis_idx]:
                same_scores.append(sim_matrix[i, j])
            else:
                diff_scores.append(sim_matrix[i, j])

    return {
        "axis": axis,
        "same_mean": float(np.mean(same_scores)),
        "same_std": float(np.std(same_scores)),
        "same_count": len(same_scores),
        "diff_mean": float(np.mean(diff_scores)),
        "diff_std": float(np.std(diff_scores)),
        "diff_count": len(diff_scores),
        "separation": float(np.mean(same_scores) - np.mean(diff_scores)),
    }


def analyze_joint(
    grid: list[tuple[str, str, str, str]],
    sim_matrix: np.ndarray,
) -> dict:
    """Analyze pairs by how many axes they share (0, 1, 2, or 3)."""
    n = len(grid)
    buckets: dict[int, list[float]] = {0: [], 1: [], 2: [], 3: []}

    for i in range(n):
        for j in range(i + 1, n):
            shared = sum(
                grid[i][k] == grid[j][k] for k in (1, 2, 3)
            )
            buckets[shared].append(float(sim_matrix[i, j]))

    result = {}
    for k in range(4):
        vals = buckets[k]
        if vals:
            result[f"shared_{k}"] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "count": len(vals),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }
    return result


def analyze_specific_values(
    grid: list[tuple[str, str, str, str]],
    sim_matrix: np.ndarray,
) -> dict:
    """Per-value analysis: does 'cats' pull harder than 'trucks'?"""
    results = {}
    for axis_name, axis_idx, values in [
        ("subject", 1, SUBJECTS),
        ("predicate", 2, PREDICATES),
        ("object", 3, OBJECTS),
    ]:
        for val in values:
            # Get all indices where this value appears
            indices = [i for i, g in enumerate(grid) if g[axis_idx] == val]
            # Pairwise sim within this value
            within = []
            for a in range(len(indices)):
                for b in range(a + 1, len(indices)):
                    within.append(float(sim_matrix[indices[a], indices[b]]))

            # Sim of this value's sentences to all OTHER sentences
            other_indices = [i for i in range(len(grid)) if i not in indices]
            across = []
            for a in indices:
                for b in other_indices:
                    across.append(float(sim_matrix[a, b]))

            results[f"{axis_name}:{val}"] = {
                "within_mean": float(np.mean(within)) if within else 0,
                "within_std": float(np.std(within)) if within else 0,
                "across_mean": float(np.mean(across)) if across else 0,
                "across_std": float(np.std(across)) if across else 0,
                "pull_strength": float(np.mean(within) - np.mean(across)) if within else 0,
            }

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Semantic grid embedding analysis")
    parser.add_argument("--save", type=str, default="prototype/semantic_grid_results.json")
    args = parser.parse_args()

    grid = build_grid()

    print("=" * 70)
    print("  SEMANTIC GRID: 3×3×3 Subject/Predicate/Object Analysis")
    print("=" * 70)
    print(f"\n  Subjects:   {SUBJECTS}")
    print(f"  Predicates: {PREDICATES}")
    print(f"  Objects:    {OBJECTS}")
    print(f"  Total: {len(grid)} propositions\n")

    # Embed all 27
    sentences = [g[0] for g in grid]
    print("  Embedding 27 propositions...")
    vecs = embed_texts(sentences)
    sim = pairwise_cosine(vecs)

    # ── Full similarity matrix ────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  FULL 27×27 SIMILARITY MATRIX (abbreviated)")
    print("=" * 70)

    # Print a compact version — group by subject
    for s_idx, subj in enumerate(SUBJECTS):
        subj_rows = [(i, g) for i, g in enumerate(grid) if g[1] == subj]
        print(f"\n  --- {subj.upper()} ---")
        for i, (idx, g) in enumerate(subj_rows):
            label = f"{g[2]:>6s} {g[3]:<6s}"
            # Show similarity to all same-subject sentences
            sims_str = "  ".join(
                f"{sim[idx, other_idx]:.2f}"
                for other_idx, _ in subj_rows
            )
            print(f"    {label} | {sims_str}")

    # ── Axis analysis ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  AXIS CONTRIBUTION ANALYSIS")
    print("=" * 70)
    print("  How much does sharing a subject/predicate/object affect similarity?\n")

    axis_results = {}
    for axis in ["subject", "predicate", "object"]:
        r = analyze_axis(grid, sim, axis)
        axis_results[axis] = r
        print(f"  {axis.upper():>10s}:  same={r['same_mean']:.4f} (±{r['same_std']:.3f})  "
              f"diff={r['diff_mean']:.4f} (±{r['diff_std']:.3f})  "
              f"separation={r['separation']:+.4f}")

    # Rank axes by separation
    ranked = sorted(axis_results.items(), key=lambda x: x[1]["separation"], reverse=True)
    print(f"\n  Axis ranking by pull strength:")
    for i, (axis, r) in enumerate(ranked, 1):
        print(f"    {i}. {axis}: {r['separation']:+.4f}")

    # ── Joint analysis ────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  JOINT ANALYSIS: Similarity by number of shared axes")
    print("=" * 70)

    joint = analyze_joint(grid, sim)
    for k in range(4):
        key = f"shared_{k}"
        if key in joint:
            j = joint[key]
            print(f"  {k} axes shared: mean={j['mean']:.4f} (±{j['std']:.3f})  "
                  f"range=[{j['min']:.3f}, {j['max']:.3f}]  n={j['count']}")

    # ── Per-value pull strength ───────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  PER-VALUE PULL STRENGTH")
    print("=" * 70)
    print("  Does 'cats' pull harder than 'trucks'? Does 'eat' pull harder than 'carry'?\n")

    value_results = analyze_specific_values(grid, sim)
    for axis_name in ["subject", "predicate", "object"]:
        print(f"  {axis_name.upper()}:")
        vals = [(k, v) for k, v in value_results.items() if k.startswith(axis_name)]
        vals.sort(key=lambda x: x[1]["pull_strength"], reverse=True)
        for k, v in vals:
            val_name = k.split(":")[1]
            print(f"    {val_name:>10s}: within={v['within_mean']:.4f}  "
                  f"across={v['across_mean']:.4f}  "
                  f"pull={v['pull_strength']:+.4f}")
        print()

    # ── Most/least similar pairs ──────────────────────────────────────────
    print(f"{'=' * 70}")
    print("  EXTREME PAIRS")
    print("=" * 70)

    pairs = []
    n = len(grid)
    for i in range(n):
        for j in range(i + 1, n):
            shared = sum(grid[i][k] == grid[j][k] for k in (1, 2, 3))
            pairs.append((float(sim[i, j]), grid[i][0], grid[j][0], shared))

    pairs.sort(key=lambda x: x[0])

    print("\n  5 LEAST similar pairs:")
    for s, a, b, sh in pairs[:5]:
        print(f"    {s:.3f}  \"{a}\" vs \"{b}\"  (shared: {sh} axes)")

    print("\n  5 MOST similar pairs (excluding identical):")
    for s, a, b, sh in pairs[-5:]:
        print(f"    {s:.3f}  \"{a}\" vs \"{b}\"  (shared: {sh} axes)")

    # ── Save ──────────────────────────────────────────────────────────────
    save_path = os.path.join(_project_root, args.save)
    output = {
        "grid": {
            "subjects": SUBJECTS,
            "predicates": PREDICATES,
            "objects": OBJECTS,
            "sentences": [g[0] for g in grid],
        },
        "axis_analysis": axis_results,
        "joint_analysis": joint,
        "per_value_pull": value_results,
        "similarity_matrix": sim.tolist(),
    }
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {save_path}")

    # Save embeddings
    npz_path = save_path.replace(".json", "_embeddings.npz")
    np.savez(
        npz_path,
        vecs=vecs,
        sentences=np.array([g[0] for g in grid], dtype=object),
        subjects=np.array([g[1] for g in grid], dtype=object),
        predicates=np.array([g[2] for g in grid], dtype=object),
        objects=np.array([g[3] for g in grid], dtype=object),
    )
    print(f"  Embeddings saved to: {npz_path}")


if __name__ == "__main__":
    main()
