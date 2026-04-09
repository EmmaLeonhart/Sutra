"""
Measure the geometric separation between colliding (undersymbolic) embeddings
and the well-structured (isosymbolic) zone.

Key questions:
1. How far are colliding embeddings from non-colliding ones?
2. Are colliding embeddings in sparse or dense regions?
3. What's the distance from the collapse zone to the isosymbolic centroid?
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main():
    # Load data
    emb = np.load(str(DATA_DIR / 'embeddings.npz'))['vectors']
    with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
        index = json.load(f)
    with open(str(DATA_DIR / 'analysis_results.json'), encoding='utf-8') as f:
        results = json.load(f)

    n = len(index)
    print(f"Total embeddings: {n}")
    print(f"Dimensions: {emb.shape[1]}")

    # Normalize
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    normed = emb / (norms + 1e-10)

    # --- Identify colliding indices ---
    # We need to recompute collisions to get all indices, or use the CSV
    # For now, use top collisions from results + recompute
    print("\nIdentifying colliding embeddings (cosine >= 0.95)...")

    colliding_indices = set()
    # Load from collisions CSV if available
    csv_path = DATA_DIR / 'collisions.csv'
    if csv_path.exists():
        import csv
        with open(str(csv_path), encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # We need the index positions, not QIDs
                # Build a text->index lookup
                pass

    # Build text+type -> index mapping
    text_type_to_idx = {}
    for i, entry in enumerate(index):
        key = (entry['text'], entry['type'], entry['qid'])
        text_type_to_idx[key] = i

    # Use the top collisions from results to get colliding indices
    for c in results['collisions']['top_collisions']:
        colliding_indices.add(c['idx_a'])
        colliding_indices.add(c['idx_b'])

    # But we only have 50 top collisions. Let's recompute to find ALL colliding indices.
    print("Computing all colliding indices (batched)...")
    batch_size = 1000
    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        sims = normed[i:end_i] @ normed.T

        for local_idx in range(end_i - i):
            global_idx = i + local_idx
            # Check if this point collides with any OTHER entity
            for j in range(global_idx + 1, n):
                if sims[local_idx, j] >= 0.95:
                    qid_a = index[global_idx]['qid']
                    qid_b = index[j]['qid']
                    if qid_a != qid_b:
                        colliding_indices.add(global_idx)
                        colliding_indices.add(j)

        if (i // batch_size) % 10 == 0:
            print(f"  {end_i}/{n} processed, {len(colliding_indices)} colliding indices so far")

    colliding_indices = sorted(colliding_indices)
    non_colliding_indices = sorted(set(range(n)) - set(colliding_indices))

    print(f"\nColliding embeddings: {len(colliding_indices)}")
    print(f"Non-colliding embeddings: {len(non_colliding_indices)}")

    # --- Compute k-NN distances for both groups ---
    print("\nComputing k-NN distances (k=10)...")
    k = 10
    knn_distances = np.zeros(n)

    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        sims = normed[i:end_i] @ normed.T
        for local_idx in range(end_i - i):
            global_idx = i + local_idx
            sims[local_idx, global_idx] = -np.inf
            top_k = np.partition(sims[local_idx], -k)[-k:]
            knn_distances[global_idx] = 1.0 - np.min(top_k)
        if (i // batch_size) % 10 == 0:
            print(f"  {end_i}/{n}")

    colliding_knn = knn_distances[colliding_indices]
    non_colliding_knn = knn_distances[non_colliding_indices]

    print(f"\n{'='*60}")
    print(f"K-NN DISTANCES (k={k})")
    print(f"{'='*60}")
    print(f"  Colliding embeddings:")
    print(f"    Mean k-NN distance: {colliding_knn.mean():.6f}")
    print(f"    Median:             {np.median(colliding_knn):.6f}")
    print(f"    Std:                {colliding_knn.std():.6f}")
    print(f"    Min: {colliding_knn.min():.6f}, Max: {colliding_knn.max():.6f}")
    print(f"  Non-colliding embeddings:")
    print(f"    Mean k-NN distance: {non_colliding_knn.mean():.6f}")
    print(f"    Median:             {np.median(non_colliding_knn):.6f}")
    print(f"    Std:                {non_colliding_knn.std():.6f}")
    print(f"    Min: {non_colliding_knn.min():.6f}, Max: {non_colliding_knn.max():.6f}")
    print(f"  Ratio (colliding/non-colliding mean): {colliding_knn.mean() / non_colliding_knn.mean():.3f}x")

    # --- Distance to nearest NON-colliding neighbor ---
    print(f"\n{'='*60}")
    print(f"DISTANCE FROM COLLIDING TO NEAREST NON-COLLIDING NEIGHBOR")
    print(f"{'='*60}")

    non_colliding_vecs = normed[non_colliding_indices]
    colliding_vecs = normed[colliding_indices]

    # For each colliding embedding, find distance to nearest non-colliding
    dist_to_non_colliding = []
    batch = 500
    for i in range(0, len(colliding_indices), batch):
        end_i = min(i + batch, len(colliding_indices))
        sims = colliding_vecs[i:end_i] @ non_colliding_vecs.T
        max_sims = sims.max(axis=1)
        dist_to_non_colliding.extend((1.0 - max_sims).tolist())
        if (i // batch) % 5 == 0:
            print(f"  {end_i}/{len(colliding_indices)}")

    dist_to_non_colliding = np.array(dist_to_non_colliding)

    # For comparison: distance from non-colliding to nearest OTHER non-colliding
    print("\nComputing non-colliding to non-colliding distances for comparison...")
    dist_non_to_non = []
    sample_size = min(5000, len(non_colliding_indices))
    sample_idx = np.random.choice(len(non_colliding_indices), sample_size, replace=False)
    sampled_vecs = non_colliding_vecs[sample_idx]

    for i in range(0, sample_size, batch):
        end_i = min(i + batch, sample_size)
        sims = sampled_vecs[i:end_i] @ non_colliding_vecs.T
        # Zero out self-similarities
        for local_idx in range(end_i - i):
            global_in_non_colliding = sample_idx[i + local_idx]
            sims[local_idx, global_in_non_colliding] = -np.inf
        max_sims = sims.max(axis=1)
        dist_non_to_non.extend((1.0 - max_sims).tolist())

    dist_non_to_non = np.array(dist_non_to_non)

    print(f"\n  Colliding → nearest non-colliding:")
    print(f"    Mean distance: {dist_to_non_colliding.mean():.6f}")
    print(f"    Median:        {np.median(dist_to_non_colliding):.6f}")
    print(f"    Std:           {dist_to_non_colliding.std():.6f}")
    print(f"  Non-colliding → nearest other non-colliding:")
    print(f"    Mean distance: {dist_non_to_non.mean():.6f}")
    print(f"    Median:        {np.median(dist_non_to_non):.6f}")
    print(f"    Std:           {dist_non_to_non.std():.6f}")
    print(f"  Ratio: {dist_to_non_colliding.mean() / dist_non_to_non.mean():.3f}x")

    # --- Centroid analysis ---
    print(f"\n{'='*60}")
    print(f"CENTROID ANALYSIS")
    print(f"{'='*60}")

    # Isosymbolic centroid = centroid of non-colliding embeddings
    iso_centroid = non_colliding_vecs.mean(axis=0)
    iso_centroid_norm = iso_centroid / (np.linalg.norm(iso_centroid) + 1e-10)

    # Colliding centroid
    col_centroid = colliding_vecs.mean(axis=0)
    col_centroid_norm = col_centroid / (np.linalg.norm(col_centroid) + 1e-10)

    # Distance from each group to isosymbolic centroid
    col_to_iso_centroid = 1.0 - (colliding_vecs @ iso_centroid_norm)
    non_to_iso_centroid = 1.0 - (non_colliding_vecs @ iso_centroid_norm)

    print(f"  Distance to non-colliding centroid:")
    print(f"    Colliding mean:     {col_to_iso_centroid.mean():.6f}")
    print(f"    Non-colliding mean: {non_to_iso_centroid.mean():.6f}")
    print(f"    Ratio:              {col_to_iso_centroid.mean() / non_to_iso_centroid.mean():.3f}x")

    # Centroid-to-centroid distance
    centroid_sim = float(np.dot(iso_centroid_norm, col_centroid_norm))
    print(f"\n  Centroid-to-centroid cosine similarity: {centroid_sim:.6f}")
    print(f"  Centroid-to-centroid cosine distance:   {1.0 - centroid_sim:.6f}")

    # --- Regime membership of colliding points ---
    print(f"\n{'='*60}")
    print(f"REGIME MEMBERSHIP OF COLLIDING EMBEDDINGS")
    print(f"{'='*60}")

    p25 = np.percentile(knn_distances, 25)
    p75 = np.percentile(knn_distances, 75)

    col_oversymbolic = sum(1 for d in colliding_knn if d <= p25)
    col_isosymbolic = sum(1 for d in colliding_knn if p25 < d <= p75)
    col_undersymbolic = sum(1 for d in colliding_knn if d > p75)

    total_col = len(colliding_indices)
    print(f"  P25 threshold: {p25:.6f}")
    print(f"  P75 threshold: {p75:.6f}")
    print(f"  Colliding embeddings in each regime:")
    print(f"    Oversymbolic (dense):  {col_oversymbolic} ({100*col_oversymbolic/total_col:.1f}%)")
    print(f"    Isosymbolic (moderate): {col_isosymbolic} ({100*col_isosymbolic/total_col:.1f}%)")
    print(f"    Undersymbolic (sparse): {col_undersymbolic} ({100*col_undersymbolic/total_col:.1f}%)")

    # Expected if uniformly distributed: 25%, 50%, 25%
    print(f"  Expected if uniform: 25%, 50%, 25%")

    # --- Save results ---
    output = {
        'colliding_count': len(colliding_indices),
        'non_colliding_count': len(non_colliding_indices),
        'knn_distances': {
            'colliding_mean': float(colliding_knn.mean()),
            'colliding_median': float(np.median(colliding_knn)),
            'colliding_std': float(colliding_knn.std()),
            'non_colliding_mean': float(non_colliding_knn.mean()),
            'non_colliding_median': float(np.median(non_colliding_knn)),
            'non_colliding_std': float(non_colliding_knn.std()),
            'ratio': float(colliding_knn.mean() / non_colliding_knn.mean()),
        },
        'nearest_non_colliding': {
            'colliding_to_non_colliding_mean': float(dist_to_non_colliding.mean()),
            'colliding_to_non_colliding_median': float(np.median(dist_to_non_colliding)),
            'non_colliding_to_non_colliding_mean': float(dist_non_to_non.mean()),
            'non_colliding_to_non_colliding_median': float(np.median(dist_non_to_non)),
            'ratio': float(dist_to_non_colliding.mean() / dist_non_to_non.mean()),
        },
        'centroid_analysis': {
            'colliding_to_iso_centroid_mean': float(col_to_iso_centroid.mean()),
            'non_colliding_to_iso_centroid_mean': float(non_to_iso_centroid.mean()),
            'ratio': float(col_to_iso_centroid.mean() / non_to_iso_centroid.mean()),
            'centroid_to_centroid_cosine_distance': float(1.0 - centroid_sim),
        },
        'regime_membership': {
            'p25': float(p25),
            'p75': float(p75),
            'colliding_oversymbolic': col_oversymbolic,
            'colliding_isosymbolic': col_isosymbolic,
            'colliding_undersymbolic': col_undersymbolic,
            'colliding_oversymbolic_pct': float(100*col_oversymbolic/total_col),
            'colliding_isosymbolic_pct': float(100*col_isosymbolic/total_col),
            'colliding_undersymbolic_pct': float(100*col_undersymbolic/total_col),
        },
    }

    out_path = DATA_DIR / 'collapse_geometry.json'
    with open(str(out_path), 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
