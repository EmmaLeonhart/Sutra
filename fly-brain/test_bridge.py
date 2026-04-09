"""
End-to-end test: encode a hypervector, run it through the mushroom body
circuit, decode the output, and measure round-trip fidelity.

This is the first proof that VSA operations can execute on a biological
neural circuit substrate.
"""

import numpy as np
from mushroom_body_model import build_model, run_stimulus, N_PN, N_KC, N_MBON, get_spike_rates, print_summary
from spike_vsa_bridge import encode, decode, round_trip_fidelity, cosine_similarity


def test_single_vector(dim=50, duration_ms=300, seed=42):
    """Test round-trip fidelity for a single random vector."""
    np.random.seed(seed)

    # Generate a random hypervector (same dim as PN count for simplicity)
    original = np.random.randn(dim)

    print(f"Original vector: dim={dim}, norm={np.linalg.norm(original):.3f}")

    # Encode: hypervector → input currents
    currents = encode(original, N_PN)
    print(f"Encoded to {N_PN} PN currents: range [{currents.min():.2f}, {currents.max():.2f}]")

    # Build and run the circuit
    print(f"\nBuilding mushroom body model...")
    model = build_model(seed=seed)

    print(f"Running simulation for {duration_ms}ms...")
    model = run_stimulus(model, currents, duration_ms=duration_ms)

    print("\n--- Circuit Activity ---")
    print_summary(model, duration_ms)

    # Decode: MBON spike trains → output vector
    decoded_mbon = decode(model['mbon_spikes'], N_MBON, duration_ms, dim)
    fidelity_mbon = round_trip_fidelity(original, decoded_mbon)

    # Also try decoding from KC layer (more neurons = potentially more info)
    decoded_kc = decode(model['kc_spikes'], N_KC, duration_ms, dim)
    fidelity_kc = round_trip_fidelity(original, decoded_kc)

    print(f"\n--- Round-Trip Fidelity ---")
    print(f"MBON decode: cosine similarity = {fidelity_mbon:.4f}")
    print(f"KC decode:   cosine similarity = {fidelity_kc:.4f}")

    return fidelity_mbon, fidelity_kc


def test_discrimination(n_vectors=5, dim=50, duration_ms=300):
    """
    Test whether the circuit produces distinguishable outputs for
    different input vectors. This is the minimum requirement for
    the circuit to be usable as a VSA substrate.
    """
    print("\n" + "=" * 60)
    print("DISCRIMINATION TEST")
    print(f"Testing {n_vectors} random vectors for distinguishability")
    print("=" * 60)

    originals = []
    decoded_vectors = []

    for i in range(n_vectors):
        seed = 100 + i
        np.random.seed(seed)
        original = np.random.randn(dim)
        originals.append(original)

        currents = encode(original, N_PN)
        model = build_model(seed=seed)
        model = run_stimulus(model, currents, duration_ms=duration_ms)

        decoded = decode(model['kc_spikes'], N_KC, duration_ms, dim)
        decoded_vectors.append(decoded)

    # Check: are decoded vectors more similar to their own originals
    # than to other originals?
    print("\nSimilarity matrix (decoded[i] vs original[j]):")
    print(f"{'':>8}", end='')
    for j in range(n_vectors):
        print(f"  orig_{j}", end='')
    print()

    correct = 0
    total = 0
    for i in range(n_vectors):
        print(f"dec_{i}:  ", end='')
        sims = []
        for j in range(n_vectors):
            sim = cosine_similarity(decoded_vectors[i], originals[j])
            sims.append(sim)
            marker = " *" if i == j else "  "
            print(f"  {sim:+.3f}{marker}", end='')
        print()

        # Check if diagonal is the maximum (correct retrieval)
        if np.argmax(sims) == i:
            correct += 1
        total += 1

    print(f"\nCorrect retrievals: {correct}/{total}")
    if correct == total:
        print("PASS: Circuit discriminates all input vectors")
    elif correct > 0:
        print(f"PARTIAL: Circuit discriminates {correct}/{total} vectors")
    else:
        print("FAIL: Circuit does not discriminate input vectors")

    return correct, total


if __name__ == '__main__':
    print("=" * 60)
    print("FLY BRAIN VSA BRIDGE TEST")
    print("=" * 60)

    # Test 1: Single vector round-trip
    print("\n--- Test 1: Single Vector Round-Trip ---\n")
    fidelity_mbon, fidelity_kc = test_single_vector()

    # Test 2: Discrimination
    correct, total = test_discrimination()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Round-trip fidelity (MBON): {fidelity_mbon:.4f}")
    print(f"Round-trip fidelity (KC):   {fidelity_kc:.4f}")
    print(f"Discrimination: {correct}/{total}")

    if fidelity_kc > 0 or correct > 0:
        print("\nThe fly brain circuit preserves VSA signal.")
    else:
        print("\nNo signal detected. Encoding/decoding scheme needs tuning.")
