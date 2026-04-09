"""
End-to-end tests for the fly brain VSA bridge.

Phase 1 gate: KC sparsity ~5%
Phase 2 gate: Round-trip fidelity and discrimination
Phase 3 gate: Scaled model maintains quality
"""

import numpy as np
from mushroom_body_model import get_kc_sparsity, get_spike_rates, print_summary
from spike_vsa_bridge import SpikeVSABridge, cosine_similarity


def test_sparsity(n_trials=5, n_kc=200):
    """Phase 1 gate: KC sparsity should be ~5% across multiple inputs."""
    print("=" * 60)
    print(f"SPARSITY TEST ({n_trials} trials, {n_kc} KCs)")
    print("=" * 60)

    sparsities = []
    for trial in range(n_trials):
        bridge = SpikeVSABridge(dim=50, seed=trial, n_kc=n_kc)
        vec = np.random.RandomState(trial + 100).randn(50)
        currents = bridge.encode(vec)
        bridge.run(currents, duration_ms=200)
        sparsity = get_kc_sparsity(bridge.model, 200)
        sparsities.append(sparsity)
        print(f"  trial {trial}: sparsity = {sparsity:.1%}")

    mean_sp = np.mean(sparsities)
    print(f"\nMean sparsity: {mean_sp:.1%}")
    passed = all(0.02 <= s <= 0.10 for s in sparsities)
    print(f"GATE: {'PASS' if passed else 'FAIL'} (target: 2-10%)")
    return passed


def test_round_trip(n_kc=200, duration_ms=300):
    """Phase 2 gate: Round-trip fidelity."""
    print("\n" + "=" * 60)
    print(f"ROUND-TRIP FIDELITY TEST ({n_kc} KCs)")
    print("=" * 60)

    bridge = SpikeVSABridge(dim=50, seed=42, n_kc=n_kc)
    original = np.random.RandomState(42).randn(50)

    print(f"Original vector: dim=50, norm={np.linalg.norm(original):.3f}")

    decoded, fidelity = bridge.round_trip(original, duration_ms=duration_ms)

    print(f"\n--- Circuit Activity ---")
    print_summary(bridge.model, duration_ms)
    print(f"\nRound-trip fidelity (KC pseudoinverse): {fidelity:.4f}")

    passed = fidelity > 0.3
    print(f"GATE: {'PASS' if passed else 'FAIL'} (target: > 0.3)")
    return fidelity, passed


def test_discrimination(n_vectors=5, n_kc=200, duration_ms=300):
    """Phase 2 gate: Different inputs produce distinguishable outputs."""
    print("\n" + "=" * 60)
    print(f"DISCRIMINATION TEST ({n_vectors} vectors, {n_kc} KCs)")
    print("=" * 60)

    originals = []
    decoded_vectors = []

    for i in range(n_vectors):
        bridge = SpikeVSABridge(dim=50, seed=42, n_kc=n_kc)  # same connectivity
        original = np.random.RandomState(200 + i).randn(50)
        originals.append(original)

        decoded, fidelity = bridge.round_trip(original, duration_ms=duration_ms)
        decoded_vectors.append(decoded)

    # Similarity matrix
    print(f"\n{'':>8}", end='')
    for j in range(n_vectors):
        print(f"  orig_{j}", end='')
    print()

    correct = 0
    for i in range(n_vectors):
        print(f"dec_{i}:  ", end='')
        sims = []
        for j in range(n_vectors):
            sim = cosine_similarity(decoded_vectors[i], originals[j])
            sims.append(sim)
            marker = " *" if i == j else "  "
            print(f"  {sim:+.3f}{marker}", end='')
        print()

        if np.argmax(sims) == i:
            correct += 1

    print(f"\nCorrect retrievals: {correct}/{n_vectors}")
    passed = correct >= 4
    print(f"GATE: {'PASS' if passed else 'FAIL'} (target: >= {n_vectors - 1}/{n_vectors})")
    return correct, n_vectors, passed


if __name__ == '__main__':
    print("FLY BRAIN VSA BRIDGE — VALIDATION GATES\n")

    # Phase 1: Sparsity
    sparsity_ok = test_sparsity(n_kc=200)

    # Phase 2: Fidelity and discrimination
    fidelity, fidelity_ok = test_round_trip(n_kc=200)
    correct, total, disc_ok = test_discrimination(n_kc=200)

    # Phase 3: Scale to 2000 KCs
    print("\n" + "=" * 60)
    print("SCALED MODEL TEST (2000 KCs)")
    print("=" * 60)
    sparsity_scaled_ok = test_sparsity(n_trials=3, n_kc=2000)
    fidelity_scaled, fidelity_scaled_ok = test_round_trip(n_kc=2000)
    correct_s, total_s, disc_scaled_ok = test_discrimination(n_kc=2000)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    results = [
        ("Phase 1: Sparsity (200 KC)", sparsity_ok),
        ("Phase 2: Fidelity (200 KC)", fidelity_ok),
        ("Phase 2: Discrimination (200 KC)", disc_ok),
        ("Phase 3: Sparsity (2000 KC)", sparsity_scaled_ok),
        ("Phase 3: Fidelity (2000 KC)", fidelity_scaled_ok),
        ("Phase 3: Discrimination (2000 KC)", disc_scaled_ok),
    ]
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}: {name}")

    all_passed = all(p for _, p in results)
    print(f"\nOverall: {'ALL GATES PASSED' if all_passed else 'SOME GATES FAILED'}")
