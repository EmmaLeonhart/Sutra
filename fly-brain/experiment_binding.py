"""
Experiment: systematically test binding approaches on the hemibrain substrate.

We test how well different input-space binding strategies preserve signal
through the bind -> snap -> unbind -> snap_to_codebook pipeline.

Approaches tested:
  A. Current: a * sign(b), standard encoding (baseline=1.2, gain=0.6)
  B. Silence negatives: set PN currents to 0 where bound_input < 0
  C. Higher gain: baseline=1.2, gain=1.5 (stronger signal-to-baseline ratio)
  D. Zero baseline: baseline=0, gain=1.0 (sign information fully preserved)
  E. Hadamard: a * b (elementwise product, not just sign)
"""

import sys, os
import numpy as np

# Ensure fly-brain is on the path
sys.path.insert(0, os.path.dirname(__file__))

from spike_vsa_bridge import SpikeVSABridge, cosine_similarity
from mushroom_body_model import build_model


def make_codebook(dim, n=5, seed=42):
    """Make a small codebook of named random vectors."""
    names = ["apple", "vinegar", "honey", "smoke", "rain"]
    rng = np.random.RandomState(seed)
    vecs = {}
    for name in names[:n]:
        vecs[name] = rng.randn(dim)
    return vecs


def test_binding_approach(approach_name, bind_fn, dim, codebook, n_trials=5):
    """
    Test a binding approach: for each pair (a, b) in the codebook,
    bind them, snap, unbind, and check if the correct vector is recovered.
    """
    names = list(codebook.keys())
    correct = 0
    total = 0
    cosines = []

    for i in range(min(n_trials, len(names))):
        for j in range(min(n_trials, len(names))):
            if i == j:
                continue
            a_name, b_name = names[i], names[j]
            a, b = codebook[a_name], codebook[b_name]

            # Bind
            bound = bind_fn(a, b)

            # Unbind (sign-flip is self-inverse, so bind again with same role)
            signs = np.sign(b)
            signs[signs == 0] = 1.0
            unbound_input = bound * signs

            # Check cosine to target
            cos = cosine_similarity(unbound_input, a)
            cosines.append(cos)

            # Check codebook match
            best_name = None
            best_dist = float('inf')
            for name, vec in codebook.items():
                d = np.linalg.norm(unbound_input - vec)
                if d < best_dist:
                    best_dist = d
                    best_name = name

            if best_name == a_name:
                correct += 1
            total += 1

    return correct, total, np.mean(cosines) if cosines else 0.0


def test_on_brain(approach_name, bind_on_brain_fn, dim, codebook,
                  snap_fn, n_trials=3):
    """
    Full on-brain test: bind on brain, snap, unbind on brain, snap to codebook.
    """
    names = list(codebook.keys())
    correct = 0
    total = 0

    for i in range(min(n_trials, len(names))):
        for j in range(min(n_trials, len(names))):
            if i == j:
                continue
            a_name, b_name = names[i], names[j]
            a, b = codebook[a_name], codebook[b_name]

            # Bind on brain
            bound = bind_on_brain_fn(a, b)

            # Snap the bound result
            snapped = snap_fn(bound)

            # Unbind: apply sign(b) in input space then snap
            signs = np.sign(b)
            signs[signs == 0] = 1.0
            unbound_approx = snapped * signs
            recovered = snap_fn(unbound_approx)

            # Check codebook match
            best_name = None
            best_dist = float('inf')
            for name, vec in codebook.items():
                d = np.linalg.norm(recovered - vec)
                if d < best_dist:
                    best_dist = d
                    best_name = name

            if best_name == a_name:
                correct += 1
            total += 1

    return correct, total


def run_all():
    print("=" * 60)
    print("BINDING APPROACH EXPERIMENTS (hemibrain substrate)")
    print("=" * 60)

    # Load hemibrain dimensions
    from hemibrain_loader import load_cache
    data = load_cache()
    n_kc, dim = data['binary_matrix'].shape
    print(f"Substrate: {dim} PNs, {n_kc} KCs")

    codebook = make_codebook(dim, n=5)

    # ---- Approach A: Current (a * sign(b), baseline=1.2, gain=0.6) ----
    print(f"\n--- A: Current (a * sign(b), baseline=1.2, gain=0.6) ---")
    seed_counter = [100]

    def make_bridge():
        b = SpikeVSABridge(dim=dim, seed=seed_counter[0], n_kc=n_kc,
                           use_hemibrain=True)
        b.fit_learned_readout(n_samples=80)
        seed_counter[0] += 1
        return b

    def bind_A(a, b):
        bridge = make_bridge()
        return bridge.bind_on_brain(a, b)

    def snap_A(v):
        bridge = make_bridge()
        decoded, _ = bridge.round_trip(v)
        return decoded

    c, t = test_on_brain("A", bind_A, dim, codebook, snap_A, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    # ---- Approach B: Silence negatives ----
    print(f"\n--- B: Silence negatives (zero PN current where bound < 0) ---")
    seed_counter[0] = 200

    def bind_B(a, b):
        bridge = make_bridge()
        signs = np.sign(b)
        signs[signs == 0] = 1.0
        bound_input = a * signs
        # Silence negatives: set negative components to 0 before encoding
        bound_input = np.maximum(bound_input, 0.0)
        currents = bridge.encode(bound_input)
        bridge.run(currents)
        return bridge.decode_learned()

    c, t = test_on_brain("B", bind_B, dim, codebook, snap_A, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    # ---- Approach C: Higher gain ----
    print(f"\n--- C: Higher gain (baseline=1.2, gain=1.5) ---")
    seed_counter[0] = 300

    def bind_C(a, b):
        bridge = make_bridge()
        signs = np.sign(b)
        signs[signs == 0] = 1.0
        bound_input = a * signs
        currents = bridge.encode(bound_input, baseline_current=1.2, gain=1.5)
        bridge.run(currents)
        return bridge.decode_learned()

    c, t = test_on_brain("C", bind_C, dim, codebook, snap_A, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    # ---- Approach D: Zero baseline (pure sign) ----
    print(f"\n--- D: Zero baseline (baseline=0.0, gain=1.0) ---")
    seed_counter[0] = 400

    def bind_D(a, b):
        bridge = make_bridge()
        signs = np.sign(b)
        signs[signs == 0] = 1.0
        bound_input = a * signs
        currents = bridge.encode(bound_input, baseline_current=0.0, gain=1.0)
        # With zero baseline, negative components become 0 (clamped)
        bridge.run(currents)
        return bridge.decode_learned()

    c, t = test_on_brain("D", bind_D, dim, codebook, snap_A, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    # ---- Approach E: Hadamard (a * b, not just sign) ----
    print(f"\n--- E: Hadamard (a * b elementwise) ---")
    seed_counter[0] = 500

    def bind_E(a, b):
        bridge = make_bridge()
        bound_input = a * b  # full elementwise product
        currents = bridge.encode(bound_input)
        bridge.run(currents)
        return bridge.decode_learned()

    c, t = test_on_brain("E", bind_E, dim, codebook, snap_A, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    # ---- Approach F: Higher gain for ALL ops (bind + snap) ----
    print(f"\n--- F: Higher gain everywhere (baseline=0.8, gain=1.2) ---")
    seed_counter[0] = 600

    def make_bridge_F():
        b = SpikeVSABridge(dim=dim, seed=seed_counter[0], n_kc=n_kc,
                           use_hemibrain=True)
        b.fit_learned_readout(n_samples=80)
        seed_counter[0] += 1
        return b

    def bind_F(a, b):
        bridge = make_bridge_F()
        signs = np.sign(b)
        signs[signs == 0] = 1.0
        bound_input = a * signs
        currents = bridge.encode(bound_input, baseline_current=0.8, gain=1.2)
        bridge.run(currents)
        return bridge.decode_learned()

    def snap_F(v):
        bridge = make_bridge_F()
        currents = bridge.encode(v, baseline_current=0.8, gain=1.2)
        bridge.run(currents)
        return bridge.decode_learned()

    c, t = test_on_brain("F", bind_F, dim, codebook, snap_F, n_trials=3)
    print(f"  On-brain: {c}/{t} correct")

    print(f"\n{'=' * 60}")
    print("DONE")


if __name__ == "__main__":
    run_all()
