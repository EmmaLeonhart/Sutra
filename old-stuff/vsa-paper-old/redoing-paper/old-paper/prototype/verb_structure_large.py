"""Verb Structure Analysis (Large) — predicate effects with 8x8x8 grid.

Scaled-up replication of verb_structure.py using the 8x8x8 grid embeddings.
Analyzes:
  1. Verb displacement consistency across 28 verb pairs (vs original 3)
  2. Verb-conditioned subspace geometry (8 verbs, 64 propositions each)
  3. Interaction effects (S*P and P*O matrices, 8x8 each)

Naturalness analysis is omitted because hand-labeling 512 combinations is
impractical, and the original finding (r=-0.031) showed no signal.

Usage:
    python prototype/verb_structure_large.py
"""

from __future__ import annotations

import io
import json
import os
import sys
from itertools import combinations, product

import numpy as np

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Load existing embeddings from the large grid experiment
data = np.load(
    os.path.join(_project_root, "prototype", "semantic_grid_large_results_embeddings.npz"),
    allow_pickle=True,
)
vecs = data["vecs"]
sentences = list(data["sentences"])
subjects_arr = list(data["subjects"])
predicates_arr = list(data["predicates"])
objects_arr = list(data["objects"])

SUBJECTS = ["cats", "trucks", "children", "eagles", "robots", "farmers", "whales", "soldiers"]
PREDICATES = ["eat", "carry", "watch", "destroy", "collect", "chase", "paint", "hide"]
OBJECTS = ["fish", "rocks", "stars", "flowers", "coins", "books", "bridges", "shadows"]


def get_vec(s: str, p: str, o: str) -> np.ndarray:
    for i in range(len(sentences)):
        if subjects_arr[i] == s and predicates_arr[i] == p and objects_arr[i] == o:
            return vecs[i]
    raise ValueError(f"Not found: {s} {p} {o}")


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def normalize(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-10)


# ==============================================================================
# 1. VERB DISPLACEMENT CONSISTENCY
# ==============================================================================

def analyze_verb_displacements():
    """For each verb pair, compute displacement vectors across all S/O combos
    and check if they are parallel."""

    print("=" * 70)
    print("  1. VERB DISPLACEMENT CONSISTENCY (8x8x8)")
    print("=" * 70)
    print(f"  {len(list(combinations(PREDICATES, 2)))} verb pairs, "
          f"{len(SUBJECTS) * len(OBJECTS)} S/O contexts each\n")

    results = {}

    for p1, p2 in combinations(PREDICATES, 2):
        displacements = []
        labels = []
        for s, o in product(SUBJECTS, OBJECTS):
            v1 = get_vec(s, p1, o)
            v2 = get_vec(s, p2, o)
            delta = v2 - v1
            displacements.append(delta)
            labels.append(f"{s}/{o}")

        # Pairwise cosine of displacement vectors
        n = len(displacements)
        pair_cosines = []
        for i in range(n):
            for j in range(i + 1, n):
                pair_cosines.append(cosine(displacements[i], displacements[j]))

        mean_cos = float(np.mean(pair_cosines))
        std_cos = float(np.std(pair_cosines))

        # Mean displacement direction and alignment
        mean_disp = np.mean(displacements, axis=0)
        mean_mag = float(np.mean([np.linalg.norm(d) for d in displacements]))
        alignment = [cosine(d, mean_disp) for d in displacements]

        # Break down by shared context
        same_subj_cosines = []
        same_obj_cosines = []
        both_cosines = []
        neither_cosines = []
        for i in range(n):
            for j in range(i + 1, n):
                si, oi = labels[i].split("/")
                sj, oj = labels[j].split("/")
                c = cosine(displacements[i], displacements[j])
                if si == sj and oi == oj:
                    both_cosines.append(c)
                elif si == sj:
                    same_subj_cosines.append(c)
                elif oi == oj:
                    same_obj_cosines.append(c)
                else:
                    neither_cosines.append(c)

        print(f"  {p1} -> {p2}:")
        print(f"    Magnitude: {mean_mag:.4f}  "
              f"Mean displacement cosine: {mean_cos:.4f} (+-{std_cos:.3f})  "
              f"Mean alignment: {np.mean(alignment):.4f}")
        print(f"    Same subj:  {np.mean(same_subj_cosines):.4f} (n={len(same_subj_cosines)})  "
              f"Same obj: {np.mean(same_obj_cosines):.4f} (n={len(same_obj_cosines)})  "
              f"Neither: {np.mean(neither_cosines):.4f} (n={len(neither_cosines)})")

        results[f"{p1}->{p2}"] = {
            "mean_displacement_cosine": mean_cos,
            "std": std_cos,
            "mean_alignment": float(np.mean(alignment)),
            "displacement_magnitude": mean_mag,
            "same_subj": float(np.mean(same_subj_cosines)),
            "same_obj": float(np.mean(same_obj_cosines)),
            "neither": float(np.mean(neither_cosines)),
        }

    # Summary statistics across all verb pairs
    all_means = [v["mean_displacement_cosine"] for v in results.values()]
    all_alignments = [v["mean_alignment"] for v in results.values()]
    print(f"\n  SUMMARY across {len(results)} verb pairs:")
    print(f"    Mean displacement cosine: {np.mean(all_means):.4f} (+-{np.std(all_means):.3f})")
    print(f"    Mean alignment: {np.mean(all_alignments):.4f} (+-{np.std(all_alignments):.3f})")

    results["_summary"] = {
        "mean_of_means": float(np.mean(all_means)),
        "std_of_means": float(np.std(all_means)),
        "mean_of_alignments": float(np.mean(all_alignments)),
    }

    return results


# ==============================================================================
# 2. VERB-CONDITIONED SUBSPACE GEOMETRY
# ==============================================================================

def analyze_verb_subspaces():
    """Within each verb, does the S/O landscape stay consistent?"""

    print(f"\n{'=' * 70}")
    print("  2. VERB-CONDITIONED SUBSPACE GEOMETRY (8x8x8)")
    print("=" * 70)
    print(f"  {len(PREDICATES)} verbs, {len(SUBJECTS) * len(OBJECTS)} propositions each\n")

    results = {}
    verb_sims = {}

    for p in PREDICATES:
        indices = []
        labels = []
        for s, o in product(SUBJECTS, OBJECTS):
            idx = next(
                i for i in range(len(sentences))
                if subjects_arr[i] == s and predicates_arr[i] == p and objects_arr[i] == o
            )
            indices.append(idx)
            labels.append(f"{s}/{o}")

        sub_vecs = vecs[indices]
        norms = np.linalg.norm(sub_vecs, axis=1, keepdims=True) + 1e-10
        normed = sub_vecs / norms
        sim = normed @ normed.T
        verb_sims[p] = (sim, labels)

    # Compare similarity matrices across all verb pairs
    n_so = len(SUBJECTS) * len(OBJECTS)
    triu = np.triu_indices(n_so, k=1)

    print("  Pearson correlation of similarity matrices across verbs:")
    print(f"  {'':>10s}", end="")
    for p in PREDICATES:
        print(f"  {p:>8s}", end="")
    print()

    corr_matrix = np.zeros((len(PREDICATES), len(PREDICATES)))
    for i, p1 in enumerate(PREDICATES):
        print(f"  {p1:>10s}", end="")
        for j, p2 in enumerate(PREDICATES):
            if i == j:
                corr_matrix[i, j] = 1.0
                print(f"      -- ", end="")
            else:
                flat1 = verb_sims[p1][0][triu]
                flat2 = verb_sims[p2][0][triu]
                corr = float(np.corrcoef(flat1, flat2)[0, 1])
                corr_matrix[i, j] = corr
                print(f"   {corr:.3f}", end="")
                if i < j:
                    results[f"{p1}_vs_{p2}"] = {"pearson": corr}
        print()

    # Summary
    upper = corr_matrix[np.triu_indices(len(PREDICATES), k=1)]
    print(f"\n  Mean cross-verb subspace correlation: {np.mean(upper):.4f} "
          f"(+-{np.std(upper):.3f})")
    print(f"  Range: [{np.min(upper):.3f}, {np.max(upper):.3f}]")

    results["_summary"] = {
        "mean_correlation": float(np.mean(upper)),
        "std_correlation": float(np.std(upper)),
        "min": float(np.min(upper)),
        "max": float(np.max(upper)),
    }

    return results


# ==============================================================================
# 3. INTERACTION EFFECTS: S*P and P*O
# ==============================================================================

def analyze_interactions():
    """Does verb X pull harder with subject Y than subject Z?"""

    print(f"\n{'=' * 70}")
    print("  3. INTERACTION EFFECTS (8x8x8)")
    print("=" * 70)

    results = {}

    # S*P interaction
    print("\n  Subject x Predicate internal coherence (mean sim within S,P group):")
    print(f"  {'':>12s}", end="")
    for p in PREDICATES:
        print(f"  {p:>8s}", end="")
    print("  |   mean")

    sp_values = []
    for s in SUBJECTS:
        print(f"  {s:>12s}", end="")
        row_vals = []
        for p in PREDICATES:
            group_vecs = [get_vec(s, p, o) for o in OBJECTS]
            sims = []
            for a in range(len(group_vecs)):
                for b in range(a + 1, len(group_vecs)):
                    sims.append(cosine(group_vecs[a], group_vecs[b]))
            mean_sim = float(np.mean(sims))
            row_vals.append(mean_sim)
            print(f"    {mean_sim:.3f}", end="")
            results[f"SP:{s}x{p}"] = mean_sim
            sp_values.append(mean_sim)
        print(f"  | {np.mean(row_vals):.3f}")

    print(f"  {'mean':>12s}", end="")
    for p in PREDICATES:
        col = [results[f"SP:{s}x{p}"] for s in SUBJECTS]
        print(f"    {np.mean(col):.3f}", end="")
    print()

    # P*O interaction
    print(f"\n  Predicate x Object internal coherence:")
    print(f"  {'':>12s}", end="")
    for o in OBJECTS:
        print(f"  {o:>8s}", end="")
    print("  |   mean")

    po_values = []
    for p in PREDICATES:
        print(f"  {p:>12s}", end="")
        row_vals = []
        for o in OBJECTS:
            group_vecs = [get_vec(s, p, o) for s in SUBJECTS]
            sims = []
            for a in range(len(group_vecs)):
                for b in range(a + 1, len(group_vecs)):
                    sims.append(cosine(group_vecs[a], group_vecs[b]))
            mean_sim = float(np.mean(sims))
            row_vals.append(mean_sim)
            print(f"    {mean_sim:.3f}", end="")
            results[f"PO:{p}x{o}"] = mean_sim
            po_values.append(mean_sim)
        print(f"  | {np.mean(row_vals):.3f}")

    print(f"\n  S*P interaction range: [{min(sp_values):.3f}, {max(sp_values):.3f}] "
          f"std={np.std(sp_values):.3f}")
    print(f"  P*O interaction range: [{min(po_values):.3f}, {max(po_values):.3f}] "
          f"std={np.std(po_values):.3f}")

    results["_sp_summary"] = {
        "mean": float(np.mean(sp_values)),
        "std": float(np.std(sp_values)),
        "range": [float(min(sp_values)), float(max(sp_values))],
    }
    results["_po_summary"] = {
        "mean": float(np.mean(po_values)),
        "std": float(np.std(po_values)),
        "range": [float(min(po_values)), float(max(po_values))],
    }

    return results


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    results = {}
    results["displacement"] = analyze_verb_displacements()
    results["subspace"] = analyze_verb_subspaces()
    results["interactions"] = analyze_interactions()

    save_path = os.path.join(_project_root, "prototype", "verb_structure_large_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nResults saved to: {save_path}")


if __name__ == "__main__":
    main()
