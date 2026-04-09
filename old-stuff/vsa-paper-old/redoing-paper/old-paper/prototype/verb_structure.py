"""Verb Structure Analysis — look for consistent predicate effects in embeddings.

The semantic grid showed predicates have weak overall pull (+0.069).
But is that because:
  (a) Verbs genuinely don't move the vector, or
  (b) Verbs move it *consistently* but in a direction orthogonal to the
      subject/object axes, so pairwise similarity doesn't capture it?

This script answers that by analyzing:
  1. Verb displacement vectors — when you swap eat→carry across all S/O pairs,
     are the displacement vectors parallel? (cosine of displacement vectors)
  2. Verb-conditioned clustering — within each verb, do S/O pairs cluster
     differently? Does "eat" reshape the space differently than "watch"?
  3. Naturalness effects — "cats eat fish" is natural, "trucks eat stars" is
     absurd. Does the model encode this via anomalous positioning?
  4. Interaction matrix — does verb X pull harder with subject Y than subject Z?

Usage:
    python prototype/verb_structure.py
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

# Load existing embeddings from the grid experiment
data = np.load(
    os.path.join(_project_root, "prototype", "semantic_grid_results_embeddings.npz"),
    allow_pickle=True,
)
vecs = data["vecs"]
sentences = list(data["sentences"])
subjects_arr = list(data["subjects"])
predicates_arr = list(data["predicates"])
objects_arr = list(data["objects"])

SUBJECTS = ["cats", "trucks", "children"]
PREDICATES = ["eat", "carry", "watch"]
OBJECTS = ["fish", "rocks", "stars"]


def get_vec(s: str, p: str, o: str) -> np.ndarray:
    """Get the embedding vector for a specific (subject, predicate, object) triple."""
    for i in range(len(sentences)):
        if subjects_arr[i] == s and predicates_arr[i] == p and objects_arr[i] == o:
            return vecs[i]
    raise ValueError(f"Not found: {s} {p} {o}")


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def normalize(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-10)


# ══════════════════════════════════════════════════════════════════════════════
# 1. VERB DISPLACEMENT CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_verb_displacements():
    """For each verb pair (e.g. eat→carry), compute the displacement vector
    for every S/O combination. Then check if these displacements are parallel."""

    print("=" * 70)
    print("  1. VERB DISPLACEMENT CONSISTENCY")
    print("=" * 70)
    print("  When you swap verb A→B, does the embedding shift the same way")
    print("  regardless of subject and object?\n")

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
                c = cosine(displacements[i], displacements[j])
                pair_cosines.append(c)

        mean_cos = float(np.mean(pair_cosines))
        std_cos = float(np.std(pair_cosines))
        min_cos = float(np.min(pair_cosines))
        max_cos = float(np.max(pair_cosines))

        # Also compute mean displacement direction and magnitude
        mean_disp = np.mean(displacements, axis=0)
        mean_mag = float(np.mean([np.linalg.norm(d) for d in displacements]))

        # How well does each individual displacement align with the mean?
        alignment = [cosine(d, mean_disp) for d in displacements]

        print(f"  {p1} → {p2}:")
        print(f"    Displacement magnitude: {mean_mag:.4f}")
        print(f"    Pairwise cosine of displacements: "
              f"mean={mean_cos:.4f} std={std_cos:.3f} "
              f"range=[{min_cos:.3f}, {max_cos:.3f}]")
        print(f"    Alignment with mean direction: "
              f"{[f'{a:.3f}' for a in alignment]}")
        print(f"    Mean alignment: {np.mean(alignment):.4f}")

        # Break down by shared subject vs shared object
        same_subj_cosines = []
        same_obj_cosines = []
        diff_both_cosines = []
        for i in range(n):
            for j in range(i + 1, n):
                si, oi = labels[i].split("/")
                sj, oj = labels[j].split("/")
                c = cosine(displacements[i], displacements[j])
                if si == sj:
                    same_subj_cosines.append(c)
                elif oi == oj:
                    same_obj_cosines.append(c)
                else:
                    diff_both_cosines.append(c)

        print(f"    Same subject:  {np.mean(same_subj_cosines):.4f} (n={len(same_subj_cosines)})")
        print(f"    Same object:   {np.mean(same_obj_cosines):.4f} (n={len(same_obj_cosines)})")
        print(f"    Neither:       {np.mean(diff_both_cosines):.4f} (n={len(diff_both_cosines)})")
        print()

        results[f"{p1}→{p2}"] = {
            "mean_displacement_cosine": mean_cos,
            "std": std_cos,
            "mean_alignment": float(np.mean(alignment)),
            "displacement_magnitude": mean_mag,
            "same_subj": float(np.mean(same_subj_cosines)),
            "same_obj": float(np.mean(same_obj_cosines)),
            "neither": float(np.mean(diff_both_cosines)),
        }

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 2. VERB-CONDITIONED SUBSPACE GEOMETRY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_verb_subspaces():
    """Within each verb, what does the S/O landscape look like?
    Does the internal structure change across verbs?"""

    print("=" * 70)
    print("  2. VERB-CONDITIONED SUBSPACE GEOMETRY")
    print("=" * 70)
    print("  Within each verb's 9 propositions, does the relative ordering")
    print("  of S/O pairs stay consistent?\n")

    results = {}

    # For each verb, compute the 9x9 similarity matrix
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

    # Compare the similarity matrices: does the ordering persist?
    print("  Correlation of similarity matrices across verbs:")
    print("  (If verbs don't change relative positioning, this should be ~1.0)\n")

    for p1, p2 in combinations(PREDICATES, 2):
        sim1 = verb_sims[p1][0]
        sim2 = verb_sims[p2][0]
        # Extract upper triangles
        triu = np.triu_indices(9, k=1)
        flat1 = sim1[triu]
        flat2 = sim2[triu]
        corr = float(np.corrcoef(flat1, flat2)[0, 1])
        rank_corr = float(np.corrcoef(
            np.argsort(np.argsort(flat1)),
            np.argsort(np.argsort(flat2))
        )[0, 1])

        print(f"  {p1} vs {p2}: Pearson r={corr:.4f}  Rank r={rank_corr:.4f}")
        results[f"{p1}_vs_{p2}"] = {"pearson": corr, "rank": rank_corr}

    # Print the actual matrices for visual comparison
    for p in PREDICATES:
        sim, labels = verb_sims[p]
        print(f"\n  --- {p.upper()} similarity sub-matrix ---")
        header = "          " + "".join(f"{l:>10s}" for l in labels)
        print(header)
        for i, li in enumerate(labels):
            row = f"  {li:>8s}"
            for j in range(9):
                if i == j:
                    row += "       -- "
                else:
                    row += f"     {sim[i, j]:.3f}"
            print(row)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 3. NATURALNESS / SELECTIONAL PREFERENCE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_naturalness():
    """Some S-P-O combos are natural (cats eat fish), others are absurd
    (trucks eat stars). Does the model encode this as anomalous positioning?"""

    print(f"\n{'=' * 70}")
    print("  3. NATURALNESS / SELECTIONAL PREFERENCE")
    print("=" * 70)
    print("  Some combos are natural (cats eat fish), others absurd (trucks eat stars).")
    print("  Does the embedding 'know' this via distance from verb centroid?\n")

    # Naturalness ratings (hand-labeled, 3=natural, 1=absurd)
    naturalness = {
        ("cats", "eat", "fish"): 3,
        ("cats", "eat", "rocks"): 1,
        ("cats", "eat", "stars"): 1,
        ("cats", "carry", "fish"): 2,
        ("cats", "carry", "rocks"): 1,
        ("cats", "carry", "stars"): 1,
        ("cats", "watch", "fish"): 3,
        ("cats", "watch", "rocks"): 2,
        ("cats", "watch", "stars"): 2,
        ("trucks", "eat", "fish"): 1,
        ("trucks", "eat", "rocks"): 1,
        ("trucks", "eat", "stars"): 1,
        ("trucks", "carry", "fish"): 2,
        ("trucks", "carry", "rocks"): 3,
        ("trucks", "carry", "stars"): 1,
        ("trucks", "watch", "fish"): 1,
        ("trucks", "watch", "rocks"): 1,
        ("trucks", "watch", "stars"): 2,
        ("children", "eat", "fish"): 3,
        ("children", "eat", "rocks"): 1,
        ("children", "eat", "stars"): 1,
        ("children", "carry", "fish"): 2,
        ("children", "carry", "rocks"): 3,
        ("children", "carry", "stars"): 1,
        ("children", "watch", "fish"): 2,
        ("children", "watch", "rocks"): 2,
        ("children", "watch", "stars"): 3,
    }

    # For each verb, compute distance of each proposition from the verb's centroid
    results = {}
    all_nat = []
    all_dist = []

    for p in PREDICATES:
        verb_vecs = []
        verb_labels = []
        verb_nat = []
        for s, o in product(SUBJECTS, OBJECTS):
            v = get_vec(s, p, o)
            verb_vecs.append(v)
            verb_labels.append(f"{s} {p} {o}")
            verb_nat.append(naturalness[(s, p, o)])

        centroid = np.mean(verb_vecs, axis=0)
        dists = [cosine(v, centroid) for v in verb_vecs]

        print(f"  --- {p.upper()} ---")
        pairs = sorted(zip(verb_nat, dists, verb_labels), reverse=True)
        for nat, dist, label in pairs:
            marker = "***" if nat == 3 else "   " if nat == 2 else " . "
            print(f"    {marker} nat={nat}  centroid_sim={dist:.4f}  {label}")

        # Correlation
        corr = float(np.corrcoef(verb_nat, dists)[0, 1])
        print(f"    Naturalness-centroid correlation: r={corr:.4f}")
        results[p] = {"correlation": corr}
        all_nat.extend(verb_nat)
        all_dist.extend(dists)
        print()

    overall_corr = float(np.corrcoef(all_nat, all_dist)[0, 1])
    print(f"  Overall naturalness-centroid correlation: r={overall_corr:.4f}")
    results["overall"] = {"correlation": overall_corr}

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 4. INTERACTION EFFECTS: S×P and P×O
# ══════════════════════════════════════════════════════════════════════════════

def analyze_interactions():
    """Does verb X pull harder with subject Y than subject Z?
    Computed as: mean sim of (s,p,*) pairs minus overall mean."""

    print(f"\n{'=' * 70}")
    print("  4. INTERACTION EFFECTS")
    print("=" * 70)
    print("  Does the verb's effect depend on the subject or object?\n")

    results = {}

    # S×P interaction: for each (subject, predicate) pair, compute
    # mean internal similarity of the 3 sentences sharing that S and P
    print("  Subject × Predicate internal coherence:")
    print(f"  {'':>12s}", end="")
    for p in PREDICATES:
        print(f"  {p:>8s}", end="")
    print()

    for s in SUBJECTS:
        print(f"  {s:>12s}", end="")
        for p in PREDICATES:
            trio_vecs = [get_vec(s, p, o) for o in OBJECTS]
            sims = []
            for a in range(3):
                for b in range(a + 1, 3):
                    sims.append(cosine(trio_vecs[a], trio_vecs[b]))
            mean_sim = float(np.mean(sims))
            print(f"    {mean_sim:.3f}", end="")
            results[f"{s}×{p}"] = mean_sim
        print()

    # P×O interaction
    print(f"\n  Predicate × Object internal coherence:")
    print(f"  {'':>12s}", end="")
    for o in OBJECTS:
        print(f"  {o:>8s}", end="")
    print()

    for p in PREDICATES:
        print(f"  {p:>12s}", end="")
        for o in OBJECTS:
            trio_vecs = [get_vec(s, p, o) for s in SUBJECTS]
            sims = []
            for a in range(3):
                for b in range(a + 1, 3):
                    sims.append(cosine(trio_vecs[a], trio_vecs[b]))
            mean_sim = float(np.mean(sims))
            print(f"    {mean_sim:.3f}", end="")
            results[f"{p}×{o}"] = mean_sim
        print()

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    results = {}
    results["displacement"] = analyze_verb_displacements()
    results["subspace"] = analyze_verb_subspaces()
    results["naturalness"] = analyze_naturalness()
    results["interactions"] = analyze_interactions()

    save_path = os.path.join(_project_root, "prototype", "verb_structure_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nResults saved to: {save_path}")


if __name__ == "__main__":
    main()
