"""
Experiment: is_converter matrix — the original Sutra conditional design.

The idea: learn a single matrix M such that for any concept c:
    is_c = M @ c           (a test vector)
    is_c . x ≈ 1  if x ≈ c   (true)
    is_c . x ≈ 0  if x ⊥ c   (false)

This is equivalent to learning M such that (M @ c) . x ≈ c . x,
which means M should approximate the identity in the directions
that matter. But the useful property is that M can also map the
result into a specific region of the space (near the reserved
true/false vectors).

On the fly brain: is_converter operates in KC space. We project
concepts through the circuit, learn M from KC pattern overlaps,
and the "test" is whether two KC patterns activate overlapping
KCs — which is EXACTLY what the mushroom body evolved to do.
"""

import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from spike_vsa_bridge import SpikeVSABridge, cosine_similarity
from mushroom_body_model import get_spike_rates


def run_is_converter_experiment():
    print("=" * 60)
    print("IS_CONVERTER EXPERIMENT")
    print("=" * 60)

    from hemibrain_loader import load_cache
    data = load_cache()
    n_kc, dim = data['binary_matrix'].shape
    print(f"Substrate: {dim} PNs -> {n_kc} KCs")

    frame_seed = 42

    # Make a set of concept vectors
    concept_names = ["apple", "vinegar", "honey", "smoke", "rain",
                     "cat", "dog", "fire", "water", "earth"]
    concepts = {}
    for name in concept_names:
        seed = hash(name) % (2**31)
        concepts[name] = np.random.RandomState(seed).randn(dim)

    # Project all concepts to KC space
    print("\nProjecting concepts to KC space...")
    kc_patterns = {}
    for name, vec in concepts.items():
        bridge = SpikeVSABridge(dim=dim, seed=frame_seed, n_kc=n_kc,
                                use_hemibrain=True)
        bridge.fit_learned_readout(n_samples=80)
        currents = bridge.encode(vec)
        bridge.run(currents)
        rates = get_spike_rates(bridge.model['kc_spikes'], n_kc, 200)
        kc_patterns[name] = (rates > 0).astype(float)
        active = int(kc_patterns[name].sum())
        print(f"  {name}: {active} active KCs")

    # ---- Approach 1: is_converter as Jaccard overlap ----
    # The simplest "is_converter" on the fly brain: is_c(x) = Jaccard(kc_c, kc_x)
    # This is literally what MBONs do — pattern matching via KC overlap.

    print("\n--- Approach 1: Jaccard overlap as is_converter ---")
    print("is_c(x) = Jaccard(kc_c, kc_x)")

    for test_name in ["apple", "cat"]:
        print(f"\n  Testing: is_{test_name}(x)")
        kc_test = kc_patterns[test_name]
        for x_name in concept_names:
            kc_x = kc_patterns[x_name]
            intersection = np.sum(kc_test * kc_x)
            union = np.sum(np.clip(kc_test + kc_x, 0, 1))
            jaccard = float(intersection / max(union, 1.0))
            match = " <-- SELF" if x_name == test_name else ""
            print(f"    is_{test_name}({x_name}) = {jaccard:.3f}{match}")

    # ---- Approach 2: Learned is_converter in PN space ----
    # Learn a matrix M (dim x dim) such that:
    #   similarity(M @ concept, input) correlates with
    #   Jaccard(kc_concept, kc_input)
    #
    # Training data: (concept, input) pairs with known KC overlaps

    print("\n--- Approach 2: Learned is_converter matrix ---")

    # Build training data
    names = list(concepts.keys())
    n = len(names)
    X_concept = []  # concept vectors
    X_input = []    # input vectors
    Y_overlap = []  # target: KC overlap

    for i in range(n):
        for j in range(n):
            X_concept.append(concepts[names[i]])
            X_input.append(concepts[names[j]])
            kc_i = kc_patterns[names[i]]
            kc_j = kc_patterns[names[j]]
            intersection = np.sum(kc_i * kc_j)
            union = np.sum(np.clip(kc_i + kc_j, 0, 1))
            Y_overlap.append(float(intersection / max(union, 1.0)))

    X_concept = np.array(X_concept)  # (n*n, dim)
    X_input = np.array(X_input)      # (n*n, dim)
    Y_overlap = np.array(Y_overlap)  # (n*n,)

    # We want: (M @ concept) . input ≈ overlap
    # This is: sum_k (M_kl * concept_l) * input_k = overlap
    # Which is: concept^T @ M^T @ input = overlap
    # Or vectorized: vec(M)^T @ (concept ⊗ input) = overlap

    # Build the design matrix: each row is outer_product(concept, input).flatten()
    # This is a (n*n, dim*dim) matrix — 100 rows, 19600 columns for dim=140
    A = np.array([np.outer(c, x).flatten() for c, x in zip(X_concept, X_input)])
    print(f"  Design matrix: {A.shape}")

    # Ridge regression: solve for vec(M)
    ridge_lambda = 1.0
    M_flat = np.linalg.solve(A.T @ A + ridge_lambda * np.eye(A.shape[1]),
                              A.T @ Y_overlap)
    M = M_flat.reshape(dim, dim)
    print(f"  M shape: {M.shape}, norm: {np.linalg.norm(M):.3f}")

    # Test: does (M @ concept) . input predict KC overlap?
    print(f"\n  Testing learned is_converter:")
    for test_name in ["apple", "cat"]:
        print(f"\n  is_{test_name}(x) via learned M:")
        is_test = M @ concepts[test_name]
        for x_name in concept_names:
            predicted = float(np.dot(is_test, concepts[x_name]))
            actual_kc = kc_patterns[test_name]
            actual_kc_x = kc_patterns[x_name]
            intersection = np.sum(actual_kc * actual_kc_x)
            union = np.sum(np.clip(actual_kc + actual_kc_x, 0, 1))
            actual = float(intersection / max(union, 1.0))
            match = " <-- SELF" if x_name == test_name else ""
            print(f"    is_{test_name}({x_name}): predicted={predicted:.3f}, "
                  f"actual={actual:.3f}{match}")

    # ---- Approach 3: Fuzzy conditional using is_converter ----
    print("\n--- Approach 3: Fuzzy conditional ---")
    print("result = weight * branch_true + (1-weight) * branch_false")

    # Scenario: "if this smells like apple, approach; else, search"
    approach_vec = np.random.RandomState(hash("approach") % (2**31)).randn(dim)
    search_vec = np.random.RandomState(hash("search") % (2**31)).randn(dim)

    is_apple = M @ concepts["apple"]

    for test_input_name in ["apple", "vinegar", "smoke"]:
        test_input = concepts[test_input_name]
        weight = float(np.dot(is_apple, test_input))
        # Clamp to [0, 1]
        weight = max(0.0, min(1.0, weight))
        result = weight * approach_vec + (1.0 - weight) * search_vec

        cos_approach = cosine_similarity(result, approach_vec)
        cos_search = cosine_similarity(result, search_vec)
        winner = "approach" if cos_approach > cos_search else "search"
        print(f"  Input: {test_input_name}")
        print(f"    weight = {weight:.3f}")
        print(f"    cos(result, approach) = {cos_approach:.3f}")
        print(f"    cos(result, search)   = {cos_search:.3f}")
        print(f"    winner: {winner}")


if __name__ == "__main__":
    run_is_converter_experiment()
