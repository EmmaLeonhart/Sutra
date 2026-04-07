"""
Analyze collision types: separate trivial (same-text) from genuine semantic collisions.

The raw collision count (164,084 at cosine >= 0.95) includes many cases where
different Wikidata entities share the exact same label or alias text. These are
trivially expected to collide. The interesting collisions are between
*semantically different* texts that the embedding model maps to near-identical vectors.

Categories:
1. IDENTICAL TEXT — same string, different QIDs (trivial, expected)
2. NEAR-IDENTICAL TEXT — minor variations (case, punctuation, suffixes)
3. GENUINE SEMANTIC — different text, high embedding similarity (oversymbolic)
4. CROSS-TYPE — label vs alias collisions on different entities

Output: papers/fol-discovery/data/collision_analysis.json
"""

import io
import sys
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def normalize_text(text):
    """Normalize text for comparison: lowercase, strip punctuation/whitespace."""
    return re.sub(r'[^\w\s]', '', text.lower()).strip()


def classify_collision(text_a, text_b, type_a, type_b):
    """Classify a collision pair into categories."""
    if text_a == text_b:
        return "identical_text"

    norm_a = normalize_text(text_a)
    norm_b = normalize_text(text_b)

    if norm_a == norm_b:
        return "near_identical_text"

    # Check if one is a substring of the other (common with aliases)
    if norm_a in norm_b or norm_b in norm_a:
        return "substring_overlap"

    return "genuine_semantic"


def main():
    print("=" * 60)
    print("COLLISION TYPE ANALYSIS")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Load embeddings and index
    emb_path = DATA_DIR / "embeddings.npz"
    idx_path = DATA_DIR / "embedding_index.json"
    items_path = DATA_DIR / "items.json"

    if not emb_path.exists():
        print(f"ERROR: {emb_path} not found")
        sys.exit(1)

    print("Loading embeddings...")
    emb = np.load(str(emb_path))['vectors']
    with open(str(idx_path), encoding='utf-8') as f:
        index = json.load(f)

    print(f"  {len(emb)} embeddings, {emb.shape[1]}-dim")

    # Normalize for cosine similarity
    print("Normalizing vectors...")
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_norm = emb / norms

    # Find collisions at threshold 0.95
    threshold = 0.95
    print(f"\nFinding collisions (cosine >= {threshold})...")
    print("  (This may take a few minutes for 41k embeddings...)")

    # Use batched approach for memory efficiency
    batch_size = 500
    n = len(emb_norm)

    categories = Counter()
    genuine_examples = []
    identical_examples = []
    near_identical_examples = []
    substring_examples = []

    total_cross_entity = 0
    total_same_entity = 0

    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        batch = emb_norm[i:end_i]

        # Only compare with vectors after this batch (avoid double-counting)
        for j in range(i, n, batch_size):
            end_j = min(j + batch_size, n)
            other = emb_norm[j:end_j]

            sims = batch @ other.T

            # Find pairs above threshold
            rows, cols = np.where(sims >= threshold)

            for r, c in zip(rows, cols):
                abs_i = i + r
                abs_j = j + c

                if abs_i >= abs_j:  # Skip self-pairs and duplicates
                    continue

                entry_a = index[abs_i]
                entry_b = index[abs_j]
                qid_a = entry_a['qid']
                qid_b = entry_b['qid']
                text_a = entry_a['text']
                text_b = entry_b['text']
                type_a = entry_a['type']
                type_b = entry_b['type']
                sim = float(sims[r, c])

                if qid_a == qid_b:
                    total_same_entity += 1
                    continue

                total_cross_entity += 1
                category = classify_collision(text_a, text_b, type_a, type_b)
                categories[category] += 1

                example = {
                    "qid_a": qid_a, "qid_b": qid_b,
                    "text_a": text_a, "text_b": text_b,
                    "type_a": type_a, "type_b": type_b,
                    "similarity": round(sim, 6),
                    "category": category,
                }

                if category == "genuine_semantic" and len(genuine_examples) < 50:
                    genuine_examples.append(example)
                elif category == "identical_text" and len(identical_examples) < 10:
                    identical_examples.append(example)
                elif category == "near_identical_text" and len(near_identical_examples) < 10:
                    near_identical_examples.append(example)
                elif category == "substring_overlap" and len(substring_examples) < 10:
                    substring_examples.append(example)

        if (i // batch_size) % 10 == 0 and i > 0:
            print(f"  Processed {end_i}/{n} embeddings... ({total_cross_entity} cross-entity collisions so far)")

    # Sort genuine examples by similarity (most interesting first)
    genuine_examples.sort(key=lambda x: x["similarity"], reverse=True)

    results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "threshold": threshold,
            "total_embeddings": n,
            "total_cross_entity_collisions": total_cross_entity,
            "total_same_entity_collisions": total_same_entity,
        },
        "categories": dict(categories),
        "category_percentages": {
            k: round(v / max(total_cross_entity, 1) * 100, 1)
            for k, v in categories.items()
        },
        "examples": {
            "genuine_semantic": genuine_examples[:20],
            "identical_text": identical_examples[:5],
            "near_identical_text": near_identical_examples[:5],
            "substring_overlap": substring_examples[:5],
        },
    }

    # Save
    output_path = DATA_DIR / "collision_analysis.json"
    with open(str(output_path), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"COLLISION TYPE BREAKDOWN (threshold >= {threshold})")
    print(f"{'=' * 60}")
    print(f"Total cross-entity collisions: {total_cross_entity:,}")
    print(f"Total same-entity collisions:  {total_same_entity:,}")
    print()
    print(f"{'Category':<25} {'Count':>10} {'Percent':>10}")
    print("-" * 50)
    for cat in ["identical_text", "near_identical_text", "substring_overlap", "genuine_semantic"]:
        count = categories.get(cat, 0)
        pct = count / max(total_cross_entity, 1) * 100
        print(f"{cat:<25} {count:>10,} {pct:>9.1f}%")

    print(f"\n{'=' * 60}")
    print("GENUINE SEMANTIC COLLISIONS (different text, high similarity)")
    print(f"{'=' * 60}")
    for ex in genuine_examples[:15]:
        print(f"  cos={ex['similarity']:.4f}  \"{ex['text_a']}\" ({ex['qid_a']}) <-> \"{ex['text_b']}\" ({ex['qid_b']})")

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
