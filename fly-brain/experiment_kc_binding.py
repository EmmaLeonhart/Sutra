"""
Experiment: binding in KC space instead of PN input space.

The insight: 140 PN dimensions aren't enough for clean sign-flip binding.
But the circuit projects to 1882 KC dimensions. What if we:

1. Project both vectors through the circuit independently (get KC patterns)
2. Compute the binding in KC space (where we have 13x more dimensions)
3. Use the KC-space bound pattern directly for matching

This treats the mushroom body's sparse projection as a DIMENSIONALITY
EXPANSION that creates room for binding — which is exactly what
Dasgupta et al. (2017) showed the fly brain evolved for.
"""

import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from spike_vsa_bridge import SpikeVSABridge, cosine_similarity
from mushroom_body_model import get_spike_rates


def run_kc_binding_test():
    print("=" * 60)
    print("KC-SPACE BINDING EXPERIMENT")
    print("=" * 60)

    from hemibrain_loader import load_cache
    data = load_cache()
    n_kc, dim = data['binary_matrix'].shape
    print(f"Substrate: {dim} PNs -> {n_kc} KCs")
    print(f"Binding in {n_kc}-D KC space (vs {dim}-D PN space)")

    # Make codebook
    names = ["apple", "vinegar", "honey", "smoke", "rain"]
    codebook = {}
    for name in names:
        seed = hash(name) % (2**31)
        codebook[name] = np.random.RandomState(seed).randn(dim)

    # Fixed frame seed for all operations (critical for KC pattern comparability)
    frame_seed = 42

    # Step 1: Get KC patterns for each codebook vector
    print(f"\nStep 1: Project codebook vectors to KC space...")
    kc_patterns = {}
    for name, vec in codebook.items():
        bridge = SpikeVSABridge(dim=dim, seed=frame_seed, n_kc=n_kc,
                                use_hemibrain=True)
        bridge.fit_learned_readout(n_samples=80)
        currents = bridge.encode(vec)
        bridge.run(currents)
        rates = get_spike_rates(bridge.model['kc_spikes'], n_kc, 200)
        kc_patterns[name] = (rates > 0).astype(float)
        active = int(kc_patterns[name].sum())
        print(f"  {name}: {active} active KCs ({100*active/n_kc:.1f}%)")

    # Step 2: Test binding in KC space
    print(f"\nStep 2: Bind in KC space (sign-flip on {n_kc}-D patterns)...")

    correct = 0
    total = 0

    for a_name in names[:3]:
        for b_name in names[:3]:
            if a_name == b_name:
                continue

            kc_a = kc_patterns[a_name]
            kc_b = kc_patterns[b_name]

            # Bind in KC space: XOR of binary patterns (equivalent to
            # sign-flip on {0,1} vectors: a XOR b)
            # For binary patterns: bound = a XOR b = a + b - 2*a*b
            kc_bound = np.abs(kc_a - kc_b)  # XOR for binary

            # Unbind: XOR again (self-inverse)
            kc_recovered = np.abs(kc_bound - kc_b)  # XOR with b again

            # Match against codebook KC patterns (Jaccard)
            best_name = None
            best_overlap = -1.0
            for name, kc_proto in kc_patterns.items():
                intersection = np.sum(kc_recovered * kc_proto)
                union = np.sum(np.clip(kc_recovered + kc_proto, 0, 1))
                overlap = float(intersection / max(union, 1.0))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_name = name

            match = "OK" if best_name == a_name else "FAIL"
            if best_name == a_name:
                correct += 1
            total += 1
            print(f"  bind({a_name}, {b_name}) -> unbind({b_name}) -> "
                  f"{best_name} (J={best_overlap:.3f}) {match}")

    print(f"\nKC-space binding: {correct}/{total} correct")

    # Step 3: Test bundling in KC space
    print(f"\nStep 3: Bundle in KC space (OR of binary patterns)...")

    # Bundle = OR of patterns (union of active KCs)
    # For 2 items: bundle = clip(a + b, 0, 1)
    for n_bundle in [2, 3, 4]:
        bundle_names = names[:n_bundle]
        kc_bundle = np.zeros(n_kc)
        for name in bundle_names:
            kc_bundle = np.clip(kc_bundle + kc_patterns[name], 0, 1)

        active = int(kc_bundle.sum())
        print(f"  Bundle of {n_bundle}: {active} active KCs ({100*active/n_kc:.1f}%)")

        # Can we recover each component?
        recovered = 0
        for name in bundle_names:
            # Check if component's pattern is a subset of the bundle
            overlap = np.sum(kc_patterns[name] * kc_bundle)
            total_in_component = np.sum(kc_patterns[name])
            containment = overlap / max(total_in_component, 1.0)
            if containment > 0.9:
                recovered += 1
                print(f"    {name}: containment={containment:.3f} RECOVERED")
            else:
                print(f"    {name}: containment={containment:.3f}")

        print(f"  Recovered: {recovered}/{n_bundle}")

    # Step 4: Bind + Bundle in KC space (role-filler pairs)
    print(f"\nStep 4: Role-filler pairs in KC space...")
    role_names = ["role_agent", "role_location", "role_action"]
    roles_kc = {}
    for rname in role_names:
        bridge = SpikeVSABridge(dim=dim, seed=frame_seed, n_kc=n_kc,
                                use_hemibrain=True)
        bridge.fit_learned_readout(n_samples=80)
        role_vec = np.random.RandomState(hash(rname) % (2**31)).randn(dim)
        currents = bridge.encode(role_vec)
        bridge.run(currents)
        rates = get_spike_rates(bridge.model['kc_spikes'], n_kc, 200)
        roles_kc[rname] = (rates > 0).astype(float)

    # bind(agent, apple) + bind(location, honey) — two role-filler pairs
    bound_1 = np.abs(roles_kc["role_agent"] - kc_patterns["apple"])
    bound_2 = np.abs(roles_kc["role_location"] - kc_patterns["honey"])
    structure = np.clip(bound_1 + bound_2, 0, 1)

    active = int(structure.sum())
    print(f"  Structure (2 role-filler pairs): {active} active KCs ({100*active/n_kc:.1f}%)")

    # Unbind agent
    unbound_agent = np.abs(structure - roles_kc["role_agent"])
    # This won't be a clean XOR because structure is OR'd, not XOR'd
    # But let's see what Jaccard matching gives us

    best_name = None
    best_overlap = -1.0
    for name, kc_proto in kc_patterns.items():
        intersection = np.sum(unbound_agent * kc_proto)
        union = np.sum(np.clip(unbound_agent + kc_proto, 0, 1))
        overlap = float(intersection / max(union, 1.0))
        if overlap > best_overlap:
            best_overlap = overlap
            best_name = name

    print(f"  Unbind agent -> {best_name} (expected: apple, J={best_overlap:.3f})")

    # Unbind location
    unbound_loc = np.abs(structure - roles_kc["role_location"])
    best_name = None
    best_overlap = -1.0
    for name, kc_proto in kc_patterns.items():
        intersection = np.sum(unbound_loc * kc_proto)
        union = np.sum(np.clip(unbound_loc + kc_proto, 0, 1))
        overlap = float(intersection / max(union, 1.0))
        if overlap > best_overlap:
            best_overlap = overlap
            best_name = name

    print(f"  Unbind location -> {best_name} (expected: honey, J={best_overlap:.3f})")


if __name__ == "__main__":
    run_kc_binding_test()
