"""
String Overlap Null Model for FOL Discovery
============================================

Tests whether the discovered "relational displacements" are merely
capturing string similarity (e.g., "Japan" → "History of Japan" is
just a string prefix operation, not relational knowledge).

For each discovered predicate, we compare:
1. Vector arithmetic MRR (from fol_results.json)
2. String overlap MRR (predict object by longest common substring with subject)

If string overlap achieves similar MRR, the vector arithmetic is trivial.
If vector arithmetic substantially outperforms string overlap, the
embedding captures genuine relational structure beyond surface strings.
"""

import json
import sys
import io
import os
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def longest_common_substring_ratio(s1, s2):
    """Ratio of longest common substring length to max string length."""
    s1 = s1.lower()
    s2 = s2.lower()
    if not s1 or not s2:
        return 0.0
    m, n = len(s1), len(s2)
    # Use rolling array for memory efficiency
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    max_len = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                curr[j] = prev[j-1] + 1
                max_len = max(max_len, curr[j])
            else:
                curr[j] = 0
        prev, curr = curr, [0] * (n + 1)
    return max_len / max(m, n)


def token_overlap_score(s1, s2):
    """Jaccard similarity of word tokens."""
    t1 = set(s1.lower().split())
    t2 = set(s2.lower().split())
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def string_containment_score(subject, candidate):
    """Does the candidate contain the subject string?"""
    return 1.0 if subject.lower() in candidate.lower() else 0.0


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")

    with open(os.path.join(data_dir, "items.json"), "r", encoding="utf-8") as f:
        items = json.load(f)

    with open(os.path.join(data_dir, "fol_results.json"), "r", encoding="utf-8") as f:
        fol_results = json.load(f)

    # Build QID -> label mapping
    qid_to_label = {}
    for item in items:
        qid = item.get("qid", "")
        label = item.get("label", "")
        if qid and label:
            qid_to_label[qid] = label

    # Get all entity labels for ranking
    all_labels = list(qid_to_label.values())
    all_qids = list(qid_to_label.keys())

    print(f"Loaded {len(qid_to_label)} entities")
    print(f"Testing string null model against {len(fol_results['prediction_results'])} predicates\n")

    results = []

    for pred in fol_results["prediction_results"]:
        pid = pred["predicate"]
        label = pred["label"]
        vector_mrr = pred["mrr"]
        alignment = pred["alignment"]
        n = pred["n_tested"]

        # Get the triples for this predicate
        op = None
        for o in fol_results["discovered_operations"]:
            if o["predicate"] == pid:
                op = o
                break
        if not op:
            continue

        triples = op["triples"]

        # For each triple, compute string-based prediction
        string_rrs = []
        containment_rrs = []
        token_rrs = []

        for subj_qid, obj_qid in triples:
            subj_label = qid_to_label.get(subj_qid, "")
            obj_label = qid_to_label.get(obj_qid, "")
            if not subj_label or not obj_label:
                continue

            # Rank all entities by string similarity to subject
            # then find where the true object lands
            scores_lcs = []
            scores_contain = []
            scores_token = []
            for cand_qid, cand_label in zip(all_qids, all_labels):
                scores_lcs.append((cand_qid, longest_common_substring_ratio(subj_label, cand_label)))
                scores_contain.append((cand_qid, string_containment_score(subj_label, cand_label)))
                scores_token.append((cand_qid, token_overlap_score(subj_label, cand_label)))

            for scores_list, rr_list in [(scores_lcs, string_rrs),
                                          (scores_contain, containment_rrs),
                                          (scores_token, token_rrs)]:
                # Sort by score descending, break ties randomly-ish
                scores_list.sort(key=lambda x: -x[1])
                rank = None
                for i, (cid, _) in enumerate(scores_list):
                    if cid == obj_qid:
                        rank = i + 1
                        break
                if rank:
                    rr_list.append(1.0 / rank)

        string_mrr = sum(string_rrs) / len(string_rrs) if string_rrs else 0
        contain_mrr = sum(containment_rrs) / len(containment_rrs) if containment_rrs else 0
        token_mrr = sum(token_rrs) / len(token_rrs) if token_rrs else 0

        results.append({
            "predicate": pid,
            "label": label,
            "n": n,
            "alignment": alignment,
            "vector_mrr": vector_mrr,
            "string_lcs_mrr": string_mrr,
            "containment_mrr": contain_mrr,
            "token_overlap_mrr": token_mrr,
            "vector_minus_string": vector_mrr - string_mrr,
            "vector_minus_token": vector_mrr - token_mrr,
        })

    # Print results
    print(f"{'Predicate':<10} {'Label':<35} {'N':>3} {'Vec MRR':>8} {'Str MRR':>8} {'Tok MRR':>8} {'Vec-Str':>8}")
    print(f"{'-'*10} {'-'*35} {'-'*3} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    # Sort by vector MRR descending
    results.sort(key=lambda x: -x["vector_mrr"])

    vec_wins = 0
    str_wins = 0
    ties = 0

    for r in results:
        delta = r["vector_minus_string"]
        marker = ""
        if delta > 0.01:
            vec_wins += 1
            marker = " ← vector wins"
        elif delta < -0.01:
            str_wins += 1
            marker = " ← STRING wins"
        else:
            ties += 1
            marker = " (tie)"

        print(f"{r['predicate']:<10} {r['label'][:34]:<35} {r['n']:>3} "
              f"{r['vector_mrr']:>8.3f} {r['string_lcs_mrr']:>8.3f} {r['token_overlap_mrr']:>8.3f} "
              f"{delta:>+8.3f}{marker}")

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"  Vector arithmetic beats string overlap: {vec_wins}/{len(results)}")
    print(f"  String overlap beats vector arithmetic: {str_wins}/{len(results)}")
    print(f"  Ties (within 0.01 MRR): {ties}/{len(results)}")
    print(f"  Mean vector MRR: {sum(r['vector_mrr'] for r in results)/len(results):.4f}")
    print(f"  Mean string LCS MRR: {sum(r['string_lcs_mrr'] for r in results)/len(results):.4f}")
    print(f"  Mean token overlap MRR: {sum(r['token_overlap_mrr'] for r in results)/len(results):.4f}")

    # Categorize: which predicates are "trivially string-based"?
    trivial = [r for r in results if r["string_lcs_mrr"] > 0.5 and r["vector_minus_string"] < 0.1]
    genuine = [r for r in results if r["vector_mrr"] > 0.5 and r["string_lcs_mrr"] < 0.3]

    print(f"\n  Trivially string-based (string MRR > 0.5, delta < 0.1): {len(trivial)}")
    for r in trivial:
        print(f"    {r['predicate']} {r['label']}: vec={r['vector_mrr']:.3f} str={r['string_lcs_mrr']:.3f}")

    print(f"\n  Genuinely relational (vector MRR > 0.5, string MRR < 0.3): {len(genuine)}")
    for r in genuine:
        print(f"    {r['predicate']} {r['label']}: vec={r['vector_mrr']:.3f} str={r['string_lcs_mrr']:.3f}")

    # Save
    output_path = os.path.join(data_dir, "string_null_model_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "vector_wins": vec_wins,
                "string_wins": str_wins,
                "ties": ties,
                "total": len(results),
                "mean_vector_mrr": sum(r['vector_mrr'] for r in results)/len(results),
                "mean_string_mrr": sum(r['string_lcs_mrr'] for r in results)/len(results),
                "n_trivial": len(trivial),
                "n_genuine": len(genuine),
            },
            "results": results,
        }, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
