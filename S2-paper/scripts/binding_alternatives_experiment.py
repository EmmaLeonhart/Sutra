"""
S2 Alternative Binding Operations Experiment
==============================================
Hadamard product fails as binding on natural embeddings (too much crosstalk
in bundled structures). Test alternatives:

1. Circular convolution (Plate's HRR) — the classic VSA binding
2. Random projection binding — multiply by a fixed random matrix
3. XOR-like binding via sign flipping — flip signs based on role
4. Learned rotation — orthogonal matrix derived from role
5. Dimension permutation — shuffle dimensions based on role hash
6. Circular convolution in Fourier domain — efficient via FFT
"""

import sys
import io
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


def embed_texts(model, tokenizer, texts, device='cpu'):
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


# === BINDING OPERATIONS ===

def bind_hadamard(a, role):
    """Standard Hadamard (elementwise multiply). Known to fail."""
    return a * role

def unbind_hadamard(bound, role):
    return bound / (role + 1e-10)


def bind_circular_conv(a, role):
    """Circular convolution (Plate's HRR). Binding in Fourier domain."""
    return np.real(np.fft.ifft(np.fft.fft(a) * np.fft.fft(role)))

def unbind_circular_conv(bound, role):
    """Circular correlation (approximate inverse of circular convolution)."""
    role_inv = np.real(np.fft.ifft(1.0 / (np.fft.fft(role) + 1e-10)))
    return np.real(np.fft.ifft(np.fft.fft(bound) * np.fft.fft(role_inv)))


def bind_sign_flip(a, role):
    """Sign-flip binding: flip signs of a based on sign of role."""
    signs = np.sign(role)
    signs[signs == 0] = 1
    return a * signs

def unbind_sign_flip(bound, role):
    """Self-inverse: applying the same sign flip undoes it."""
    signs = np.sign(role)
    signs[signs == 0] = 1
    return bound * signs


def _role_to_permutation(role, dim):
    """Deterministic permutation from a role vector."""
    # Use role values as sort keys to get a deterministic permutation
    return np.argsort(role)

def bind_permutation(a, role):
    """Permutation binding: rearrange dimensions based on role."""
    perm = _role_to_permutation(role, len(a))
    return a[perm]

def unbind_permutation(bound, role):
    """Inverse permutation."""
    perm = _role_to_permutation(role, len(bound))
    inv_perm = np.argsort(perm)
    return bound[inv_perm]


def _role_to_rotation_matrix(role, dim, n_rotations=50):
    """
    Build an approximate rotation from a role vector using Givens rotations.
    Uses pairs of dimensions determined by role values.
    """
    # Seed a local RNG from the role's hash for determinism
    seed = int(np.abs(role[:4]).sum() * 1e6) % (2**31)
    rng = np.random.RandomState(seed)

    # Apply n_rotations Givens rotations
    result = np.eye(dim, dtype=np.float64)
    for _ in range(n_rotations):
        i, j = rng.choice(dim, 2, replace=False)
        angle = rng.uniform(0, 2 * np.pi)
        c, s = np.cos(angle), np.sin(angle)
        G = np.eye(dim, dtype=np.float64)
        G[i, i] = c
        G[j, j] = c
        G[i, j] = -s
        G[j, i] = s
        result = G @ result
    return result

# Cache rotation matrices (they're expensive to compute)
_rotation_cache = {}

def bind_rotation(a, role):
    """Rotation binding: apply a role-dependent orthogonal rotation."""
    key = role.tobytes()
    if key not in _rotation_cache:
        _rotation_cache[key] = _role_to_rotation_matrix(role, len(a))
    R = _rotation_cache[key]
    return R @ a

def unbind_rotation(bound, role):
    """Inverse rotation (transpose of orthogonal matrix)."""
    key = role.tobytes()
    if key not in _rotation_cache:
        _rotation_cache[key] = _role_to_rotation_matrix(role, len(bound))
    R = _rotation_cache[key]
    return R.T @ bound


def bind_map_fft(a, role):
    """
    MAP (Multiply-Add-Permute) binding variant.
    Multiply in frequency domain then shift.
    """
    fa = np.fft.fft(a)
    fr = np.fft.fft(role)
    bound_fft = fa * fr
    return np.real(np.fft.ifft(bound_fft))

def unbind_map_fft(bound, role):
    """MAP unbinding via conjugate in frequency domain."""
    fb = np.fft.fft(bound)
    fr = np.fft.fft(role)
    # Correlation = multiply by conjugate
    unbound_fft = fb * np.conj(fr)
    return np.real(np.fft.ifft(unbound_fft))


# === TEST HARNESS ===

BINDING_METHODS = {
    'hadamard': (bind_hadamard, unbind_hadamard),
    'circular_conv': (bind_circular_conv, unbind_circular_conv),
    'sign_flip': (bind_sign_flip, unbind_sign_flip),
    'permutation': (bind_permutation, unbind_permutation),
    'rotation': (bind_rotation, unbind_rotation),
    'fft_correlation': (bind_map_fft, unbind_map_fft),
}


def test_single_bind_unbind(fillers, labels, method_name, bind_fn, unbind_fn, roles):
    """Basic test: bind then unbind, no bundling."""
    a = fillers[0]
    role = roles[0]
    bound = bind_fn(a, role)
    recovered = unbind_fn(bound, role)
    cos = cosine_similarity(recovered, a)
    return cos


def test_bundled_recovery(fillers, labels, method_name, bind_fn, unbind_fn, roles):
    """
    Build bundled structures with N role-filler pairs, recover target.
    The critical test.
    """
    codebook = np.array(fillers)
    dim = fillers.shape[1]
    results = []

    for num_roles in range(1, min(len(fillers), 8)):
        # Build structure
        structure = np.zeros(dim, dtype=np.float64)
        for i in range(num_roles):
            structure += bind_fn(fillers[i].astype(np.float64), roles[i].astype(np.float64))

        # Recover filler[0]
        recovered = unbind_fn(structure, roles[0].astype(np.float64))
        raw_cos = cosine_similarity(recovered, fillers[0])

        # Snap
        snapped, snap_idx, snap_dist = snap_to_nearest(recovered, codebook)
        snap_correct = snap_idx == 0

        # Rank
        diffs = codebook - recovered
        dists = np.linalg.norm(diffs, axis=1)
        rank = int(np.where(np.argsort(dists) == 0)[0][0]) + 1

        results.append({
            'num_roles': num_roles,
            'raw_cos': raw_cos,
            'snap_correct': snap_correct,
            'target_rank': rank,
        })

    return results


def benchmark_cost(bind_fn, unbind_fn, a, role, n_iter=5000):
    """Time a binding operation."""
    t0 = time.perf_counter()
    for _ in range(n_iter):
        bound = bind_fn(a, role)
    bind_time = (time.perf_counter() - t0) / n_iter

    t0 = time.perf_counter()
    bound = bind_fn(a, role)
    for _ in range(n_iter):
        _ = unbind_fn(bound, role)
    unbind_time = (time.perf_counter() - t0) / n_iter

    return bind_time * 1e6, unbind_time * 1e6  # microseconds


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='thenlper/gte-large')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    print(f"S2 Alternative Binding Operations Experiment")
    print(f"============================================")
    print(f"Model: {args.model}\n")

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
    dim = fillers.shape[1]
    print(f"Shape: {fillers.shape}\n")

    # Random roles (same for all methods for fair comparison)
    np.random.seed(42)
    random_roles = np.random.randn(len(fillers), dim).astype(np.float32)

    all_results = {}

    # === Single bind/unbind test ===
    print("=== SINGLE BIND/UNBIND (no bundling) ===")
    print(f"{'Method':<20} | {'cos(recovered, original)':>26}")
    print(f"{'-'*20} | {'-'*26}")
    for name, (bind_fn, unbind_fn) in BINDING_METHODS.items():
        _rotation_cache.clear()
        cos = test_single_bind_unbind(fillers, labels, name, bind_fn, unbind_fn, random_roles)
        print(f"{name:<20} | {cos:>26.6f}")

    # === Bundled recovery (THE critical test) ===
    print("\n=== BUNDLED STRUCTURE RECOVERY ===")
    print("Number of role-filler pairs bundled → can we recover filler[0]?\n")

    header = f"{'N roles':>7}"
    for name in BINDING_METHODS:
        header += f" | {name:>16}"
    print(header)
    print("-" * len(header))

    method_results = {}
    for name, (bind_fn, unbind_fn) in BINDING_METHODS.items():
        _rotation_cache.clear()
        results = test_bundled_recovery(fillers, labels, name, bind_fn, unbind_fn, random_roles)
        method_results[name] = results

    # Print comparison table
    for i in range(7):  # 1-7 roles
        row = f"{i+1:>7}"
        for name in BINDING_METHODS:
            r = method_results[name][i]
            marker = "OK" if r['snap_correct'] else f"r{r['target_rank']}"
            row += f" | {r['raw_cos']:>8.4f} {marker:>6}"
        print(row)

    # === Summary: max roles with correct snap ===
    print("\n=== MAX ROLES WITH CORRECT SNAP ===")
    for name in BINDING_METHODS:
        results = method_results[name]
        max_correct = 0
        for r in results:
            if r['snap_correct']:
                max_correct = r['num_roles']
            else:
                break
        all_correct = sum(1 for r in results if r['snap_correct'])
        print(f"  {name:<20}: max consecutive correct = {max_correct}, total correct = {all_correct}/7")

    # === Cost benchmark ===
    print("\n=== OPERATION COST ===")
    print(f"{'Method':<20} | {'Bind (μs)':>12} | {'Unbind (μs)':>12} | {'vs Hadamard':>12}")
    print(f"{'-'*20} | {'-'*12} | {'-'*12} | {'-'*12}")

    costs = {}
    a = fillers[0].astype(np.float64)
    role = random_roles[0].astype(np.float64)
    hadamard_bind_cost = None

    for name, (bind_fn, unbind_fn) in BINDING_METHODS.items():
        _rotation_cache.clear()
        # Pre-warm rotation cache
        if name == 'rotation':
            _ = bind_fn(a, role)
        bind_us, unbind_us = benchmark_cost(bind_fn, unbind_fn, a, role)
        costs[name] = {'bind_us': bind_us, 'unbind_us': unbind_us}
        if name == 'hadamard':
            hadamard_bind_cost = bind_us
        ratio = f"{bind_us/hadamard_bind_cost:.1f}x" if hadamard_bind_cost else "-"
        print(f"{name:<20} | {bind_us:>12.1f} | {unbind_us:>12.1f} | {ratio:>12}")

    # === Final verdict ===
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    for name in BINDING_METHODS:
        results = method_results[name]
        max_correct = 0
        for r in results:
            if r['snap_correct']:
                max_correct = r['num_roles']
            else:
                break
        cost = costs[name]['bind_us']
        verdict = "VIABLE" if max_correct >= 3 else "INSUFFICIENT" if max_correct >= 2 else "FAILS"
        print(f"  {name:<20}: capacity={max_correct} roles, cost={cost:.1f}μs → {verdict}")

    # Save
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        save_data = {
            'model': args.model,
            'methods': {},
        }
        for name in BINDING_METHODS:
            save_data['methods'][name] = {
                'bundled_results': method_results[name],
                'costs': costs[name],
            }
        with open(args.output, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
        print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
