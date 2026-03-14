"""Linnaean Taxonomy Hierarchy Test (Large).

Scaled-up replication of linnaean_hierarchy.py with:
  - 20 Linnaean hierarchies (vs 10) spanning all major domains
  - 15 common-name hierarchies (vs 6)

Usage:
    python prototype/linnaean_hierarchy_large.py
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


# ==============================================================================
# LINNAEAN HIERARCHIES (20 organisms)
# ==============================================================================

LINNAEAN = {
    # Original 10
    "domestic_dog": [
        "Canis lupus familiaris", "Canis lupus", "Canis", "Canidae",
        "Carnivora", "Mammalia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "domestic_cat": [
        "Felis catus", "Felis", "Felidae", "Carnivora", "Mammalia",
        "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "human": [
        "Homo sapiens", "Homo", "Hominidae", "Primates", "Mammalia",
        "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "horse": [
        "Equus caballus", "Equus", "Equidae", "Perissodactyla", "Mammalia",
        "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "brown_trout": [
        "Salmo trutta", "Salmo", "Salmonidae", "Salmoniformes",
        "Actinopterygii", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "house_sparrow": [
        "Passer domesticus", "Passer", "Passeridae", "Passeriformes",
        "Aves", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "fruit_fly": [
        "Drosophila melanogaster", "Drosophila", "Drosophilidae", "Diptera",
        "Insecta", "Arthropoda", "Animalia", "Eukaryota",
    ],
    "e_coli": [
        "Escherichia coli", "Escherichia", "Enterobacteriaceae",
        "Enterobacterales", "Gammaproteobacteria", "Proteobacteria", "Bacteria",
    ],
    "oak_tree": [
        "Quercus robur", "Quercus", "Fagaceae", "Fagales",
        "Magnoliopsida", "Plantae", "Eukaryota",
    ],
    "bread_yeast": [
        "Saccharomyces cerevisiae", "Saccharomyces", "Saccharomycetaceae",
        "Saccharomycetales", "Fungi", "Eukaryota",
    ],
    # New 10
    "african_elephant": [
        "Loxodonta africana", "Loxodonta", "Elephantidae", "Proboscidea",
        "Mammalia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "bottlenose_dolphin": [
        "Tursiops truncatus", "Tursiops", "Delphinidae", "Cetacea",
        "Mammalia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "bald_eagle": [
        "Haliaeetus leucocephalus", "Haliaeetus", "Accipitridae", "Accipitriformes",
        "Aves", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "king_cobra": [
        "Ophiophagus hannah", "Ophiophagus", "Elapidae", "Squamata",
        "Reptilia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "blue_whale": [
        "Balaenoptera musculus", "Balaenoptera", "Balaenopteridae", "Cetacea",
        "Mammalia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "honey_bee": [
        "Apis mellifera", "Apis", "Apidae", "Hymenoptera",
        "Insecta", "Arthropoda", "Animalia", "Eukaryota",
    ],
    "common_wheat": [
        "Triticum aestivum", "Triticum", "Poaceae", "Poales",
        "Magnoliopsida", "Plantae", "Eukaryota",
    ],
    "rose": [
        "Rosa gallica", "Rosa", "Rosaceae", "Rosales",
        "Magnoliopsida", "Plantae", "Eukaryota",
    ],
    "giant_panda": [
        "Ailuropoda melanoleuca", "Ailuropoda", "Ursidae", "Carnivora",
        "Mammalia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
    "nile_crocodile": [
        "Crocodylus niloticus", "Crocodylus", "Crocodylidae", "Crocodilia",
        "Reptilia", "Vertebrata", "Chordata", "Animalia", "Eukaryota",
    ],
}

# Common English names (15 organisms)
COMMON_NAMES = {
    # Original 6
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
    # New 9
    "african_elephant": [
        "calf", "elephant", "pachyderm", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "bottlenose_dolphin": [
        "calf", "dolphin", "whale", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "bald_eagle": [
        "eaglet", "eagle", "raptor", "bird",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "king_cobra": [
        "hatchling", "cobra", "snake", "reptile",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "blue_whale": [
        "calf", "whale", "cetacean", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "honey_bee": [
        "larva", "bee", "insect", "arthropod",
        "invertebrate", "animal", "organism", "living thing",
    ],
    "giant_panda": [
        "cub", "panda", "bear", "carnivore", "mammal",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "nile_crocodile": [
        "hatchling", "crocodile", "reptile",
        "vertebrate", "animal", "organism", "living thing",
    ],
    "oak_tree": [
        "acorn", "oak", "tree", "plant", "organism", "living thing",
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

    # ==================================================================
    # PART 1: LINNAEAN HIERARCHIES
    # ==================================================================
    print("=" * 70)
    print("  PART 1: LINNAEAN TAXONOMY HIERARCHIES (20 organisms)")
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

        status = "MONO" if data["monotonic"] else f"{data['violation_count']}v"
        print(f"  {name:<25s}: {status:>5s}  "
              f"origin={data['sims_from_origin'][0]:.3f}->{data['sims_from_origin'][-1]:.3f}")

    results["linnaean"] = {k: {kk: vv for kk, vv in v.items() if kk != "violations"}
                           for k, v in linnaean_results.items()}

    mono_count = sum(1 for d in linnaean_results.values() if d["monotonic"])
    total_violations = sum(d["violation_count"] for d in linnaean_results.values())
    print(f"\n  LINNAEAN SUMMARY: {mono_count}/{len(LINNAEAN)} monotonic, "
          f"{total_violations} total violations")

    # ==================================================================
    # PART 2: COMMON NAMES
    # ==================================================================
    print(f"\n{'=' * 70}")
    print("  PART 2: COMMON ENGLISH NAMES (15 organisms)")
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

        status = "MONO" if data["monotonic"] else f"{data['violation_count']}v"
        print(f"  {name:<25s}: {status:>5s}  "
              f"origin={data['sims_from_origin'][0]:.3f}->{data['sims_from_origin'][-1]:.3f}")

    common_mono = sum(1 for d in common_results.values() if d["monotonic"])
    common_violations = sum(d["violation_count"] for d in common_results.values())
    print(f"\n  COMMON NAMES SUMMARY: {common_mono}/{len(COMMON_NAMES)} monotonic, "
          f"{common_violations} total violations")

    results["common_names"] = {k: {kk: vv for kk, vv in v.items() if kk != "violations"}
                                for k, v in common_results.items()}

    # ==================================================================
    # PART 3: CROSS-HIERARCHY CONVERGENCE
    # ==================================================================
    print(f"\n{'=' * 70}")
    print("  PART 3: CROSS-HIERARCHY CONVERGENCE")
    print("=" * 70)

    pairs = [
        ("domestic_dog", "domestic_cat", "Both carnivorans"),
        ("domestic_dog", "human", "Both mammals"),
        ("domestic_dog", "brown_trout", "Both vertebrates"),
        ("domestic_dog", "fruit_fly", "Both animals"),
        ("domestic_dog", "oak_tree", "Both eukaryotes"),
        ("domestic_dog", "e_coli", "Different domains"),
        ("domestic_cat", "horse", "Both mammals"),
        ("human", "house_sparrow", "Both vertebrates"),
        ("african_elephant", "bottlenose_dolphin", "Both placental mammals"),
        ("bald_eagle", "house_sparrow", "Both birds"),
        ("king_cobra", "nile_crocodile", "Both reptiles"),
        ("blue_whale", "bottlenose_dolphin", "Both cetaceans"),
        ("honey_bee", "fruit_fly", "Both insects"),
        ("oak_tree", "common_wheat", "Both angiosperms"),
        ("rose", "common_wheat", "Both angiosperms"),
        ("giant_panda", "domestic_dog", "Both carnivorans"),
    ]

    convergence_data = {}
    for name_a, name_b, desc in pairs:
        chain_a = LINNAEAN[name_a]
        chain_b = LINNAEAN[name_b]
        shared = set(chain_a) & set(chain_b)

        # Similarity at species level (most specific)
        base_sim = cosine(word_to_vec[chain_a[0]], word_to_vec[chain_b[0]])

        # Top level
        top_sim = cosine(word_to_vec[chain_a[-1]], word_to_vec[chain_b[-1]])

        print(f"  {name_a:<22s} vs {name_b:<22s} ({desc})")
        print(f"    Species sim: {base_sim:.4f}  Top sim: {top_sim:.4f}  "
              f"Shared ranks: {len(shared)}")

        convergence_data[f"{name_a}_vs_{name_b}"] = {
            "base_sim": float(base_sim),
            "top_sim": float(top_sim),
            "shared_count": len(shared),
            "shared_ranks": list(shared),
        }

    results["convergence"] = convergence_data

    # ==================================================================
    # PART 4: DISPLACEMENT DIRECTION
    # ==================================================================
    print(f"\n{'=' * 70}")
    print("  PART 4: DISPLACEMENT DIRECTION CONSISTENCY")
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

            print(f"  {name:<25s}: mean_align={np.mean(alignments):.3f}  "
                  f"pairwise={np.mean(pairwise):.3f}")

            displacement_data[name] = {
                "mean_alignment": float(np.mean(alignments)),
                "pairwise_consistency": float(np.mean(pairwise)),
                "mean_direction": mean_dir.tolist(),
            }

    # Cross-hierarchy "up" direction
    names_with_dirs = list(displacement_data.keys())
    if len(names_with_dirs) > 1:
        dir_vecs = np.array([displacement_data[n]["mean_direction"] for n in names_with_dirs])
        cross = pairwise_cosine(dir_vecs)
        upper = cross[np.triu_indices(len(names_with_dirs), k=1)]
        print(f"\n  Cross-hierarchy 'up' direction (all {len(names_with_dirs)} Linnaean):")
        print(f"    Mean: {np.mean(upper):.4f} (+-{np.std(upper):.3f})  "
              f"range [{np.min(upper):.3f}, {np.max(upper):.3f}]")

        euk_names = [n for n in names_with_dirs if n != "e_coli"]
        if len(euk_names) > 1:
            euk_indices = [names_with_dirs.index(n) for n in euk_names]
            euk_pairs = [cross[i, j] for i in euk_indices for j in euk_indices if i < j]
            print(f"    Eukaryotes only ({len(euk_names)}): {np.mean(euk_pairs):.4f}")

    results["linnaean_displacement"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "mean_direction"}
        for k, v in displacement_data.items()
    }

    # ==================================================================
    # PART 5: HEAD-TO-HEAD
    # ==================================================================
    print(f"\n{'=' * 70}")
    print("  PART 5: HEAD-TO-HEAD -- LINNAEAN vs COMMON NAMES")
    print("=" * 70)

    shared_organisms = set(LINNAEAN.keys()) & set(COMMON_NAMES.keys())
    print(f"\n  {'Organism':<25s} {'Linnaean':>12s} {'Common':>12s}")
    print(f"  {'-' * 50}")
    for org in sorted(shared_organisms):
        l_status = "MONO" if linnaean_results[org]["monotonic"] else f"{linnaean_results[org]['violation_count']} viol"
        c_status = "MONO" if common_results[org]["monotonic"] else f"{common_results[org]['violation_count']} viol"
        print(f"  {org:<25s} {l_status:>12s} {c_status:>12s}")

    l_total_mono = sum(1 for d in linnaean_results.values() if d["monotonic"])
    c_total_mono = sum(1 for d in common_results.values() if d["monotonic"])
    l_total_viol = sum(d["violation_count"] for d in linnaean_results.values())
    c_total_viol = sum(d["violation_count"] for d in common_results.values())

    print(f"\n  TOTALS:")
    print(f"    Linnaean ({len(LINNAEAN)}): {l_total_mono} monotonic, {l_total_viol} violations")
    print(f"    Common ({len(COMMON_NAMES)}): {c_total_mono} monotonic, {c_total_viol} violations")

    # Comparison with original
    print(f"\n  COMPARISON WITH ORIGINAL (10 Linnaean + 6 common):")
    print(f"    Original Linnaean: 1/10 monotonic, 19 violations")
    print(f"    Original Common:   0/6 monotonic, 18 violations")
    print(f"    Current Linnaean:  {l_total_mono}/{len(LINNAEAN)} monotonic, {l_total_viol} violations")
    print(f"    Current Common:    {c_total_mono}/{len(COMMON_NAMES)} monotonic, {c_total_viol} violations")

    results["head_to_head"] = {
        "linnaean_monotonic": l_total_mono,
        "linnaean_total": len(LINNAEAN),
        "linnaean_violations": l_total_viol,
        "common_monotonic": c_total_mono,
        "common_total": len(COMMON_NAMES),
        "common_violations": c_total_viol,
    }

    # Save
    save_path = os.path.join(_project_root, "prototype", "linnaean_hierarchy_large_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {save_path}")

    all_embedded = sorted(set(all_words + common_words))
    all_vecs_combined = embed_texts(all_embedded)
    emb_path = os.path.join(_project_root, "prototype", "linnaean_hierarchy_large_embeddings.npz")
    np.savez(emb_path, words=all_embedded, vecs=all_vecs_combined)
    print(f"Embeddings saved to: {emb_path}")


if __name__ == "__main__":
    main()
