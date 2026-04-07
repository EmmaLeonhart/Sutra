"""
Export all genuine semantic collisions to CSV.

Finds all cross-entity embedding collisions at cosine >= 0.95, classifies each
pair using the same logic as analyze_collision_types.py, and writes only the
genuine_semantic collisions to a CSV file.

Output: papers/fol-discovery/data/collisions.csv
"""

import io
import sys
import csv
import json
import re
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def normalize_text(text):
    """Normalize text for comparison: lowercase, strip punctuation/whitespace."""
    return re.sub(r'[^\w\s]', '', text.lower()).strip()


def classify_collision(text_a, text_b):
    """Classify a collision pair into categories."""
    if text_a == text_b:
        return "identical_text"

    norm_a = normalize_text(text_a)
    norm_b = normalize_text(text_b)

    if norm_a == norm_b:
        return "near_identical_text"

    if norm_a in norm_b or norm_b in norm_a:
        return "substring_overlap"

    return "genuine_semantic"


def main():
    print("=" * 60)
    print("EXPORT GENUINE SEMANTIC COLLISIONS TO CSV")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    emb_path = DATA_DIR / "embeddings.npz"
    idx_path = DATA_DIR / "embedding_index.json"
    out_path = DATA_DIR / "collisions.csv"

    if not emb_path.exists():
        print(f"ERROR: {emb_path} not found")
        sys.exit(1)

    print("Loading embeddings...")
    emb = np.load(str(emb_path))['vectors']
    with open(str(idx_path), encoding='utf-8') as f:
        index = json.load(f)

    n = len(emb)
    print(f"  {n} embeddings, {emb.shape[1]}-dim")

    # Normalize for cosine similarity
    print("Normalizing vectors...")
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_norm = emb / norms

    threshold = 0.95
    batch_size = 500

    print(f"\nFinding collisions (cosine >= {threshold})...")
    print("  (This may take a few minutes for 41k embeddings...)")

    # Open CSV for writing as we go to avoid storing all rows in memory
    csv_file = open(str(out_path), 'w', newline='', encoding='utf-8')
    writer = csv.writer(csv_file)
    writer.writerow(['qid_a', 'text_a', 'type_a', 'qid_b', 'text_b', 'type_b',
                      'cosine_similarity', 'category'])

    total_cross_entity = 0
    total_genuine = 0
    category_counts = {"identical_text": 0, "near_identical_text": 0,
                       "substring_overlap": 0, "genuine_semantic": 0}

    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        batch = emb_norm[i:end_i]

        for j in range(i, n, batch_size):
            end_j = min(j + batch_size, n)
            other = emb_norm[j:end_j]

            sims = batch @ other.T

            rows, cols = np.where(sims >= threshold)

            for r, c in zip(rows, cols):
                abs_i = i + r
                abs_j = j + c

                if abs_i >= abs_j:
                    continue

                entry_a = index[abs_i]
                entry_b = index[abs_j]

                if entry_a['qid'] == entry_b['qid']:
                    continue

                total_cross_entity += 1
                category = classify_collision(entry_a['text'], entry_b['text'])
                category_counts[category] += 1

                if category == "genuine_semantic":
                    total_genuine += 1
                    writer.writerow([
                        entry_a['qid'], entry_a['text'], entry_a['type'],
                        entry_b['qid'], entry_b['text'], entry_b['type'],
                        round(float(sims[r, c]), 6),
                        category,
                    ])

        if (i // batch_size) % 10 == 0 and i > 0:
            print(f"  Processed {end_i}/{n} embeddings... "
                  f"({total_genuine} genuine semantic so far)")

    csv_file.close()

    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"Total cross-entity collisions: {total_cross_entity:,}")
    for cat, count in category_counts.items():
        pct = count / max(total_cross_entity, 1) * 100
        print(f"  {cat:<25} {count:>10,} ({pct:.1f}%)")
    print(f"\nGenuine semantic collisions written: {total_genuine:,}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
