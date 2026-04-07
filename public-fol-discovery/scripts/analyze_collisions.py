"""
Collision and Density Analysis for Embedding Space
===================================================
Analyzes the trajectory map to find:
1. Embedding collisions — semantically unrelated entities landing near each other
2. Density classification — under/iso/oversymbolic regions
3. Trajectory consistency — do same-predicate trajectories form parallel displacements?

This is the core empirical analysis for the Claw4S submission.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
from collections import defaultdict
from itertools import combinations
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_data():
    """Load all project data."""
    emb = np.load(str(DATA_DIR / 'embeddings.npz'))['vectors']
    with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
        index = json.load(f)
    with open(str(DATA_DIR / 'items.json'), encoding='utf-8') as f:
        items = json.load(f)
    return emb, index, items


def compute_all_pairwise_similarities(emb, index, threshold=0.95):
    """Find embedding collisions: distinct entities with very high cosine similarity.
    
    A collision is when two vectors from DIFFERENT QIDs have cosine similarity
    above the threshold. Same-QID high similarity (label ≈ alias) is expected.
    """
    print(f"\n{'='*70}", flush=True)
    print(f"COLLISION DETECTION (threshold={threshold})", flush=True)
    print(f"{'='*70}", flush=True)
    
    # Normalize all vectors
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    normed = emb / (norms + 1e-10)
    
    n = len(index)
    print(f"Computing pairwise similarities for {n} vectors...", flush=True)
    
    # For large n, compute in batches to avoid memory issues
    collisions = []
    same_entity_high = []
    
    batch_size = 1000
    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        # Compute similarities of batch against all vectors after it
        sims = normed[i:end_i] @ normed.T
        
        for local_idx in range(end_i - i):
            global_idx = i + local_idx
            # Only look at upper triangle (j > global_idx)
            for j in range(global_idx + 1, n):
                sim = sims[local_idx, j]
                if sim >= threshold:
                    qid_a = index[global_idx]['qid']
                    qid_b = index[j]['qid']
                    
                    if qid_a != qid_b:
                        collisions.append({
                            'idx_a': global_idx,
                            'idx_b': j,
                            'qid_a': qid_a,
                            'qid_b': qid_b,
                            'text_a': index[global_idx]['text'],
                            'text_b': index[j]['text'],
                            'type_a': index[global_idx]['type'],
                            'type_b': index[j]['type'],
                            'similarity': float(sim),
                        })
                    else:
                        same_entity_high.append({
                            'qid': qid_a,
                            'text_a': index[global_idx]['text'],
                            'text_b': index[j]['text'],
                            'similarity': float(sim),
                        })
        
        if (i // batch_size) % 5 == 0:
            print(f"  Processed {end_i}/{n} vectors, found {len(collisions)} cross-entity collisions so far", flush=True)
    
    # Sort by similarity descending
    collisions.sort(key=lambda x: -x['similarity'])
    same_entity_high.sort(key=lambda x: -x['similarity'])
    
    print(f"\nResults:", flush=True)
    print(f"  Cross-entity collisions (sim >= {threshold}): {len(collisions)}", flush=True)
    print(f"  Same-entity high similarity: {len(same_entity_high)}", flush=True)
    
    if collisions:
        print(f"\n  TOP COLLISIONS (different entities, very similar vectors):", flush=True)
        for c in collisions[:20]:
            print(f"    {c['similarity']:.4f}  '{c['text_a']}' ({c['qid_a']}) ↔ '{c['text_b']}' ({c['qid_b']})", flush=True)
    
    return collisions, same_entity_high


def density_analysis(emb, index, k=10):
    """Compute local density for each embedding point using k-nearest-neighbor distance.
    
    Points in dense regions have small k-NN distances (oversymbolic).
    Points in sparse regions have large k-NN distances (undersymbolic).
    """
    print(f"\n{'='*70}", flush=True)
    print(f"DENSITY ANALYSIS (k={k})", flush=True)
    print(f"{'='*70}", flush=True)
    
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    normed = emb / (norms + 1e-10)
    
    n = len(index)
    knn_distances = np.zeros(n)
    
    batch_size = 500
    for i in range(0, n, batch_size):
        end_i = min(i + batch_size, n)
        sims = normed[i:end_i] @ normed.T
        
        for local_idx in range(end_i - i):
            global_idx = i + local_idx
            # Set self-similarity to -inf
            sims[local_idx, global_idx] = -np.inf
            # Get k-th highest similarity (k-th nearest neighbor)
            top_k = np.partition(sims[local_idx], -k)[-k:]
            knn_distances[global_idx] = 1.0 - np.min(top_k)  # cosine distance to k-th neighbor
        
        if (i // batch_size) % 10 == 0:
            print(f"  Processed {end_i}/{n} vectors", flush=True)
    
    # Classify into regimes
    p25 = np.percentile(knn_distances, 25)
    p75 = np.percentile(knn_distances, 75)
    
    oversymbolic = [(i, knn_distances[i]) for i in range(n) if knn_distances[i] <= p25]
    isosymbolic = [(i, knn_distances[i]) for i in range(n) if p25 < knn_distances[i] <= p75]
    undersymbolic = [(i, knn_distances[i]) for i in range(n) if knn_distances[i] > p75]
    
    print(f"\nDensity Statistics:", flush=True)
    print(f"  Mean k-NN cosine distance: {knn_distances.mean():.4f}", flush=True)
    print(f"  Min: {knn_distances.min():.4f}, Max: {knn_distances.max():.4f}", flush=True)
    print(f"  Std: {knn_distances.std():.4f}", flush=True)
    print(f"  P25: {p25:.4f}, P50: {np.median(knn_distances):.4f}, P75: {p75:.4f}", flush=True)
    
    print(f"\nRegime Classification:", flush=True)
    print(f"  Oversymbolic (dense, <= P25):    {len(oversymbolic)} points", flush=True)
    print(f"  Isosymbolic  (moderate):         {len(isosymbolic)} points", flush=True)
    print(f"  Undersymbolic (sparse, > P75):   {len(undersymbolic)} points", flush=True)
    
    # Show examples from each regime
    print(f"\n  MOST DENSE (oversymbolic candidates):", flush=True)
    for idx, dist in sorted(oversymbolic, key=lambda x: x[1])[:10]:
        print(f"    kNN_dist={dist:.4f}  '{index[idx]['text']}' ({index[idx]['qid']})", flush=True)
    
    print(f"\n  MOST SPARSE (undersymbolic candidates):", flush=True)
    for idx, dist in sorted(undersymbolic, key=lambda x: -x[1])[:10]:
        print(f"    kNN_dist={dist:.4f}  '{index[idx]['text']}' ({index[idx]['qid']})", flush=True)
    
    return knn_distances, oversymbolic, isosymbolic, undersymbolic


def trajectory_consistency(emb, index, items):
    """Analyze whether same-predicate trajectories produce consistent displacement vectors.

    If P31 (instance of) consistently produces similar displacement vectors,
    that's an isosymbolic operation — the graph relationship has a faithful
    geometric counterpart in the embedding space.
    """
    print(f"\n{'='*70}", flush=True)
    print(f"TRAJECTORY CONSISTENCY ANALYSIS", flush=True)
    print(f"{'='*70}", flush=True)
    
    # Build QID -> label vector index
    qid_to_vec = {}
    for i, entry in enumerate(index):
        if entry['type'] == 'label':
            qid_to_vec[entry['qid']] = emb[i]
    
    # Collect displacement vectors per predicate
    predicate_displacements = defaultdict(list)
    predicate_distances = defaultdict(list)
    
    for item in items:
        subj_qid = item['qid']
        if subj_qid not in qid_to_vec:
            continue
        subj_vec = qid_to_vec[subj_qid]
        
        for triple in item['triples']:
            if triple['value']['type'] != 'wikibase-item':
                continue
            obj_qid = triple['value']['value']
            if obj_qid not in qid_to_vec:
                continue
            obj_vec = qid_to_vec[obj_qid]
            
            pred = triple['predicate']
            displacement = obj_vec - subj_vec
            cos_sim = float(np.dot(subj_vec, obj_vec) / (
                np.linalg.norm(subj_vec) * np.linalg.norm(obj_vec) + 1e-10
            ))
            
            predicate_displacements[pred].append(displacement)
            predicate_distances[pred].append(1.0 - cos_sim)
    
    # Analyze consistency for predicates with enough samples
    print(f"\nPredicates with displacement vectors: {len(predicate_displacements)}", flush=True)
    
    results = []
    for pred, displacements in predicate_displacements.items():
        if len(displacements) < 5:
            continue
        
        displacements = np.array(displacements)
        distances = predicate_distances[pred]
        
        # Mean displacement vector
        mean_disp = displacements.mean(axis=0)
        mean_disp_norm = mean_disp / (np.linalg.norm(mean_disp) + 1e-10)
        
        # Consistency: how aligned are individual displacements with the mean?
        norms = np.linalg.norm(displacements, axis=1, keepdims=True)
        normed_disp = displacements / (norms + 1e-10)
        alignments = normed_disp @ mean_disp_norm
        
        mean_alignment = float(alignments.mean())
        std_alignment = float(alignments.std())
        mean_distance = float(np.mean(distances))
        
        results.append({
            'predicate': pred,
            'count': len(displacements),
            'mean_alignment': mean_alignment,
            'std_alignment': std_alignment,
            'mean_cosine_distance': mean_distance,
        })
    
    results.sort(key=lambda x: -x['mean_alignment'])
    
    print(f"\nPredicate Consistency (min 5 triples, sorted by alignment):", flush=True)
    print(f"  {'Predicate':<12} {'Count':>6} {'Alignment':>10} {'Std':>8} {'MeanDist':>10}", flush=True)
    print(f"  {'-'*50}", flush=True)
    
    for r in results[:30]:
        print(f"  {r['predicate']:<12} {r['count']:>6} {r['mean_alignment']:>10.4f} {r['std_alignment']:>8.4f} {r['mean_cosine_distance']:>10.4f}", flush=True)
    
    # Highlight predicates with high consistency (potential isosymbolic operations)
    iso_candidates = [r for r in results if r['mean_alignment'] > 0.5 and r['count'] >= 10]
    print(f"\n  Isosymbolic operation candidates (alignment > 0.5, n >= 10): {len(iso_candidates)}", flush=True)
    for r in iso_candidates:
        print(f"    {r['predicate']}: alignment={r['mean_alignment']:.4f}, n={r['count']}", flush=True)
    
    return results


def summary_stats(emb, index, items):
    """Print overall dataset statistics."""
    print(f"\n{'='*70}", flush=True)
    print(f"DATASET SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    
    full_items = [i for i in items if i['triples']]
    total_triples = sum(len(i['triples']) for i in items)
    wikibase_triples = sum(
        sum(1 for t in i['triples'] if t['value']['type'] == 'wikibase-item')
        for i in items
    )
    
    labels = sum(1 for e in index if e['type'] == 'label')
    aliases = sum(1 for e in index if e['type'] == 'alias')
    
    # Unique QIDs
    unique_qids = set(e['qid'] for e in index)
    
    print(f"  Items: {len(items)} total, {len(full_items)} fully imported", flush=True)
    print(f"  Unique QIDs with embeddings: {len(unique_qids)}", flush=True)
    print(f"  Embeddings: {emb.shape[0]} ({labels} labels, {aliases} aliases)", flush=True)
    print(f"  Embedding dimensions: {emb.shape[1]}", flush=True)
    print(f"  Total triples: {total_triples} ({wikibase_triples} entity-entity)", flush=True)
    
    # Predicate distribution
    pred_counts = defaultdict(int)
    for item in items:
        for t in item['triples']:
            pred_counts[t['predicate']] += 1
    
    print(f"  Unique predicates used: {len(pred_counts)}", flush=True)
    print(f"\n  Top 15 predicates:", flush=True)
    for pred, count in sorted(pred_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {pred}: {count}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Analyze embedding space collisions and density")
    parser.add_argument('--threshold', type=float, default=0.95, help='Collision similarity threshold')
    parser.add_argument('--k', type=int, default=10, help='k for k-NN density analysis')
    parser.add_argument('--skip-collisions', action='store_true', help='Skip pairwise collision detection')
    parser.add_argument('--output', default=str(DATA_DIR / 'analysis_results.json'), help='Output file')
    args = parser.parse_args()
    
    emb, index, items = load_data()
    
    # Summary
    summary_stats(emb, index, items)
    
    # Collision detection
    if not args.skip_collisions:
        collisions, same_entity = compute_all_pairwise_similarities(emb, index, args.threshold)
    else:
        collisions, same_entity = [], []
    
    # Density analysis
    knn_distances, oversymbolic, isosymbolic, undersymbolic = density_analysis(emb, index, args.k)
    
    # Trajectory consistency
    consistency = trajectory_consistency(emb, index, items)
    
    # Save results
    results = {
        'dataset': {
            'items': len(items),
            'embeddings': emb.shape[0],
            'dimensions': emb.shape[1],
        },
        'collisions': {
            'threshold': args.threshold,
            'cross_entity': len(collisions),
            'same_entity': len(same_entity),
            'top_collisions': collisions[:50],
        },
        'density': {
            'k': args.k,
            'mean_knn_distance': float(knn_distances.mean()),
            'std_knn_distance': float(knn_distances.std()),
            'min': float(knn_distances.min()),
            'max': float(knn_distances.max()),
            'oversymbolic_count': len(oversymbolic),
            'isosymbolic_count': len(isosymbolic),
            'undersymbolic_count': len(undersymbolic),
        },
        'consistency': consistency[:30],
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to {args.output}", flush=True)
    print("Done!", flush=True)


if __name__ == '__main__':
    main()
