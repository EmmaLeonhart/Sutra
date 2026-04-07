"""
VSA Analysis: Empirical Tests of Vector Symbolic Architecture Properties
========================================================================
Tests whether frozen text embeddings satisfy VSA axioms and compares
bundling (addition) vs binding (element-wise multiplication) operations.

Four experiments:
1. Bundling axiom verification: does d = f(tail) - f(head) produce results
   SIMILAR to other displacements for the same predicate? (bundling property)
2. Binding comparison: test element-wise multiplication (MAP binding) as an
   alternative to addition — does binding outperform bundling?
3. FHRR bridge: test whether operations work better in angular/phase space
   (unit-normalized vectors on the hypersphere)
4. Dissimilarity test: is the result of our operation similar or dissimilar
   to its inputs? (distinguishes bundling from binding formally)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
from collections import defaultdict
from pathlib import Path
import os

DATA_DIR = Path(os.environ.get("FOL_DATA_DIR", str(Path(__file__).resolve().parent.parent / "old" / "data")))


def load_data():
    emb = np.load(str(DATA_DIR / 'embeddings.npz'))['vectors']
    with open(str(DATA_DIR / 'embedding_index.json'), encoding='utf-8') as f:
        index = json.load(f)
    with open(str(DATA_DIR / 'items.json'), encoding='utf-8') as f:
        items = json.load(f)
    try:
        with open(str(DATA_DIR / 'properties.json'), encoding='utf-8') as f:
            properties = json.load(f)
    except FileNotFoundError:
        properties = {}
    return emb, index, items, properties


def build_qid_to_label_vec(emb, index):
    qid_map = {}
    for i, entry in enumerate(index):
        if entry['type'] == 'label' and entry['qid'] not in qid_map:
            qid_map[entry['qid']] = (emb[i], i)
    return qid_map


def get_property_label(pid, properties):
    if pid in properties:
        p = properties[pid]
        if isinstance(p, dict):
            return p.get('label', pid)
    return pid


def cosine_sim(a, b):
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def get_predicate_triples(items, qid_map, min_triples=10):
    """Extract predicate -> list of (head_vec, tail_vec, head_qid, tail_qid) triples."""
    pred_triples = defaultdict(list)
    # items can be a list of dicts or a dict of dicts
    if isinstance(items, list):
        items_iter = [(item.get('qid', ''), item) for item in items]
    else:
        items_iter = items.items()
    for qid, item in items_iter:
        if qid not in qid_map:
            continue
        head_vec = qid_map[qid][0]
        for triple in item.get('triples', []):
            val = triple.get('value', {})
            pred = triple.get('predicate', '')
            obj = val.get('value', '') if isinstance(val, dict) and val.get('type') == 'wikibase-item' else ''
            if obj.startswith('Q') and obj in qid_map:
                tail_vec = qid_map[obj][0]
                pred_triples[pred].append((head_vec, tail_vec, qid, obj))

    return {p: triples for p, triples in pred_triples.items() if len(triples) >= min_triples}


def experiment_1_bundling_axioms(pred_triples, properties, top_n=20):
    """
    Test VSA bundling axioms:
    - Bundling produces output SIMILAR to inputs
    - Individual displacements are similar to the mean displacement
    - The mean displacement is similar to individual displacements (recoverable)
    """
    print("\n" + "="*80)
    print("EXPERIMENT 1: Bundling Axiom Verification")
    print("="*80)
    print("Testing: does displacement d_i resemble the mean displacement d_bar?")
    print("If yes → bundling (superposition). If no → binding (dissimilar output).\n")

    results = []
    for pred, triples in pred_triples.items():
        displacements = [t[1] - t[0] for t in triples]  # tail - head
        mean_disp = np.mean(displacements, axis=0)

        # Consistency = mean cosine of each displacement with the mean
        consistencies = [cosine_sim(d, mean_disp) for d in displacements]
        mean_consistency = np.mean(consistencies)

        # Similarity of result to inputs (bundling test)
        # For bundling: (head + d) should be SIMILAR to head and to d
        # For binding: (head ⊗ d) should be DISSIMILAR to head and to d
        sim_to_head = []
        sim_to_disp = []
        for head_vec, tail_vec, _, _ in triples:
            predicted = head_vec + mean_disp
            predicted_norm = predicted / (np.linalg.norm(predicted) + 1e-10)
            head_norm = head_vec / (np.linalg.norm(head_vec) + 1e-10)
            disp_norm = mean_disp / (np.linalg.norm(mean_disp) + 1e-10)
            sim_to_head.append(cosine_sim(predicted, head_vec))
            sim_to_disp.append(cosine_sim(predicted, mean_disp))

        label = get_property_label(pred, properties)
        results.append({
            'predicate': pred,
            'label': label,
            'n': len(triples),
            'consistency': mean_consistency,
            'sim_result_to_head': np.mean(sim_to_head),
            'sim_result_to_disp': np.mean(sim_to_disp),
            'is_bundling': np.mean(sim_to_head) > 0.3,  # result resembles input → bundling
        })

    results.sort(key=lambda x: x['consistency'], reverse=True)

    print(f"{'Predicate':<40} {'N':>4} {'Consist':>8} {'Sim→Head':>9} {'Sim→Disp':>9} {'Type':<10}")
    print("-" * 85)

    n_bundling = 0
    n_total = 0
    for r in results[:top_n]:
        op_type = "BUNDLING" if r['is_bundling'] else "BINDING?"
        if r['is_bundling']:
            n_bundling += 1
        n_total += 1
        print(f"{r['label'][:39]:<40} {r['n']:>4} {r['consistency']:>8.3f} {r['sim_result_to_head']:>9.3f} {r['sim_result_to_disp']:>9.3f} {op_type:<10}")

    # Summary across ALL predicates
    all_sim_head = [r['sim_result_to_head'] for r in results]
    all_sim_disp = [r['sim_result_to_disp'] for r in results]
    n_bundling_all = sum(1 for r in results if r['is_bundling'])

    print(f"\nSummary across all {len(results)} predicates:")
    print(f"  Mean similarity of (head + d) to head: {np.mean(all_sim_head):.3f}")
    print(f"  Mean similarity of (head + d) to d:    {np.mean(all_sim_disp):.3f}")
    print(f"  Predicates classified as bundling:      {n_bundling_all}/{len(results)} ({100*n_bundling_all/len(results):.1f}%)")
    print(f"\n  VERDICT: {'BUNDLING confirmed' if n_bundling_all > len(results)*0.8 else 'Mixed results'}")
    print(f"  (Bundling = result similar to inputs; Binding = result dissimilar to inputs)")

    return results


def experiment_2_binding_comparison(pred_triples, emb, qid_map, properties, top_n=15):
    """
    Compare additive displacement (bundling) vs element-wise multiplication (MAP binding).
    For each predicate, compute:
    - Addition-based prediction: head + mean_displacement
    - Multiplication-based prediction: head * mean_ratio (element-wise)
    Compare MRR for both.
    """
    print("\n" + "="*80)
    print("EXPERIMENT 2: Bundling vs Binding (Addition vs Multiplication)")
    print("="*80)
    print("Comparing: head + d (bundling) vs head * r (MAP binding)")
    print("If addition wins → space uses bundling. If multiplication wins → space uses binding.\n")

    # Build lookup for nearest neighbor search
    all_vecs = []
    all_qids = []
    for qid, (vec, idx) in qid_map.items():
        all_vecs.append(vec)
        all_qids.append(qid)
    all_vecs = np.array(all_vecs)
    # Normalize for cosine search
    norms = np.linalg.norm(all_vecs, axis=1, keepdims=True)
    norms[norms < 1e-10] = 1.0
    all_vecs_norm = all_vecs / norms

    results = []
    # Only test predicates with consistency > 0.5
    consistent_preds = {}
    for pred, triples in pred_triples.items():
        disps = [t[1] - t[0] for t in triples]
        mean_disp = np.mean(disps, axis=0)
        consistency = np.mean([cosine_sim(d, mean_disp) for d in disps])
        if consistency > 0.5:
            consistent_preds[pred] = (triples, mean_disp, consistency)

    for pred, (triples, mean_disp, consistency) in list(consistent_preds.items())[:30]:
        # Compute mean ratio for multiplication (element-wise)
        ratios = []
        for head_vec, tail_vec, _, _ in triples:
            # Avoid division by zero
            safe_head = np.where(np.abs(head_vec) > 1e-10, head_vec, 1e-10)
            ratio = tail_vec / safe_head
            ratios.append(ratio)
        mean_ratio = np.mean(ratios, axis=0)

        add_ranks = []
        mul_ranks = []

        for i, (head_vec, tail_vec, head_qid, tail_qid) in enumerate(triples):
            # Leave-one-out mean displacement
            other_disps = [triples[j][1] - triples[j][0] for j in range(len(triples)) if j != i]
            loo_disp = np.mean(other_disps, axis=0)

            # Leave-one-out mean ratio
            other_ratios = []
            for j in range(len(triples)):
                if j == i:
                    continue
                h = triples[j][0]
                t = triples[j][1]
                safe_h = np.where(np.abs(h) > 1e-10, h, 1e-10)
                other_ratios.append(t / safe_h)
            loo_ratio = np.mean(other_ratios, axis=0)

            # Addition prediction
            pred_add = head_vec + loo_disp
            pred_add_norm = pred_add / (np.linalg.norm(pred_add) + 1e-10)

            # Multiplication prediction
            pred_mul = head_vec * loo_ratio
            pred_mul_norm = pred_mul / (np.linalg.norm(pred_mul) + 1e-10)

            # Rank the true tail
            sims_add = all_vecs_norm @ pred_add_norm
            sims_mul = all_vecs_norm @ pred_mul_norm

            # Find rank of true tail
            if tail_qid in qid_map:
                tail_idx_in_all = all_qids.index(tail_qid)
                rank_add = int((sims_add > sims_add[tail_idx_in_all]).sum()) + 1
                rank_mul = int((sims_mul > sims_mul[tail_idx_in_all]).sum()) + 1
                add_ranks.append(rank_add)
                mul_ranks.append(rank_mul)

        if add_ranks:
            add_mrr = np.mean([1.0/r for r in add_ranks])
            mul_mrr = np.mean([1.0/r for r in mul_ranks])
            add_h10 = np.mean([1 if r <= 10 else 0 for r in add_ranks])
            mul_h10 = np.mean([1 if r <= 10 else 0 for r in mul_ranks])

            label = get_property_label(pred, properties)
            results.append({
                'predicate': pred,
                'label': label,
                'n': len(triples),
                'consistency': consistency,
                'add_mrr': add_mrr,
                'mul_mrr': mul_mrr,
                'add_h10': add_h10,
                'mul_h10': mul_h10,
                'winner': 'ADD' if add_mrr > mul_mrr else 'MUL',
            })

    results.sort(key=lambda x: x['consistency'], reverse=True)

    print(f"{'Predicate':<35} {'N':>4} {'Cons':>5} {'Add MRR':>8} {'Mul MRR':>8} {'Add H@10':>8} {'Mul H@10':>8} {'Winner':<6}")
    print("-" * 95)
    for r in results[:top_n]:
        print(f"{r['label'][:34]:<35} {r['n']:>4} {r['consistency']:>5.2f} {r['add_mrr']:>8.3f} {r['mul_mrr']:>8.3f} {r['add_h10']:>8.3f} {r['mul_h10']:>8.3f} {r['winner']:<6}")

    add_wins = sum(1 for r in results if r['winner'] == 'ADD')
    mul_wins = sum(1 for r in results if r['winner'] == 'MUL')
    mean_add = np.mean([r['add_mrr'] for r in results]) if results else 0
    mean_mul = np.mean([r['mul_mrr'] for r in results]) if results else 0

    print(f"\nSummary across {len(results)} consistent predicates:")
    print(f"  Addition (bundling) wins: {add_wins}/{len(results)}")
    print(f"  Multiplication (MAP binding) wins: {mul_wins}/{len(results)}")
    print(f"  Mean MRR — Addition: {mean_add:.3f}, Multiplication: {mean_mul:.3f}")
    print(f"\n  VERDICT: {'BUNDLING dominates' if add_wins > mul_wins else 'BINDING dominates' if mul_wins > add_wins else 'TIE'}")

    return results


def experiment_3_fhrr_bridge(pred_triples, properties, top_n=15):
    """
    Test the FHRR bridge hypothesis: do operations work in angular space?
    FHRR binding operates on phase angles. If our embeddings are L2-normalized
    (on the hypersphere), angle-based operations should be natural.

    Compare:
    - Raw displacement consistency (Euclidean subtraction)
    - Angular displacement consistency (on normalized vectors)
    """
    print("\n" + "="*80)
    print("EXPERIMENT 3: FHRR Bridge — Angular vs Euclidean Operations")
    print("="*80)
    print("Testing: do operations improve when we work in angular space?")
    print("If yes → supports FHRR bridge. If no → purely additive bundling.\n")

    results = []
    for pred, triples in pred_triples.items():
        # Raw displacements (Euclidean)
        raw_disps = [t[1] - t[0] for t in triples]
        raw_mean = np.mean(raw_disps, axis=0)
        raw_consistency = np.mean([cosine_sim(d, raw_mean) for d in raw_disps])

        # Normalized displacements (angular — normalize head and tail first)
        norm_disps = []
        for head_vec, tail_vec, _, _ in triples:
            h_norm = head_vec / (np.linalg.norm(head_vec) + 1e-10)
            t_norm = tail_vec / (np.linalg.norm(tail_vec) + 1e-10)
            norm_disps.append(t_norm - h_norm)
        norm_mean = np.mean(norm_disps, axis=0)
        norm_consistency = np.mean([cosine_sim(d, norm_mean) for d in norm_disps])

        # Check if vectors are already L2-normalized
        head_norms = [np.linalg.norm(t[0]) for t in triples[:5]]
        is_normalized = all(abs(n - 1.0) < 0.01 for n in head_norms)

        label = get_property_label(pred, properties)
        results.append({
            'predicate': pred,
            'label': label,
            'n': len(triples),
            'raw_consistency': raw_consistency,
            'norm_consistency': norm_consistency,
            'diff': norm_consistency - raw_consistency,
            'is_normalized': is_normalized,
        })

    results.sort(key=lambda x: x['raw_consistency'], reverse=True)

    # Report normalization status
    if results and results[0]['is_normalized']:
        print("NOTE: Embeddings are already L2-normalized (||v|| = 1.0).")
        print("This means raw and normalized operations are identical — vectors are already on the hypersphere.")
        print("The FHRR bridge is automatically satisfied for this model.\n")

    print(f"{'Predicate':<35} {'N':>4} {'Raw Cons':>9} {'Norm Cons':>10} {'Diff':>7}")
    print("-" * 70)
    for r in results[:top_n]:
        print(f"{r['label'][:34]:<35} {r['n']:>4} {r['raw_consistency']:>9.3f} {r['norm_consistency']:>10.3f} {r['diff']:>+7.3f}")

    diffs = [r['diff'] for r in results]
    print(f"\nSummary: mean difference (norm - raw) = {np.mean(diffs):+.4f}")
    print(f"  {'Already normalized — FHRR bridge trivially holds' if results[0]['is_normalized'] else 'Normalization ' + ('helps' if np.mean(diffs) > 0.01 else 'does not help')}")

    return results


def experiment_4_dissimilarity_test(pred_triples, properties, top_n=20):
    """
    Formal VSA test: is the output of our operation similar or dissimilar to inputs?

    Binding requirement (Plate 2003): δ(A ⊗ B, A) ≈ 0 (dissimilar)
    Bundling property: δ(A + B, A) > 0 (similar)

    We measure: for each triple, how similar is f(head) + d_mean to f(head)?
    If similar → bundling. If dissimilar → binding.
    """
    print("\n" + "="*80)
    print("EXPERIMENT 4: Formal Dissimilarity Test (Plate 2003 Binding Criterion)")
    print("="*80)
    print("Binding requires: result is DISSIMILAR to inputs (cos ≈ 0)")
    print("Bundling means: result is SIMILAR to inputs (cos > 0)\n")

    all_sims_to_head = []
    all_sims_to_tail = []
    all_sims_to_disp = []

    results = []
    for pred, triples in pred_triples.items():
        disps = [t[1] - t[0] for t in triples]
        mean_disp = np.mean(disps, axis=0)
        consistency = np.mean([cosine_sim(d, mean_disp) for d in disps])

        if consistency < 0.5:
            continue

        sims_head = []
        sims_tail = []
        sims_disp = []

        for head_vec, tail_vec, _, _ in triples:
            result = head_vec + mean_disp
            sims_head.append(cosine_sim(result, head_vec))
            sims_tail.append(cosine_sim(result, tail_vec))
            sims_disp.append(cosine_sim(result, mean_disp))

        mean_sim_head = np.mean(sims_head)
        mean_sim_tail = np.mean(sims_tail)
        mean_sim_disp = np.mean(sims_disp)

        all_sims_to_head.extend(sims_head)
        all_sims_to_tail.extend(sims_tail)
        all_sims_to_disp.extend(sims_disp)

        label = get_property_label(pred, properties)
        results.append({
            'predicate': pred,
            'label': label,
            'n': len(triples),
            'consistency': consistency,
            'sim_to_head': mean_sim_head,
            'sim_to_tail': mean_sim_tail,
            'sim_to_disp': mean_sim_disp,
        })

    results.sort(key=lambda x: x['consistency'], reverse=True)

    print(f"{'Predicate':<35} {'N':>4} {'Cons':>5} {'→Head':>6} {'→Tail':>6} {'→Disp':>6}")
    print("-" * 68)
    for r in results[:top_n]:
        print(f"{r['label'][:34]:<35} {r['n']:>4} {r['consistency']:>5.2f} {r['sim_to_head']:>6.3f} {r['sim_to_tail']:>6.3f} {r['sim_to_disp']:>6.3f}")

    print(f"\nAggregate across {len(results)} consistent predicates ({len(all_sims_to_head)} triples):")
    print(f"  Mean cos(result, head):         {np.mean(all_sims_to_head):.3f}")
    print(f"  Mean cos(result, tail):         {np.mean(all_sims_to_tail):.3f}")
    print(f"  Mean cos(result, displacement): {np.mean(all_sims_to_disp):.3f}")

    if np.mean(all_sims_to_head) > 0.3:
        print(f"\n  VERDICT: BUNDLING confirmed.")
        print(f"  Result (head + d) remains SIMILAR to head (cos = {np.mean(all_sims_to_head):.3f})")
        print(f"  This FAILS the binding dissimilarity requirement (would need cos ≈ 0)")
    else:
        print(f"\n  VERDICT: Closer to binding.")
        print(f"  Result is relatively dissimilar to head (cos = {np.mean(all_sims_to_head):.3f})")

    return results


def main():
    print("Loading data...")
    emb, index, items, properties = load_data()
    qid_map = build_qid_to_label_vec(emb, index)
    print(f"Loaded {len(emb)} embeddings, {len(qid_map)} entities with label vectors")

    # Check normalization
    sample_norms = [np.linalg.norm(emb[i]) for i in range(min(100, len(emb)))]
    print(f"Embedding norms: mean={np.mean(sample_norms):.4f}, std={np.std(sample_norms):.4f}")

    pred_triples = get_predicate_triples(items, qid_map, min_triples=10)
    print(f"Found {len(pred_triples)} predicates with ≥10 triples")

    # Run all experiments
    r1 = experiment_1_bundling_axioms(pred_triples, properties)
    r2 = experiment_2_binding_comparison(pred_triples, emb, qid_map, properties)
    r3 = experiment_3_fhrr_bridge(pred_triples, properties)
    r4 = experiment_4_dissimilarity_test(pred_triples, properties)

    # Save results
    output = {
        'experiment_1_bundling_axioms': r1,
        'experiment_2_binding_comparison': r2,
        'experiment_3_fhrr_bridge': r3,
        'experiment_4_dissimilarity_test': r4,
    }

    out_path = Path(__file__).resolve().parent.parent / 'vsa_results.json'
    with open(str(out_path), 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
