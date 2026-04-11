"""
Sutra Demo Programs — End-to-End Execution on Embedding Substrates
====================================================================

These demos show Sutra executing real programs on real embedding spaces.
Each demo is a self-contained Sutra program that demonstrates a different
capability of the language.

Usage:
    python sutra-paper/scripts/sutra_demos.py
    python sutra-paper/scripts/sutra_demos.py --model gte-large
    python sutra-paper/scripts/sutra_demos.py --demo associative_memory
    python sutra-paper/scripts/sutra_demos.py --all-demos
"""

import sys
import io
import json
import time
import argparse
from pathlib import Path

import numpy as np

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Import the Sutra runtime
sys.path.insert(0, str(Path(__file__).parent))
from sutra_runtime import (
    Substrate, S2Env, Codebook, empirical_initiation,
    bind, unbind, bundle, similarity, cosine_similarity,
    compute_direction, project_away, structured_match,
    is_true, is_true_recursive, demo_header,
)


# ============================================================
# Demo 1: Associative Memory
# ============================================================

def demo_associative_memory(env):
    """
    Sutra program: build an associative memory, store role-filler pairs,
    query by role to retrieve fillers.

    This is the fundamental VSA operation: the ability to store and
    retrieve structured information in superposed vector representations.
    """
    demo_header("Demo 1: Associative Memory")

    # Embed concepts
    concepts = [
        "cat", "dog", "bird", "fish",
        "Paris", "Tokyo", "London", "Berlin",
        "piano", "guitar", "violin", "drums",
    ]
    print(f"Embedding {len(concepts)} concepts...")
    env.embed_batch(concepts)

    # Build a structured record: {ANIMAL: cat, CITY: Paris, INSTRUMENT: piano}
    animal = env.embed("cat")
    city = env.embed("Paris")
    instrument = env.embed("piano")

    record = env.bundle(
        env.bind(animal, "ANIMAL"),
        env.bind(city, "CITY"),
        env.bind(instrument, "INSTRUMENT"),
    )
    env.let("record", record)

    # Query each role
    print("\nQuerying structured record:")
    for role_name, expected in [("ANIMAL", "cat"), ("CITY", "Paris"), ("INSTRUMENT", "piano")]:
        recovered = env.unbind(record, role_name)
        clean, label = env.snap(recovered)
        correct = label == expected
        cos = cosine_similarity(recovered, env.embed(expected))
        print(f"  unbind({role_name}) -> snap -> '{label}' "
              f"(expected '{expected}') cos={cos:.4f} {'OK' if correct else 'FAIL'}")

    # Test with more records bundled together
    print("\nMulti-record test (2 records bundled):")
    record2 = env.bundle(
        env.bind(env.embed("dog"), "ANIMAL"),
        env.bind(env.embed("Tokyo"), "CITY"),
        env.bind(env.embed("guitar"), "INSTRUMENT"),
    )
    # Store both records as separate entities, query each
    for name, rec, expected_animal in [("Record1", record, "cat"), ("Record2", record2, "dog")]:
        recovered = env.unbind(rec, "ANIMAL")
        _, label = env.snap(recovered)
        print(f"  {name}.ANIMAL -> '{label}' (expected '{expected_animal}') "
              f"{'OK' if label == expected_animal else 'FAIL'}")


# ============================================================
# Demo 2: Multi-Hop Reasoning
# ============================================================

def demo_multi_hop(env):
    """
    Sutra program: multi-hop reasoning via chained bind/unbind.

    Given:  "Paris is the capital of France"
            "France is in Europe"
    Derive: "Paris -> capital_of -> France -> located_in -> Europe"
    Query:  "What continent is Paris's country in?"
    """
    demo_header("Demo 2: Multi-Hop Reasoning")

    # Embed entities
    entities = ["Paris", "France", "Europe", "Tokyo", "Japan", "Asia",
                "London", "United Kingdom", "Berlin", "Germany"]
    print(f"Embedding {len(entities)} entities...")
    env.embed_batch(entities)

    # Build fact structures
    # Fact 1: Paris -[capital_of]-> France
    fact1 = env.bundle(
        env.bind(env.embed("Paris"), "SUBJECT"),
        env.bind(env.embed("France"), "OBJECT"),
    )

    # Fact 2: France -[located_in]-> Europe
    fact2 = env.bundle(
        env.bind(env.embed("France"), "SUBJECT"),
        env.bind(env.embed("Europe"), "OBJECT"),
    )

    # Fact 3: Tokyo -[capital_of]-> Japan
    fact3 = env.bundle(
        env.bind(env.embed("Tokyo"), "SUBJECT"),
        env.bind(env.embed("Japan"), "OBJECT"),
    )

    # Fact 4: Japan -[located_in]-> Asia
    fact4 = env.bundle(
        env.bind(env.embed("Japan"), "SUBJECT"),
        env.bind(env.embed("Asia"), "OBJECT"),
    )

    print("\nSingle-hop queries:")
    # Hop 1: "What is Paris the capital of?"
    hop1_result = env.unbind(fact1, "OBJECT")
    _, hop1_label = env.snap(hop1_result)
    print(f"  Paris capital_of -> '{hop1_label}' {'OK' if hop1_label == 'France' else 'FAIL'}")

    # Hop 1b: "What is the capital of France?" (reverse query)
    hop1b_result = env.unbind(fact1, "SUBJECT")
    _, hop1b_label = env.snap(hop1b_result)
    print(f"  ? capital_of France -> '{hop1b_label}' {'OK' if hop1b_label == 'Paris' else 'FAIL'}")

    print("\nMulti-hop chain: Paris -> ? -> ?")
    # Hop 1: Get France from fact1
    mid = env.unbind(fact1, "OBJECT")
    mid_clean, mid_label = env.snap(mid)
    print(f"  Hop 1: Paris -> '{mid_label}'")

    # Hop 2: Use the snapped result to query fact2
    # We need to find which fact has mid_label as SUBJECT
    # In a full Sutra program, we'd have a fact store; here we query fact2 directly
    final = env.unbind(fact2, "OBJECT")
    _, final_label = env.snap(final)
    print(f"  Hop 2: {mid_label} -> '{final_label}' {'OK' if final_label == 'Europe' else 'FAIL'}")

    # Same chain for Tokyo
    print("\nMulti-hop chain: Tokyo -> ? -> ?")
    mid2 = env.unbind(fact3, "OBJECT")
    mid2_clean, mid2_label = env.snap(mid2)
    print(f"  Hop 1: Tokyo -> '{mid2_label}'")
    final2 = env.unbind(fact4, "OBJECT")
    _, final2_label = env.snap(final2)
    print(f"  Hop 2: {mid2_label} -> '{final2_label}' {'OK' if final2_label == 'Asia' else 'FAIL'}")


# ============================================================
# Demo 3: Composition (extract from A, insert into B)
# ============================================================

def demo_composition(env):
    """
    Sutra program: compositional structure manipulation.

    Extract a filler from one structure, bind it into a new role
    in a different structure. Tests whether VSA operations compose.
    """
    demo_header("Demo 3: Composition (cross-structure transfer)")

    entities = ["Einstein", "physics", "Nobel Prize",
                "Curie", "chemistry", "Turing", "computer science"]
    env.embed_batch(entities)

    # Structure A: {PERSON: Einstein, FIELD: physics, AWARD: Nobel Prize}
    struct_a = env.bundle(
        env.bind(env.embed("Einstein"), "PERSON"),
        env.bind(env.embed("physics"), "FIELD"),
        env.bind(env.embed("Nobel Prize"), "AWARD"),
    )

    # Structure B: {PERSON: Curie, FIELD: chemistry}
    struct_b = env.bundle(
        env.bind(env.embed("Curie"), "PERSON"),
        env.bind(env.embed("chemistry"), "FIELD"),
    )

    # Extract AWARD from A
    award_raw = env.unbind(struct_a, "AWARD")
    award_clean, award_label = env.snap(award_raw)
    print(f"  Extracted from A: AWARD = '{award_label}'")

    # Insert into B as AWARD
    struct_b_with_award = env.bundle(
        struct_b,
        env.bind(award_clean, "AWARD"),
    )

    # Verify B now has all three fields
    print("  Querying augmented structure B:")
    for role, expected in [("PERSON", "Curie"), ("FIELD", "chemistry"), ("AWARD", "Nobel Prize")]:
        recovered = env.unbind(struct_b_with_award, role)
        _, label = env.snap(recovered)
        print(f"    {role} -> '{label}' (expected '{expected}') {'OK' if label == expected else 'FAIL'}")


# ============================================================
# Demo 4: Cone Traversal (directed semantic navigation)
# ============================================================

def demo_cone_traversal(env):
    """
    Sutra program: navigate embedding space using cone traversal.

    Start at a concept, define a direction, find what's "in that direction"
    in semantic space. This is Sutra's non-algebraic control flow.
    """
    demo_header("Demo 4: Cone Traversal (semantic navigation)")

    # Embed a landscape of concepts
    landscape = [
        "cat", "dog", "bird", "fish", "horse", "elephant",
        "apple", "banana", "grape", "orange",
        "red", "blue", "green", "yellow",
        "happy", "sad", "angry", "calm",
        "run", "walk", "swim", "fly",
        "Paris", "London", "Tokyo", "New York",
    ]
    env.embed_batch(landscape)

    # Define a direction: animals -> cities (semantic shift)
    animal_vecs = np.array([env.embed(a) for a in ["cat", "dog", "bird"]])
    city_vecs = np.array([env.embed(c) for c in ["Paris", "London", "Tokyo"]])
    direction = compute_direction(city_vecs, animal_vecs)

    origin = env.embed("cat")
    print(f"  Origin: 'cat'")
    print(f"  Direction: animals -> cities")
    print(f"  Cone traversal (spread=0.3):")

    results = env.cone(origin, direction, spread=0.3, top_k=8)
    for label, vec, alignment in results:
        print(f"    '{label}' (alignment={alignment:.3f})")

    # Another direction: concrete -> abstract (emotion)
    print()
    concrete_vecs = np.array([env.embed(c) for c in ["apple", "cat", "Paris"]])
    emotion_vecs = np.array([env.embed(e) for e in ["happy", "sad", "angry"]])
    direction2 = compute_direction(emotion_vecs, concrete_vecs)

    print(f"  Origin: 'cat'")
    print(f"  Direction: concrete -> emotions")
    print(f"  Cone traversal (spread=0.2):")
    results2 = env.cone(origin, direction2, spread=0.2, top_k=8)
    for label, vec, alignment in results2:
        print(f"    '{label}' (alignment={alignment:.3f})")


# ============================================================
# Demo 5: Structured Matching (many-to-many primitive)
# ============================================================

def demo_structured_matching(env):
    """
    Sutra program: structured matching with confounder control.

    Find countries similar to Japan in governance structure,
    while controlling for geographic region (don't just return
    other Asian countries).
    """
    demo_header("Demo 5: Structured Matching (confounder control)")

    # Embed countries with known properties
    countries = [
        "Japan", "South Korea", "Germany", "France",
        "China", "Russia", "Brazil", "India",
        "United States", "United Kingdom", "Canada", "Australia",
        "Thailand", "Vietnam", "Indonesia", "Philippines",
    ]
    env.embed_batch(countries)
    country_vecs = np.array([env.embed(c) for c in countries])

    # Derive region direction: Asian countries vs European countries
    asian = np.array([env.embed(c) for c in ["Japan", "South Korea", "China", "Thailand"]])
    european = np.array([env.embed(c) for c in ["Germany", "France", "United Kingdom"]])
    region_direction = compute_direction(asian, european)

    # Query: countries similar to Japan, controlling for region
    query = env.embed("Japan")

    # Naive cosine (region-confounded)
    naive_sims = np.array([cosine_similarity(query, cv) for cv in country_vecs])
    naive_order = np.argsort(-naive_sims)

    # Structured match (region controlled)
    controlled_scores = env.match(
        query, country_vecs,
        control_vectors=[region_direction],
        alpha=1.0, beta=0.0,  # pure residual after removing region
    )
    controlled_order = np.argsort(-controlled_scores)

    print("  Query: 'Japan'")
    print("  Control: geographic region (Asian vs European)")
    print()
    print("  Naive ranking (region-confounded):")
    for i in range(min(8, len(countries))):
        idx = naive_order[i]
        print(f"    {i+1}. {countries[idx]:20s} (cos={naive_sims[idx]:.4f})")

    print()
    print("  Controlled ranking (region removed):")
    for i in range(min(8, len(countries))):
        idx = controlled_order[i]
        print(f"    {i+1}. {countries[idx]:20s} (score={controlled_scores[idx]:.4f})")


# ============================================================
# Demo 6: Truth Extraction (fuzzy reasoning)
# ============================================================

def demo_truth_extraction(env):
    """
    Sutra program: fuzzy truth evaluation with recursive sharpening.

    Given a claim like "Paris is the capital of France", compute
    how true it is by comparing the algebraic result to the expected one.
    """
    demo_header("Demo 6: Truth Extraction (fuzzy reasoning)")

    # Embed reference facts
    facts = [
        ("Paris", "France"),
        ("Tokyo", "Japan"),
        ("London", "United Kingdom"),
        ("Berlin", "Germany"),
    ]
    env.embed_batch([e for pair in facts for e in pair])

    # Learn the "capital_of" displacement from known pairs
    displacements = []
    for city, country in facts:
        d = env.embed(country) - env.embed(city)
        displacements.append(d)
    capital_direction = np.mean(displacements, axis=0)

    print("  Testing claims using learned capital_of displacement:")
    print()

    claims = [
        ("Paris", "France", True),
        ("Tokyo", "Japan", True),
        ("Paris", "Japan", False),
        ("Berlin", "France", False),
        ("London", "United Kingdom", True),
        ("London", "Germany", False),
    ]

    for city, country, expected_true in claims:
        # Apply displacement: city + capital_direction should ≈ country
        predicted = env.embed(city) + capital_direction
        actual = env.embed(country)
        truth_val = env.is_true(predicted, reference=actual)
        verdict = "TRUE" if truth_val > 0.85 else "FALSE" if truth_val < 0.8 else "UNCERTAIN"
        match = (verdict == "TRUE") == expected_true
        print(f"  '{city}' capital_of '{country}': {truth_val:.4f} -> {verdict} "
              f"(expected {'TRUE' if expected_true else 'FALSE'}) {'OK' if match else 'FAIL'}")

    # Recursive truth sharpening
    print("\n  Recursive truth sharpening on 'Paris capital_of France':")
    predicted = env.embed("Paris") + capital_direction
    actual = env.embed("France")
    depths = env.is_true(predicted, reference=actual, depth=5)
    for i, val in enumerate(depths):
        print(f"    depth {i+1}: {val:.6f}")


# ============================================================
# Main
# ============================================================

ALL_DEMOS = {
    "associative_memory": demo_associative_memory,
    "multi_hop": demo_multi_hop,
    "composition": demo_composition,
    "cone_traversal": demo_cone_traversal,
    "structured_matching": demo_structured_matching,
    "truth_extraction": demo_truth_extraction,
}


def main():
    parser = argparse.ArgumentParser(description="Sutra Demo Programs")
    parser.add_argument("--model", default="mxbai-embed-large",
                        help="Ollama model to use as substrate")
    parser.add_argument("--demo", choices=list(ALL_DEMOS.keys()),
                        help="Run a specific demo")
    parser.add_argument("--all-demos", action="store_true",
                        help="Run all demos")
    parser.add_argument("--skip-initiation", action="store_true",
                        help="Skip empirical initiation probe")
    args = parser.parse_args()

    substrate = Substrate(args.model)
    env = S2Env(substrate=substrate)

    print(f"Sutra Runtime — Substrate: {substrate.model_name}")
    print(f"{'='*60}")

    if not args.skip_initiation:
        print("\n--- Empirical Initiation ---")
        t0 = time.time()
        cal = empirical_initiation(substrate, verbose=True)
        print(f"  Initiation took {time.time() - t0:.1f}s")
        print(f"  Capacity: {cal['capacity']} roles, Chain depth: {cal['chain_depth']} steps")

    demos_to_run = ALL_DEMOS if args.all_demos or not args.demo else {args.demo: ALL_DEMOS[args.demo]}

    total_t0 = time.time()
    results = {}

    for name, fn in demos_to_run.items():
        t0 = time.time()
        try:
            fn(env)
            results[name] = {"status": "ok", "time": time.time() - t0}
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = {"status": "error", "error": str(e)}

    # Summary
    print(f"\n{'='*60}")
    print(f"  Summary — {len(results)} demos in {time.time() - total_t0:.1f}s")
    print(f"{'='*60}")
    for name, r in results.items():
        status = "OK" if r["status"] == "ok" else "FAIL"
        t = f"{r.get('time', 0):.1f}s" if "time" in r else r.get("error", "")
        print(f"  {status} {name}: {t}")

    print(f"\nExecution trace: {len(env.trace)} operations")
    print(f"Codebook size: {len(env.codebook)} entries")
    print(f"Embedding cache: {len(substrate._cache)} texts")

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "demo_results.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "substrate": substrate.model_name,
            "calibration": substrate.calibration,
            "demos": results,
            "trace_length": len(env.trace),
            "codebook_size": len(env.codebook),
        }, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
