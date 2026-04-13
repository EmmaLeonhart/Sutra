"""
Fuzzy weighted superposition conditionals on the fly brain substrate.

Spec-aligned replacement for the deprecated `permutation_conditional.py`.
Per `planning/sutra-spec/03-control-flow.md`:

    result = (condition * branch_true) + (NOT_condition * branch_false)

generalized to 4-way:

    result = sum_i  w_i  *  behavior_vec[program_map[prototype_i]]

where w_i are the substrate's cosine scores of the snapped query against
the 4 precomputed prototype brain-views (PH, PF, AH, AF). Defuzzification
is argmax cosine against the behavior vectors.

Why this replaces the old `sign_flip(NOT_key, query)` approach:

    sign_flip is a binding op (pointwise product with a ±1 key). Using
    it as semantic NOT is a category error — a random ±1 key has no
    principled relationship to the "other polarity" of a continuous
    feature axis. The old demo's Program A hit 100% because it never
    applied NOT keys. Programs B/C/D averaged ~50% because they were
    asking an arbitrary random sign pattern to mean "not smell", and
    it doesn't.

The correct VSA form for a 4-way branch is the one above: compute
brain-view similarity to all 4 joint prototypes, and use those scores as
weighted contributions to a per-program behavior bundle. No sign_flip.
No deprecated NOT-as-permutation trick. The 4 programs differ only in
the prototype-to-behavior map; the decision pipeline is identical.
"""

import io
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import numpy as np

from vsa_operations import FlyBrainVSA
from spike_vsa_bridge import SpikeVSABridge


class FixedFrameFlyBrainVSA(FlyBrainVSA):
    """Pins the PN->KC projection seed so snap outputs are comparable."""

    def snap(self, vector):
        bridge_kwargs = dict(n_kc=self.n_kc)
        if self.use_hemibrain:
            bridge_kwargs['use_hemibrain'] = True
        bridge = SpikeVSABridge(
            dim=self.dim, seed=self.seed, **bridge_kwargs,
        )
        n_samples = 80 if self.use_hemibrain else 20
        bridge.fit_learned_readout(n_samples=n_samples)
        decoded, _ = bridge.round_trip(vector, self.snap_duration_ms)
        return decoded


PROTOTYPE_NAMES = ["PH", "PF", "AH", "AF"]
BEHAVIOR_NAMES = ["approach", "ignore", "search", "idle"]

# The 4 programs are 4 permutations of prototype -> behavior assignments.
# No sign_flip, no permutation keys on the query — just a different
# lookup map per program.
PROGRAM_BEHAVIOR = {
    "A": {"PH": "approach", "PF": "ignore",   "AH": "search",   "AF": "idle"},
    "B": {"PH": "search",   "PF": "idle",     "AH": "approach", "AF": "ignore"},
    "C": {"PH": "ignore",   "PF": "approach", "AH": "idle",     "AF": "search"},
    "D": {"PH": "idle",     "PF": "search",   "AH": "ignore",   "AF": "approach"},
}

PROGRAM_LABELS = {
    "A": "Natural",
    "B": "Inverted smell",
    "C": "Inverted hunger",
    "D": "Both inverted",
}


def build_primitives(vsa, rng):
    """Build smell / hunger basis vectors (distinct per polarity)."""
    return {
        "smell_present": rng.randn(vsa.dim),
        "smell_absent":  rng.randn(vsa.dim),
        "hunger_hungry": rng.randn(vsa.dim),
        "hunger_fed":    rng.randn(vsa.dim),
    }


def build_behavior_vecs(vsa, rng):
    """Distinct random vectors for each behavior — the output codebook."""
    return {name: rng.randn(vsa.dim) for name in BEHAVIOR_NAMES}


def compile_prototypes(vsa, prims):
    """Snap each (smell, hunger) joint through the MB."""
    k_PH = vsa.bind(prims["smell_present"], prims["hunger_hungry"])
    k_PF = vsa.bind(prims["smell_present"], prims["hunger_fed"])
    k_AH = vsa.bind(prims["smell_absent"],  prims["hunger_hungry"])
    k_AF = vsa.bind(prims["smell_absent"],  prims["hunger_fed"])
    return {
        "PH": vsa.snap(k_PH),
        "PF": vsa.snap(k_PF),
        "AH": vsa.snap(k_AH),
        "AF": vsa.snap(k_AF),
    }


def fuzzy_weights(vsa, brain_query, prototypes):
    """
    Cosine scores -> fuzzy weights in [0,1] summing to 1.

    This is the 4-way analogue of `weight = is_true(condition)` from the
    2-way spec formula. The raw similarities are clamped at 0 (ReLU) so
    a negative-correlation prototype contributes zero, then normalized.
    """
    raw = np.array([vsa.similarity(brain_query, prototypes[n])
                    for n in PROTOTYPE_NAMES])
    clipped = np.maximum(raw, 0.0)
    total = clipped.sum()
    if total < 1e-8:
        # Fallback: all negative -> uniform, defuzz will argmax raw.
        return np.ones(4) / 4, raw
    return clipped / total, raw


def run_decision(vsa, prototypes, behavior_vecs,
                 smell_vec, hunger_vec, program_id):
    """
    Execute one (program, input) decision.

    Pipeline:
      query = bind(smell, hunger)           # algebraic
      brain_query = snap(query)             # MB cleanup
      weights = clipped_cos_to_prototypes   # fuzzy w_i
      result = sum_i w_i * behavior_vec[program_map[prototype_i]]
      winner = argmax cosine(result, behavior_vecs)

    This is the spec's `(cond * branch_true) + (NOT_cond * branch_false)`
    form, generalized to 4 branches. No sign_flip on the query.
    """
    query = vsa.bind(smell_vec, hunger_vec)
    brain_query = vsa.snap(query)

    weights, raw_scores = fuzzy_weights(vsa, brain_query, prototypes)

    # Fuzzy weighted superposition over behavior vectors.
    prog_map = PROGRAM_BEHAVIOR[program_id]
    result = np.zeros(vsa.dim)
    for w, proto_name in zip(weights, PROTOTYPE_NAMES):
        behavior_name = prog_map[proto_name]
        result = result + w * behavior_vecs[behavior_name]

    # Defuzzify: argmax cosine against the behavior codebook.
    scores = {bn: float(np.dot(result, bv) /
                        (np.linalg.norm(result) * np.linalg.norm(bv) + 1e-8))
              for bn, bv in behavior_vecs.items()}
    winner = max(scores, key=scores.get)
    return winner, weights, raw_scores, scores


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--hemibrain', action='store_true')
    args = parser.parse_args()

    print("=" * 72)
    print("FUZZY WEIGHTED SUPERPOSITION CONDITIONALS ON THE FLY BRAIN")
    print("Spec-aligned replacement for permutation_conditional.py")
    print("=" * 72)

    if args.hemibrain:
        print("\nBuilding fly brain substrate from HEMIBRAIN connectome...")
        vsa = FixedFrameFlyBrainVSA(seed=42, use_hemibrain=True)
        print(f"  Real connectome: {vsa.dim} PNs -> {vsa.n_kc} KCs -> APL -> 20 MBONs")
    else:
        print("\nBuilding fly brain substrate (50 PNs -> 2000 KCs -> APL -> 20 MBONs)...")
        vsa = FixedFrameFlyBrainVSA(dim=50, n_kc=2000, seed=42)

    rng = np.random.RandomState(vsa.seed)
    prims = build_primitives(vsa, rng)
    behavior_vecs = build_behavior_vecs(vsa, rng)

    print("Compiling prototype table (4 joint-input snaps)...")
    prototypes = compile_prototypes(vsa, prims)

    inputs = [
        ("vinegar",   "hungry", prims["smell_present"], prims["hunger_hungry"]),
        ("vinegar",   "fed",    prims["smell_present"], prims["hunger_fed"]),
        ("clean_air", "hungry", prims["smell_absent"],  prims["hunger_hungry"]),
        ("clean_air", "fed",    prims["smell_absent"],  prims["hunger_fed"]),
    ]

    expected = {
        "A": ["approach", "ignore",   "search",   "idle"],
        "B": ["search",   "idle",     "approach", "ignore"],
        "C": ["ignore",   "approach", "idle",     "search"],
        "D": ["idle",     "search",   "ignore",   "approach"],
    }

    all_results = {}
    for prog_id in ["A", "B", "C", "D"]:
        print(f"\n{'-' * 72}")
        print(f"PROGRAM {prog_id}: {PROGRAM_LABELS[prog_id]}")
        print(f"{'-' * 72}")
        print(f"  {'Input':<22} {'Expected':>10} {'Got':>10}  "
              f"{'w_PH':>6} {'w_PF':>6} {'w_AH':>6} {'w_AF':>6}")

        results = []
        for i, (sn, hn, s_vec, h_vec) in enumerate(inputs):
            winner, weights, raw, scores = run_decision(
                vsa, prototypes, behavior_vecs, s_vec, h_vec, prog_id,
            )
            exp = expected[prog_id][i]
            mark = "OK" if winner == exp else "XX"
            results.append((sn, hn, exp, winner, weights, raw))
            print(f"  {sn + ' + ' + hn:<22} {exp:>10} {winner:>10} {mark} "
                  f"{weights[0]:>6.2f} {weights[1]:>6.2f} "
                  f"{weights[2]:>6.2f} {weights[3]:>6.2f}")
        all_results[prog_id] = results

    correct = 0
    total = 0
    for prog_id in ["A", "B", "C", "D"]:
        for (_, _, exp, got, _, _) in all_results[prog_id]:
            total += 1
            if got == exp:
                correct += 1

    mappings = {tuple(r[3] for r in all_results[prog_id])
                for prog_id in ["A", "B", "C", "D"]}
    all_distinct = len(mappings) == 4

    print(f"\n{'=' * 72}")
    print(f"Decisions matching expected: {correct}/{total}")
    print(f"All 4 programs distinct: {all_distinct}")
    print(f"GATE: {'PASS' if correct == total and all_distinct else 'FAIL'}")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
