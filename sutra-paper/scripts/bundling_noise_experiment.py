"""
Sutra Bundling Noise & Recovery Experiment
============================================
The REAL noise source in Sutra is not chain depth with a single role —
that's mathematically exact. The noise comes from BUNDLED structures
where unbinding one role produces crosstalk from other bound pairs.

Tests:
1. How does recovery accuracy vary with number of roles bundled?
2. Can snap-to-nearest recover from bundling crosstalk?
3. At what point does snap fail (noisy vector closer to wrong entry)?
4. Does the codebook size / composition affect recovery?
5. Role vector choice: random vs natural embeddings as roles
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
    return (summed / counts).cpu().numpy()


def cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def snap_to_nearest(vector, codebook_matrix):
    diffs = codebook_matrix - vector
    dists = np.linalg.norm(diffs, axis=1)
    best_idx = np.argmin(dists)
    return codebook_matrix[best_idx], int(best_idx), float(dists[best_idx])


def test_bundling_recovery_vs_roles(fillers, filler_labels, role_type='natural', roles=None):
    """
    Build structures with increasing numbers of role-filler pairs.
    Try to recover each filler. Measure accuracy with and without snap.
    """
    n = len(fillers)
    dim = fillers.shape[1]
    codebook = np.array(fillers)

    if roles is None:
        if role_type == 'random':
            roles = np.random.randn(n, dim).astype(np.float32)
        else:
            # Use shuffled fillers as roles (natural embeddings)
            idx = np.random.permutation(n)
            roles = fillers[idx]

    print(f"\n  Role type: {role_type}")
    print(f"  {'N roles':>8} | {'Raw cos to target':>18} | {'Snap correct?':>14} | {'Snap cos':>10} | {'Rank of target':>16}")
    print(f"  {'-'*8} | {'-'*18} | {'-'*14} | {'-'*10} | {'-'*16}")

    results = []
    for num_roles in range(1, min(n, 11)):
        # Build bundled structure with num_roles pairs
        structure = np.zeros(dim, dtype=np.float64)
        for i in range(num_roles):
            structure += roles[i] * fillers[i]

        # Try to recover filler 0
        recovered = structure / (roles[0] + 1e-10)
        raw_cos = cosine_similarity(recovered, fillers[0])

        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest(recovered, codebook)
        snap_correct = snap_idx == 0
        snap_cos = cosine_similarity(snapped, fillers[0])

        # Rank of target in codebook by distance
        diffs = codebook - recovered
        dists = np.linalg.norm(diffs, axis=1)
        rank = int(np.where(np.argsort(dists) == 0)[0][0]) + 1

        results.append({
            'num_roles': num_roles,
            'raw_cos': raw_cos,
            'snap_correct': snap_correct,
            'snap_cos': snap_cos,
            'target_rank': rank,
        })

        status = "YES" if snap_correct else "NO"
        print(f"  {num_roles:>8} | {raw_cos:>18.6f} | {status:>14} | {snap_cos:>10.6f} | {rank:>16}")

    return results


def test_random_roles_vs_natural(fillers, filler_labels):
    """Compare random orthogonal roles vs natural embedding roles."""
    print("\n=== RANDOM vs NATURAL ROLES ===")
    print("Random roles should give better separation (more orthogonal).\n")

    dim = fillers.shape[1]
    n = len(fillers)

    # Random roles (truly random, high-dimensional → nearly orthogonal)
    random_roles = np.random.randn(n, dim).astype(np.float32)

    # Natural roles (other embeddings — NOT orthogonal)
    idx = np.random.permutation(n)
    natural_roles = fillers[idx]

    print("--- Random Roles ---")
    random_results = test_bundling_recovery_vs_roles(fillers, filler_labels, 'random', random_roles)

    print("\n--- Natural Embedding Roles ---")
    natural_results = test_bundling_recovery_vs_roles(fillers, filler_labels, 'natural', natural_roles)

    # Summary
    print("\n  COMPARISON:")
    for r_rand, r_nat in zip(random_results, natural_results):
        nr = r_rand['num_roles']
        print(f"    {nr} roles: random cos={r_rand['raw_cos']:.4f} snap={'OK' if r_rand['snap_correct'] else 'FAIL'}  |  natural cos={r_nat['raw_cos']:.4f} snap={'OK' if r_nat['snap_correct'] else 'FAIL'}")

    return random_results, natural_results


def test_chain_through_bundled_structures(fillers, filler_labels):
    """
    The REAL chain test: unbind from structure → use result → build new structure → unbind again.
    This compounds noise from bundling crosstalk.
    """
    print("\n=== CHAINED BUNDLED OPERATIONS ===")
    print("Unbind from structure, use result in next structure, repeat.")
    print("This is where noise actually compounds.\n")

    dim = fillers.shape[1]
    codebook = np.array(fillers)

    # Use random roles for cleaner results
    roles = np.random.randn(len(fillers), dim).astype(np.float32)

    # Target: filler[0]
    current = fillers[0].copy()
    num_bundle_partners = 2  # each structure has 3 role-filler pairs

    results = []
    for step in range(1, 11):
        # Build a structure: bind current with role[0], plus 2 distractors
        structure = roles[0] * current
        for j in range(1, num_bundle_partners + 1):
            partner_idx = (step + j) % len(fillers)
            structure += roles[j] * fillers[partner_idx]

        # Unbind to recover current
        recovered = structure / (roles[0] + 1e-10)
        raw_cos = cosine_similarity(recovered, fillers[0])

        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest(recovered, codebook)
        snap_correct = snap_idx == 0

        results.append({
            'step': step,
            'raw_cos': float(raw_cos),
            'snap_correct': bool(snap_correct),
            'snap_idx': int(snap_idx),
        })

        status = "CORRECT" if snap_correct else f"WRONG → {filler_labels[snap_idx]}"

        # WITHOUT snap: use noisy recovered for next step
        # WITH snap: use snapped for next step
        # Test both paths
        print(f"  Step {step:2d}: raw_cos={raw_cos:.6f}  snap={status}")

        # Use SNAPPED version to continue (best case)
        current = snapped if snap_correct else recovered

    print(f"\n  Steps with correct snap: {sum(1 for r in results if r['snap_correct'])}/10")

    # Now test WITHOUT snap
    print("\n  --- Same chain WITHOUT snap (pure algebraic) ---")
    current = fillers[0].copy()
    for step in range(1, 11):
        structure = roles[0] * current
        for j in range(1, num_bundle_partners + 1):
            partner_idx = (step + j) % len(fillers)
            structure += roles[j] * fillers[partner_idx]
        recovered = structure / (roles[0] + 1e-10)
        raw_cos = cosine_similarity(recovered, fillers[0])
        print(f"  Step {step:2d}: raw_cos={raw_cos:.6f}")
        current = recovered  # NO snap — noise compounds

    return results


def test_codebook_size_effect(fillers, filler_labels):
    """Does adding more items to the codebook help or hurt snap accuracy?"""
    print("\n=== CODEBOOK SIZE EFFECT ===")
    print("Snap accuracy with 5, 10, 20 codebook entries (3-role structures).\n")

    dim = fillers.shape[1]
    roles = np.random.randn(len(fillers), dim).astype(np.float32)

    for codebook_size in [5, 10, 15, 20]:
        codebook = np.array(fillers[:codebook_size])
        # 3-role structure, recover filler[0]
        structure = roles[0] * fillers[0] + roles[1] * fillers[1] + roles[2] * fillers[2]
        recovered = structure / (roles[0] + 1e-10)

        snapped, snap_idx, snap_dist = snap_to_nearest(recovered, codebook)
        snap_correct = snap_idx == 0
        raw_cos = cosine_similarity(recovered, fillers[0])

        # Rank of target
        diffs = codebook - recovered
        dists = np.linalg.norm(diffs, axis=1)
        rank = int(np.where(np.argsort(dists) == 0)[0][0]) + 1

        status = "CORRECT" if snap_correct else f"WRONG (→ idx {snap_idx})"
        print(f"  Codebook size {codebook_size:2d}: raw_cos={raw_cos:.4f}  snap={status}  target_rank={rank}/{codebook_size}")


def main():
    parser = argparse.ArgumentParser(description='Sutra Bundling Noise Experiment')
    parser.add_argument('--model', type=str, default='thenlper/gte-large')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    print(f"Sutra Bundling Noise & Recovery Experiment")
    print(f"=======================================")
    print(f"Model: {args.model}")

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
    fillers = embed_texts(model, tokenizer, test_texts, device=args.device)
    print(f"Shape: {fillers.shape}")

    np.random.seed(42)  # reproducibility

    random_results, natural_results = test_random_roles_vs_natural(fillers, labels)
    chain_results = test_chain_through_bundled_structures(fillers, labels)
    test_codebook_size_effect(fillers, labels)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        all_results = {
            'model': args.model,
            'random_roles': random_results,
            'natural_roles': natural_results,
            'chain_results': chain_results,
        }
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
