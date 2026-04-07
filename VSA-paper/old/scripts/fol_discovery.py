"""
First-Order Logic Discovery in Embedding Spaces
=================================================
Given an arbitrary embedding space and a knowledge base of ground-truth
triples (from Wikidata), discover which first-order logical operations
are latently encoded as vector arithmetic.

This is the core contribution: we don't BUILD an embedding space for logic.
We DISCOVER logic that's already there.

The program:
1. Computes displacement vectors for each predicate's triples
2. Tests consistency (are displacements parallel? → discovered operation)
3. Validates by prediction (given A + displacement, do we land on B?)
4. Tests composition (can we chain operations? A→B→C as A + d1 + d2 → C?)
5. Characterizes failure modes (which predicates DON'T encode as operations?)

Usage:
  python fol_discovery.py                    # full analysis
  python fol_discovery.py --predict          # prediction evaluation only
  python fol_discovery.py --compose          # composition test only
  python fol_discovery.py --min-triples 20   # require more evidence per predicate
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
from collections import defaultdict
import argparse
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("FOL_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))


def load_data():
    """Load all project data."""
    emb = np.load(str(DATA_DIR / 'embeddings.npz'))['vectors']
    with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
        index = json.load(f)
    with open(str(DATA_DIR / 'items.json'), encoding='utf-8') as f:
        items = json.load(f)

    # Load property labels for readable output
    try:
        with open(str(DATA_DIR / 'properties.json'), encoding='utf-8') as f:
            properties = json.load(f)
    except FileNotFoundError:
        properties = {}
    
    return emb, index, items, properties


def build_qid_to_label_vec(emb, index):
    """Map QID → (label_embedding_vector, vector_index)."""
    qid_map = {}
    for i, entry in enumerate(index):
        if entry['type'] == 'label' and entry['qid'] not in qid_map:
            qid_map[entry['qid']] = (emb[i], i)
    return qid_map


def get_property_label(pid, properties):
    """Get human-readable label for a property ID."""
    if pid in properties:
        p = properties[pid]
        if isinstance(p, dict):
            return p.get('label', pid)
        return pid
    return pid


def discover_operations(emb, index, items, properties, min_triples=10):
    """Discover which predicates encode as consistent vector operations.
    
    For each predicate with enough triples:
    1. Compute displacement vectors (object_vec - subject_vec) for all triples
    2. Compute mean displacement (the "operation vector")
    3. Measure consistency: how aligned are individual displacements with the mean?
    4. A high-consistency predicate = a discovered FOL operation
    
    Returns list of discovered operations sorted by consistency.
    """
    print(f"\n{'='*70}", flush=True)
    print(f"PHASE 1: OPERATION DISCOVERY", flush=True)
    print(f"Finding predicates that encode as consistent vector arithmetic", flush=True)
    print(f"{'='*70}", flush=True)
    
    qid_map = build_qid_to_label_vec(emb, index)
    
    # Collect displacement vectors per predicate
    predicate_data = defaultdict(lambda: {
        'displacements': [], 'triples': [], 'distances': []
    })
    
    for item in items:
        subj_qid = item['qid']
        if subj_qid not in qid_map:
            continue
        subj_vec, _ = qid_map[subj_qid]
        
        for triple in item['triples']:
            if triple['value']['type'] != 'wikibase-item':
                continue
            obj_qid = triple['value']['value']
            if obj_qid not in qid_map:
                continue
            obj_vec, _ = qid_map[obj_qid]
            
            pred = triple['predicate']
            displacement = obj_vec - subj_vec
            cos_sim = float(np.dot(subj_vec, obj_vec) / (
                np.linalg.norm(subj_vec) * np.linalg.norm(obj_vec) + 1e-10
            ))
            
            predicate_data[pred]['displacements'].append(displacement)
            predicate_data[pred]['triples'].append((subj_qid, obj_qid))
            predicate_data[pred]['distances'].append(1.0 - cos_sim)
    
    # Analyze each predicate
    operations = []
    
    for pred, data in predicate_data.items():
        if len(data['displacements']) < min_triples:
            continue
        
        displacements = np.array(data['displacements'])
        n = len(displacements)
        
        # Mean displacement vector = the discovered operation
        mean_disp = displacements.mean(axis=0)
        mean_disp_magnitude = np.linalg.norm(mean_disp)
        
        if mean_disp_magnitude < 1e-10:
            continue
        
        mean_disp_unit = mean_disp / mean_disp_magnitude
        
        # Consistency: alignment of each displacement with the mean
        norms = np.linalg.norm(displacements, axis=1, keepdims=True)
        normed_disp = displacements / (norms + 1e-10)
        alignments = normed_disp @ mean_disp_unit
        
        # Magnitude consistency: how similar are the magnitudes?
        magnitudes = norms.flatten()
        magnitude_cv = magnitudes.std() / (magnitudes.mean() + 1e-10)  # coefficient of variation
        
        # Pairwise consistency: how similar are all displacements to each other?
        pairwise_sims = normed_disp @ normed_disp.T
        # Get upper triangle (excluding diagonal)
        triu_mask = np.triu_indices(n, k=1)
        pairwise_mean = float(pairwise_sims[triu_mask].mean()) if n > 1 else 0.0
        
        label = get_property_label(pred, properties)
        
        operations.append({
            'predicate': pred,
            'label': label,
            'n_triples': n,
            'mean_alignment': float(alignments.mean()),
            'std_alignment': float(alignments.std()),
            'min_alignment': float(alignments.min()),
            'pairwise_consistency': pairwise_mean,
            'mean_magnitude': float(magnitudes.mean()),
            'magnitude_cv': float(magnitude_cv),
            'mean_cosine_distance': float(np.mean(data['distances'])),
            'operation_vector': mean_disp,  # keep for prediction
            'triples': data['triples'],
        })
    
    operations.sort(key=lambda x: -x['mean_alignment'])
    
    # Report
    strong = [op for op in operations if op['mean_alignment'] > 0.7]
    moderate = [op for op in operations if 0.5 < op['mean_alignment'] <= 0.7]
    weak = [op for op in operations if op['mean_alignment'] <= 0.5]
    
    print(f"\nAnalyzed {len(operations)} predicates (min {min_triples} triples each)", flush=True)
    print(f"  Strong operations (alignment > 0.7):   {len(strong)}", flush=True)
    print(f"  Moderate operations (0.5 - 0.7):       {len(moderate)}", flush=True)
    print(f"  Weak/no operation (< 0.5):             {len(weak)}", flush=True)
    
    print(f"\n  TOP DISCOVERED OPERATIONS:", flush=True)
    print(f"  {'Predicate':<10} {'Label':<40} {'N':>5} {'Align':>7} {'PairCon':>8} {'MagCV':>7} {'Dist':>6}", flush=True)
    print(f"  {'-'*85}", flush=True)
    
    for op in operations[:40]:
        label_trunc = op['label'][:38] if len(op['label']) > 38 else op['label']
        print(f"  {op['predicate']:<10} {label_trunc:<40} {op['n_triples']:>5} "
              f"{op['mean_alignment']:>7.4f} {op['pairwise_consistency']:>8.4f} "
              f"{op['magnitude_cv']:>7.3f} {op['mean_cosine_distance']:>6.3f}", flush=True)
    
    return operations


def prediction_evaluation(operations, emb, index, items, properties, top_k_values=[1, 5, 10, 50]):
    """Test: can we predict the object of a triple using the discovered operation?
    
    For each triple (S, P, O):
    - Compute predicted_O = S_vec + operation_vector_P
    - Find nearest neighbors to predicted_O
    - Check if actual O is in top-k
    
    Uses leave-one-out: the operation vector is computed excluding the test triple.
    """
    print(f"\n{'='*70}", flush=True)
    print(f"PHASE 2: PREDICTION EVALUATION", flush=True)
    print(f"Can discovered operations predict unknown triples?", flush=True)
    print(f"{'='*70}", flush=True)
    
    qid_map = build_qid_to_label_vec(emb, index)
    
    # Build reverse index: vector_index → qid
    vec_to_qid = {}
    for i, entry in enumerate(index):
        if entry['type'] == 'label':
            vec_to_qid[i] = entry['qid']
    
    # Get all label vectors for nearest-neighbor search
    label_indices = [i for i, e in enumerate(index) if e['type'] == 'label']
    label_vecs = emb[label_indices]
    label_norms = np.linalg.norm(label_vecs, axis=1, keepdims=True)
    label_normed = label_vecs / (label_norms + 1e-10)
    label_qids = [index[i]['qid'] for i in label_indices]
    
    max_k = max(top_k_values)
    
    results_by_predicate = []
    
    # Test strong and moderate operations
    test_ops = [op for op in operations if op['mean_alignment'] > 0.5 and op['n_triples'] >= 10]
    
    print(f"\nTesting {len(test_ops)} operations with alignment > 0.5", flush=True)
    
    for op in test_ops:
        pred = op['predicate']
        triples = op['triples']
        all_displacements = []
        
        # Recompute displacements for leave-one-out
        for subj_qid, obj_qid in triples:
            if subj_qid in qid_map and obj_qid in qid_map:
                s_vec = qid_map[subj_qid][0]
                o_vec = qid_map[obj_qid][0]
                all_displacements.append(o_vec - s_vec)
        
        if len(all_displacements) < 5:
            continue
        
        all_displacements = np.array(all_displacements)
        
        hits = {k: 0 for k in top_k_values}
        mean_rank = 0
        reciprocal_rank_sum = 0
        tested = 0
        
        for i, (subj_qid, obj_qid) in enumerate(triples):
            if subj_qid not in qid_map or obj_qid not in qid_map:
                continue
            
            s_vec = qid_map[subj_qid][0]
            
            # Leave-one-out: mean displacement excluding this triple
            loo_displacements = np.delete(all_displacements, i, axis=0)
            loo_mean = loo_displacements.mean(axis=0)
            
            # Predict: subject + operation = predicted object
            predicted = s_vec + loo_mean
            predicted_norm = predicted / (np.linalg.norm(predicted) + 1e-10)
            
            # Find nearest neighbors
            sims = label_normed @ predicted_norm
            ranking = np.argsort(-sims)
            
            # Find rank of actual object
            try:
                obj_idx_in_labels = label_qids.index(obj_qid)
                rank = np.where(ranking == obj_idx_in_labels)[0][0] + 1
            except (ValueError, IndexError):
                rank = len(label_qids) + 1
            
            for k in top_k_values:
                if rank <= k:
                    hits[k] += 1
            
            mean_rank += rank
            reciprocal_rank_sum += 1.0 / rank
            tested += 1
        
        if tested == 0:
            continue
        
        result = {
            'predicate': pred,
            'label': op['label'],
            'n_tested': tested,
            'alignment': op['mean_alignment'],
            'mrr': reciprocal_rank_sum / tested,
            'mean_rank': mean_rank / tested,
        }
        for k in top_k_values:
            result[f'hits_at_{k}'] = hits[k] / tested
        
        results_by_predicate.append(result)
    
    results_by_predicate.sort(key=lambda x: -x['mrr'])
    
    # Report
    print(f"\n  PREDICTION RESULTS (leave-one-out):", flush=True)
    print(f"  {'Predicate':<10} {'Label':<35} {'N':>4} {'Align':>6} {'MRR':>6} "
          + " ".join(f"{'H@'+str(k):>6}" for k in top_k_values), flush=True)
    print(f"  {'-'*100}", flush=True)
    
    for r in results_by_predicate[:40]:
        label_trunc = r['label'][:33] if len(r['label']) > 33 else r['label']
        hits_str = " ".join(f"{r[f'hits_at_{k}']:>6.3f}" for k in top_k_values)
        print(f"  {r['predicate']:<10} {label_trunc:<35} {r['n_tested']:>4} "
              f"{r['alignment']:>6.3f} {r['mrr']:>6.3f} {hits_str}", flush=True)
    
    # Aggregate statistics
    if results_by_predicate:
        all_mrr = [r['mrr'] for r in results_by_predicate]
        all_h1 = [r['hits_at_1'] for r in results_by_predicate]
        all_h10 = [r['hits_at_10'] for r in results_by_predicate]
        
        print(f"\n  AGGREGATE STATISTICS:", flush=True)
        print(f"  Operations tested:     {len(results_by_predicate)}", flush=True)
        print(f"  Mean MRR:              {np.mean(all_mrr):.4f}", flush=True)
        print(f"  Mean Hits@1:           {np.mean(all_h1):.4f}", flush=True)
        print(f"  Mean Hits@10:          {np.mean(all_h10):.4f}", flush=True)
        
        # Correlation between alignment and prediction quality
        alignments = [r['alignment'] for r in results_by_predicate]
        corr_mrr = np.corrcoef(alignments, all_mrr)[0, 1] if len(alignments) > 2 else 0
        corr_h1 = np.corrcoef(alignments, all_h1)[0, 1] if len(alignments) > 2 else 0
        
        print(f"  Correlation (alignment ↔ MRR):   {corr_mrr:.4f}", flush=True)
        print(f"  Correlation (alignment ↔ H@1):   {corr_h1:.4f}", flush=True)
    
    return results_by_predicate


def composition_test(operations, emb, index, items, properties):
    """Test: can we compose two operations to predict a two-hop result?
    
    Find triples where S→P1→M and M→P2→O both exist, then test:
    predicted_O = S_vec + op_P1 + op_P2
    Does predicted_O land near actual O?
    """
    print(f"\n{'='*70}", flush=True)
    print(f"PHASE 3: COMPOSITION TEST", flush=True)
    print(f"Can discovered operations be chained? (S + d1 + d2 → O)", flush=True)
    print(f"{'='*70}", flush=True)
    
    qid_map = build_qid_to_label_vec(emb, index)
    
    # Build adjacency: subject → [(predicate, object)]
    adjacency = defaultdict(list)
    for item in items:
        for triple in item['triples']:
            if triple['value']['type'] == 'wikibase-item':
                adjacency[item['qid']].append((triple['predicate'], triple['value']['value']))
    
    # Get operation vectors for strong operations
    op_vectors = {}
    for op in operations:
        if op['mean_alignment'] > 0.5 and op['n_triples'] >= 10:
            op_vectors[op['predicate']] = op['operation_vector']
    
    print(f"  Using {len(op_vectors)} discovered operations for composition", flush=True)
    
    # Build label search index
    label_indices = [i for i, e in enumerate(index) if e['type'] == 'label']
    label_vecs = emb[label_indices]
    label_norms = np.linalg.norm(label_vecs, axis=1, keepdims=True)
    label_normed = label_vecs / (label_norms + 1e-10)
    label_qids = [index[i]['qid'] for i in label_indices]
    
    # Find two-hop paths: S →P1→ M →P2→ O where both P1 and P2 are discovered ops
    compositions_tested = 0
    compositions_hit_1 = 0
    compositions_hit_10 = 0
    compositions_hit_50 = 0
    total_rank = 0
    composition_examples = []
    
    for subj_qid, edges in adjacency.items():
        if subj_qid not in qid_map:
            continue
        s_vec = qid_map[subj_qid][0]
        
        for p1, mid_qid in edges:
            if p1 not in op_vectors or mid_qid not in qid_map:
                continue
            
            for p2, obj_qid in adjacency.get(mid_qid, []):
                if p2 not in op_vectors or obj_qid not in qid_map:
                    continue
                if p1 == p2:
                    continue  # Skip same-predicate chains
                
                # Compose: predicted = S + op_P1 + op_P2
                predicted = s_vec + op_vectors[p1] + op_vectors[p2]
                predicted_norm = predicted / (np.linalg.norm(predicted) + 1e-10)
                
                sims = label_normed @ predicted_norm
                ranking = np.argsort(-sims)
                
                try:
                    obj_idx = label_qids.index(obj_qid)
                    rank = np.where(ranking == obj_idx)[0][0] + 1
                except (ValueError, IndexError):
                    rank = len(label_qids) + 1
                
                if rank <= 1:
                    compositions_hit_1 += 1
                if rank <= 10:
                    compositions_hit_10 += 1
                if rank <= 50:
                    compositions_hit_50 += 1
                total_rank += rank
                compositions_tested += 1
                
                if len(composition_examples) < 20 and rank <= 50:
                    s_label = next((e['text'] for e in index if e['qid'] == subj_qid and e['type'] == 'label'), subj_qid)
                    m_label = next((e['text'] for e in index if e['qid'] == mid_qid and e['type'] == 'label'), mid_qid)
                    o_label = next((e['text'] for e in index if e['qid'] == obj_qid and e['type'] == 'label'), obj_qid)
                    p1_label = get_property_label(p1, properties)
                    p2_label = get_property_label(p2, properties)
                    composition_examples.append({
                        'chain': f"{s_label} →[{p1_label}]→ {m_label} →[{p2_label}]→ {o_label}",
                        'rank': rank,
                    })
                
                # Cap at reasonable number of tests
                if compositions_tested >= 5000:
                    break
            if compositions_tested >= 5000:
                break
        if compositions_tested >= 5000:
            break
    
    if compositions_tested > 0:
        print(f"\n  Two-hop compositions tested: {compositions_tested}", flush=True)
        print(f"  Hits@1:  {compositions_hit_1/compositions_tested:.4f} ({compositions_hit_1}/{compositions_tested})", flush=True)
        print(f"  Hits@10: {compositions_hit_10/compositions_tested:.4f} ({compositions_hit_10}/{compositions_tested})", flush=True)
        print(f"  Hits@50: {compositions_hit_50/compositions_tested:.4f} ({compositions_hit_50}/{compositions_tested})", flush=True)
        print(f"  Mean rank: {total_rank/compositions_tested:.1f}", flush=True)
        
        if composition_examples:
            print(f"\n  SUCCESSFUL COMPOSITIONS (top examples):", flush=True)
            for ex in sorted(composition_examples, key=lambda x: x['rank'])[:15]:
                print(f"    Rank {ex['rank']:>4}: {ex['chain']}", flush=True)
    else:
        print(f"\n  No two-hop compositions found with discoverable operations.", flush=True)
    
    return compositions_tested, compositions_hit_10


def failure_analysis(operations, properties):
    """Characterize which predicates DON'T encode as vector operations and why."""
    print(f"\n{'='*70}", flush=True)
    print(f"PHASE 4: FAILURE ANALYSIS", flush=True)
    print(f"Which predicates resist vector encoding?", flush=True)
    print(f"{'='*70}", flush=True)
    
    weak = [op for op in operations if op['mean_alignment'] <= 0.3]
    weak.sort(key=lambda x: x['mean_alignment'])
    
    print(f"\n  WEAKEST OPERATIONS (alignment <= 0.3):", flush=True)
    print(f"  {'Predicate':<10} {'Label':<40} {'N':>5} {'Align':>7} {'MagCV':>7} {'Dist':>6}", flush=True)
    print(f"  {'-'*80}", flush=True)
    
    for op in weak[:20]:
        label_trunc = op['label'][:38] if len(op['label']) > 38 else op['label']
        print(f"  {op['predicate']:<10} {label_trunc:<40} {op['n_triples']:>5} "
              f"{op['mean_alignment']:>7.4f} {op['magnitude_cv']:>7.3f} "
              f"{op['mean_cosine_distance']:>6.3f}", flush=True)
    
    # Categorize failures
    high_variance_mag = [op for op in weak if op['magnitude_cv'] > 1.0]
    low_distance = [op for op in weak if op['mean_cosine_distance'] < 0.1]
    
    print(f"\n  Failure patterns:", flush=True)
    print(f"    High magnitude variance (CV > 1.0): {len(high_variance_mag)} — inconsistent scales", flush=True)
    print(f"    Low mean distance (< 0.1):          {len(low_distance)} — subject ≈ object", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Discover FOL operations in embedding space")
    parser.add_argument('--min-triples', type=int, default=10, help='Min triples per predicate')
    parser.add_argument('--predict', action='store_true', help='Run prediction evaluation only')
    parser.add_argument('--compose', action='store_true', help='Run composition test only')
    parser.add_argument('--output', default=str(DATA_DIR / 'fol_results.json'), help='Output file')
    args = parser.parse_args()
    
    emb, index, items, properties = load_data()
    
    print(f"Loaded: {emb.shape[0]} embeddings, {len(items)} items", flush=True)
    
    # Phase 1: Discover operations
    operations = discover_operations(emb, index, items, properties, args.min_triples)
    
    # Phase 2: Prediction evaluation
    prediction_results = prediction_evaluation(operations, emb, index, items, properties)
    
    # Phase 3: Composition test
    comp_tested, comp_hits = composition_test(operations, emb, index, items, properties)
    
    # Phase 4: Failure analysis
    failure_analysis(operations, properties)
    
    # Save results (without numpy arrays)
    serializable_ops = []
    for op in operations:
        op_copy = {k: v for k, v in op.items() if k != 'operation_vector'}
        op_copy['operation_vector_norm'] = float(np.linalg.norm(op['operation_vector']))
        serializable_ops.append(op_copy)
    
    results = {
        'summary': {
            'total_embeddings': emb.shape[0],
            'total_items': len(items),
            'predicates_analyzed': len(operations),
            'strong_operations': len([o for o in operations if o['mean_alignment'] > 0.7]),
            'moderate_operations': len([o for o in operations if 0.5 < o['mean_alignment'] <= 0.7]),
            'weak_operations': len([o for o in operations if o['mean_alignment'] <= 0.5]),
        },
        'discovered_operations': serializable_ops[:50],
        'prediction_results': prediction_results[:50],
        'composition': {
            'tested': comp_tested,
            'hits_at_10': comp_hits,
        },
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to {args.output}", flush=True)
    print(f"\n{'='*70}", flush=True)
    print(f"SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  Embedding space: {emb.shape[1]}-dimensional (mxbai-embed-large)", flush=True)
    print(f"  Knowledge base: {len(items)} entities, {sum(len(i['triples']) for i in items)} triples", flush=True)
    print(f"  Operations discovered: {len([o for o in operations if o['mean_alignment'] > 0.5])}", flush=True)
    print(f"  Strong operations (>0.7): {len([o for o in operations if o['mean_alignment'] > 0.7])}", flush=True)
    if prediction_results:
        print(f"  Mean MRR: {np.mean([r['mrr'] for r in prediction_results]):.4f}", flush=True)
        print(f"  Mean Hits@1: {np.mean([r['hits_at_1'] for r in prediction_results]):.4f}", flush=True)
        print(f"  Mean Hits@10: {np.mean([r['hits_at_10'] for r in prediction_results]):.4f}", flush=True)
    print(f"\n  The thesis: these operations were DISCOVERED, not engineered.", flush=True)
    print(f"  The embedding space was not built for logic — the logic was already there.", flush=True)


if __name__ == '__main__':
    main()
