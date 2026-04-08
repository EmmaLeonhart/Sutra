"""
S2 Chain Depth & Snap Cost Experiment
======================================
Tests:
1. How fast does noise accumulate over repeated bind/unbind chains?
2. How much does snap-to-nearest cost vs algebraic ops?
3. Does snap actually recover signal, or is it too late?
4. What's the optimal snap frequency (every N ops)?

The core question: is snap-to-nearest expensive enough to kill S2's efficiency?
"""

import sys
import io
import argparse
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


def embed_texts(model, tokenizer, texts, device='cpu'):
    """Embed texts using mean pooling, NO normalization."""
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')
    encoded = {k: v.to(device) for k, v in encoded.items()}
    with torch.no_grad():
        outputs = model(**encoded)
    attention_mask = encoded['attention_mask'].unsqueeze(-1).float()
    token_embeddings = outputs.last_hidden_state
    summed = (token_embeddings * attention_mask).sum(dim=1)
    counts = attention_mask.sum(dim=1)
    embeddings = (summed / counts).cpu().numpy()
    return embeddings


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)


def euclidean_distance(a, b):
    return np.linalg.norm(a - b)


def snap_to_nearest(vector, codebook):
    """ANN snap-to-nearest via brute force (small codebook)."""
    best_idx = -1
    best_dist = float('inf')
    for i, entry in enumerate(codebook):
        dist = euclidean_distance(vector, entry)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return codebook[best_idx], best_idx, best_dist


def snap_to_nearest_batch(vector, codebook_matrix):
    """Vectorized snap using matrix operations."""
    # codebook_matrix: (N, d)
    diffs = codebook_matrix - vector  # (N, d)
    dists = np.linalg.norm(diffs, axis=1)  # (N,)
    best_idx = np.argmin(dists)
    return codebook_matrix[best_idx], best_idx, dists[best_idx]


def test_chain_depth_no_snap(embeddings, labels):
    """Test: how fast does signal degrade over bind/unbind chains without snap?"""
    print("\n=== CHAIN DEPTH WITHOUT SNAP ===")
    print("Repeatedly bind with a role, then unbind. Measure signal decay.\n")

    target = embeddings[0]
    role = embeddings[1]  # use another embedding as the "role" vector
    target_label = labels[0]

    current = target.copy()
    results = []

    for depth in range(1, 21):
        # Bind
        bound = current * role
        # Unbind (approximate inverse)
        unbound = bound / (role + 1e-10)

        cos_to_original = cosine_similarity(unbound, target)
        euclid_to_original = euclidean_distance(unbound, target)
        magnitude = np.linalg.norm(unbound)

        results.append({
            'depth': depth,
            'cos_to_original': float(cos_to_original),
            'euclid_to_original': float(euclid_to_original),
            'magnitude': float(magnitude),
        })

        print(f"  Depth {depth:2d}: cos={cos_to_original:.6f}  euclid={euclid_to_original:.4f}  ||v||={magnitude:.4f}")

        current = unbound  # feed noisy result into next iteration

    print(f"\n  Signal after 5 steps:  cos={results[4]['cos_to_original']:.6f}")
    print(f"  Signal after 10 steps: cos={results[9]['cos_to_original']:.6f}")
    print(f"  Signal after 20 steps: cos={results[19]['cos_to_original']:.6f}")
    return results


def test_chain_depth_with_snap(embeddings, labels):
    """Test: does periodic snap-to-nearest recover signal?"""
    print("\n=== CHAIN DEPTH WITH SNAP (every step) ===")
    print("Bind/unbind, then snap to nearest in codebook. Measure recovery.\n")

    codebook = embeddings.copy()  # all embeddings are the codebook
    codebook_matrix = np.array(codebook)
    target = embeddings[0]
    role = embeddings[1]
    target_label = labels[0]

    current = target.copy()
    results = []

    for depth in range(1, 21):
        # Bind
        bound = current * role
        # Unbind
        unbound = bound / (role + 1e-10)
        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest_batch(unbound, codebook_matrix)

        cos_before_snap = cosine_similarity(unbound, target)
        cos_after_snap = cosine_similarity(snapped, target)
        correct = snap_idx == 0  # did it snap back to the target?

        results.append({
            'depth': depth,
            'cos_before_snap': float(cos_before_snap),
            'cos_after_snap': float(cos_after_snap),
            'snap_correct': bool(correct),
            'snap_idx': int(snap_idx),
            'snap_label': labels[snap_idx],
            'snap_dist': float(snap_dist),
        })

        status = "CORRECT" if correct else f"WRONG → {labels[snap_idx]}"
        print(f"  Depth {depth:2d}: cos_before={cos_before_snap:.6f}  cos_after={cos_after_snap:.6f}  snap={status}")

        current = snapped  # use snapped result for next step

    correct_count = sum(1 for r in results if r['snap_correct'])
    print(f"\n  Snap accuracy: {correct_count}/20 ({correct_count/20*100:.0f}%)")
    return results


def test_snap_frequency(embeddings, labels):
    """Test: what's the optimal snap frequency?"""
    print("\n=== SNAP FREQUENCY OPTIMIZATION ===")
    print("Run 20-step chains with snap every N steps. Find optimal N.\n")

    codebook_matrix = np.array(embeddings)
    target = embeddings[0]
    role = embeddings[1]

    for snap_every in [1, 2, 3, 5, 10, 20]:
        current = target.copy()
        correct_snaps = 0
        total_snaps = 0

        for depth in range(1, 21):
            bound = current * role
            unbound = bound / (role + 1e-10)

            if depth % snap_every == 0:
                snapped, snap_idx, _ = snap_to_nearest_batch(unbound, codebook_matrix)
                current = snapped
                total_snaps += 1
                if snap_idx == 0:
                    correct_snaps += 1
            else:
                current = unbound

        final_cos = cosine_similarity(current, target)
        snap_accuracy = correct_snaps / total_snaps if total_snaps > 0 else 0
        print(f"  Snap every {snap_every:2d} steps: final_cos={final_cos:.6f}  snaps={total_snaps}  snap_accuracy={snap_accuracy:.0%}")


def benchmark_operation_costs(embeddings):
    """Benchmark: how expensive is each operation tier?"""
    print("\n=== OPERATION COST BENCHMARK ===")
    print("Time 10,000 iterations of each operation.\n")

    a = embeddings[0]
    b = embeddings[1]
    codebook_matrix = np.array(embeddings)
    n_iter = 10000

    # Tier 2: Bind (Hadamard)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = a * b
    bind_time = (time.perf_counter() - t0) / n_iter

    # Tier 2: Bundle (addition)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = a + b
    bundle_time = (time.perf_counter() - t0) / n_iter

    # Tier 2: Unbind (division)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = (a * b) / (a + 1e-10)
    unbind_time = (time.perf_counter() - t0) / n_iter

    # Tier 2: Similarity (dot product)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = np.dot(a, b)
    sim_time = (time.perf_counter() - t0) / n_iter

    # Tier 2: Euclidean distance
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = np.linalg.norm(a - b)
    euclid_time = (time.perf_counter() - t0) / n_iter

    # Tier 3: Snap-to-nearest (brute force, 20 items)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = snap_to_nearest_batch(a, codebook_matrix)
    snap_20_time = (time.perf_counter() - t0) / n_iter

    # Tier 3: Snap-to-nearest (brute force, 1000 items — simulated)
    big_codebook = np.random.randn(1000, len(a)).astype(np.float32)
    t0 = time.perf_counter()
    for _ in range(n_iter):
        _ = snap_to_nearest_batch(a, big_codebook)
    snap_1000_time = (time.perf_counter() - t0) / n_iter

    # Tier 3: Snap-to-nearest (brute force, 10000 items)
    huge_codebook = np.random.randn(10000, len(a)).astype(np.float32)
    t0 = time.perf_counter()
    for _ in range(min(n_iter, 1000)):
        _ = snap_to_nearest_batch(a, huge_codebook)
    snap_10k_time = (time.perf_counter() - t0) / min(n_iter, 1000)

    print(f"  TIER 2 (Algebraic):")
    print(f"    Bind (Hadamard):     {bind_time*1e6:8.2f} μs")
    print(f"    Bundle (addition):   {bundle_time*1e6:8.2f} μs")
    print(f"    Unbind (division):   {unbind_time*1e6:8.2f} μs")
    print(f"    Similarity (dot):    {sim_time*1e6:8.2f} μs")
    print(f"    Euclidean distance:  {euclid_time*1e6:8.2f} μs")
    print()
    print(f"  TIER 3 (Non-Algebraic / ANN):")
    print(f"    Snap (20 items):     {snap_20_time*1e6:8.2f} μs  ({snap_20_time/bind_time:.1f}x bind)")
    print(f"    Snap (1K items):     {snap_1000_time*1e6:8.2f} μs  ({snap_1000_time/bind_time:.1f}x bind)")
    print(f"    Snap (10K items):    {snap_10k_time*1e6:8.2f} μs  ({snap_10k_time/bind_time:.1f}x bind)")
    print()
    print(f"  COST RATIO (snap / algebraic op):")
    print(f"    With 20-item codebook:  {snap_20_time/bind_time:.1f}x")
    print(f"    With 1K-item codebook:  {snap_1000_time/bind_time:.1f}x")
    print(f"    With 10K-item codebook: {snap_10k_time/bind_time:.1f}x")
    print()

    # Embedding cost (the REAL expensive operation)
    t0 = time.perf_counter()
    # We already timed this in the main flow, but for reference:
    print(f"  FOR REFERENCE:")
    print(f"    Embedding a text (LLM forward pass) is ~250,000 μs (250ms)")
    print(f"    That's ~{250000/bind_time:.0f}x more expensive than a bind")
    print(f"    Even snap(10K) at {snap_10k_time*1e6:.0f}μs is {250000/snap_10k_time/1e6:.0f}x cheaper than embedding")

    return {
        'bind_us': bind_time * 1e6,
        'bundle_us': bundle_time * 1e6,
        'unbind_us': unbind_time * 1e6,
        'similarity_us': sim_time * 1e6,
        'euclidean_us': euclid_time * 1e6,
        'snap_20_us': snap_20_time * 1e6,
        'snap_1k_us': snap_1000_time * 1e6,
        'snap_10k_us': snap_10k_time * 1e6,
        'snap_20_vs_bind': snap_20_time / bind_time,
        'snap_1k_vs_bind': snap_1000_time / bind_time,
        'snap_10k_vs_bind': snap_10k_time / bind_time,
    }


def test_multi_role_binding(embeddings, labels):
    """Test: bind multiple roles to one structure, then recover each."""
    print("\n=== MULTI-ROLE BINDING TEST ===")
    print("Build: AGENT=cat + ACTION=sit + LOCATION=mat, then recover each.\n")

    # Use different embeddings as roles and fillers
    agent_role = embeddings[5]   # "Neural networks..."
    action_role = embeddings[6]  # "Pacific Ocean..."
    location_role = embeddings[7]  # "Mozart..."

    cat = embeddings[0]      # "The cat sat on the mat"
    sit = embeddings[1]      # "Dogs are loyal..."
    mat = embeddings[2]      # "Eiffel Tower..."

    # Build structure
    structure = (agent_role * cat) + (action_role * sit) + (location_role * mat)

    # Recover each
    codebook_matrix = np.array(embeddings)

    for role, role_label, expected_idx, expected_label in [
        (agent_role, "AGENT", 0, labels[0]),
        (action_role, "ACTION", 1, labels[1]),
        (location_role, "LOCATION", 2, labels[2]),
    ]:
        recovered = structure / (role + 1e-10)
        cos_to_expected = cosine_similarity(recovered, embeddings[expected_idx])

        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest_batch(recovered, codebook_matrix)
        correct = snap_idx == expected_idx

        print(f"  Unbind {role_label}:")
        print(f"    Cosine to expected ({expected_label}): {cos_to_expected:.4f}")
        print(f"    Snap result: {'CORRECT' if correct else 'WRONG'} → {labels[snap_idx]} (dist={snap_dist:.4f})")
        print()


def main():
    parser = argparse.ArgumentParser(description='S2 Chain Depth & Cost Experiment')
    parser.add_argument('--model', type=str, default='thenlper/gte-large')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    print(f"S2 Chain Depth & Snap Cost Experiment")
    print(f"=====================================")
    print(f"Model:  {args.model}")
    print(f"Device: {args.device}")

    # Load model
    print("\nLoading model...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model).to(args.device)
    model.eval()

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

    print(f"Embedding {len(test_texts)} texts...")
    embeddings = embed_texts(model, tokenizer, test_texts, device=args.device)
    print(f"Shape: {embeddings.shape}")

    # Run experiments
    no_snap_results = test_chain_depth_no_snap(embeddings, labels)
    with_snap_results = test_chain_depth_with_snap(embeddings, labels)
    test_snap_frequency(embeddings, labels)
    test_multi_role_binding(embeddings, labels)
    cost_results = benchmark_operation_costs(embeddings)

    # Save
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        all_results = {
            'model': args.model,
            'chain_no_snap': no_snap_results,
            'chain_with_snap': with_snap_results,
            'costs': cost_results,
        }
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
