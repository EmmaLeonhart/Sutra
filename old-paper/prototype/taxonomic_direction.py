"""Taxonomic Direction Analysis: Is there a consistent 'upward' vector in embedding space?

Core question: When you move from specific→general along a taxonomic hierarchy
(dog→canine→mammal→animal→organism→entity), does the displacement vector point
in a consistent direction? And does that direction generalize ACROSS hierarchies
(nouns AND verbs)?

Hypothesis: If embeddings encode some notion of abstraction level, then the
displacement vectors specific→general should share a common directional component.
If not, "going up" in different hierarchies goes in completely unrelated directions.

Usage:
    python prototype/taxonomic_direction.py
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
# HIERARCHIES: specific (index 0) → general (last index)
# ══════════════════════════════════════════════════════════════════════════════

NOUN_HIERARCHIES = {
    "dog": ["puppy", "dog", "hound", "canine", "carnivore", "mammal", "animal", "organism", "entity"],
    "cat": ["kitten", "cat", "feline", "carnivore", "mammal", "animal", "organism", "entity"],
    "horse": ["foal", "horse", "stallion", "equine", "mammal", "animal", "organism", "entity"],
    "fish": ["trout", "fish", "aquatic animal", "animal", "organism", "entity"],
    "bird": ["sparrow", "bird", "avian", "animal", "organism", "entity"],
    "tree": ["oak", "tree", "plant", "organism", "entity"],
    "rock": ["pebble", "rock", "stone", "mineral", "substance", "matter", "entity"],
    "truck": ["pickup", "truck", "vehicle", "machine", "artifact", "object", "entity"],
    "child": ["toddler", "child", "person", "human", "primate", "mammal", "animal", "organism", "entity"],
    "star": ["sun", "star", "celestial body", "astronomical object", "entity"],
}

VERB_HIERARCHIES = {
    # Action verbs: specific manner → general action → maximally abstract
    "eat": ["munch", "eat", "consume", "ingest", "take in", "process", "act"],
    "devour": ["devour", "gorge", "consume", "ingest", "take in", "process", "act"],
    "carry": ["lug", "carry", "transport", "move", "displace", "act"],
    "throw": ["hurl", "throw", "propel", "move", "displace", "act"],
    "watch": ["stare", "watch", "observe", "perceive", "sense", "experience", "act"],
    "listen": ["eavesdrop", "listen", "hear", "perceive", "sense", "experience", "act"],
    "cut": ["slice", "cut", "sever", "divide", "separate", "alter", "act"],
    "build": ["assemble", "build", "construct", "create", "produce", "act"],
    "run": ["sprint", "run", "move", "travel", "act"],
    "speak": ["whisper", "speak", "communicate", "express", "act"],
}

ADJECTIVE_HIERARCHIES = {
    # Specific quality → general quality
    "red": ["crimson", "red", "warm-colored", "colored", "visible", "perceptible"],
    "huge": ["enormous", "huge", "large", "big", "sized"],
    "cold": ["freezing", "cold", "cool", "temperature", "condition"],
    "fast": ["lightning-fast", "fast", "quick", "speedy", "moving"],
}


# ══════════════════════════════════════════════════════════════════════════════
# PART 1: EMBED ALL HIERARCHIES
# ══════════════════════════════════════════════════════════════════════════════

def embed_all_hierarchies():
    """Embed every word in every hierarchy."""
    print("=" * 70)
    print("  PART 1: EMBEDDING ALL TAXONOMIC HIERARCHIES")
    print("=" * 70)

    all_hierarchies = {}
    all_hierarchies.update({f"noun_{k}": v for k, v in NOUN_HIERARCHIES.items()})
    all_hierarchies.update({f"verb_{k}": v for k, v in VERB_HIERARCHIES.items()})
    all_hierarchies.update({f"adj_{k}": v for k, v in ADJECTIVE_HIERARCHIES.items()})

    # Collect unique words
    unique_words = sorted(set(w for chain in all_hierarchies.values() for w in chain))
    print(f"\n  {len(all_hierarchies)} hierarchies, {len(unique_words)} unique words")
    print(f"  Nouns: {len(NOUN_HIERARCHIES)}, Verbs: {len(VERB_HIERARCHIES)}, "
          f"Adjectives: {len(ADJECTIVE_HIERARCHIES)}")

    print(f"\n  Embedding {len(unique_words)} unique words...")
    vecs = embed_texts(unique_words)
    word_to_vec = {w: vecs[i] for i, w in enumerate(unique_words)}

    # Print pairwise similarity within each hierarchy
    for hname, chain in all_hierarchies.items():
        print(f"\n  --- {hname}: {' → '.join(chain)} ---")
        chain_vecs = np.array([word_to_vec[w] for w in chain])
        sim = pairwise_cosine(chain_vecs)

        # Adjacent similarities
        adjacent = [sim[i, i + 1] for i in range(len(chain) - 1)]
        print(f"    Adjacent sims: {['%.3f' % a for a in adjacent]}")
        print(f"    Adjacent mean: {np.mean(adjacent):.4f}")
        print(f"    Endpoint ({chain[0]}→{chain[-1]}): {sim[0, -1]:.4f}")

    return all_hierarchies, word_to_vec, unique_words, vecs


# ══════════════════════════════════════════════════════════════════════════════
# PART 2: DISPLACEMENT VECTORS — "UP" DIRECTION WITHIN EACH HIERARCHY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_displacement_vectors(all_hierarchies, word_to_vec):
    """For each hierarchy, compute the displacement vectors for each
    specific→general step. Then check consistency within hierarchy."""

    print(f"\n{'=' * 70}")
    print("  PART 2: DISPLACEMENT VECTORS (SPECIFIC → GENERAL)")
    print("=" * 70)
    print("  For each hierarchy, compute the 'upward' displacement at each step.")
    print("  Check: do all steps point in roughly the same direction?\n")

    hierarchy_data = {}

    for hname, chain in all_hierarchies.items():
        vecs = [word_to_vec[w] for w in chain]
        n = len(chain)

        # Displacement vectors: step i → i+1
        displacements = []
        for i in range(n - 1):
            d = vecs[i + 1] - vecs[i]
            norm = np.linalg.norm(d)
            if norm > 1e-10:
                displacements.append(d / norm)  # unit displacement
            else:
                displacements.append(d)

        # Mean direction
        if len(displacements) > 0:
            raw_mean = np.mean(displacements, axis=0)
            mean_norm = np.linalg.norm(raw_mean)
            if mean_norm > 1e-10:
                mean_dir = raw_mean / mean_norm
            else:
                mean_dir = raw_mean

            # Consistency: cosine of each displacement with mean direction
            alignments = [cosine(d, mean_dir) for d in displacements]

            # Pairwise consistency between adjacent displacements
            pairwise = []
            for i in range(len(displacements)):
                for j in range(i + 1, len(displacements)):
                    pairwise.append(cosine(displacements[i], displacements[j]))

            step_labels = [f"{chain[i]}→{chain[i+1]}" for i in range(n - 1)]

            print(f"  {hname}:")
            for k, label in enumerate(step_labels):
                print(f"    {label:<35s}  alignment to mean: {alignments[k]:+.4f}")
            print(f"    Mean alignment: {np.mean(alignments):.4f}")
            print(f"    Pairwise consistency: {np.mean(pairwise):.4f}  "
                  f"range [{min(pairwise):.3f}, {max(pairwise):.3f}]")
            print()

            hierarchy_data[hname] = {
                "chain": chain,
                "step_labels": step_labels,
                "alignments": [float(a) for a in alignments],
                "mean_alignment": float(np.mean(alignments)),
                "pairwise_consistency": float(np.mean(pairwise)),
                "pairwise_range": [float(min(pairwise)), float(max(pairwise))],
                "mean_direction_magnitude": float(mean_norm),
                "displacements_raw": [d.tolist() for d in displacements],
                "mean_direction": mean_dir.tolist(),
            }
        else:
            hierarchy_data[hname] = {"chain": chain, "error": "no valid displacements"}

    return hierarchy_data


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: CROSS-HIERARCHY COMPARISON — IS "UP" THE SAME EVERYWHERE?
# ══════════════════════════════════════════════════════════════════════════════

def analyze_cross_hierarchy(hierarchy_data):
    """Compare the mean 'upward' direction across different hierarchies.
    Key question: does the noun 'up' direction align with the verb 'up' direction?"""

    print(f"{'=' * 70}")
    print("  PART 3: CROSS-HIERARCHY — IS 'UP' THE SAME DIRECTION EVERYWHERE?")
    print("=" * 70)
    print("  Compare the mean 'upward' vector across all hierarchies.\n")

    # Get all hierarchies with valid mean directions
    valid = {k: v for k, v in hierarchy_data.items()
             if "mean_direction" in v}

    names = sorted(valid.keys())
    mean_dirs = np.array([valid[n]["mean_direction"] for n in names])

    # Cross-hierarchy cosine similarity of mean "up" directions
    cross_sim = pairwise_cosine(mean_dirs)

    # Group by POS
    noun_names = [n for n in names if n.startswith("noun_")]
    verb_names = [n for n in names if n.startswith("verb_")]
    adj_names = [n for n in names if n.startswith("adj_")]

    def group_stats(group_names, label):
        if len(group_names) < 2:
            print(f"  {label}: not enough hierarchies")
            return None
        indices = [names.index(n) for n in group_names]
        within = []
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                within.append(cross_sim[indices[i], indices[j]])
        print(f"  {label} ({len(group_names)} hierarchies):")
        print(f"    Within-group 'up' direction cosine: mean={np.mean(within):.4f}  "
              f"range=[{min(within):.3f}, {max(within):.3f}]")

        # Print the full within-group matrix
        short_names = [n.split("_", 1)[1] for n in group_names]
        header = "      " + "".join(f"{sn:>12s}" for sn in short_names)
        print(header)
        for i, ni in enumerate(group_names):
            row = f"      {short_names[i]:>10s}"
            ii = names.index(ni)
            for j, nj in enumerate(group_names):
                jj = names.index(nj)
                if i == j:
                    row += "          --"
                else:
                    row += f"       {cross_sim[ii, jj]:.3f}"
            print(row)
        print()
        return within

    noun_within = group_stats(noun_names, "NOUNS")
    verb_within = group_stats(verb_names, "VERBS")
    adj_within = group_stats(adj_names, "ADJECTIVES")

    # Cross-POS comparison
    print(f"  CROSS-POS: Noun 'up' vs Verb 'up' vs Adjective 'up'")
    for g1_names, g1_label in [(noun_names, "noun"), (verb_names, "verb"), (adj_names, "adj")]:
        for g2_names, g2_label in [(noun_names, "noun"), (verb_names, "verb"), (adj_names, "adj")]:
            if g1_label >= g2_label:
                continue
            cross = []
            for n1 in g1_names:
                for n2 in g2_names:
                    i1, i2 = names.index(n1), names.index(n2)
                    cross.append(cross_sim[i1, i2])
            if cross:
                print(f"    {g1_label} × {g2_label}: mean={np.mean(cross):.4f}  "
                      f"range=[{min(cross):.3f}, {max(cross):.3f}]")

    # Compute a GLOBAL "up" direction (mean of all mean directions)
    global_up = np.mean(mean_dirs, axis=0)
    global_up_norm = global_up / (np.linalg.norm(global_up) + 1e-10)

    print(f"\n  GLOBAL 'UP' DIRECTION (mean of all {len(names)} hierarchy directions):")
    print(f"    Magnitude of mean: {np.linalg.norm(global_up):.4f} "
          f"(1.0 = perfect agreement, 0.0 = random)")

    # Each hierarchy's alignment with global up
    global_alignments = [cosine(mean_dirs[i], global_up_norm) for i in range(len(names))]
    print(f"\n    {'Hierarchy':<25s} {'Alignment':>10s} {'Type':>8s}")
    print(f"    {'-' * 45}")
    for i, n in enumerate(names):
        pos = n.split("_")[0]
        print(f"    {n:<25s} {global_alignments[i]:>+10.4f} {pos:>8s}")

    print(f"\n    Noun mean alignment with global 'up': "
          f"{np.mean([global_alignments[names.index(n)] for n in noun_names]):.4f}")
    print(f"    Verb mean alignment with global 'up': "
          f"{np.mean([global_alignments[names.index(n)] for n in verb_names]):.4f}")
    if adj_names:
        print(f"    Adj  mean alignment with global 'up': "
              f"{np.mean([global_alignments[names.index(n)] for n in adj_names]):.4f}")

    return {
        "cross_hierarchy_sim": {names[i]: {names[j]: float(cross_sim[i, j])
                                            for j in range(len(names))}
                                 for i in range(len(names))},
        "noun_within": [float(x) for x in noun_within] if noun_within else [],
        "verb_within": [float(x) for x in verb_within] if verb_within else [],
        "adj_within": [float(x) for x in adj_within] if adj_within else [],
        "global_up_magnitude": float(np.linalg.norm(global_up)),
        "global_alignments": {names[i]: float(global_alignments[i])
                              for i in range(len(names))},
        "global_up_direction": global_up_norm.tolist(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: ABSTRACTION LEVEL — DO MORE ABSTRACT WORDS CLUSTER?
# ══════════════════════════════════════════════════════════════════════════════

def analyze_abstraction_levels(all_hierarchies, word_to_vec):
    """Do words at the same abstraction level cluster together across hierarchies?
    E.g., do all the 'leaf' words (puppy, kitten, trout, pebble) form a cluster?
    Do all the 'top' words (entity, act, perceptible) form a cluster?"""

    print(f"\n{'=' * 70}")
    print("  PART 4: DO SAME-LEVEL WORDS CLUSTER ACROSS HIERARCHIES?")
    print("=" * 70)

    # Normalize hierarchy positions to [0, 1] where 0=most specific, 1=most general
    word_levels = {}  # word → list of normalized positions
    for hname, chain in all_hierarchies.items():
        for i, w in enumerate(chain):
            level = i / (len(chain) - 1) if len(chain) > 1 else 0.5
            if w not in word_levels:
                word_levels[w] = []
            word_levels[w].append(level)

    # Average level for each word
    word_avg_level = {w: np.mean(levels) for w, levels in word_levels.items()}

    # Bin into low (0-0.33), mid (0.33-0.67), high (0.67-1.0)
    bins = {"specific (0.0-0.33)": [], "mid (0.33-0.67)": [], "general (0.67-1.0)": []}
    for w, level in word_avg_level.items():
        if level < 0.33:
            bins["specific (0.0-0.33)"].append(w)
        elif level < 0.67:
            bins["mid (0.33-0.67)"].append(w)
        else:
            bins["general (0.67-1.0)"].append(w)

    print(f"\n  Words binned by normalized abstraction level:")
    for bin_name, words in bins.items():
        print(f"    {bin_name}: {len(words)} words")
        # Show some examples
        examples = sorted(words)[:10]
        print(f"      Examples: {', '.join(examples)}")

    # Within-bin vs across-bin similarity
    results = {}
    for bin_name, words in bins.items():
        if len(words) < 2:
            continue
        bin_vecs = np.array([word_to_vec[w] for w in words])
        sim = pairwise_cosine(bin_vecs)
        upper = sim[np.triu_indices(len(words), k=1)]
        results[bin_name] = {
            "count": len(words),
            "mean_sim": float(np.mean(upper)),
            "min_sim": float(np.min(upper)),
            "max_sim": float(np.max(upper)),
        }
        print(f"\n    {bin_name}: mean within-bin sim = {np.mean(upper):.4f}  "
              f"range [{np.min(upper):.3f}, {np.max(upper):.3f}]")

    # Cross-bin similarities
    bin_names = list(bins.keys())
    for i in range(len(bin_names)):
        for j in range(i + 1, len(bin_names)):
            words_i = bins[bin_names[i]]
            words_j = bins[bin_names[j]]
            if not words_i or not words_j:
                continue
            cross = []
            for wi in words_i:
                for wj in words_j:
                    cross.append(cosine(word_to_vec[wi], word_to_vec[wj]))
            print(f"    {bin_names[i]} × {bin_names[j]}: "
                  f"mean cross-bin sim = {np.mean(cross):.4f}")
            results[f"cross_{bin_names[i]}_x_{bin_names[j]}"] = {
                "mean_sim": float(np.mean(cross)),
            }

    # Terminal words analysis: words that appear at the end of multiple hierarchies
    terminal_words = {}
    for hname, chain in all_hierarchies.items():
        top = chain[-1]
        if top not in terminal_words:
            terminal_words[top] = []
        terminal_words[top].append(hname)

    shared_terminals = {w: hs for w, hs in terminal_words.items() if len(hs) > 1}
    print(f"\n  Shared terminal (most-general) words:")
    for w, hs in sorted(shared_terminals.items(), key=lambda x: -len(x[1])):
        print(f"    \"{w}\" — terminal in {len(hs)} hierarchies: {', '.join(hs)}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# PART 5: STEP-BY-STEP DISTANCE FROM ORIGIN WORD
# ══════════════════════════════════════════════════════════════════════════════

def analyze_distance_decay(all_hierarchies, word_to_vec):
    """How does cosine similarity to the origin word decay as you go up?
    Is the decay monotonic? Is it consistent across POS types?"""

    print(f"\n{'=' * 70}")
    print("  PART 5: DISTANCE DECAY FROM ORIGIN WORD")
    print("=" * 70)
    print("  How does similarity to the most-specific word decay as you ascend?\n")

    noun_decays = []
    verb_decays = []
    adj_decays = []
    all_decays = {}

    for hname, chain in all_hierarchies.items():
        origin_vec = word_to_vec[chain[0]]
        sims_from_origin = [cosine(origin_vec, word_to_vec[w]) for w in chain]

        # Normalize position to [0, 1]
        positions = [i / (len(chain) - 1) for i in range(len(chain))] if len(chain) > 1 else [0.5]

        # Check monotonicity
        monotonic = all(sims_from_origin[i] >= sims_from_origin[i + 1]
                        for i in range(len(sims_from_origin) - 1))
        violations = sum(1 for i in range(len(sims_from_origin) - 1)
                         if sims_from_origin[i] < sims_from_origin[i + 1])

        print(f"  {hname}: {'MONOTONIC' if monotonic else f'{violations} violation(s)'}")
        for i, w in enumerate(chain):
            marker = " ←!" if (i > 0 and sims_from_origin[i] > sims_from_origin[i - 1]) else ""
            print(f"    [{positions[i]:.2f}] {w:<25s} sim={sims_from_origin[i]:.4f}{marker}")

        decay_data = {
            "chain": chain,
            "sims_from_origin": [float(s) for s in sims_from_origin],
            "positions": positions,
            "monotonic": monotonic,
            "violations": violations,
        }
        all_decays[hname] = decay_data

        if hname.startswith("noun_"):
            noun_decays.append(decay_data)
        elif hname.startswith("verb_"):
            verb_decays.append(decay_data)
        elif hname.startswith("adj_"):
            adj_decays.append(decay_data)

    # Summary by POS
    print(f"\n  MONOTONICITY SUMMARY:")
    for label, decays in [("Nouns", noun_decays), ("Verbs", verb_decays), ("Adj", adj_decays)]:
        mono_count = sum(1 for d in decays if d["monotonic"])
        total_violations = sum(d["violations"] for d in decays)
        print(f"    {label}: {mono_count}/{len(decays)} monotonic, "
              f"{total_violations} total violations")

    # Average decay curve (interpolated to common positions)
    print(f"\n  AVERAGE DECAY CURVES (interpolated to 5 steps):")
    common_positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    for label, decays in [("Nouns", noun_decays), ("Verbs", verb_decays), ("Adj", adj_decays)]:
        if not decays:
            continue
        interpolated = []
        for d in decays:
            interp = np.interp(common_positions, d["positions"], d["sims_from_origin"])
            interpolated.append(interp)
        avg_curve = np.mean(interpolated, axis=0)
        std_curve = np.std(interpolated, axis=0)
        print(f"    {label}:")
        for i, pos in enumerate(common_positions):
            print(f"      [{pos:.2f}] mean={avg_curve[i]:.4f} ± {std_curve[i]:.4f}")

    return all_decays


# ══════════════════════════════════════════════════════════════════════════════

def main():
    results = {}

    # Combine all hierarchies
    all_hierarchies = {}
    all_hierarchies.update({f"noun_{k}": v for k, v in NOUN_HIERARCHIES.items()})
    all_hierarchies.update({f"verb_{k}": v for k, v in VERB_HIERARCHIES.items()})
    all_hierarchies.update({f"adj_{k}": v for k, v in ADJECTIVE_HIERARCHIES.items()})

    # Part 1: Embed everything
    _, word_to_vec, unique_words, raw_vecs = embed_all_hierarchies()

    # Part 2: Displacement vectors within each hierarchy
    displacement_data = analyze_displacement_vectors(all_hierarchies, word_to_vec)
    results["displacement_vectors"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "displacements_raw" and kk != "mean_direction"}
        for k, v in displacement_data.items()
    }

    # Part 3: Cross-hierarchy comparison
    cross_data = analyze_cross_hierarchy(displacement_data)
    results["cross_hierarchy"] = {
        k: v for k, v in cross_data.items() if k != "global_up_direction"
    }

    # Part 4: Abstraction level clustering
    abstraction_data = analyze_abstraction_levels(all_hierarchies, word_to_vec)
    results["abstraction_levels"] = abstraction_data

    # Part 5: Distance decay
    decay_data = analyze_distance_decay(all_hierarchies, word_to_vec)
    results["distance_decay"] = decay_data

    # Save results JSON
    save_path = os.path.join(_project_root, "prototype", "taxonomic_direction_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {save_path}")

    # Save raw embeddings
    emb_path = os.path.join(_project_root, "prototype", "taxonomic_direction_embeddings.npz")
    np.savez(emb_path, words=unique_words, vecs=raw_vecs)
    print(f"Embeddings saved to: {emb_path}")

    # Save displacement mean directions for cross-hierarchy analysis
    dir_path = os.path.join(_project_root, "prototype", "taxonomic_direction_vectors.npz")
    dir_names = []
    dir_vecs = []
    for hname, data in displacement_data.items():
        if "mean_direction" in data:
            dir_names.append(hname)
            dir_vecs.append(data["mean_direction"])
    np.savez(dir_path, names=dir_names, directions=np.array(dir_vecs))
    print(f"Direction vectors saved to: {dir_path}")


if __name__ == "__main__":
    main()
