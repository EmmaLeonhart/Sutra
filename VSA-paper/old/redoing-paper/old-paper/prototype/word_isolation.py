"""Word Isolation & Taxonomic Jitter Analysis.

Two questions:
  1. How do the grid words relate to each other in ISOLATION (just the bare
     word, no sentence)? Does word-level similarity predict proposition-level
     similarity?
  2. When you jitter a word along its taxonomic hierarchy (dog→hound→canine→
     mammal→animal→creature), how does that propagate into propositions?
     Is the effect consistent across sentence contexts?

Usage:
    python prototype/word_isolation.py
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


# ══════════════════════════════════════════════════════════════════════════════
# PART 1: GRID WORDS IN ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

GRID_WORDS = {
    "subjects": ["cats", "trucks", "children"],
    "predicates": ["eat", "carry", "watch"],
    "objects": ["fish", "rocks", "stars"],
}


def analyze_isolated_words():
    """Embed grid words in isolation and compare to proposition-level effects."""
    print("=" * 70)
    print("  PART 1: GRID WORDS IN ISOLATION")
    print("=" * 70)

    all_words = (GRID_WORDS["subjects"] + GRID_WORDS["predicates"]
                 + GRID_WORDS["objects"])
    print(f"\n  Embedding {len(all_words)} words in isolation...")
    word_vecs = embed_texts(all_words)
    sim = pairwise_cosine(word_vecs)

    # Print full matrix
    print(f"\n  Word-level cosine similarity (bare words, no context):")
    header = "           " + "".join(f"{w:>10s}" for w in all_words)
    print(header)
    for i, w in enumerate(all_words):
        row = f"  {w:>9s}"
        for j in range(len(all_words)):
            if i == j:
                row += "       -- "
            else:
                row += f"     {sim[i, j]:.3f}"
        print(row)

    # Within-role vs across-role
    print(f"\n  Within-role vs across-role similarity:")
    for role, words in GRID_WORDS.items():
        indices = [all_words.index(w) for w in words]
        within = []
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                within.append(sim[indices[a], indices[b]])
        print(f"    {role:>11s}: mean within = {np.mean(within):.4f}  "
              f"({', '.join(f'{w:.3f}' for w in within)})")

    # Cross-role
    for r1, r2 in [("subjects", "predicates"), ("subjects", "objects"),
                    ("predicates", "objects")]:
        idx1 = [all_words.index(w) for w in GRID_WORDS[r1]]
        idx2 = [all_words.index(w) for w in GRID_WORDS[r2]]
        cross = [sim[i, j] for i in idx1 for j in idx2]
        print(f"    {r1[:4]}×{r2[:4]:>5s}: mean cross  = {np.mean(cross):.4f}  "
              f"range [{min(cross):.3f}, {max(cross):.3f}]")

    return {w: word_vecs[i] for i, w in enumerate(all_words)}, sim


# ══════════════════════════════════════════════════════════════════════════════
# PART 2: TAXONOMIC HIERARCHIES
# ══════════════════════════════════════════════════════════════════════════════

TAXONOMIES = {
    "dog_hierarchy": {
        "words": ["puppy", "dog", "hound", "canine", "mammal", "animal", "creature"],
        "description": "Specific → general for dogs",
    },
    "cat_hierarchy": {
        "words": ["kitten", "cat", "feline", "mammal", "animal", "creature"],
        "description": "Specific → general for cats",
    },
    "fish_hierarchy": {
        "words": ["trout", "fish", "seafood", "food", "thing"],
        "description": "Specific → general for fish",
    },
    "rock_hierarchy": {
        "words": ["pebble", "rock", "stone", "mineral", "object", "thing"],
        "description": "Specific → general for rocks",
    },
    "eat_synonyms": {
        "words": ["eat", "consume", "devour", "ingest", "munch"],
        "description": "Verb synonyms for eating",
    },
    "carry_synonyms": {
        "words": ["carry", "transport", "haul", "move", "bring"],
        "description": "Verb synonyms for carrying",
    },
    "watch_synonyms": {
        "words": ["watch", "observe", "view", "see", "gaze at"],
        "description": "Verb synonyms for watching",
    },
}


def analyze_taxonomies():
    """Embed taxonomic variants in isolation."""
    print(f"\n{'=' * 70}")
    print("  PART 2: TAXONOMIC HIERARCHIES — WORDS IN ISOLATION")
    print("=" * 70)

    results = {}
    all_tax_vecs = {}

    for tax_name, tax in TAXONOMIES.items():
        words = tax["words"]
        print(f"\n  --- {tax_name}: {tax['description']} ---")
        print(f"  Words: {words}")

        vecs = embed_texts(words)
        sim = pairwise_cosine(vecs)
        all_tax_vecs[tax_name] = {w: vecs[i] for i, w in enumerate(words)}

        # Print matrix
        header = "           " + "".join(f"{w:>10s}" for w in words)
        print(header)
        for i, w in enumerate(words):
            row = f"  {w:>9s}"
            for j in range(len(words)):
                if i == j:
                    row += "       -- "
                else:
                    row += f"     {sim[i, j]:.3f}"
            print(row)

        # Adjacent vs distant similarities (for hierarchies)
        if "hierarchy" in tax_name:
            adjacent = [sim[i, i + 1] for i in range(len(words) - 1)]
            print(f"  Adjacent steps: {['%.3f' % a for a in adjacent]}")
            print(f"  Adjacent mean: {np.mean(adjacent):.4f}")
            endpoints = sim[0, -1]
            print(f"  Endpoint sim ({words[0]}→{words[-1]}): {endpoints:.4f}")

        # For synonyms, show mean pairwise
        if "synonyms" in tax_name:
            upper = sim[np.triu_indices(len(words), k=1)]
            print(f"  Mean pairwise: {np.mean(upper):.4f}  "
                  f"range [{np.min(upper):.3f}, {np.max(upper):.3f}]")

        results[tax_name] = {"words": words, "sim": sim.tolist()}

    return results, all_tax_vecs


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: JITTER IN PROPOSITIONS
# ══════════════════════════════════════════════════════════════════════════════

JITTER_TEMPLATES = [
    ("{word} eat fish", "subject"),
    ("{word} carry rocks", "subject"),
    ("{word} watch stars", "subject"),
    ("Cats {word} fish", "predicate"),
    ("Trucks {word} rocks", "predicate"),
    ("Children {word} stars", "predicate"),
    ("Cats eat {word}", "object"),
    ("Trucks carry {word}", "object"),
    ("Children watch {word}", "object"),
]

JITTER_SETS = {
    "subject": {
        "hierarchy": ["puppy", "dog", "hound", "canine", "mammal", "animal", "creature"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "subject"],
    },
    "predicate": {
        "hierarchy": ["eat", "consume", "devour", "ingest", "munch"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "predicate"],
    },
    "object": {
        "hierarchy": ["trout", "fish", "seafood", "food", "thing"],
        "templates": [t for t, r in JITTER_TEMPLATES if r == "object"],
    },
}


def analyze_jitter():
    """Substitute taxonomic variants into proposition templates and measure
    whether the word-level distance predicts proposition-level distance."""

    print(f"\n{'=' * 70}")
    print("  PART 3: TAXONOMIC JITTER IN PROPOSITIONS")
    print("=" * 70)
    print("  Does swapping 'dog'→'canine'→'mammal' in a sentence shift the")
    print("  embedding proportionally to the word-level distance?\n")

    results = {}

    for role, config in JITTER_SETS.items():
        hierarchy = config["hierarchy"]
        templates = config["templates"]

        print(f"  ═══ {role.upper()} JITTER: {hierarchy} ═══\n")

        # Embed words in isolation
        word_vecs = embed_texts(hierarchy)
        word_sim = pairwise_cosine(word_vecs)

        for template in templates:
            sentences = [template.format(word=w) for w in hierarchy]
            print(f"  Template: \"{template}\"")
            print(f"  Sentences: {sentences}")

            sent_vecs = embed_texts(sentences)
            sent_sim = pairwise_cosine(sent_vecs)

            # Compare word-level and sentence-level similarity
            n = len(hierarchy)
            word_upper = []
            sent_upper = []
            labels = []
            for i in range(n):
                for j in range(i + 1, n):
                    word_upper.append(word_sim[i, j])
                    sent_upper.append(sent_sim[i, j])
                    labels.append(f"{hierarchy[i]}↔{hierarchy[j]}")

            # Correlation between word sim and sentence sim
            corr = float(np.corrcoef(word_upper, sent_upper)[0, 1])

            # Print comparison table
            print(f"\n    {'Pair':<25s} {'Word sim':>10s} {'Sent sim':>10s} {'Delta':>10s}")
            print(f"    {'-' * 55}")
            for k in range(len(labels)):
                delta = sent_upper[k] - word_upper[k]
                print(f"    {labels[k]:<25s} {word_upper[k]:>10.3f} {sent_upper[k]:>10.3f} {delta:>+10.3f}")

            print(f"\n    Word↔Sentence correlation: r={corr:.4f}")

            # How much does sentence context compress the distance?
            word_range = max(word_upper) - min(word_upper)
            sent_range = max(sent_upper) - min(sent_upper)
            compression = sent_range / word_range if word_range > 0 else 0
            print(f"    Word sim range: {min(word_upper):.3f}–{max(word_upper):.3f} "
                  f"(span {word_range:.3f})")
            print(f"    Sent sim range: {min(sent_upper):.3f}–{max(sent_upper):.3f} "
                  f"(span {sent_range:.3f})")
            print(f"    Context compression ratio: {compression:.3f}")
            print()

            results[template] = {
                "role": role,
                "hierarchy": hierarchy,
                "word_sent_correlation": corr,
                "compression_ratio": compression,
                "word_sims": word_upper,
                "sent_sims": sent_upper,
                "pairs": labels,
            }

    # Summary
    print(f"  {'=' * 70}")
    print(f"  JITTER SUMMARY")
    print(f"  {'=' * 70}")
    print(f"\n  {'Template':<35s} {'Role':>10s} {'Corr':>8s} {'Compress':>10s}")
    print(f"  {'-' * 65}")
    for template, r in results.items():
        print(f"  {template:<35s} {r['role']:>10s} {r['word_sent_correlation']:>8.3f} "
              f"{r['compression_ratio']:>10.3f}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: CROSS-HIERARCHY MEETING POINTS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_hierarchy_convergence():
    """Do dog→animal and cat→animal converge in embedding space?"""

    print(f"\n{'=' * 70}")
    print("  PART 4: HIERARCHY CONVERGENCE")
    print("=" * 70)
    print("  Do 'dog→mammal→animal' and 'cat→mammal→animal' converge at")
    print("  shared superclasses?\n")

    dog_chain = ["puppy", "dog", "hound", "canine", "mammal", "animal", "creature"]
    cat_chain = ["kitten", "cat", "feline", "mammal", "animal", "creature"]
    fish_chain = ["trout", "fish", "seafood", "food", "thing"]
    rock_chain = ["pebble", "rock", "stone", "mineral", "object", "thing"]

    chains = {
        "dog": dog_chain,
        "cat": cat_chain,
        "fish": fish_chain,
        "rock": rock_chain,
    }

    # Embed everything
    all_words = list(set(w for chain in chains.values() for w in chain))
    all_words.sort()
    print(f"  Embedding {len(all_words)} unique words...")
    vecs = embed_texts(all_words)
    word_to_vec = {w: vecs[i] for i, w in enumerate(all_words)}

    # Cross-chain similarity at each level of abstraction
    chain_pairs = [("dog", "cat"), ("fish", "rock"), ("dog", "fish"), ("cat", "rock")]

    for name_a, name_b in chain_pairs:
        chain_a = chains[name_a]
        chain_b = chains[name_b]
        print(f"\n  --- {name_a} vs {name_b} ---")
        print(f"    {name_a}: {chain_a}")
        print(f"    {name_b}: {chain_b}")

        # Pairwise sim at each level
        print(f"\n    {'Level A':<12s} {'Level B':<12s} {'Cosine':>8s} {'Shared?':>8s}")
        print(f"    {'-' * 42}")
        for wa in chain_a:
            for wb in chain_b:
                sim = cosine(word_to_vec[wa], word_to_vec[wb])
                shared = "YES" if wa == wb else ""
                if sim > 0.5 or shared:
                    print(f"    {wa:<12s} {wb:<12s} {sim:>8.3f} {shared:>8s}")

    return {}


# ══════════════════════════════════════════════════════════════════════════════

def main():
    results = {}

    word_vecs, word_sim = analyze_isolated_words()
    results["isolated_grid_sim"] = word_sim.tolist()

    tax_results, tax_vecs = analyze_taxonomies()
    results["taxonomies"] = tax_results

    jitter_results = analyze_jitter()
    results["jitter"] = {k: {kk: vv for kk, vv in v.items()
                             if kk != "word_sims" and kk != "sent_sims"}
                         for k, v in jitter_results.items()}

    analyze_hierarchy_convergence()

    save_path = os.path.join(_project_root, "prototype", "word_isolation_results.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {save_path}")


if __name__ == "__main__":
    main()
