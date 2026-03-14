"""Taxonomic Direction Analysis (Large) — expanded hierarchy set.

Scaled-up replication of taxonomic_direction.py with:
  - 20 noun hierarchies (vs 10)
  - 20 verb hierarchies (vs 10)
  - 10 adjective hierarchies (vs 4)
  = 50 total hierarchies (vs 24), ~250+ unique words

Usage:
    python prototype/taxonomic_direction_large.py
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
# HIERARCHIES: specific (index 0) -> general (last index)
# ==============================================================================

NOUN_HIERARCHIES = {
    # Original 10
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
    # New 10
    "eagle": ["eaglet", "eagle", "raptor", "bird of prey", "bird", "animal", "organism", "entity"],
    "whale": ["calf", "whale", "cetacean", "mammal", "animal", "organism", "entity"],
    "snake": ["hatchling", "snake", "serpent", "reptile", "animal", "organism", "entity"],
    "flower": ["bud", "flower", "blossom", "plant", "organism", "entity"],
    "insect": ["larva", "insect", "arthropod", "invertebrate", "animal", "organism", "entity"],
    "mushroom": ["spore", "mushroom", "fungus", "organism", "entity"],
    "robot": ["drone", "robot", "automaton", "machine", "artifact", "object", "entity"],
    "sword": ["dagger", "sword", "blade", "weapon", "tool", "artifact", "object", "entity"],
    "river": ["stream", "river", "waterway", "body of water", "landform", "entity"],
    "book": ["novel", "book", "publication", "document", "artifact", "object", "entity"],
}

VERB_HIERARCHIES = {
    # Original 10
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
    # New 10
    "destroy": ["smash", "destroy", "demolish", "damage", "harm", "affect", "act"],
    "collect": ["scoop", "collect", "gather", "accumulate", "acquire", "act"],
    "chase": ["sprint after", "chase", "pursue", "follow", "track", "act"],
    "paint": ["sketch", "paint", "draw", "depict", "represent", "create", "act"],
    "hide": ["conceal", "hide", "obscure", "cover", "protect", "act"],
    "sing": ["hum", "sing", "vocalize", "produce sound", "emit", "act"],
    "read": ["skim", "read", "study", "learn", "process", "act"],
    "write": ["scribble", "write", "compose", "create", "produce", "act"],
    "push": ["shove", "push", "force", "move", "displace", "act"],
    "climb": ["scramble", "climb", "ascend", "move", "travel", "act"],
}

ADJECTIVE_HIERARCHIES = {
    # Original 4
    "red": ["crimson", "red", "warm-colored", "colored", "visible", "perceptible"],
    "huge": ["enormous", "huge", "large", "big", "sized"],
    "cold": ["freezing", "cold", "cool", "temperature", "condition"],
    "fast": ["lightning-fast", "fast", "quick", "speedy", "moving"],
    # New 6
    "loud": ["deafening", "loud", "noisy", "audible", "perceptible"],
    "bright": ["blinding", "bright", "luminous", "visible", "perceptible"],
    "soft": ["silky", "soft", "smooth", "textured", "tactile", "perceptible"],
    "sweet": ["sugary", "sweet", "flavored", "tasteable", "perceptible"],
    "old": ["ancient", "old", "aged", "mature", "developed"],
    "heavy": ["leaden", "heavy", "weighty", "massive", "sized"],
}


# ==============================================================================
# PART 1: EMBED ALL HIERARCHIES
# ==============================================================================

def embed_all_hierarchies():
    print("=" * 70)
    print("  PART 1: EMBEDDING ALL TAXONOMIC HIERARCHIES (50 total)")
    print("=" * 70)

    all_hierarchies = {}
    all_hierarchies.update({f"noun_{k}": v for k, v in NOUN_HIERARCHIES.items()})
    all_hierarchies.update({f"verb_{k}": v for k, v in VERB_HIERARCHIES.items()})
    all_hierarchies.update({f"adj_{k}": v for k, v in ADJECTIVE_HIERARCHIES.items()})

    unique_words = sorted(set(w for chain in all_hierarchies.values() for w in chain))
    print(f"\n  {len(all_hierarchies)} hierarchies, {len(unique_words)} unique words")
    print(f"  Nouns: {len(NOUN_HIERARCHIES)}, Verbs: {len(VERB_HIERARCHIES)}, "
          f"Adjectives: {len(ADJECTIVE_HIERARCHIES)}")

    print(f"\n  Embedding {len(unique_words)} unique words...")
    vecs = embed_texts(unique_words)
    word_to_vec = {w: vecs[i] for i, w in enumerate(unique_words)}

    # Print summary for each hierarchy
    for hname, chain in all_hierarchies.items():
        chain_vecs = np.array([word_to_vec[w] for w in chain])
        sim = pairwise_cosine(chain_vecs)
        adjacent = [sim[i, i + 1] for i in range(len(chain) - 1)]
        print(f"  {hname:<25s}: adj_mean={np.mean(adjacent):.3f}  "
              f"endpoint={sim[0, -1]:.3f}  len={len(chain)}")

    return all_hierarchies, word_to_vec, unique_words, vecs


# ==============================================================================
# PART 2: DISPLACEMENT VECTORS
# ==============================================================================

def analyze_displacement_vectors(all_hierarchies, word_to_vec):
    print(f"\n{'=' * 70}")
    print("  PART 2: DISPLACEMENT VECTORS (SPECIFIC -> GENERAL)")
    print("=" * 70)

    hierarchy_data = {}

    for hname, chain in all_hierarchies.items():
        vecs = [word_to_vec[w] for w in chain]
        n = len(chain)

        displacements = []
        for i in range(n - 1):
            d = vecs[i + 1] - vecs[i]
            norm = np.linalg.norm(d)
            if norm > 1e-10:
                displacements.append(d / norm)
            else:
                displacements.append(d)

        if len(displacements) > 0:
            raw_mean = np.mean(displacements, axis=0)
            mean_norm = np.linalg.norm(raw_mean)
            mean_dir = raw_mean / (mean_norm + 1e-10)

            alignments = [cosine(d, mean_dir) for d in displacements]
            pairwise = []
            for i in range(len(displacements)):
                for j in range(i + 1, len(displacements)):
                    pairwise.append(cosine(displacements[i], displacements[j]))

            print(f"  {hname:<25s}: mean_align={np.mean(alignments):.3f}  "
                  f"pairwise={np.mean(pairwise):.3f}  dir_mag={mean_norm:.3f}")

            hierarchy_data[hname] = {
                "chain": chain,
                "step_labels": [f"{chain[i]}->{chain[i+1]}" for i in range(n - 1)],
                "alignments": [float(a) for a in alignments],
                "mean_alignment": float(np.mean(alignments)),
                "pairwise_consistency": float(np.mean(pairwise)),
                "pairwise_range": [float(min(pairwise)), float(max(pairwise))],
                "mean_direction_magnitude": float(mean_norm),
                "displacements_raw": [d.tolist() for d in displacements],
                "mean_direction": mean_dir.tolist(),
            }

    return hierarchy_data


# ==============================================================================
# PART 3: CROSS-HIERARCHY COMPARISON
# ==============================================================================

def analyze_cross_hierarchy(hierarchy_data):
    print(f"\n{'=' * 70}")
    print("  PART 3: CROSS-HIERARCHY 'UP' DIRECTION COMPARISON")
    print("=" * 70)

    valid = {k: v for k, v in hierarchy_data.items() if "mean_direction" in v}
    names = sorted(valid.keys())
    mean_dirs = np.array([valid[n]["mean_direction"] for n in names])
    cross_sim = pairwise_cosine(mean_dirs)

    noun_names = [n for n in names if n.startswith("noun_")]
    verb_names = [n for n in names if n.startswith("verb_")]
    adj_names = [n for n in names if n.startswith("adj_")]

    def group_stats(group_names, label):
        if len(group_names) < 2:
            return None
        indices = [names.index(n) for n in group_names]
        within = []
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                within.append(cross_sim[indices[i], indices[j]])
        print(f"\n  {label} ({len(group_names)} hierarchies):")
        print(f"    Within-group 'up' direction cosine: mean={np.mean(within):.4f} "
              f"(+-{np.std(within):.3f})  range=[{min(within):.3f}, {max(within):.3f}]")
        return within

    noun_within = group_stats(noun_names, "NOUNS")
    verb_within = group_stats(verb_names, "VERBS")
    adj_within = group_stats(adj_names, "ADJECTIVES")

    # Cross-POS
    print(f"\n  CROSS-POS COMPARISON:")
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
                print(f"    {g1_label} x {g2_label}: mean={np.mean(cross):.4f} "
                      f"(+-{np.std(cross):.3f})  range=[{min(cross):.3f}, {max(cross):.3f}]")

    # Global "up"
    global_up = np.mean(mean_dirs, axis=0)
    global_up_norm = global_up / (np.linalg.norm(global_up) + 1e-10)
    global_mag = float(np.linalg.norm(global_up))

    global_alignments = [cosine(mean_dirs[i], global_up_norm) for i in range(len(names))]

    print(f"\n  GLOBAL 'UP' DIRECTION (mean of {len(names)} hierarchies):")
    print(f"    Magnitude: {global_mag:.4f}")
    print(f"    Noun alignment:  {np.mean([global_alignments[names.index(n)] for n in noun_names]):.4f}")
    print(f"    Verb alignment:  {np.mean([global_alignments[names.index(n)] for n in verb_names]):.4f}")
    print(f"    Adj alignment:   {np.mean([global_alignments[names.index(n)] for n in adj_names]):.4f}")

    return {
        "noun_within": [float(x) for x in noun_within] if noun_within else [],
        "verb_within": [float(x) for x in verb_within] if verb_within else [],
        "adj_within": [float(x) for x in adj_within] if adj_within else [],
        "global_up_magnitude": global_mag,
        "global_up_direction": global_up_norm.tolist(),
    }


# ==============================================================================
# PART 4: ABSTRACTION LEVEL CLUSTERING
# ==============================================================================

def analyze_abstraction_levels(all_hierarchies, word_to_vec):
    print(f"\n{'=' * 70}")
    print("  PART 4: ABSTRACTION LEVEL CLUSTERING")
    print("=" * 70)

    word_levels = {}
    for hname, chain in all_hierarchies.items():
        for i, w in enumerate(chain):
            level = i / (len(chain) - 1) if len(chain) > 1 else 0.5
            if w not in word_levels:
                word_levels[w] = []
            word_levels[w].append(level)

    word_avg_level = {w: np.mean(levels) for w, levels in word_levels.items()}

    bins = {"specific (0.0-0.33)": [], "mid (0.33-0.67)": [], "general (0.67-1.0)": []}
    for w, level in word_avg_level.items():
        if level < 0.33:
            bins["specific (0.0-0.33)"].append(w)
        elif level < 0.67:
            bins["mid (0.33-0.67)"].append(w)
        else:
            bins["general (0.67-1.0)"].append(w)

    results = {}
    for bin_name, words in bins.items():
        print(f"\n  {bin_name}: {len(words)} words")
        if len(words) < 2:
            continue
        bin_vecs = np.array([word_to_vec[w] for w in words])
        sim = pairwise_cosine(bin_vecs)
        upper = sim[np.triu_indices(len(words), k=1)]
        results[bin_name] = {
            "count": len(words),
            "mean_sim": float(np.mean(upper)),
            "std_sim": float(np.std(upper)),
        }
        print(f"    Within-bin sim: mean={np.mean(upper):.4f} (+-{np.std(upper):.3f})")

    # Cross-bin
    bin_names = list(bins.keys())
    for i in range(len(bin_names)):
        for j in range(i + 1, len(bin_names)):
            words_i = bins[bin_names[i]]
            words_j = bins[bin_names[j]]
            if not words_i or not words_j:
                continue
            cross = [cosine(word_to_vec[wi], word_to_vec[wj])
                     for wi in words_i for wj in words_j]
            print(f"    {bin_names[i][:8]} x {bin_names[j][:8]}: mean={np.mean(cross):.4f}")

    return results


# ==============================================================================
# PART 5: DISTANCE DECAY FROM ORIGIN
# ==============================================================================

def analyze_distance_decay(all_hierarchies, word_to_vec):
    print(f"\n{'=' * 70}")
    print("  PART 5: DISTANCE DECAY FROM ORIGIN WORD")
    print("=" * 70)

    noun_decays = []
    verb_decays = []
    adj_decays = []
    all_decays = {}

    for hname, chain in all_hierarchies.items():
        origin_vec = word_to_vec[chain[0]]
        sims_from_origin = [cosine(origin_vec, word_to_vec[w]) for w in chain]
        positions = [i / (len(chain) - 1) for i in range(len(chain))] if len(chain) > 1 else [0.5]

        monotonic = all(sims_from_origin[i] >= sims_from_origin[i + 1]
                        for i in range(len(sims_from_origin) - 1))
        violations = sum(1 for i in range(len(sims_from_origin) - 1)
                         if sims_from_origin[i] < sims_from_origin[i + 1])

        status = "MONO" if monotonic else f"{violations}v"
        print(f"  {hname:<25s}: {status:>5s}  "
              f"origin={sims_from_origin[0]:.3f}->{sims_from_origin[-1]:.3f}")

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

    print(f"\n  MONOTONICITY SUMMARY:")
    for label, decays in [("Nouns", noun_decays), ("Verbs", verb_decays), ("Adj", adj_decays)]:
        mono_count = sum(1 for d in decays if d["monotonic"])
        total_violations = sum(d["violations"] for d in decays)
        print(f"    {label}: {mono_count}/{len(decays)} monotonic, "
              f"{total_violations} total violations")

    return all_decays


# ==============================================================================

def main():
    results = {}

    all_hierarchies = {}
    all_hierarchies.update({f"noun_{k}": v for k, v in NOUN_HIERARCHIES.items()})
    all_hierarchies.update({f"verb_{k}": v for k, v in VERB_HIERARCHIES.items()})
    all_hierarchies.update({f"adj_{k}": v for k, v in ADJECTIVE_HIERARCHIES.items()})

    _, word_to_vec, unique_words, raw_vecs = embed_all_hierarchies()

    displacement_data = analyze_displacement_vectors(all_hierarchies, word_to_vec)
    results["displacement_vectors"] = {
        k: {kk: vv for kk, vv in v.items()
            if kk != "displacements_raw" and kk != "mean_direction"}
        for k, v in displacement_data.items()
    }

    cross_data = analyze_cross_hierarchy(displacement_data)
    results["cross_hierarchy"] = {
        k: v for k, v in cross_data.items() if k != "global_up_direction"
    }

    abstraction_data = analyze_abstraction_levels(all_hierarchies, word_to_vec)
    results["abstraction_levels"] = abstraction_data

    decay_data = analyze_distance_decay(all_hierarchies, word_to_vec)
    results["distance_decay"] = decay_data

    # Comparison with original 24-hierarchy findings
    print(f"\n{'=' * 70}")
    print("  COMPARISON WITH ORIGINAL 24-HIERARCHY FINDINGS")
    print("=" * 70)
    print("  Original: Noun x Noun = 0.465, Verb x Verb = 0.381, Adj x Adj = 0.057")
    print(f"  Current:  Noun within mean = {np.mean(cross_data.get('noun_within', [0])):.4f}")
    print(f"            Verb within mean = {np.mean(cross_data.get('verb_within', [0])):.4f}")
    print(f"            Adj within mean  = {np.mean(cross_data.get('adj_within', [0])):.4f}")
    print(f"  Original global up magnitude: 0.456")
    print(f"  Current global up magnitude:  {cross_data.get('global_up_magnitude', 0):.4f}")

    save_path = os.path.join(_project_root, "prototype", "taxonomic_direction_large_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {save_path}")

    emb_path = os.path.join(_project_root, "prototype", "taxonomic_direction_large_embeddings.npz")
    np.savez(emb_path, words=unique_words, vecs=raw_vecs)
    print(f"  Embeddings saved to: {emb_path}")

    dir_path = os.path.join(_project_root, "prototype", "taxonomic_direction_large_vectors.npz")
    dir_names = []
    dir_vecs = []
    for hname, data in displacement_data.items():
        if "mean_direction" in data:
            dir_names.append(hname)
            dir_vecs.append(data["mean_direction"])
    np.savez(dir_path, names=dir_names, directions=np.array(dir_vecs))
    print(f"  Direction vectors saved to: {dir_path}")


if __name__ == "__main__":
    main()
