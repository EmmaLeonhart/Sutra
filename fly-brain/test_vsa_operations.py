"""
VSA operations test suite for the fly brain substrate.

Tests the demo program from the architecture doc plus capacity,
discrimination, and multi-hop composition.
"""

import numpy as np
from vsa_operations import FlyBrainVSA


def test_demo_program():
    """
    The architecture doc's target demo:
    Encode two odor stimuli, bind them, snap through the circuit,
    unbind to retrieve, check similarity.

    This is the minimum viable result: Akasha code executing associative
    memory on a biological neural circuit.
    """
    print("=" * 60)
    print("DEMO PROGRAM: Associative Memory on Fly Brain")
    print("=" * 60)

    vsa = FlyBrainVSA(dim=50, n_kc=2000, seed=42)

    # Akasha equivalent:
    #   var odorA = embed("apple");
    #   var odorB = embed("vinegar");
    odorA = vsa.embed("apple")
    odorB = vsa.embed("vinegar")

    print(f"odorA (apple):   norm={np.linalg.norm(odorA):.3f}")
    print(f"odorB (vinegar): norm={np.linalg.norm(odorB):.3f}")
    print(f"similarity(odorA, odorB) = {vsa.similarity(odorA, odorB):.4f}")

    # Akasha equivalent:
    #   var association = bind(odorA, odorB);
    association = vsa.bind(odorA, odorB)
    print(f"\nassociation = bind(odorA, odorB)")
    print(f"  similarity to odorA: {vsa.similarity(association, odorA):.4f}")
    print(f"  similarity to odorB: {vsa.similarity(association, odorB):.4f}")

    # Akasha equivalent:
    #   var stored = snap(association);
    print(f"\nRunning snap through mushroom body circuit...")
    stored = vsa.snap(association)
    print(f"  stored = snap(association)")

    # Akasha equivalent:
    #   var retrieved = unbind(odorA, stored);
    retrieved = vsa.unbind(odorA, stored)
    print(f"  retrieved = unbind(odorA, stored)")

    # Akasha equivalent:
    #   var score = similarity(retrieved, odorB);
    score = vsa.similarity(retrieved, odorB)
    print(f"\nsimilarity(retrieved, odorB) = {score:.4f}")

    # Also check: does retrieved snap to the right codebook entry?
    _, nearest_name, nearest_dist = vsa.snap_to_codebook(retrieved)
    print(f"Nearest codebook entry: '{nearest_name}' (dist={nearest_dist:.3f})")

    passed = score > 0.1 and nearest_name == "vinegar"
    print(f"\nGATE: {'PASS' if passed else 'FAIL'}")
    print(f"  Similarity > 0.1: {'yes' if score > 0.1 else 'no'} ({score:.4f})")
    print(f"  Codebook match: {'yes' if nearest_name == 'vinegar' else 'no'} (got '{nearest_name}')")
    return passed, score


def test_discrimination():
    """Different concepts should produce distinguishable embeddings after snap."""
    print("\n" + "=" * 60)
    print("DISCRIMINATION TEST")
    print("=" * 60)

    vsa = FlyBrainVSA(dim=50, n_kc=2000, seed=42)
    concepts = ["apple", "vinegar", "honey", "smoke", "rain"]

    # Embed and snap each concept
    snapped = {}
    for name in concepts:
        vec = vsa.embed(name)
        snapped[name] = vsa.snap(vec)

    # Check pairwise similarity of snapped vectors
    print("\nPairwise similarity of snapped vectors:")
    print(f"{'':>10}", end='')
    for name in concepts:
        print(f"  {name:>8}", end='')
    print()

    for i, name_i in enumerate(concepts):
        print(f"{name_i:>10}", end='')
        for j, name_j in enumerate(concepts):
            sim = vsa.similarity(snapped[name_i], snapped[name_j])
            marker = " *" if i == j else "  "
            print(f"  {sim:+.3f}{marker}", end='')
        print()

    # Check: does each snapped vector snap back to the right codebook entry?
    correct = 0
    for name in concepts:
        _, nearest, _ = vsa.snap_to_codebook(snapped[name])
        if nearest == name:
            correct += 1
        else:
            print(f"  MISS: '{name}' snapped to '{nearest}'")

    print(f"\nCodebook accuracy: {correct}/{len(concepts)}")
    passed = correct >= 4
    print(f"GATE: {'PASS' if passed else 'FAIL'}")
    return passed


def test_bundling_capacity():
    """How many bound pairs can be bundled before retrieval fails?"""
    print("\n" + "=" * 60)
    print("BUNDLING CAPACITY TEST")
    print("=" * 60)

    vsa = FlyBrainVSA(dim=50, n_kc=2000, seed=42)

    # Create role vectors
    roles = [np.random.RandomState(300 + i).randn(50) for i in range(7)]
    fillers = [vsa.embed(f"concept_{i}") for i in range(7)]

    max_correct = 0
    for n_pairs in range(1, 8):
        # Bundle n_pairs of bound role-filler pairs
        structure = np.zeros(50)
        for i in range(n_pairs):
            structure = structure + vsa.bind(roles[i], fillers[i])

        # Snap through the circuit
        cleaned = vsa.snap(structure)

        # Try to retrieve each filler
        correct = 0
        for i in range(n_pairs):
            retrieved = vsa.unbind(roles[i], cleaned)
            _, nearest_name, _ = vsa.snap_to_codebook(retrieved)
            expected = f"concept_{i}"
            if nearest_name == expected:
                correct += 1

        all_correct = correct == n_pairs
        print(f"  {n_pairs} pairs: {correct}/{n_pairs} retrieved {'PASS' if all_correct else 'FAIL'}")

        if all_correct:
            max_correct = n_pairs
        else:
            break

    print(f"\nMax capacity: {max_correct} bound pairs")
    passed = max_correct >= 1
    print(f"GATE: {'PASS' if passed else 'FAIL'} (target: >= 1)")
    return passed, max_correct


def test_composition():
    """Multi-hop: build structure, extract, rebind, extract again."""
    print("\n" + "=" * 60)
    print("COMPOSITION TEST (Multi-Hop)")
    print("=" * 60)

    vsa = FlyBrainVSA(dim=50, n_kc=2000, seed=42)

    # Create concepts and roles
    cat = vsa.embed("cat")
    dog = vsa.embed("dog")
    mat = vsa.embed("mat")
    agent_role = np.random.RandomState(500).randn(50)
    location_role = np.random.RandomState(501).randn(50)

    # Hop 1: "cat sits on mat"
    struct1 = vsa.bundle(
        vsa.bind(agent_role, cat),
        vsa.bind(location_role, mat)
    )
    cleaned1 = vsa.snap(struct1)

    # Extract agent from hop 1
    recovered_agent = vsa.unbind(agent_role, cleaned1)
    _, agent_name, _ = vsa.snap_to_codebook(recovered_agent)
    print(f"Hop 1: extracted agent = '{agent_name}' (expected 'cat')")

    # Hop 2: "dog chases [recovered agent]"
    struct2 = vsa.bundle(
        vsa.bind(agent_role, dog),
        vsa.bind(location_role, recovered_agent)  # use raw recovered, not codebook
    )
    cleaned2 = vsa.snap(struct2)

    # Extract location from hop 2 — should recover something like cat
    recovered_loc = vsa.unbind(location_role, cleaned2)
    _, loc_name, _ = vsa.snap_to_codebook(recovered_loc)
    print(f"Hop 2: extracted location = '{loc_name}' (expected 'cat')")

    # Extract agent from hop 2
    recovered_agent2 = vsa.unbind(agent_role, cleaned2)
    _, agent2_name, _ = vsa.snap_to_codebook(recovered_agent2)
    print(f"Hop 2: extracted agent = '{agent2_name}' (expected 'dog')")

    hop1_ok = agent_name == "cat"
    hop2_agent_ok = agent2_name == "dog"
    hop2_loc_ok = loc_name == "cat"

    passed = hop1_ok and hop2_agent_ok
    print(f"\nHop 1 agent correct: {hop1_ok}")
    print(f"Hop 2 agent correct: {hop2_agent_ok}")
    print(f"Hop 2 location correct: {hop2_loc_ok}")
    print(f"GATE: {'PASS' if passed else 'FAIL'} (hops 1+2 agent extraction)")
    return passed


if __name__ == '__main__':
    print("FLY BRAIN VSA OPERATIONS — PHASE 4 TESTS\n")

    demo_ok, demo_score = test_demo_program()
    disc_ok = test_discrimination()
    cap_ok, capacity = test_bundling_capacity()
    comp_ok = test_composition()

    print("\n" + "=" * 60)
    print("PHASE 4 SUMMARY")
    print("=" * 60)
    results = [
        ("Demo program (associative memory)", demo_ok),
        ("Discrimination (5 concepts)", disc_ok),
        ("Bundling capacity", cap_ok),
        ("Multi-hop composition", comp_ok),
    ]
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}: {name}")

    all_passed = all(p for _, p in results)
    print(f"\nOverall: {'ALL GATES PASSED' if all_passed else 'SOME GATES FAILED'}")
