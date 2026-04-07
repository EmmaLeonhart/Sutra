"""Linnaean Taxonomy Hierarchy Test.

Does using formal taxonomic names (consistently scientific register)
produce monotonic distance decay, unlike the mixed-register hierarchies
tested in Experiment 6?

If non-monotonicity was caused by register mixing (casual "dog" next to
technical "mammal"), then staying in pure Latin taxonomy should fix it.

Usage:
    python prototype/linnaean_hierarchy.py
"""

from __future__ import annotations

import io
import json
import os
import sys

import numpy as np

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.pillar2_mapping import embed_texts


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def pairwise_cosine(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    normed = vecs / norms
    return normed @ normed.T


# ══════════════════════════════════════════════════════════════════════════════
# LINNAEAN HIERARCHIES — formal taxonomic names only
# Each goes from subspecies/species up to domain
# ══════════════════════════════════════════════════════════════════════════════

LINNAEAN = {
    "domestic_dog": [
        "Canis lupus familiaris",  # subspecies
        "Canis lupus",             # species
        "Canis",                   # genus
        "Canidae",                 # family
        "Carnivora",               # order
        "Mammalia",                # class
        "Vertebrata",              # subphylum
        "Chordata",                # phylum
        "Animalia",                # kingdom
        "Eukaryota",               # domain
    ],
    "domestic_cat": [
        "Felis catus",
        "Felis",
        "Felidae",
        "Carnivora",
        "Mammalia",
        "Vertebrata",
        "Chordata",
        "Animalia",
        "Eukaryota",
    ],
    "human": [
        "Homo sapiens",
        "Homo",
        "Hominidae",
        "Primates",
        "Mammalia",
        "Vertebrata",
        "Chordata",
        "Animalia",
        "Eukaryota",
    ],
    "horse": [
        "Equus caballus",
        "Equus",
        "Equidae",
        "Perissodactyla",
        "Mammalia",
        "Vertebrata",
        "Chordata",
        "Animalia",
        "Eukaryota",
    ],
    "brown_trout": [
        "Salmo trutta",
        "Salmo",
        "Salmonidae",
        "Salmoniformes",
        "Actinopterygii",
        "Vertebrata",
        "Chordata",
        "Animalia",
        "Eukaryota",
    ],
    "house_sparrow": [
        "Passer domesticus",
        "Passer",
        "Passeridae",
        "Passeriformes",
        "Aves",
        "Vertebrata",
        "Chordata",
        "Animalia",
        "Eukaryota",
    ],
    "fruit_fly": [
        "Drosophila melanogaster",
        "Drosophila",
        "Drosophilidae",
        "Diptera",
        "Insecta",
        "Arthropoda",
        "Animalia",
        "Eukaryota",
    ],
    "e_coli": [
        "Escherichia coli",
        "Escherichia",
        "Enterobacteriaceae",
        "Enterobacterales",
        "Gammaproteobacteria",
        "Proteobacteria",
        "Bacteria",
    ],
    "oak_tree": [
        "Quercus robur",
        "Quercus",
        "Fagaceae",
        "Fagales",
        "Magnoliopsida",
        "Plantae",
        "Eukaryota",
    ],
    "bread_yeast": [
        "Saccharomyces cerevisiae",
        "Saccharomyces",
        "Saccharomycetaceae",
        "Saccharomycetales",
        "Fungi",
        "Eukaryota",
    ],
}

# For comparison: the same organisms using common English names
COMMON_NAMES = {
    "domestic_dog": [
        "puppy", "dog", "canine", "carnivore", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "domestic_cat": [
        "kitten", "cat", "feline", "carnivore", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "human": [
        "baby", "human", "great ape", "primate", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "horse": [
        "foal", "horse", "equine", "odd-toed ungulate", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "brown_trout": [
        "trout", "salmon", "ray-finned fish", "fish",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "house_sparrow": [
        "sparrow", "songbird", "bird",
        "vertebrate", "animal", "organism", "living thing",
    ],
}


def analyze_hierarchy(name, chain, word_to_vec):
    """Analyze monotonicity and decay for one hierarchy."""
    origin_vec = word_to_vec[chain[0]]
    sims = [cosine(origin_vec, word_to_vec[w]) for w in chain]
    positions = [i / (len(chain) - 1) for i in range(len(chain))] if len(chain) > 1 else [0.5]

    monotonic = all(sims[i] >= sims[i + 1] for i in range(len(sims) - 1))
    violations = []
    for i in range(len(sims) - 1):
        if sims[i] < sims[i + 1]:
            violations.append((i, chain[i], chain[i + 1],
                               sims[i], sims[i + 1], sims[i + 1] - sims[i]))

    # Adjacent similarities
    adjacent = []
    for i in range(len(chain) - 1):
        adjacent.append(cosine(word_to_vec[chain[i]], word_to_vec[chain[i + 1]]))

    return {
        "chain": chain,
        "sims_from_origin": sims,
        "positions": positions,
        "adjacent_sims": adjacent,
        "monotonic": monotonic,
        "violation_count": len(violations),
        "violations": violations,
    }


def main():
    results = {}

    # ══════════════════════════════════════════════════════════════════════
    # PART 1: EMBED ALL LINNAEAN NAMES
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 70)
    print("  PART 1: LINNAEAN TAXONOMY HIERARCHIES")
    print("=" * 70)

    all_words = sorted(set(w for chain in LINNAEAN.values() for w in chain))
    print(f"\n  {len(LINNAEAN)} hierarchies, {len(all_words)} unique Linnaean terms")
    print(f"  Embedding...")
    vecs = embed_texts(all_words)
    word_to_vec = {w: vecs[i] for i, w in enumerate(all_words)}

    linnaean_results = {}
    for name, chain in LINNAEAN.items():
        data = analyze_hierarchy(name, chain, word_to_vec)
        linnaean_results[name] = data

        status = "MONOTONIC" if data["monotonic"] else f"{data['violation_count']} violation(s)"
        print(f"\n  {name}: {status}")
        for i, w in enumerate(chain):
            marker = ""
            if i > 0 and data["sims_from_origin"][i] > data["sims_from_origin"][i - 1]:
                marker = " ←!"
            adj = f"  (adj: {data['adjacent_sims'][i-1]:.3f})" if i > 0 else ""
            print(f"    [{data['positions'][i]:.2f}] {w:<30s} sim={data['sims_from_origin'][i]:.4f}{marker}{adj}")

        if data["violations"]:
            for v in data["violations"]:
                print(f"    VIOLATION: {v[1]} ({v[3]:.4f}) < {v[2]} ({v[4]:.4f}), "
                      f"bounce +{v[5]:.4f}")

    results["linnaean"] = {k: {kk: vv for kk, vv in v.items() if kk != "violations"}
                           for k, v in linnaean_results.items()}

    # Summary
    mono_count = sum(1 for d in linnaean_results.values() if d["monotonic"])
    total_violations = sum(d["violation_count"] for d in linnaean_results.values())
    print(f"\n  LINNAEAN SUMMARY: {mono_count}/{len(LINNAEAN)} monotonic, "
          f"{total_violations} total violations")

    # ══════════════════════════════════════════════════════════════════════
    # PART 2: COMMON NAMES FOR COMPARISON
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("  PART 2: COMMON ENGLISH NAMES (SAME ORGANISMS)")
    print("=" * 70)

    common_words = sorted(set(w for chain in COMMON_NAMES.values() for w in chain))
    print(f"\n  {len(COMMON_NAMES)} hierarchies, {len(common_words)} unique common terms")
    print(f"  Embedding...")
    cvecs = embed_texts(common_words)
    common_to_vec = {w: cvecs[i] for i, w in enumerate(common_words)}

    common_results = {}
    for name, chain in COMMON_NAMES.items():
        data = analyze_hierarchy(name, chain, common_to_vec)
        common_results[name] = data

        status = "MONOTONIC" if data["monotonic"] else f"{data['violation_count']} violation(s)"
        print(f"\n  {name}: {status}")
        for i, w in enumerate(chain):
            marker = ""
            if i > 0 and data["sims_from_origin"][i] > data["sims_from_origin"][i - 1]:
                marker = " ←!"
            adj = f"  (adj: {data['adjacent_sims'][i-1]:.3f})" if i > 0 else ""
            print(f"    [{data['positions'][i]:.2f}] {w:<25s} sim={data['sims_from_origin'][i]:.4f}{marker}{adj}")

    common_mono = sum(1 for d in common_results.values() if d["monotonic"])
    common_violations = sum(d["violation_count"] for d in common_results.values())
    print(f"\n  COMMON NAMES SUMMARY: {common_mono}/{len(COMMON_NAMES)} monotonic, "
          f"{common_violations} total violations")

    results["common_names"] = {k: {kk: vv for kk, vv in v.items() if kk != "violations"}
                                for k, v in common_results.items()}

    # ══════════════════════════════════════════════════════════════════════
    # PART 3: CROSS-HIERARCHY CONVERGENCE IN LINNAEAN
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("  PART 3: CROSS-HIERARCHY CONVERGENCE (LINNAEAN)")
    print("=" * 70)
    print("  Do Canis and Felis converge as they ascend through shared ranks?\n")

    # Track similarity between pairs at shared taxonomic levels
    pairs = [
        ("domestic_dog", "domestic_cat", "Both carnivorans"),
        ("domestic_dog", "human", "Both mammals"),
        ("domestic_dog", "brown_trout", "Both vertebrates"),
        ("domestic_dog", "fruit_fly", "Both animals"),
        ("domestic_dog", "oak_tree", "Both eukaryotes"),
        ("domestic_dog", "e_coli", "Different domains"),
        ("domestic_cat", "horse", "Both mammals"),
        ("human", "house_sparrow", "Both vertebrates"),
    ]

    convergence_data = {}
    for name_a, name_b, desc in pairs:
        chain_a = LINNAEAN[name_a]
        chain_b = LINNAEAN[name_b]

        print(f"\n  --- {name_a} vs {name_b} ({desc}) ---")

        # Find shared terms
        shared = set(chain_a) & set(chain_b)

        # Pairwise at each level
        print(f"    {'Level A':<30s} {'Level B':<30s} {'Cosine':>8s} {'Shared?':>8s}")
        print(f"    {'-' * 78}")

        level_sims = []
        for i, wa in enumerate(chain_a):
            best_match = None
            best_sim = -1
            for j, wb in enumerate(chain_b):
                sim = cosine(word_to_vec[wa], word_to_vec.get(wb, common_to_vec.get(wb, np.zeros(1024))))
                if wa == wb:
                    best_match = (wb, sim, True)
                    break
                if sim > best_sim:
                    best_sim = sim
                    best_match = (wb, sim, False)

            if best_match:
                wb, sim, is_shared = best_match
                if is_shared or sim > 0.5:
                    marker = "YES" if is_shared else ""
                    print(f"    {wa:<30s} {wb:<30s} {sim:>8.3f} {marker:>8s}")
                    level_sims.append({"a": wa, "b": wb, "sim": sim, "shared": is_shared})

        # Show convergence trajectory: sim between the two chains at each rank
        # Align by shared terms from the top
        shared_ordered = [w for w in chain_a if w in shared]
        if shared_ordered:
            print(f"\n    Convergence at shared ranks:")
            for sw in shared_ordered:
                idx_a = chain_a.index(sw)
                idx_b = chain_b.index(sw)
                # Similarity between the two chains at the rank just BELOW the shared level
                if idx_a > 0 and idx_b > 0:
                    below_a = chain_a[idx_a - 1]
                    below_b = chain_b[idx_b - 1]
                    sim_below = cosine(word_to_vec[below_a], word_to_vec[below_b])
                    print(f"      Below {sw}: {below_a} ↔ {below_b} = {sim_below:.4f}")

        convergence_data[f"{name_a}_vs_{name_b}"] = level_sims

    results["convergence"] = convergence_data

    # ══════════════════════════════════════════════════════════════════════
    # PART 4: DISPLACEMENT DIRECTION IN LINNAEAN
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("  PART 4: DISPLACEMENT DIRECTION CONSISTENCY (LINNAEAN)")
    print("=" * 70)

    displacement_data = {}
    for name, chain in LINNAEAN.items():
        chain_vecs = [word_to_vec[w] for w in chain]
        displacements = []
        for i in range(len(chain) - 1):
            d = chain_vecs[i + 1] - chain_vecs[i]
            norm = np.linalg.norm(d)
            if norm > 1e-10:
                displacements.append(d / norm)

        if displacements:
            raw_mean = np.mean(displacements, axis=0)
            mean_norm = np.linalg.norm(raw_mean)
            mean_dir = raw_mean / (mean_norm + 1e-10)

            alignments = [cosine(d, mean_dir) for d in displacements]
            pairwise = []
            for i in range(len(displacements)):
                for j in range(i + 1, len(displacements)):
                    pairwise.append(cosine(displacements[i], displacements[j]))

            step_labels = [f"{chain[i]}→{chain[i+1]}" for i in range(len(chain) - 1)]
            print(f"\n  {name}:")
            for k, label in enumerate(step_labels):
                print(f"    {label:<45s}  align: {alignments[k]:+.4f}")
            print(f"    Mean alignment: {np.mean(alignments):.4f}")
            print(f"    Pairwise consistency: {np.mean(pairwise):.4f}")

            displacement_data[name] = {
                "mean_alignment": float(np.mean(alignments)),
                "pairwise_consistency": float(np.mean(pairwise)),
                "alignments": [float(a) for a in alignments],
                "mean_direction": mean_dir.tolist(),
            }

    # Cross-hierarchy "up" direction comparison (Linnaean only)
    names_with_dirs = list(displacement_data.keys())
    if len(names_with_dirs) > 1:
        dir_vecs = np.array([displacement_data[n]["mean_direction"] for n in names_with_dirs])
        cross = pairwise_cosine(dir_vecs)
        upper = cross[np.triu_indices(len(names_with_dirs), k=1)]
        print(f"\n  Cross-hierarchy 'up' direction (Linnaean):")
        print(f"    Mean: {np.mean(upper):.4f}  range [{np.min(upper):.3f}, {np.max(upper):.3f}]")

        # Compare eukaryote hierarchies vs bacteria
        euk_names = [n for n in names_with_dirs if n != "e_coli"]
        if len(euk_names) > 1:
            euk_indices = [names_with_dirs.index(n) for n in euk_names]
            euk_pairs = [cross[i, j] for i in euk_indices for j in euk_indices if i < j]
            print(f"    Eukaryotes only: {np.mean(euk_pairs):.4f}")

    results["linnaean_displacement"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "mean_direction"}
        for k, v in displacement_data.items()
    }

    # ══════════════════════════════════════════════════════════════════════
    # PART 5: HEAD-TO-HEAD COMPARISON
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("  PART 5: HEAD-TO-HEAD — LINNAEAN vs COMMON NAMES")
    print("=" * 70)

    shared_organisms = set(LINNAEAN.keys()) & set(COMMON_NAMES.keys())
    print(f"\n  {'Organism':<20s} {'Linnaean':>12s} {'Common':>12s} {'Register':>10s}")
    print(f"  {'-' * 56}")
    for org in sorted(shared_organisms):
        l_mono = "MONO" if linnaean_results[org]["monotonic"] else f"{linnaean_results[org]['violation_count']} viol"
        c_mono = "MONO" if common_results[org]["monotonic"] else f"{common_results[org]['violation_count']} viol"

        # Endpoint similarity (how far does it decay?)
        l_endpoint = linnaean_results[org]["sims_from_origin"][-1]
        c_endpoint = common_results[org]["sims_from_origin"][-1]

        print(f"  {org:<20s} {l_mono:>12s} {c_mono:>12s}    L={l_endpoint:.3f} C={c_endpoint:.3f}")

    l_total_mono = sum(1 for d in linnaean_results.values() if d["monotonic"])
    c_total_mono = sum(1 for d in common_results.values() if d["monotonic"])
    l_total_viol = sum(d["violation_count"] for d in linnaean_results.values())
    c_total_viol = sum(d["violation_count"] for d in common_results.values())

    print(f"\n  TOTALS:")
    print(f"    Linnaean: {l_total_mono}/{len(LINNAEAN)} monotonic, {l_total_viol} violations")
    print(f"    Common:   {c_total_mono}/{len(COMMON_NAMES)} monotonic, {c_total_viol} violations")

    results["head_to_head"] = {
        "linnaean_monotonic": l_total_mono,
        "linnaean_total": len(LINNAEAN),
        "linnaean_violations": l_total_viol,
        "common_monotonic": c_total_mono,
        "common_total": len(COMMON_NAMES),
        "common_violations": c_total_viol,
    }

    # Save everything
    save_path = os.path.join(_project_root, "prototype", "linnaean_hierarchy_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {save_path}")

    # Save embeddings
    all_embedded = sorted(set(all_words + common_words))
    all_vecs_combined = embed_texts(all_embedded)
    emb_path = os.path.join(_project_root, "prototype", "linnaean_hierarchy_embeddings.npz")
    np.savez(emb_path, words=all_embedded, vecs=all_vecs_combined)
    print(f"Embeddings saved to: {emb_path}")


if __name__ == "__main__":
    main()
