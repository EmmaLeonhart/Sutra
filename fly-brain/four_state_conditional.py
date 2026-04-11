"""
Four-state conditional on fly brain substrate.

Executes the Akasha program in four_state_conditional.su on a simulated
Drosophila mushroom body circuit. Demonstrates a compiled program with
two fuzzy axes producing four distinct behavioral states.

Architecture:
  Input vectors (smell, hunger)
      ↓
  snap() — encode as PN currents, run spiking circuit, decode from KCs
      ↓
  similarity() — cosine comparison to reference concepts
      ↓
  defuzzy() — threshold collapse to boolean
      ↓
  4-way branch → behavioral output

The mushroom body's sparse random projection + APL winner-take-all
inhibition is the computational substrate. The if-statement reads the
fly brain's output; it doesn't compute it.
"""

import numpy as np
from vsa_operations import FlyBrainVSA


def run_program(smell_name, hunger_name, vsa, threshold=0.3):
    """
    Execute the 4-state Akasha program on the fly brain.

    Maps to the Akasha source:
        vector smell_clean = snap(embed(smell_name));
        vector hunger_clean = snap(embed(hunger_name));
        fuzzy has_smell = similarity(smell_clean, embed("vinegar"));
        fuzzy is_hungry = similarity(hunger_clean, embed("hungry"));
        // defuzzy + branch → one of 4 states

    Args:
        smell_name: concept name for olfactory input ("vinegar" or "clean_air")
        hunger_name: concept name for internal state ("hungry" or "fed")
        vsa: FlyBrainVSA instance (fly brain substrate)
        threshold: defuzzification threshold

    Returns:
        (behavior, smell_score, hunger_score)
    """
    # embed() — create hypervectors for input concepts
    smell_vec = vsa.embed(smell_name)
    hunger_vec = vsa.embed(hunger_name)

    # Reference vectors for comparison
    vinegar_ref = vsa.embed("vinegar")
    hungry_ref = vsa.embed("hungry")

    # snap() — run each input through the mushroom body circuit
    # This is where the fly brain does real computation:
    #   encode as PN currents → sparse random projection to KCs
    #   → APL enforces 5% winner-take-all → decode from KC population
    smell_clean = vsa.snap(smell_vec)
    hunger_clean = vsa.snap(hunger_vec)

    # similarity() — cosine comparison in the fly brain's coding space
    smell_score = vsa.similarity(smell_clean, vinegar_ref)
    hunger_score = vsa.similarity(hunger_clean, hungry_ref)

    # defuzzy() — collapse continuous similarity to boolean
    has_smell = smell_score > threshold
    is_hungry = hunger_score > threshold

    # 4-way branch — the if-statement from the Akasha source
    if has_smell and is_hungry:
        behavior = "approach"
    elif has_smell and not is_hungry:
        behavior = "ignore"
    elif not has_smell and is_hungry:
        behavior = "search"
    else:
        behavior = "idle"

    return behavior, smell_score, hunger_score


def main():
    print("=" * 70)
    print("FOUR-STATE CONDITIONAL ON DROSOPHILA MUSHROOM BODY")
    print("Akasha program compiled to spiking neural circuit")
    print("=" * 70)

    print("\nBuilding fly brain substrate (50 PNs → 2000 KCs → APL → 20 MBONs)...")
    vsa = FlyBrainVSA(dim=50, n_kc=2000, seed=42)

    # The four input combinations
    test_cases = [
        ("vinegar",   "hungry", "approach"),
        ("vinegar",   "fed",    "ignore"),
        ("clean_air", "hungry", "search"),
        ("clean_air", "fed",    "idle"),
    ]

    print(f"\nAkasha source: four_state_conditional.su")
    print(f"Substrate: mushroom body circuit (Brian2 LIF simulation)")
    print(f"Defuzzification threshold: 0.3\n")

    header = (f"{'Smell':<12} {'Context':<10} {'Expected':<10} "
              f"{'Got':<10} {'Smell Score':>12} {'Hunger Score':>13} {'':>6}")
    print(header)
    print("-" * len(header))

    correct = 0
    results = []
    for smell, context, expected in test_cases:
        behavior, smell_score, hunger_score = run_program(
            smell, context, vsa, threshold=0.3
        )
        passed = behavior == expected
        if passed:
            correct += 1
        results.append((smell, context, expected, behavior, smell_score, hunger_score, passed))
        print(f"{smell:<12} {context:<10} {expected:<10} "
              f"{behavior:<10} {smell_score:>+12.4f} {hunger_score:>+13.4f} "
              f"{'PASS' if passed else 'FAIL':>6}")

    print(f"\n{'=' * 70}")
    print(f"Result: {correct}/{len(test_cases)} states resolved correctly")
    print(f"GATE: {'PASS' if correct == len(test_cases) else 'FAIL'}")

    # Explain what happened
    print(f"\n--- What the fly brain computed ---")
    for smell, context, expected, behavior, ss, hs, passed in results:
        smell_flag = "above" if ss > 0.2 else "below"
        hunger_flag = "above" if hs > 0.2 else "below"
        print(f"  {smell:>9} + {context:<7} → smell={ss:+.3f} ({smell_flag}), "
              f"hunger={hs:+.3f} ({hunger_flag}) → {behavior}")

    print(f"\nEach input was encoded as PN currents, processed through 2000 Kenyon")
    print(f"cells with APL winner-take-all inhibition (5% sparsity), and decoded")
    print(f"via pseudoinverse. The fuzzy scores are cosine similarities between")
    print(f"the circuit's output and the reference concept vectors. The if-statement")
    print(f"reads the fly brain's answer; it doesn't compute it.")


if __name__ == '__main__':
    main()
