"""Explore embedding geometry for proposition families.

Embeds sets of related propositions and dumps the raw vectors + pairwise
similarity matrices to a .npz file for later analysis.  Also prints a
readable similarity matrix and basic cluster statistics to the console.

Usage:
    python prototype/explore_embeddings.py
    python prototype/explore_embeddings.py --save embeddings.npz
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

import numpy as np

# ── boilerplate ────────────────────────────────────────────────────────────────
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.pillar2_mapping import cosine_similarity, embed_texts

# ── Proposition families ──────────────────────────────────────────────────────

FAMILIES: dict[str, list[str]] = {
    # --- Family 1: "X are cute" with varying specificity of subject ---
    "cute_animals": [
        "Dogs are cute",
        "Hounds are cute",
        "Canines are cute",
        "Wolves are cute",
        "Huskies are cute",
    ],

    # --- Family 2: Classic syllogism ---
    "socrates_syllogism": [
        "All men are mortal",
        "Socrates is a man",
        "Socrates is mortal",
    ],

    # --- Family 3: Syllogism with substituted terms (same structure) ---
    "syllogism_variant": [
        "All birds can fly",
        "A robin is a bird",
        "A robin can fly",
    ],

    # --- Family 4: Causal chain (from our benchmark domain) ---
    "causal_chain": [
        "Altitude increases",
        "Atmospheric pressure decreases",
        "Water boils at a lower temperature",
    ],

    # --- Family 5: Same predicate, different domains ---
    "inhibits_X": [
        "Ketoconazole inhibits CYP2C9",
        "Aspirin inhibits platelet aggregation",
        "Shade inhibits photosynthesis",
        "Regulation inhibits competition",
    ],
}


# ── Analysis ──────────────────────────────────────────────────────────────────

def pairwise_cosine(vecs: np.ndarray) -> np.ndarray:
    """NxN cosine similarity matrix."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    normed = vecs / norms
    return normed @ normed.T


def analyze_family(name: str, sentences: list[str], vecs: np.ndarray) -> dict:
    """Print and return analysis for one family of propositions."""
    sim = pairwise_cosine(vecs)
    n = len(sentences)

    print(f"\n{'=' * 70}")
    print(f"  FAMILY: {name}  ({n} propositions)")
    print("=" * 70)

    # Print sentences with short labels
    for i, s in enumerate(sentences):
        print(f"  [{i}] {s}")

    # Similarity matrix
    print(f"\n  Pairwise cosine similarity:")
    header = "       " + "".join(f"  [{i}]  " for i in range(n))
    print(header)
    for i in range(n):
        row = f"  [{i}]  "
        for j in range(n):
            if i == j:
                row += "   --   "
            else:
                row += f" {sim[i, j]:+.3f} "
        print(row)

    # Stats
    upper = sim[np.triu_indices(n, k=1)]
    mean_sim = float(np.mean(upper))
    min_sim = float(np.min(upper))
    max_sim = float(np.max(upper))
    std_sim = float(np.std(upper))

    print(f"\n  Mean pairwise similarity: {mean_sim:.4f}")
    print(f"  Min: {min_sim:.4f}  Max: {max_sim:.4f}  Std: {std_sim:.4f}")

    # Centroid distance (how tight is the cluster?)
    centroid = vecs.mean(axis=0)
    centroid_dists = [float(cosine_similarity(centroid, vecs[i:i+1])[0]) for i in range(n)]
    print(f"  Centroid similarities: {['%.3f' % d for d in centroid_dists]}")
    print(f"  Cluster tightness (mean dist to centroid): {np.mean(centroid_dists):.4f}")

    return {
        "name": name,
        "sentences": sentences,
        "pairwise_sim": sim.tolist(),
        "mean_sim": mean_sim,
        "min_sim": min_sim,
        "max_sim": max_sim,
        "std_sim": std_sim,
        "centroid_similarities": centroid_dists,
    }


def cross_family_analysis(
    all_vecs: dict[str, np.ndarray],
    all_sentences: dict[str, list[str]],
) -> None:
    """Compare centroids across families."""
    names = list(all_vecs.keys())
    centroids = np.array([all_vecs[n].mean(axis=0) for n in names])
    csim = pairwise_cosine(centroids)

    print(f"\n{'=' * 70}")
    print("  CROSS-FAMILY CENTROID SIMILARITIES")
    print("=" * 70)

    # Short names for display
    short = {n: n[:12] for n in names}
    header = "              " + "".join(f"{short[n]:>14s}" for n in names)
    print(header)
    for i, ni in enumerate(names):
        row = f"  {short[ni]:<12s}"
        for j, nj in enumerate(names):
            if i == j:
                row += "       --     "
            else:
                row += f"       {csim[i, j]:+.3f} "
        print(row)

    # Also: which individual propositions from different families are closest?
    print(f"\n  Closest cross-family pairs:")
    all_flat = []
    for name in names:
        for i, s in enumerate(all_sentences[name]):
            all_flat.append((name, i, s))

    flat_vecs = np.vstack([all_vecs[n] for n in names])
    flat_sim = pairwise_cosine(flat_vecs)

    # Find top cross-family pairs
    pairs = []
    for i in range(len(all_flat)):
        for j in range(i + 1, len(all_flat)):
            if all_flat[i][0] != all_flat[j][0]:  # different families
                pairs.append((flat_sim[i, j], all_flat[i], all_flat[j]))

    pairs.sort(key=lambda x: x[0], reverse=True)
    for sim_val, (fam_a, _, sent_a), (fam_b, _, sent_b) in pairs[:8]:
        print(f"    {sim_val:.3f}  [{fam_a}] \"{sent_a}\"")
        print(f"           [{fam_b}] \"{sent_b}\"")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Explore proposition embeddings")
    parser.add_argument(
        "--save", type=str, default="prototype/embeddings_exploration.npz",
        help="Save embeddings + metadata to .npz file"
    )
    args = parser.parse_args()

    all_vecs: dict[str, np.ndarray] = {}
    all_sentences: dict[str, list[str]] = {}
    all_analyses: list[dict] = []

    print("Embedding proposition families with mxbai-embed-large (1024-dim)...\n")

    for name, sentences in FAMILIES.items():
        print(f"  Embedding {name} ({len(sentences)} propositions)...")
        vecs = embed_texts(sentences)
        all_vecs[name] = vecs
        all_sentences[name] = sentences
        analysis = analyze_family(name, sentences, vecs)
        all_analyses.append(analysis)

    cross_family_analysis(all_vecs, all_sentences)

    # Save everything for later exploration
    save_data = {}
    all_labels = []
    for name in FAMILIES:
        save_data[f"vecs_{name}"] = all_vecs[name]
        for s in FAMILIES[name]:
            all_labels.append(f"{name}|{s}")

    # Also save a flat matrix of all embeddings for easy loading
    save_data["all_vecs"] = np.vstack([all_vecs[n] for n in FAMILIES])
    save_data["all_labels"] = np.array(all_labels, dtype=object)

    save_path = os.path.join(_project_root, args.save)
    np.savez(save_path, **save_data)
    print(f"\nEmbeddings saved to: {save_path}")
    print(f"  Load with: data = np.load('{args.save}', allow_pickle=True)")
    print(f"  Keys: {list(save_data.keys())}")

    # Also save analysis as JSON
    json_path = save_path.replace(".npz", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_analyses, f, indent=2)
    print(f"  Analysis JSON: {json_path}")


if __name__ == "__main__":
    main()
