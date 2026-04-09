"""Word Isolation & Taxonomic Jitter Analysis (Large).

Scaled-up replication of word_isolation.py with:
  - 24 grid words (8+8+8) instead of 9 (3+3+3)
  - 15 taxonomic hierarchies instead of 7 (8 noun + 7 verb synonym)
  - 24 jitter templates instead of 9
  - 8 convergence chains instead of 4

Usage:
    python prototype/word_isolation_large.py
"""

from __future__ import annotations

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


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def pairwise_cosine(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    normed = vecs / norms
    return normed @ normed.T


# ==============================================================================
# PART 1: GRID WORDS IN ISOLATION (24 words from 8x8x8 grid)
# ==============================================================================

GRID_WORDS = {
    "subjects": ["cats", "trucks", "children", "eagles", "robots", "farmers", "whales", "soldiers"],
    "predicates": ["eat", "carry", "watch", "destroy", "collect", "chase", "paint", "hide"],
    "objects": ["fish", "rocks", "stars", "flowers", "coins", "books", "bridges", "shadows"],
}


def analyze_isolated_words():
    """Embed grid words in isolation and compare to proposition-level effects."""
    print("=" * 70)
    print("  PART 1: GRID WORDS IN ISOLATION (24 words)")
    print("=" * 70)

    all_words = (GRID_WORDS["subjects"] + GRID_WORDS["predicates"]
                 + GRID_WORDS["objects"])
    print(f"\n  Embedding {len(all_words)} words in isolation...")
    word_vecs = embed_texts(all_words)
    sim = pairwise_cosine(word_vecs)

    # Within-role vs across-role
    print(f"\n  Within-role similarity:")
    for role, words in GRID_WORDS.items():
        indices = [all_words.index(w) for w in words]
        within = []
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                within.append(sim[indices[a], indices[b]])
        print(f"    {role:>11s}: mean={np.mean(within):.4f} (+-{np.std(within):.3f})  "
              f"range=[{min(within):.3f}, {max(within):.3f}]  n={len(within)}")

    # Cross-role
    print(f"\n  Cross-role similarity:")
    for r1, r2 in [("subjects", "predicates"), ("subjects", "objects"),
                    ("predicates", "objects")]:
        idx1 = [all_words.index(w) for w in GRID_WORDS[r1]]
        idx2 = [all_words.index(w) for w in GRID_WORDS[r2]]
        cross = [sim[i, j] for i in idx1 for j in idx2]
        print(f"    {r1[:4]}x{r2[:4]:>5s}: mean={np.mean(cross):.4f} (+-{np.std(cross):.3f})  "
              f"range=[{min(cross):.3f}, {max(cross):.3f}]")

    # Most similar cross-role pairs (collocational associations)
    print(f"\n  Top 10 cross-role similarities:")
    cross_pairs = []
    roles = list(GRID_WORDS.keys())
    for ri in range(len(roles)):
        for rj in range(ri + 1, len(roles)):
            for w1 in GRID_WORDS[roles[ri]]:
                for w2 in GRID_WORDS[roles[rj]]:
                    i1 = all_words.index(w1)
                    i2 = all_words.index(w2)
                    cross_pairs.append((sim[i1, i2], w1, roles[ri], w2, roles[rj]))
    cross_pairs.sort(reverse=True)
    for s, w1, r1, w2, r2 in cross_pairs[:10]:
        print(f"    {s:.3f}  {w1} ({r1[:4]}) <-> {w2} ({r2[:4]})")

    return {w: word_vecs[i] for i, w in enumerate(all_words)}, sim


# ==============================================================================
# PART 2: TAXONOMIC HIERARCHIES (15 hierarchies)
# ==============================================================================

TAXONOMIES = {
    # Noun hierarchies (8) — matching grid subjects + objects
    "cat_hierarchy": {
        "words": ["kitten", "cat", "feline", "carnivore", "mammal", "animal", "creature"],
        "description": "Specific -> general for cats",
    },
    "eagle_hierarchy": {
        "words": ["eaglet", "eagle", "raptor", "bird", "animal", "creature"],
        "description": "Specific -> general for eagles",
    },
    "whale_hierarchy": {
        "words": ["calf", "whale", "cetacean", "mammal", "animal", "creature"],
        "description": "Specific -> general for whales",
    },
    "fish_hierarchy": {
        "words": ["trout", "fish", "seafood", "food", "thing"],
        "description": "Specific -> general for fish",
    },
    "rock_hierarchy": {
        "words": ["pebble", "rock", "stone", "mineral", "object", "thing"],
        "description": "Specific -> general for rocks",
    },
    "flower_hierarchy": {
        "words": ["tulip", "flower", "plant", "organism", "thing"],
        "description": "Specific -> general for flowers",
    },
    "book_hierarchy": {
        "words": ["novel", "book", "publication", "document", "object", "thing"],
        "description": "Specific -> general for books",
    },
    "bridge_hierarchy": {
        "words": ["footbridge", "bridge", "structure", "construction", "object", "thing"],
        "description": "Specific -> general for bridges",
    },
    # Verb synonym groups (7) — matching grid predicates
    "eat_synonyms": {
        "words": ["eat", "consume", "devour", "ingest", "munch", "dine", "feast"],
        "description": "Verb synonyms for eating",
    },
    "carry_synonyms": {
        "words": ["carry", "transport", "haul", "move", "bring", "convey", "lug"],
        "description": "Verb synonyms for carrying",
    },
    "watch_synonyms": {
        "words": ["watch", "observe", "view", "see", "gaze at", "monitor", "witness"],
        "description": "Verb synonyms for watching",
    },
    "destroy_synonyms": {
        "words": ["destroy", "demolish", "ruin", "wreck", "shatter", "annihilate", "obliterate"],
        "description": "Verb synonyms for destroying",
    },
    "collect_synonyms": {
        "words": ["collect", "gather", "accumulate", "amass", "hoard", "compile", "assemble"],
        "description": "Verb synonyms for collecting",
    },
    "chase_synonyms": {
        "words": ["chase", "pursue", "follow", "hunt", "track", "stalk", "trail"],
        "description": "Verb synonyms for chasing",
    },
    "paint_synonyms": {
        "words": ["paint", "draw", "sketch", "illustrate", "depict", "render", "portray"],
        "description": "Verb synonyms for painting/drawing",
    },
}


def analyze_taxonomies():
    """Embed taxonomic variants in isolation."""
    print(f"\n{'=' * 70}")
    print("  PART 2: TAXONOMIC HIERARCHIES (15 groups)")
    print("=" * 70)

    results = {}
    all_tax_vecs = {}

    for tax_name, tax in TAXONOMIES.items():
        words = tax["words"]
        print(f"\n  --- {tax_name}: {tax['description']} ---")

        vecs = embed_texts(words)
        sim = pairwise_cosine(vecs)
        all_tax_vecs[tax_name] = {w: vecs[i] for i, w in enumerate(words)}

        if "hierarchy" in tax_name:
            adjacent = [sim[i, i + 1] for i in range(len(words) - 1)]
            print(f"    Adjacent: {['%.3f' % a for a in adjacent]}  mean={np.mean(adjacent):.3f}")
            print(f"    Endpoints ({words[0]}->{words[-1]}): {sim[0, -1]:.4f}")

        if "synonyms" in tax_name:
            upper = sim[np.triu_indices(len(words), k=1)]
            print(f"    Mean pairwise: {np.mean(upper):.4f}  "
                  f"range [{np.min(upper):.3f}, {np.max(upper):.3f}]")

        results[tax_name] = {"words": words, "sim": sim.tolist()}

    return results, all_tax_vecs


# ==============================================================================
# PART 3: JITTER IN PROPOSITIONS (24 templates)
# ==============================================================================

JITTER_TEMPLATES = [
    # Subject jitter (8 templates — one per predicate/object combo)
    ("{word} eat fish", "subject"),
    ("{word} carry rocks", "subject"),
    ("{word} watch stars", "subject"),
    ("{word} destroy flowers", "subject"),
    ("{word} collect coins", "subject"),
    ("{word} chase books", "subject"),
    ("{word} paint bridges", "subject"),
    ("{word} hide shadows", "subject"),
    # Predicate jitter (8 templates)
    ("Cats {word} fish", "predicate"),
    ("Trucks {word} rocks", "predicate"),
    ("Children {word} stars", "predicate"),
    ("Eagles {word} flowers", "predicate"),
    ("Robots {word} coins", "predicate"),
    ("Farmers {word} books", "predicate"),
    ("Whales {word} bridges", "predicate"),
    ("Soldiers {word} shadows", "predicate"),
    # Object jitter (8 templates)
    ("Cats eat {word}", "object"),
    ("Trucks carry {word}", "object"),
    ("Children watch {word}", "object"),
    ("Eagles destroy {word}", "object"),
    ("Robots collect {word}", "object"),
    ("Farmers chase {word}", "object"),
    ("Whales paint {word}", "object"),
    ("Soldiers hide {word}", "object"),
]

JITTER_SETS = {
    "subject": {
        "hierarchy": ["kitten", "cat", "feline", "carnivore", "mammal", "animal", "creature"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "subject"],
    },
    "predicate": {
        "hierarchy": ["eat", "consume", "devour", "ingest", "munch", "dine", "feast"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "predicate"],
    },
    "object": {
        "hierarchy": ["trout", "fish", "seafood", "food", "thing"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "object"],
    },
}


def analyze_jitter():
    """Substitute taxonomic variants into proposition templates."""

    print(f"\n{'=' * 70}")
    print("  PART 3: TAXONOMIC JITTER IN PROPOSITIONS (24 templates)")
    print("=" * 70)

    results = {}
    role_summaries = {"subject": [], "predicate": [], "object": []}

    for role, config in JITTER_SETS.items():
        hierarchy = config["hierarchy"]
        templates = config["templates"]

        print(f"\n  === {role.upper()} JITTER: {hierarchy} ({len(templates)} templates) ===\n")

        # Embed words in isolation
        word_vecs = embed_texts(hierarchy)
        word_sim = pairwise_cosine(word_vecs)

        for template in templates:
            sents = [template.format(word=w) for w in hierarchy]
            sent_vecs = embed_texts(sents)
            sent_sim = pairwise_cosine(sent_vecs)

            n = len(hierarchy)
            word_upper = []
            sent_upper = []
            for i in range(n):
                for j in range(i + 1, n):
                    word_upper.append(word_sim[i, j])
                    sent_upper.append(sent_sim[i, j])

            corr = float(np.corrcoef(word_upper, sent_upper)[0, 1])

            word_range = max(word_upper) - min(word_upper)
            sent_range = max(sent_upper) - min(sent_upper)
            compression = sent_range / word_range if word_range > 0 else 0

            print(f"    {template:<35s}  r={corr:.3f}  compress={compression:.3f}  "
                  f"sent=[{min(sent_upper):.3f}, {max(sent_upper):.3f}]")

            role_summaries[role].append(corr)

            results[template] = {
                "role": role,
                "word_sent_correlation": corr,
                "compression_ratio": compression,
            }

    # Summary
    print(f"\n  {'=' * 70}")
    print(f"  JITTER SUMMARY")
    print(f"  {'=' * 70}")
    for role, corrs in role_summaries.items():
        print(f"    {role:>10s}: mean r={np.mean(corrs):.4f} (+-{np.std(corrs):.3f})  "
              f"range=[{min(corrs):.3f}, {max(corrs):.3f}]  n={len(corrs)}")

    return results


# ==============================================================================
# PART 4: CROSS-HIERARCHY MEETING POINTS (8 chains)
# ==============================================================================

def analyze_hierarchy_convergence():
    """Do hierarchies converge at shared superclasses?"""

    print(f"\n{'=' * 70}")
    print("  PART 4: HIERARCHY CONVERGENCE (8 chains)")
    print("=" * 70)

    chains = {
        "cat": ["kitten", "cat", "feline", "carnivore", "mammal", "animal", "creature"],
        "eagle": ["eaglet", "eagle", "raptor", "bird", "animal", "creature"],
        "whale": ["calf", "whale", "cetacean", "mammal", "animal", "creature"],
        "fish": ["trout", "fish", "seafood", "food", "thing"],
        "rock": ["pebble", "rock", "stone", "mineral", "object", "thing"],
        "flower": ["tulip", "flower", "plant", "organism", "thing"],
        "book": ["novel", "book", "publication", "document", "object", "thing"],
        "bridge": ["footbridge", "bridge", "structure", "construction", "object", "thing"],
    }

    all_words = list(set(w for chain in chains.values() for w in chain))
    all_words.sort()
    print(f"  Embedding {len(all_words)} unique words...")
    vecs = embed_texts(all_words)
    word_to_vec = {w: vecs[i] for i, w in enumerate(all_words)}

    # Pairs that share superclasses
    chain_pairs = [
        ("cat", "whale", "Both mammals"),
        ("cat", "eagle", "Both animals"),
        ("eagle", "fish", "Different animal branches"),
        ("fish", "rock", "thing convergence"),
        ("rock", "book", "Both objects"),
        ("rock", "bridge", "Both objects"),
        ("flower", "fish", "thing vs creature"),
        ("book", "bridge", "Both objects"),
    ]

    convergence_data = {}
    for name_a, name_b, desc in chain_pairs:
        chain_a = chains[name_a]
        chain_b = chains[name_b]

        shared = set(chain_a) & set(chain_b)

        print(f"\n  --- {name_a} vs {name_b} ({desc}) ---")
        print(f"    Shared terms: {shared if shared else 'none'}")

        # Key similarity points
        base_sim = cosine(word_to_vec[chain_a[0]], word_to_vec[chain_b[0]])
        mid_a = chain_a[len(chain_a) // 2]
        mid_b = chain_b[len(chain_b) // 2]
        mid_sim = cosine(word_to_vec[mid_a], word_to_vec[mid_b])
        top_sim = cosine(word_to_vec[chain_a[-1]], word_to_vec[chain_b[-1]])

        print(f"    Base ({chain_a[0]} <-> {chain_b[0]}): {base_sim:.4f}")
        print(f"    Mid  ({mid_a} <-> {mid_b}): {mid_sim:.4f}")
        print(f"    Top  ({chain_a[-1]} <-> {chain_b[-1]}): {top_sim:.4f}")

        # If shared words exist, show convergence
        if shared:
            for sw in shared:
                idx_a = chain_a.index(sw)
                idx_b = chain_b.index(sw)
                if idx_a > 0 and idx_b > 0:
                    below_a = chain_a[idx_a - 1]
                    below_b = chain_b[idx_b - 1]
                    sim_below = cosine(word_to_vec[below_a], word_to_vec[below_b])
                    print(f"    Below {sw}: {below_a} <-> {below_b} = {sim_below:.4f}")

        convergence_data[f"{name_a}_vs_{name_b}"] = {
            "base_sim": base_sim, "mid_sim": mid_sim, "top_sim": top_sim,
            "shared": list(shared),
        }

    return convergence_data


# ==============================================================================

def main():
    results = {}

    word_vecs, word_sim = analyze_isolated_words()
    results["isolated_grid_sim"] = word_sim.tolist()

    tax_results, tax_vecs = analyze_taxonomies()
    results["taxonomies"] = tax_results

    jitter_results = analyze_jitter()
    results["jitter"] = jitter_results

    convergence_results = analyze_hierarchy_convergence()
    results["convergence"] = convergence_results

    save_path = os.path.join(_project_root, "prototype", "word_isolation_large_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {save_path}")


if __name__ == "__main__":
    main()
