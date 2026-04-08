"""
S2 Empirical Initiation Prototype
==================================
Tests whether an embedding model's space supports S2's algebraic operations
WITHOUT normalization. Uses Euclidean distance as primary metric.

Tests:
1. Binding (Hadamard product): a*b should be distant from both a and b
2. Unbinding (approximate inverse): unbind(a, a*b) ≈ b
3. Bundling (addition): a+b should be closer to both a and b than random
4. Magnitude distribution: vectors should NOT all have the same magnitude
5. Capacity: how many items can be bundled before SNR degrades

Usage:
    python empirical_initiation.py [--model MODEL_NAME]
"""

import sys
import io
import argparse
import json
import time
from pathlib import Path

# Windows UTF-8 fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


def embed_texts(model, tokenizer, texts, device='cpu', pooling='mean'):
    """Embed a list of texts using mean pooling, NO normalization."""
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        outputs = model(**encoded)

    # Mean pooling over token positions (excluding padding)
    attention_mask = encoded['attention_mask'].unsqueeze(-1).float()
    token_embeddings = outputs.last_hidden_state
    summed = (token_embeddings * attention_mask).sum(dim=1)
    counts = attention_mask.sum(dim=1)
    embeddings = (summed / counts).cpu().numpy()

    # DO NOT NORMALIZE — magnitude is meaningful
    return embeddings


def euclidean_distance(a, b):
    """Euclidean distance between two vectors."""
    return np.linalg.norm(a - b)


def cosine_similarity(a, b):
    """Cosine similarity (for comparison only — S2 uses Euclidean)."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)


def test_binding(embeddings, labels):
    """Test: Hadamard product (binding) produces vectors distant from inputs."""
    print("\n=== BINDING TEST (Hadamard Product) ===")
    print("Expectation: bind(a, b) should be DISTANT from both a and b")
    print()

    results = []
    n = len(embeddings)
    for i in range(min(n, 5)):
        for j in range(i+1, min(n, 5)):
            a, b = embeddings[i], embeddings[j]
            bound = a * b  # Hadamard product

            dist_a = euclidean_distance(bound, a)
            dist_b = euclidean_distance(bound, b)
            dist_ab = euclidean_distance(a, b)
            cos_a = cosine_similarity(bound, a)
            cos_b = cosine_similarity(bound, b)

            results.append({
                'pair': f'{labels[i]} * {labels[j]}',
                'dist_bound_a': dist_a,
                'dist_bound_b': dist_b,
                'dist_a_b': dist_ab,
                'cos_bound_a': cos_a,
                'cos_bound_b': cos_b,
            })

            print(f"  {labels[i]} * {labels[j]}:")
            print(f"    Euclidean dist(bound, a) = {dist_a:.4f}")
            print(f"    Euclidean dist(bound, b) = {dist_b:.4f}")
            print(f"    Euclidean dist(a, b)     = {dist_ab:.4f}")
            print(f"    Cosine sim(bound, a)     = {cos_a:.4f}")
            print(f"    Cosine sim(bound, b)     = {cos_b:.4f}")
            print()

    # Binding should increase distance
    avg_dissimilarity = np.mean([(r['dist_bound_a'] + r['dist_bound_b']) / 2 for r in results])
    avg_input_dist = np.mean([r['dist_a_b'] for r in results])
    avg_cos = np.mean([(r['cos_bound_a'] + r['cos_bound_b']) / 2 for r in results])

    print(f"  SUMMARY:")
    print(f"    Avg Euclidean distance (bound ↔ inputs): {avg_dissimilarity:.4f}")
    print(f"    Avg Euclidean distance (input ↔ input):  {avg_input_dist:.4f}")
    print(f"    Avg cosine similarity (bound ↔ inputs):  {avg_cos:.4f}")
    binding_works = avg_cos < 0.5
    print(f"    Binding {'WORKS' if binding_works else 'FAILS'}: bound vectors are {'dissimilar' if binding_works else 'still similar'} to inputs")
    return results, binding_works


def test_unbinding(embeddings, labels):
    """Test: unbind(a, bind(a, b)) ≈ b"""
    print("\n=== UNBINDING TEST (Approximate Inverse) ===")
    print("Expectation: unbind(a, a*b) should be CLOSE to b")
    print()

    results = []
    n = len(embeddings)
    for i in range(min(n, 5)):
        for j in range(i+1, min(n, 5)):
            a, b = embeddings[i], embeddings[j]
            bound = a * b

            # Unbinding: elementwise division (approximate inverse of Hadamard)
            # Add small epsilon to avoid division by zero
            unbound = bound / (a + 1e-10)

            dist_to_b = euclidean_distance(unbound, b)
            cos_to_b = cosine_similarity(unbound, b)

            # Compare to random baseline
            random_idx = (j + 1) % n
            dist_to_random = euclidean_distance(unbound, embeddings[random_idx])
            cos_to_random = cosine_similarity(unbound, embeddings[random_idx])

            results.append({
                'pair': f'unbind({labels[i]}, {labels[i]}*{labels[j]})',
                'target': labels[j],
                'dist_to_target': dist_to_b,
                'cos_to_target': cos_to_b,
                'dist_to_random': dist_to_random,
                'cos_to_random': cos_to_random,
            })

            print(f"  unbind({labels[i]}, {labels[i]}*{labels[j]}):")
            print(f"    Euclidean dist to {labels[j]} (target):  {dist_to_b:.4f}")
            print(f"    Euclidean dist to {labels[random_idx]} (random): {dist_to_random:.4f}")
            print(f"    Cosine sim to {labels[j]} (target):     {cos_to_b:.4f}")
            print(f"    Cosine sim to {labels[random_idx]} (random):    {cos_to_random:.4f}")
            print()

    avg_target_cos = np.mean([r['cos_to_target'] for r in results])
    avg_random_cos = np.mean([r['cos_to_random'] for r in results])
    unbinding_works = avg_target_cos > avg_random_cos + 0.1

    print(f"  SUMMARY:")
    print(f"    Avg cosine to target:  {avg_target_cos:.4f}")
    print(f"    Avg cosine to random:  {avg_random_cos:.4f}")
    print(f"    Unbinding {'WORKS' if unbinding_works else 'FAILS'}: recovered vectors are {'closer to target' if unbinding_works else 'not distinguishable from random'}")
    return results, unbinding_works


def test_bundling(embeddings, labels):
    """Test: a+b should be similar to both a and b (superposition)."""
    print("\n=== BUNDLING TEST (Addition / Superposition) ===")
    print("Expectation: a+b should be CLOSER to both a and b than to unrelated vectors")
    print()

    results = []
    n = len(embeddings)
    for i in range(min(n, 4)):
        for j in range(i+1, min(n, 4)):
            a, b = embeddings[i], embeddings[j]
            bundled = a + b

            cos_a = cosine_similarity(bundled, a)
            cos_b = cosine_similarity(bundled, b)
            dist_a = euclidean_distance(bundled, a)
            dist_b = euclidean_distance(bundled, b)

            # Random baseline
            random_idx = (j + 2) % n
            cos_random = cosine_similarity(bundled, embeddings[random_idx])

            results.append({
                'pair': f'{labels[i]} + {labels[j]}',
                'cos_a': cos_a,
                'cos_b': cos_b,
                'cos_random': cos_random,
                'dist_a': dist_a,
                'dist_b': dist_b,
            })

            print(f"  {labels[i]} + {labels[j]}:")
            print(f"    Cosine sim to {labels[i]}:    {cos_a:.4f}")
            print(f"    Cosine sim to {labels[j]}:    {cos_b:.4f}")
            print(f"    Cosine sim to {labels[random_idx]} (random): {cos_random:.4f}")
            print(f"    Euclidean dist to {labels[i]}: {dist_a:.4f}")
            print(f"    Euclidean dist to {labels[j]}: {dist_b:.4f}")
            print()

    avg_component_cos = np.mean([(r['cos_a'] + r['cos_b']) / 2 for r in results])
    avg_random_cos = np.mean([r['cos_random'] for r in results])
    bundling_works = avg_component_cos > avg_random_cos + 0.05

    print(f"  SUMMARY:")
    print(f"    Avg cosine to components: {avg_component_cos:.4f}")
    print(f"    Avg cosine to random:     {avg_random_cos:.4f}")
    print(f"    Bundling {'WORKS' if bundling_works else 'FAILS'}: superposition {'preserves' if bundling_works else 'does not preserve'} membership")
    return results, bundling_works


def test_magnitude_distribution(embeddings, labels):
    """Test: vectors should NOT all have the same magnitude."""
    print("\n=== MAGNITUDE DISTRIBUTION TEST ===")
    print("Expectation: magnitudes should VARY (not normalized to unit sphere)")
    print()

    magnitudes = [np.linalg.norm(e) for e in embeddings]

    for label, mag in zip(labels, magnitudes):
        print(f"  ||{label}|| = {mag:.4f}")

    mag_std = np.std(magnitudes)
    mag_mean = np.mean(magnitudes)
    mag_cv = mag_std / mag_mean if mag_mean > 0 else 0  # coefficient of variation

    print(f"\n  Mean magnitude:    {mag_mean:.4f}")
    print(f"  Std magnitude:     {mag_std:.4f}")
    print(f"  Coefficient of variation: {mag_cv:.4f}")

    # If all magnitudes are ~1.0 with tiny std, it's effectively normalized
    is_normalized = (abs(mag_mean - 1.0) < 0.1 and mag_std < 0.01)
    has_variation = mag_cv > 0.01

    if is_normalized:
        print(f"  WARNING: Vectors appear NORMALIZED (mean ≈ 1.0, std ≈ 0)")
        print(f"  This substrate is NOT suitable for S2")
    elif has_variation:
        print(f"  GOOD: Magnitude varies — information is preserved")
    else:
        print(f"  LOW VARIATION: Magnitudes are similar but not unit-normalized")

    return magnitudes, has_variation


def test_bundling_capacity(embeddings, labels):
    """Test: how many items can be bundled before SNR degrades."""
    print("\n=== BUNDLING CAPACITY TEST ===")
    print("How many items can be superposed before membership becomes undetectable?")
    print()

    n = len(embeddings)
    if n < 3:
        print("  Need at least 3 embeddings for capacity test")
        return [], 0

    target = embeddings[0]
    target_label = labels[0]

    max_k = min(n - 1, 20)
    results = []

    for k in range(1, max_k + 1):
        # Bundle target with k-1 other vectors
        bundled = target.copy()
        for i in range(1, k + 1):
            idx = i % n
            if idx == 0:
                idx = 1  # skip the target itself
            bundled = bundled + embeddings[idx]

        cos_to_target = cosine_similarity(bundled, target)

        # Random baseline (not in the bundle)
        random_idx = (k + 5) % n
        if random_idx == 0:
            random_idx = 1
        cos_to_random = cosine_similarity(bundled, embeddings[random_idx])

        snr = cos_to_target - cos_to_random
        results.append({
            'k': k,
            'cos_target': cos_to_target,
            'cos_random': cos_to_random,
            'snr': snr,
        })

        marker = " ← SNR < 0.05, capacity limit" if snr < 0.05 else ""
        print(f"  k={k:2d}: cos(bundle, target)={cos_to_target:.4f}, cos(bundle, random)={cos_to_random:.4f}, SNR={snr:.4f}{marker}")

    # Find capacity (where SNR drops below 0.05)
    capacity = max_k
    for r in results:
        if r['snr'] < 0.05:
            capacity = r['k'] - 1
            break

    print(f"\n  Estimated bundling capacity: ~{capacity} items before SNR < 0.05")
    return results, capacity


def main():
    parser = argparse.ArgumentParser(description='S2 Empirical Initiation')
    parser.add_argument('--model', type=str, default='thenlper/gte-large',
                        help='HuggingFace model name (default: thenlper/gte-large)')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=str, default=None, help='Save results to JSON file')
    args = parser.parse_args()

    print(f"S2 Empirical Initiation")
    print(f"=======================")
    print(f"Model:  {args.model}")
    print(f"Device: {args.device}")
    print()

    # Load model
    print("Loading model...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model).to(args.device)
    model.eval()
    print(f"Loaded in {time.time() - t0:.1f}s")
    print(f"Hidden size: {model.config.hidden_size}")
    print()

    # Test texts — diverse concepts to test algebraic operations
    test_texts = [
        "The cat sat on the mat",
        "Dogs are loyal companions",
        "The Eiffel Tower stands in Paris",
        "Quantum mechanics describes atomic behavior",
        "Shakespeare wrote Hamlet in 1600",
        "Neural networks learn from data",
        "The Pacific Ocean is the largest ocean",
        "Mozart composed symphonies in Vienna",
        "DNA carries genetic information",
        "Democracy means government by the people",
        "Photosynthesis converts sunlight to energy",
        "The Great Wall of China spans thousands of miles",
        "Black holes warp spacetime around them",
        "Coffee beans are roasted before grinding",
        "The Amazon rainforest produces oxygen",
        "Earthquakes occur along tectonic plate boundaries",
        "Antibiotics fight bacterial infections",
        "The stock market reflects economic sentiment",
        "Glaciers are retreating due to climate change",
        "Beethoven composed nine symphonies",
    ]
    labels = [t[:30] + "..." if len(t) > 30 else t for t in test_texts]

    # Embed
    print(f"Embedding {len(test_texts)} test texts...")
    t0 = time.time()
    embeddings = embed_texts(model, tokenizer, test_texts, device=args.device)
    print(f"Embedded in {time.time() - t0:.1f}s")
    print(f"Embedding shape: {embeddings.shape}")

    # Run all tests
    mag_results, mag_ok = test_magnitude_distribution(embeddings, labels)
    bind_results, bind_ok = test_binding(embeddings, labels)
    unbind_results, unbind_ok = test_unbinding(embeddings, labels)
    bundle_results, bundle_ok = test_bundling(embeddings, labels)
    capacity_results, capacity = test_bundling_capacity(embeddings, labels)

    # Validation gates
    print("\n" + "="*60)
    print("VALIDATION GATES")
    print("="*60)
    print(f"  Magnitude variation:  {'PASS' if mag_ok else 'FAIL'}")
    print(f"  Binding dissimilarity: {'PASS' if bind_ok else 'FAIL'}")
    print(f"  Unbinding accuracy:   {'PASS' if unbind_ok else 'FAIL'}")
    print(f"  Bundling membership:  {'PASS' if bundle_ok else 'FAIL'}")
    print(f"  Bundling capacity:    ~{capacity} items")

    all_pass = mag_ok and bind_ok and unbind_ok and bundle_ok
    print(f"\n  Overall: {'SUBSTRATE APPROVED for S2' if all_pass else 'SUBSTRATE REJECTED'}")

    # Save results
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results = {
            'model': args.model,
            'hidden_size': int(model.config.hidden_size),
            'num_test_texts': len(test_texts),
            'magnitude_variation': bool(mag_ok),
            'binding_works': bool(bind_ok),
            'unbinding_works': bool(unbind_ok),
            'bundling_works': bool(bundle_ok),
            'bundling_capacity': int(capacity),
            'all_gates_pass': bool(all_pass),
            'magnitudes': [float(m) for m in mag_results],
        }
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
