"""
Extended Grammatical Role Matrix Discovery
============================================
Extends the SVO model to include adjectives and adverbs:

Pattern 1 (SVO):       sentence ≈ subject + M_verb @ verb + M_obj @ object
Pattern 2 (Adj-SVO):   sentence ≈ M_adj @ adj + subject + M_verb @ verb + M_obj @ object
Pattern 3 (SV-Adv-O):  sentence ≈ subject + M_verb @ verb + M_adv @ adverb + M_obj @ object
Pattern 4 (S-Prep):    sentence ≈ subject + M_verb @ verb + M_prep @ preposition + M_pobj @ prep_object

Each pattern is evaluated independently: we generate sentences of that pattern,
learn the role matrices, and evaluate via leave-one-out.

Usage:
    python discover_matrices_extended.py
    python discover_matrices_extended.py --model nomic-embed-text
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
import ollama
from pathlib import Path
from itertools import product
import time

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL = "mxbai-embed-large"


def embed_texts(texts, model=None):
    if model is None:
        model = MODEL
    result = ollama.embed(model=model, input=texts)
    return np.array([e for e in result.embeddings])


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# === VOCABULARY ===

SUBJECTS = [
    "I", "he", "she", "they", "we", "you",
    "the man", "the woman", "the child", "the king", "the queen",
    "John", "Mary", "Alice", "Bob", "Tom",
    "a farmer", "a soldier", "a scientist", "a merchant",
]  # 20

VERBS = [
    "love", "hate", "fear", "want", "know",
    "see", "hear", "find", "carry", "build",
    "eat", "drink", "read", "write", "sell",
    "praise", "blame", "teach", "trust", "break",
]  # 20

OBJECTS = [
    "cats", "dogs", "horses", "birds", "fish",
    "music", "art", "science", "truth", "justice",
    "food", "water", "books", "gold", "fire",
    "children", "strangers", "enemies", "friends", "kings",
]  # 20

ADJECTIVES = [
    "old", "young", "tall", "small", "brave",
    "wise", "rich", "poor", "strong", "weak",
    "kind", "cruel", "happy", "sad", "angry",
]  # 15

ADVERBS = [
    "quickly", "slowly", "quietly", "loudly", "carefully",
    "eagerly", "gently", "fiercely", "secretly", "openly",
    "always", "never", "often", "rarely", "sometimes",
]  # 15

PREPOSITIONS = [
    "in", "on", "at", "near", "under",
    "behind", "beside", "above", "below", "around",
]  # 10

PREP_OBJECTS = [
    "the garden", "the house", "the river", "the mountain", "the forest",
    "the city", "the castle", "the church", "the market", "the field",
]  # 10


def embed_all_vocab(model=None):
    """Embed every unique vocabulary item."""
    all_words = list(set(
        SUBJECTS + VERBS + OBJECTS + ADJECTIVES + ADVERBS +
        PREPOSITIONS + PREP_OBJECTS
    ))
    vecs = embed_texts(all_words, model=model)
    word_to_vec = {w: v for w, v in zip(all_words, vecs)}
    print(f"  {len(word_to_vec)} unique vocabulary items embedded", flush=True)
    return word_to_vec


def solve_matrices(sentence_vecs, features_per_sentence, d, word_vecs=None):
    """Generic solver: given feature vectors per sentence, solve for role matrices.

    features_per_sentence: list of lists of (role_name, word) per sentence
    word_vecs: dict mapping word -> vector
    Returns dict of {role_name: matrix}
    """
    n = len(sentence_vecs)
    role_names = list(dict.fromkeys(
        name for feats in features_per_sentence for name, _ in feats
    ))
    n_roles = len(role_names)
    role_idx = {name: i for i, name in enumerate(role_names)}

    # Build system: residual = sum(M_role @ role_vec)
    # features row = [role1_vec, role2_vec, ...] concatenated
    features = np.zeros((n, n_roles * d))
    residuals = np.zeros((n, d))

    for i, feats in enumerate(features_per_sentence):
        # residual = sentence - subject (subject is NOT multiplied by a matrix)
        subj_vec = np.zeros(d)
        for name, word in feats:
            if name == 'subject':
                subj_vec = word_vecs[word]
                break
        residuals[i] = sentence_vecs[i] - subj_vec

        for name, word in feats:
            if name == 'subject':
                continue
            idx = role_idx[name]
            features[i, idx*d:(idx+1)*d] = word_vecs[word]

    M_T, _, rank, _ = np.linalg.lstsq(features, residuals, rcond=None)
    M_combined = M_T.T  # (d, n_roles * d)

    matrices = {}
    for name in role_names:
        if name == 'subject':
            continue
        idx = role_idx[name]
        matrices[name] = M_combined[:, idx*d:(idx+1)*d]

    return matrices, rank


def predict(word_vecs, components_row, matrices):
    """Predict sentence vec from components using learned matrices."""
    d = next(iter(word_vecs.values())).shape[0]
    result = np.zeros(d)
    for name, word in components_row:
        vec = word_vecs[word]
        if name == 'subject':
            result = result + vec
        elif name in matrices:
            result = result + matrices[name] @ vec
    return result


def evaluate_pattern(pattern_name, sentences, components, word_vecs, model=None):
    """Full evaluation of one sentence pattern."""
    print(f"\n{'='*70}", flush=True)
    print(f"PATTERN: {pattern_name}", flush=True)
    print(f"{'='*70}", flush=True)

    # Embed sentences
    print(f"  Embedding {len(sentences)} sentences...", flush=True)
    t0 = time.time()
    batch_size = 100
    all_vecs = []
    for i in range(0, len(sentences), batch_size):
        vecs = embed_texts(sentences[i:i+batch_size], model=model)
        all_vecs.append(vecs)
    sentence_vecs = np.vstack(all_vecs)
    d = sentence_vecs.shape[1]
    print(f"  Done in {time.time()-t0:.1f}s ({d}-dim)", flush=True)

    n = len(sentences)

    # Build features
    features_per_sentence = []
    for comp in components:
        features_per_sentence.append(comp)

    # Learn from all data
    matrices, rank = solve_matrices(sentence_vecs, features_per_sentence, d, word_vecs)
    print(f"  Feature rank: {rank}", flush=True)
    print(f"  Roles: {list(matrices.keys())}", flush=True)

    # Training evaluation
    train_mat_cos = []
    train_base_cos = []
    for i in range(n):
        actual = sentence_vecs[i]
        predicted = predict(word_vecs, components[i], matrices)
        train_mat_cos.append(cosine_sim(predicted, actual))

        # Baseline: simple addition
        baseline = sum(word_vecs[word] for _, word in components[i])
        train_base_cos.append(cosine_sim(baseline, actual))

    train_mat_cos = np.array(train_mat_cos)
    train_base_cos = np.array(train_base_cos)

    print(f"\n  Training set:", flush=True)
    print(f"    Matrix:   {train_mat_cos.mean():.4f} (median {np.median(train_mat_cos):.4f})", flush=True)
    print(f"    Baseline: {train_base_cos.mean():.4f} (median {np.median(train_base_cos):.4f})", flush=True)
    print(f"    Improvement: {train_mat_cos.mean() - train_base_cos.mean():+.4f}", flush=True)

    # Leave-one-out (sample if large)
    loo_n = min(200, n)
    rng = np.random.RandomState(42)
    loo_indices = rng.choice(n, loo_n, replace=False) if n > 200 else range(n)

    print(f"\n  Leave-one-out ({loo_n} held out)...", flush=True)
    loo_mat_cos = []
    loo_base_cos = []

    for count, i in enumerate(loo_indices):
        train_vecs = np.delete(sentence_vecs, i, axis=0)
        train_feats = [features_per_sentence[j] for j in range(n) if j != i]

        M_loo, _ = solve_matrices(train_vecs, train_feats, d, word_vecs)

        actual = sentence_vecs[i]
        predicted = predict(word_vecs, components[i], M_loo)
        loo_mat_cos.append(cosine_sim(predicted, actual))

        baseline = sum(word_vecs[word] for _, word in components[i])
        loo_base_cos.append(cosine_sim(baseline, actual))

        if (count + 1) % 50 == 0:
            print(f"    {count+1}/{loo_n}", flush=True)

    loo_mat_cos = np.array(loo_mat_cos)
    loo_base_cos = np.array(loo_base_cos)

    print(f"    Matrix:   {loo_mat_cos.mean():.4f} (median {np.median(loo_mat_cos):.4f})", flush=True)
    print(f"    Baseline: {loo_base_cos.mean():.4f} (median {np.median(loo_base_cos):.4f})", flush=True)
    print(f"    Improvement: {loo_mat_cos.mean() - loo_base_cos.mean():+.4f}", flush=True)

    # Matrix properties
    for name, M in matrices.items():
        frob = np.linalg.norm(M, 'fro')
        id_dist = np.linalg.norm(M - np.eye(d), 'fro')
        print(f"    M_{name}: Frobenius={frob:.3f}, dist_from_I={id_dist:.3f}", flush=True)

    return {
        'pattern': pattern_name,
        'n_sentences': n,
        'roles': list(matrices.keys()),
        'feature_rank': int(rank),
        'training': {
            'matrix_mean': float(train_mat_cos.mean()),
            'baseline_mean': float(train_base_cos.mean()),
            'improvement': float(train_mat_cos.mean() - train_base_cos.mean()),
        },
        'leave_one_out': {
            'n_evaluated': loo_n,
            'matrix_mean': float(loo_mat_cos.mean()),
            'baseline_mean': float(loo_base_cos.mean()),
            'improvement': float(loo_mat_cos.mean() - loo_base_cos.mean()),
        },
        'matrix_properties': {
            name: {
                'frobenius': float(np.linalg.norm(M, 'fro')),
                'identity_distance': float(np.linalg.norm(M - np.eye(d), 'fro')),
            }
            for name, M in matrices.items()
        },
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mxbai-embed-large')
    parser.add_argument('--max-per-pattern', type=int, default=800)
    args = parser.parse_args()

    global MODEL
    MODEL = args.model
    print(f"Model: {args.model}", flush=True)

    # Embed all vocabulary
    print("Embedding vocabulary...", flush=True)
    word_vecs = embed_all_vocab(model=args.model)

    results = []

    # Pattern 1: SVO (baseline)
    combos = list(product(SUBJECTS, VERBS, OBJECTS))
    rng = np.random.RandomState(42)
    if len(combos) > args.max_per_pattern:
        idx = rng.choice(len(combos), args.max_per_pattern, replace=False)
        combos = [combos[i] for i in sorted(idx)]
    svo_sentences = [f"{s} {v} {o}" for s, v, o in combos]
    svo_components = [[('subject', s), ('verb', v), ('object', o)] for s, v, o in combos]
    r = evaluate_pattern("SVO", svo_sentences, svo_components, word_vecs, model=args.model)
    results.append(r)

    # Pattern 2: Adj-S V O ("the brave man loves cats")
    combos = list(product(ADJECTIVES[:10], SUBJECTS[:10], VERBS[:10], OBJECTS[:10]))
    if len(combos) > args.max_per_pattern:
        idx = rng.choice(len(combos), args.max_per_pattern, replace=False)
        combos = [combos[i] for i in sorted(idx)]
    adj_sentences = [f"the {a} {s} {v} {o}" if not s.startswith("the ") and not s.startswith("a ")
                     else f"{s.split(' ', 1)[0]} {a} {s.split(' ', 1)[1]} {v} {o}" if ' ' in s
                     else f"the {a} {s} {v} {o}"
                     for a, s, v, o in combos]
    # For the matrix solve, we embed the full "the <adj> <subj>" as subject
    # and separately embed the adjective
    adj_components = [
        [('subject', s), ('adjective', a), ('verb', v), ('object', o)]
        for a, s, v, o in combos
    ]
    r = evaluate_pattern("Adj-SVO", adj_sentences, adj_components, word_vecs, model=args.model)
    results.append(r)

    # Pattern 3: S V-Adv O ("he quickly finds water")
    combos = list(product(SUBJECTS[:10], VERBS[:10], ADVERBS[:10], OBJECTS[:10]))
    if len(combos) > args.max_per_pattern:
        idx = rng.choice(len(combos), args.max_per_pattern, replace=False)
        combos = [combos[i] for i in sorted(idx)]
    adv_sentences = [f"{s} {adv} {v} {o}" for s, v, adv, o in combos]
    adv_components = [
        [('subject', s), ('verb', v), ('adverb', adv), ('object', o)]
        for s, v, adv, o in combos
    ]
    r = evaluate_pattern("S-Adv-V-O", adv_sentences, adv_components, word_vecs, model=args.model)
    results.append(r)

    # Pattern 4: S V Prep PObj ("the man walks in the garden")
    walk_verbs = ["walks", "sits", "stands", "lives", "works", "hides", "sleeps", "plays", "rests", "waits"]
    combos = list(product(SUBJECTS[:10], walk_verbs, PREPOSITIONS, PREP_OBJECTS))
    if len(combos) > args.max_per_pattern:
        idx = rng.choice(len(combos), args.max_per_pattern, replace=False)
        combos = [combos[i] for i in sorted(idx)]
    prep_sentences = [f"{s} {v} {p} {po}" for s, v, p, po in combos]
    prep_components = [
        [('subject', s), ('verb', v), ('preposition', p), ('prep_object', po)]
        for s, v, p, po in combos
    ]

    # Need to embed the new verbs and prep objects
    new_words = list(set(walk_verbs) - set(word_vecs.keys()))
    if new_words:
        new_vecs = embed_texts(new_words, model=args.model)
        for w, v in zip(new_words, new_vecs):
            word_vecs[w] = v

    r = evaluate_pattern("S-V-Prep-PObj", prep_sentences, prep_components, word_vecs, model=args.model)
    results.append(r)

    # Summary
    print(f"\n{'='*70}", flush=True)
    print(f"CROSS-PATTERN SUMMARY ({args.model})", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"{'Pattern':<20} {'Roles':>5} {'N':>5} {'Matrix':>8} {'Base':>8} {'Improv':>8}", flush=True)
    print(f"{'-'*60}", flush=True)
    for r in results:
        loo = r['leave_one_out']
        print(f"{r['pattern']:<20} {len(r['roles']):>5} {r['n_sentences']:>5} "
              f"{loo['matrix_mean']:>8.4f} {loo['baseline_mean']:>8.4f} "
              f"{loo['improvement']:>+8.4f}", flush=True)

    # Save
    output_path = DATA_DIR / f'extended_matrices_{args.model.replace("/", "_")}.json'
    with open(str(output_path), 'w', encoding='utf-8') as f:
        json.dump({
            'model': args.model,
            'patterns': results,
        }, f, indent=2)
    print(f"\nSaved to {output_path}", flush=True)


if __name__ == '__main__':
    main()
