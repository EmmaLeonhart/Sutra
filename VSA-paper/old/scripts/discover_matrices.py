"""
Compositional Transformation Matrix Discovery
===============================================
Discover the matrices that transform individual word embeddings into their
compositional role within a sentence.

Core hypothesis:
    embed("I love cats") ≈ embed("I") + M_verb @ embed("love") + M_obj @ embed("cats")

We generate controlled sentence permutations from high-frequency vocabulary,
embed everything, then solve for the role matrices (M_verb, M_obj, etc.)
via least squares.

Evaluation:
1. Predict held-out sentence embeddings using the learned matrices
2. Measure cosine similarity between predicted and actual
3. Compare against baseline of simple addition (no matrices)
4. Test cross-model transfer

Usage:
    python discover_matrices.py                     # full pipeline
    python discover_matrices.py --model nomic-embed-text  # different model
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
    """Embed a list of texts via Ollama."""
    if model is None:
        model = MODEL
    result = ollama.embed(model=model, input=texts)
    return np.array([e for e in result.embeddings])


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# --- Vocabulary for controlled permutations ---

SUBJECTS = [
    # Pronouns
    "I", "he", "she", "they", "we", "you", "it",
    # Definite NPs
    "the man", "the woman", "the child", "the dog", "the cat",
    "the teacher", "the doctor", "the student", "the king", "the queen",
    # Proper names
    "John", "Mary", "Alice", "Bob", "Tom",
    # Indefinite NPs
    "a farmer", "a soldier", "a scientist", "a merchant", "a priest",
]

VERBS = [
    # Emotion/cognition
    "love", "hate", "fear", "want", "know",
    "like", "trust", "doubt", "admire", "envy",
    # Perception
    "see", "hear", "feel", "smell", "taste",
    # Action
    "eat", "drink", "find", "carry", "build",
    "read", "write", "break", "sell", "buy",
    # Communication
    "praise", "blame", "teach", "warn", "ask",
]

OBJECTS = [
    # Animals
    "cats", "dogs", "horses", "birds", "fish",
    # Abstract
    "music", "art", "science", "truth", "justice",
    # Concrete
    "food", "water", "books", "gold", "fire",
    "bread", "wine", "stone", "wood", "iron",
    # People-ish
    "children", "strangers", "enemies", "friends", "kings",
]


def generate_sentences(subjects, verbs, objects, max_sentences=500):
    """Generate controlled SVO sentences from vocabulary lists."""
    sentences = []
    components = []  # (subject_text, verb_text, object_text)

    all_combos = list(product(subjects, verbs, objects))
    # Limit to max_sentences
    if len(all_combos) > max_sentences:
        rng = np.random.RandomState(42)
        indices = rng.choice(len(all_combos), max_sentences, replace=False)
        all_combos = [all_combos[i] for i in sorted(indices)]

    for subj, verb, obj in all_combos:
        # Simple SVO pattern
        sentence = f"{subj} {verb} {obj}"
        sentences.append(sentence)
        components.append((subj, verb, obj))

    return sentences, components


def embed_vocabulary(subjects, verbs, objects, model=None):
    """Embed all individual vocabulary items."""
    print("Embedding individual vocabulary items...", flush=True)

    all_words = list(set(subjects + verbs + objects))
    vecs = embed_texts(all_words, model=model)

    word_to_vec = {}
    for word, vec in zip(all_words, vecs):
        word_to_vec[word] = vec

    print(f"  {len(word_to_vec)} unique words embedded ({vecs.shape[1]}-dim)", flush=True)
    return word_to_vec


def solve_role_matrices(sentence_vecs, components, word_vecs):
    """Solve for role transformation matrices.

    Model: sentence ≈ subject + M_verb @ verb + M_obj @ object

    Rearrange: sentence - subject = M_verb @ verb + M_obj @ object
    This is a linear system we can solve via least squares.

    Let residual = sentence - subject_vec
    Let X_i = [verb_vec, object_vec] stacked appropriately
    Then residual = [M_verb | M_obj] @ [verb_vec; object_vec]

    We solve for the combined matrix [M_verb | M_obj] of shape (d, 2d).
    """
    n = len(components)
    d = sentence_vecs.shape[1]

    # Build system: for each sentence i,
    # residual_i = sentence_i - subject_i
    # We want: residual_i ≈ M_verb @ verb_i + M_obj @ obj_i
    # Stack verb_i and obj_i into a (2d,) vector, solve for M of shape (d, 2d)

    residuals = np.zeros((n, d))
    features = np.zeros((n, 2 * d))

    for i, (subj, verb, obj) in enumerate(components):
        residuals[i] = sentence_vecs[i] - word_vecs[subj]
        features[i, :d] = word_vecs[verb]
        features[i, d:] = word_vecs[obj]

    # Solve: features @ M_combined^T = residuals
    # M_combined^T = lstsq(features, residuals)
    print(f"Solving for role matrices ({n} equations, {d}-dim)...", flush=True)
    M_combined_T, _, rank, _ = np.linalg.lstsq(features, residuals, rcond=None)
    M_combined = M_combined_T.T  # (d, 2d)

    M_verb = M_combined[:, :d]   # (d, d)
    M_obj = M_combined[:, d:]    # (d, d)

    print(f"  Rank of feature matrix: {rank}", flush=True)
    print(f"  M_verb shape: {M_verb.shape}, M_obj shape: {M_obj.shape}", flush=True)

    return M_verb, M_obj


def evaluate_prediction(sentence_vecs, components, word_vecs, M_verb, M_obj):
    """Evaluate: predicted = subject + M_verb @ verb + M_obj @ object."""
    n = len(components)
    d = sentence_vecs.shape[1]

    matrix_cosines = []
    baseline_cosines = []  # simple addition: subject + verb + object

    for i, (subj, verb, obj) in enumerate(components):
        actual = sentence_vecs[i]

        # Matrix prediction
        predicted = word_vecs[subj] + M_verb @ word_vecs[verb] + M_obj @ word_vecs[obj]
        matrix_cosines.append(cosine_sim(predicted, actual))

        # Baseline: simple addition
        baseline = word_vecs[subj] + word_vecs[verb] + word_vecs[obj]
        baseline_cosines.append(cosine_sim(baseline, actual))

    return np.array(matrix_cosines), np.array(baseline_cosines)


def leave_one_out_evaluation(sentence_vecs, components, word_vecs):
    """Leave-one-out: learn matrices from N-1 sentences, predict the held-out one."""
    n = len(components)
    d = sentence_vecs.shape[1]

    loo_matrix_cosines = []
    loo_baseline_cosines = []

    # For efficiency, do LOO on a sample if n is large
    if n > 200:
        rng = np.random.RandomState(42)
        loo_indices = rng.choice(n, 200, replace=False)
    else:
        loo_indices = range(n)

    print(f"Leave-one-out evaluation ({len(loo_indices)} held-out sentences)...", flush=True)

    for count, i in enumerate(loo_indices):
        # Training set
        train_vecs = np.delete(sentence_vecs, i, axis=0)
        train_components = [components[j] for j in range(n) if j != i]

        # Learn matrices from training set
        M_verb, M_obj = solve_role_matrices_quiet(train_vecs, train_components, word_vecs)

        # Predict held-out
        subj, verb, obj = components[i]
        actual = sentence_vecs[i]

        predicted = word_vecs[subj] + M_verb @ word_vecs[verb] + M_obj @ word_vecs[obj]
        loo_matrix_cosines.append(cosine_sim(predicted, actual))

        baseline = word_vecs[subj] + word_vecs[verb] + word_vecs[obj]
        loo_baseline_cosines.append(cosine_sim(baseline, actual))

        if (count + 1) % 50 == 0:
            print(f"  {count+1}/{len(loo_indices)} done", flush=True)

    return np.array(loo_matrix_cosines), np.array(loo_baseline_cosines)


def solve_role_matrices_quiet(sentence_vecs, components, word_vecs):
    """Same as solve_role_matrices but without printing."""
    n = len(components)
    d = sentence_vecs.shape[1]
    residuals = np.zeros((n, d))
    features = np.zeros((n, 2 * d))
    for i, (subj, verb, obj) in enumerate(components):
        residuals[i] = sentence_vecs[i] - word_vecs[subj]
        features[i, :d] = word_vecs[verb]
        features[i, d:] = word_vecs[obj]
    M_combined_T, _, _, _ = np.linalg.lstsq(features, residuals, rcond=None)
    M_combined = M_combined_T.T
    return M_combined[:, :d], M_combined[:, d:]


def analyze_matrices(M_verb, M_obj):
    """Analyze properties of the learned matrices."""
    print(f"\n{'='*60}", flush=True)
    print(f"MATRIX PROPERTIES", flush=True)
    print(f"{'='*60}", flush=True)

    for name, M in [("M_verb", M_verb), ("M_obj", M_obj)]:
        # Singular values
        sv = np.linalg.svd(M, compute_uv=False)
        condition = sv[0] / (sv[-1] + 1e-10)

        # Frobenius norm
        frob = np.linalg.norm(M, 'fro')

        # How close to identity?
        identity_dist = np.linalg.norm(M - np.eye(M.shape[0]), 'fro')

        # How close to zero?
        zero_dist = frob

        # Eigenvalue analysis
        eigvals = np.linalg.eigvals(M)
        max_eigval = np.max(np.abs(eigvals))
        mean_eigval = np.mean(np.abs(eigvals))

        print(f"\n  {name}:", flush=True)
        print(f"    Frobenius norm:        {frob:.4f}", flush=True)
        print(f"    Distance from I:       {identity_dist:.4f}", flush=True)
        print(f"    Condition number:      {condition:.2f}", flush=True)
        print(f"    Top 5 singular values: {sv[:5]}", flush=True)
        print(f"    Max |eigenvalue|:      {max_eigval:.4f}", flush=True)
        print(f"    Mean |eigenvalue|:     {mean_eigval:.4f}", flush=True)

        # If close to identity, the matrix is basically doing nothing
        if identity_dist < frob * 0.5:
            print(f"    → Close to identity (role ≈ simple addition)", flush=True)
        elif frob < 0.1:
            print(f"    → Near zero (role contribution minimal)", flush=True)
        else:
            print(f"    → Non-trivial transformation", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mxbai-embed-large')
    parser.add_argument('--max-sentences', type=int, default=500)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    global MODEL
    MODEL = args.model

    if args.output is None:
        args.output = str(DATA_DIR / f'matrix_discovery_{args.model.replace("/", "_")}.json')

    print(f"Model: {args.model}", flush=True)
    print(f"Max sentences: {args.max_sentences}", flush=True)

    # Generate sentences
    sentences, components = generate_sentences(SUBJECTS, VERBS, OBJECTS, args.max_sentences)
    print(f"\nGenerated {len(sentences)} SVO sentences", flush=True)
    print(f"  Subjects: {len(SUBJECTS)}, Verbs: {len(VERBS)}, Objects: {len(OBJECTS)}", flush=True)
    print(f"  Example: '{sentences[0]}'", flush=True)

    # Embed everything
    word_vecs = embed_vocabulary(SUBJECTS, VERBS, OBJECTS, model=args.model)

    print(f"\nEmbedding {len(sentences)} sentences...", flush=True)
    t0 = time.time()
    # Batch embedding
    batch_size = 100
    all_sentence_vecs = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i+batch_size]
        vecs = embed_texts(batch, model=args.model)
        all_sentence_vecs.append(vecs)
        if (i // batch_size + 1) % 5 == 0:
            print(f"  {min(i+batch_size, len(sentences))}/{len(sentences)}", flush=True)
    sentence_vecs = np.vstack(all_sentence_vecs)
    print(f"  Done in {time.time()-t0:.1f}s", flush=True)

    # Solve for matrices using ALL data (for analysis)
    M_verb, M_obj = solve_role_matrices(sentence_vecs, components, word_vecs)

    # Evaluate on training data (upper bound)
    print(f"\n{'='*60}", flush=True)
    print(f"TRAINING SET EVALUATION (upper bound)", flush=True)
    print(f"{'='*60}", flush=True)

    mat_cos, base_cos = evaluate_prediction(sentence_vecs, components, word_vecs, M_verb, M_obj)
    print(f"  Matrix prediction:   mean={mat_cos.mean():.4f}, median={np.median(mat_cos):.4f}, std={mat_cos.std():.4f}", flush=True)
    print(f"  Baseline (addition): mean={base_cos.mean():.4f}, median={np.median(base_cos):.4f}, std={base_cos.std():.4f}", flush=True)
    print(f"  Improvement:         {mat_cos.mean() - base_cos.mean():+.4f}", flush=True)

    # Leave-one-out evaluation (generalization)
    print(f"\n{'='*60}", flush=True)
    print(f"LEAVE-ONE-OUT EVALUATION (generalization)", flush=True)
    print(f"{'='*60}", flush=True)

    loo_mat, loo_base = leave_one_out_evaluation(sentence_vecs, components, word_vecs)
    print(f"  Matrix prediction:   mean={loo_mat.mean():.4f}, median={np.median(loo_mat):.4f}, std={loo_mat.std():.4f}", flush=True)
    print(f"  Baseline (addition): mean={loo_base.mean():.4f}, median={np.median(loo_base):.4f}, std={loo_base.std():.4f}", flush=True)
    print(f"  Improvement:         {loo_mat.mean() - loo_base.mean():+.4f}", flush=True)

    # Matrix analysis
    analyze_matrices(M_verb, M_obj)

    # Save results
    output = {
        'model': args.model,
        'n_sentences': len(sentences),
        'n_subjects': len(SUBJECTS),
        'n_verbs': len(VERBS),
        'n_objects': len(OBJECTS),
        'embedding_dim': int(sentence_vecs.shape[1]),
        'training_set': {
            'matrix_mean_cosine': float(mat_cos.mean()),
            'matrix_median_cosine': float(np.median(mat_cos)),
            'baseline_mean_cosine': float(base_cos.mean()),
            'baseline_median_cosine': float(np.median(base_cos)),
            'improvement': float(mat_cos.mean() - base_cos.mean()),
        },
        'leave_one_out': {
            'n_evaluated': len(loo_mat),
            'matrix_mean_cosine': float(loo_mat.mean()),
            'matrix_median_cosine': float(np.median(loo_mat)),
            'baseline_mean_cosine': float(loo_base.mean()),
            'baseline_median_cosine': float(np.median(loo_base)),
            'improvement': float(loo_mat.mean() - loo_base.mean()),
        },
        'matrix_properties': {
            'M_verb_frobenius': float(np.linalg.norm(M_verb, 'fro')),
            'M_obj_frobenius': float(np.linalg.norm(M_obj, 'fro')),
            'M_verb_identity_distance': float(np.linalg.norm(M_verb - np.eye(M_verb.shape[0]), 'fro')),
            'M_obj_identity_distance': float(np.linalg.norm(M_obj - np.eye(M_obj.shape[0]), 'fro')),
        },
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {args.output}", flush=True)

    # Save matrices for cross-model transfer
    matrix_path = str(DATA_DIR / f'matrices_{args.model.replace("/", "_")}.npz')
    np.savez_compressed(matrix_path, M_verb=M_verb, M_obj=M_obj)
    print(f"Matrices saved to {matrix_path}", flush=True)


if __name__ == '__main__':
    main()
