"""
DEPRECATED. Use `fuzzy_conditional.py` instead.

This demo uses `sign_flip(NOT_key, query)` as semantic negation. That is
a category error — a random ±1 key has no principled relationship to the
"other polarity" of a continuous feature axis — and it is why programs
B/C/D averaged ~50% correct across 20 seeds on hemibrain while program A
hit 100%. The spec (`planning/sutra-spec/03-control-flow.md`) prescribes
fuzzy weighted superposition: `result = Σ w_i · branch_i`. Kept on disk
as the failure record only; not imported by anything current.

Permutation-based conditionals on the fly brain substrate.

This is the follow-up to `programmer_control_demo.py`. Where that demo ran
if-statements in Python and only used the fly brain for cleaning up the
two input vectors, this demo compiles the *conditional itself* onto the
fly brain:

  - The if/else tree becomes a prototype table — one "brain-view" vector
    per case, precomputed by running snap() on the fly brain at compile
    time. The compiled artifact is a dictionary from prototype name to
    the corresponding brain-view vector, plus a mapping from prototype
    name to behavior name (that's Program A).
  - Negation (`!`) compiles to a permutation key applied to the query.
  - The decision is: run snap() on the query to get its brain-view, then
    cosine-match against the 4 prototypes. No Python `if` over smell or
    hunger; no Python `elif` chain over behaviors.
  - The 4 programs share the SAME prototype table. The only thing that
    varies per program is which permutation keys multiply into the query
    vector before it goes into snap.

The biological story: the fly's mushroom body is *already* a
nearest-neighbor matching system. Each KC is selective for a specific
conjunction of PN inputs, and MBONs read out KC populations via learned
weights. Running snap() on a query and comparing it to 4 precomputed
prototypes is a faithful software analogue of what the real MB does when
an odor activates KCs and MBONs vote on behavior.

Architecture:

    bind(smell, hunger)                # query construction (algebraic)
        │
        ├── permute(NOT_SMELL,  .)    # negation by permutation key
        ├── permute(NOT_HUNGER, .)
        │
        ▼
    snap(.)                            # fly brain cleanup (MB circuit)
        │
        ▼
    argmax cosine vs. 4 brain-view prototypes
        │                              (prototypes were snapped at compile
        ▼                               time, so the comparison happens
    behavior name                       in the MB's output space)

There is no Python `if` in the decision path. The `if`-tree compiles to a
precomputed prototype table, and the decision is a single cosine argmax.
"""

import io
import sys

# Windows console is cp1252 by default and cannot encode the arrow /
# checkmark glyphs used in this script. Re-wrap stdout as UTF-8.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import numpy as np

from vsa_operations import FlyBrainVSA
from spike_vsa_bridge import SpikeVSABridge


class FixedFrameFlyBrainVSA(FlyBrainVSA):
    """
    FlyBrainVSA variant where every snap uses the SAME MB connectivity.

    The parent class increments `_snap_count` between calls so that each
    snap builds a fresh PN->KC random projection. That's fine if you
    only need each snap in isolation (the original demo does cosine
    comparisons against pre-snap reference vectors). But for this demo
    we need snap(query) and snap(prototype) to be *comparable to each
    other*, and that only works if both decoded vectors live in the
    same reconstruction frame.

    Concretely: round-trip fidelity of ~0.53 means each snap output has
    error ~1.6x the signal magnitude. Two independent snaps of the same
    vector under different connectivity matrices give cosine ~0.28,
    which is marginal for 4-way discrimination. Pinning the seed brings
    that up to ~1.0 for identical inputs and ~0 for orthogonal inputs,
    which is exactly what we need.
    """

    def snap(self, vector):
        bridge_kwargs = dict(n_kc=self.n_kc)
        if self.use_hemibrain:
            bridge_kwargs['use_hemibrain'] = True
        bridge = SpikeVSABridge(
            dim=self.dim, seed=self.seed, **bridge_kwargs,
        )
        # Fit the biologically-plausible learned MBON readout on this
        # bridge. Cache hit is trivial after the first snap in this
        # run, because every snap here uses the same seed/dim/n_kc
        # tuple. See spike_vsa_bridge.py for the training procedure.
        n_samples = 80 if self.use_hemibrain else 20
        bridge.fit_learned_readout(n_samples=n_samples)
        decoded, _ = bridge.round_trip(vector, self.snap_duration_ms)
        return decoded


PROTOTYPE_NAMES = ["PH", "PF", "AH", "AF"]

# Program A: the natural/sensible mapping from prototype name to behavior.
# This is the entire "compiled if-tree" — a dict. Programs B/C/D reuse it.
PROGRAM_A_BEHAVIOR = {
    "PH": "approach",  # smell_present, hunger_hungry
    "PF": "ignore",    # smell_present, hunger_fed
    "AH": "search",    # smell_absent,  hunger_hungry
    "AF": "idle",      # smell_absent,  hunger_fed
}


def build_primitives(vsa, rng):
    """
    Build the smell/hunger state pairs and the two permutation keys.

    smell_absent is constructed as NOT_SMELL * smell_present so that
    applying NOT_SMELL to a query swaps the smell axis exactly. Same
    for hunger. This is the compile-time contract that makes "Program B
    is Program A with the smell axis inverted" a pure vector operation.
    """
    smell_present = rng.randn(vsa.dim)
    hunger_hungry = rng.randn(vsa.dim)

    NOT_SMELL = vsa.make_sign_flip_key("NOT_SMELL")
    NOT_HUNGER = vsa.make_sign_flip_key("NOT_HUNGER")

    smell_absent = vsa.sign_flip(NOT_SMELL, smell_present)
    hunger_fed = vsa.sign_flip(NOT_HUNGER, hunger_hungry)

    return {
        "smell_present": smell_present,
        "smell_absent":  smell_absent,
        "hunger_hungry": hunger_hungry,
        "hunger_fed":    hunger_fed,
        "NOT_SMELL":     NOT_SMELL,
        "NOT_HUNGER":    NOT_HUNGER,
    }


def compile_prototypes(vsa, prims):
    """
    Build the four joint keys (PH, PF, AH, AF) and snap each one through
    the mushroom body at compile time. The returned dict maps prototype
    name to a "brain-view" vector — the MB's output for that joint input.

    This is the compiled artifact. It encodes Program A's if-tree as
    "here are the four patterns the fly brain learns to recognize". The
    behavior assignment lives separately in `PROGRAM_A_BEHAVIOR`.
    """
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


def match_prototype(vsa, brain_query, prototypes):
    """
    Cosine argmax against the four brain-view prototypes.

    Returns (winning_name, score_table). This is the biological analogue
    of four MBONs competing for a winner — each MBON encodes a specific
    KC population pattern, and the one whose pattern most matches the
    current KC activity wins. Here we model it as cosine argmax in the
    MB's output space.
    """
    scores = {name: vsa.similarity(brain_query, proto)
              for name, proto in prototypes.items()}
    best_name = max(scores, key=scores.get)
    return best_name, scores


# The four programs, expressed as (apply_not_smell, apply_not_hunger).
# This is the *only* place in the decision pipeline where program
# identity shows up, and it shows up as a pair of booleans that control
# which permutation keys get applied to the query.
PROGRAM_PERMUTATIONS = {
    "A": (False, False),   # Natural
    "B": (True,  False),   # Inverted smell  (`!` on has_smell)
    "C": (False, True),    # Inverted hunger (`!` on is_hungry)
    "D": (True,  True),    # Both inverted
}

PROGRAM_LABELS = {
    "A": "Natural",
    "B": "Inverted smell",
    "C": "Inverted hunger",
    "D": "Both inverted",
}


def run_decision(vsa, prototypes, smell_vec, hunger_vec, prims,
                 not_smell, not_hunger):
    """
    Execute one (program, input) decision on the fly brain substrate.

    This is the whole decision path. Note what is *not* here: no `if`
    over has_smell, no `elif`, no 4-way branch, no Python choice of
    behavior. The flow is:

       bind(smell, hunger)      → form the query
       permute as program says  → compose NOT keys into the query
       snap on fly brain        → run the MB to get the brain-view query
       cosine argmax vs 4       → pick the matching prototype
       dict lookup              → prototype → behavior name
                                  (that's Program A, compiled as a table)

    The two booleans `not_smell` / `not_hunger` determine the program,
    and they're multiplied into the query as permutation keys. No
    branching on them: multiplication by an all-ones vector is the
    identity under pointwise multiply, so the "disabled" permutation
    is a numerical pass-through, not a skipped statement.
    """
    # Query = bind(smell, hunger)
    query = vsa.bind(smell_vec, hunger_vec)

    # Apply sign-flip keys. A "disabled" key is an all-ones vector,
    # which is the identity under pointwise multiplication.
    key_smell  = prims["NOT_SMELL"]  if not_smell  else np.ones(vsa.dim)
    key_hunger = prims["NOT_HUNGER"] if not_hunger else np.ones(vsa.dim)
    query = vsa.sign_flip(key_smell,  query)
    query = vsa.sign_flip(key_hunger, query)

    # Fly-brain cleanup — the mushroom body produces a brain-view
    # version of the query. This is the biological substrate's actual
    # work: sparse random projection + APL winner-take-all.
    brain_query = vsa.snap(query)

    # Cosine argmax against the 4 precomputed brain-view prototypes.
    # This is the "MBONs competing for a winner" step.
    winner, scores = match_prototype(vsa, brain_query, prototypes)

    # The compiled if-tree is this dict lookup. No Python `if`.
    behavior = PROGRAM_A_BEHAVIOR[winner]
    return behavior, winner, scores


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--hemibrain', action='store_true',
                        help='Use real hemibrain connectome instead of random projection')
    args = parser.parse_args()

    print("=" * 72)
    print("PERMUTATION CONDITIONALS ON THE FLY BRAIN")
    print("4 programs × 4 inputs, decision runs inside the mushroom body")
    print("=" * 72)

    if args.hemibrain:
        print("\nBuilding fly brain substrate from HEMIBRAIN connectome...")
        vsa = FixedFrameFlyBrainVSA(seed=42, use_hemibrain=True)
        print(f"  Real connectome: {vsa.dim} PNs → {vsa.n_kc} KCs → APL → 20 MBONs")
    else:
        print("\nBuilding fly brain substrate (50 PNs → 2000 KCs → APL → 20 MBONs)...")
        vsa = FixedFrameFlyBrainVSA(dim=50, n_kc=2000, seed=42)
    print("Using fixed-frame snap so compile-time prototypes and decision-time")
    print("queries decode through the same PN->KC connectivity.")
    rng = np.random.RandomState(vsa.seed)

    print("Building VSA primitives (smell/hunger bases + NOT keys)...")
    prims = build_primitives(vsa, rng)

    print("Compiling Program A prototype table (4 snaps, one per case)...")
    prototypes = compile_prototypes(vsa, prims)
    for name, proto in prototypes.items():
        print(f"  prototype {name}: norm={np.linalg.norm(proto):.3f}")

    # Four inputs × four programs = 16 decisions, each one a fly-brain snap.
    inputs = [
        ("vinegar",   "hungry", prims["smell_present"], prims["hunger_hungry"]),
        ("vinegar",   "fed",    prims["smell_present"], prims["hunger_fed"]),
        ("clean_air", "hungry", prims["smell_absent"],  prims["hunger_hungry"]),
        ("clean_air", "fed",    prims["smell_absent"],  prims["hunger_fed"]),
    ]

    # Expected behaviors per program (from DEMO.md table).
    expected = {
        "A": ["approach", "ignore",   "search",   "idle"],
        "B": ["search",   "idle",     "approach", "ignore"],
        "C": ["ignore",   "approach", "idle",     "search"],
        "D": ["idle",     "search",   "ignore",   "approach"],
    }

    all_results = {}
    for prog_id in ["A", "B", "C", "D"]:
        not_smell, not_hunger = PROGRAM_PERMUTATIONS[prog_id]
        print(f"\n{'─' * 72}")
        print(f"PROGRAM {prog_id}: {PROGRAM_LABELS[prog_id]}"
              f"   (not_smell={not_smell}, not_hunger={not_hunger})")
        print(f"{'─' * 72}")
        print(f"  {'Input':<22} {'Expected':>10} {'Got':>10}  "
              f"{'PH':>7} {'PF':>7} {'AH':>7} {'AF':>7}")
        print(f"  {'-' * 72}")

        results = []
        for i, (sn, hn, s_vec, h_vec) in enumerate(inputs):
            behavior, winner, scores = run_decision(
                vsa, prototypes, s_vec, h_vec, prims,
                not_smell, not_hunger,
            )
            exp = expected[prog_id][i]
            mark = "✓" if behavior == exp else "✗"
            results.append((sn, hn, exp, behavior, winner, scores))
            print(f"  {sn + ' + ' + hn:<22} {exp:>10} {behavior:>10}{mark} "
                  f"{scores['PH']:>+7.3f} {scores['PF']:>+7.3f} "
                  f"{scores['AH']:>+7.3f} {scores['AF']:>+7.3f}")
        all_results[prog_id] = results

    # Summary table + pass/fail gate.
    print(f"\n{'=' * 72}")
    print("SIDE-BY-SIDE: same prototypes, same substrate, four different queries")
    print(f"{'=' * 72}\n")

    header = f"{'Input':<22}"
    for prog_id in ["A", "B", "C", "D"]:
        header += f" {'Prog ' + prog_id:>10}"
    print(header)
    print("-" * len(header))
    for i, (sn, hn, _, _) in enumerate(inputs):
        row = f"{sn + ' + ' + hn:<22}"
        for prog_id in ["A", "B", "C", "D"]:
            row += f" {all_results[prog_id][i][3]:>10}"
        print(row)

    # Gate: all programs must produce the expected mapping, and the four
    # mappings must be distinct (permutations of each other).
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

    print(f"\nDecisions matching expected mapping: {correct}/{total}")
    print(f"All 4 programs produce distinct behavior mappings: {all_distinct}")
    print(f"GATE: {'PASS' if correct == total and all_distinct else 'FAIL'}")

    print(f"\n{'=' * 72}")
    print("WHAT CHANGED VS programmer_control_demo.py")
    print(f"{'=' * 72}")
    print("""
The previous demo ran the if/elif/else tree in Python. The fly brain was
used only to clean up the two input vectors (smell, hunger); the decision
itself was an ordinary Python conditional over has_smell / is_hungry.

This demo compiles the whole conditional to a prototype table in the
fly brain's output space, and runs every decision through the mushroom
body:

  - If-tree    → 4 brain-view prototypes, precomputed by running snap()
                 on each (smell, hunger) conjunction at compile time
  - Negation   → permutation key  (`!X` compiles to `permute(NOT_KEY, X)`)
  - Decision   → query + permutations + snap + cosine argmax vs prototypes
  - Programs   → four permutation key compositions over ONE prototype table

There is no Python `if` in the decision path. Every program applies the
same operations in the same order; only the permutation keys multiplied
into the query change. The fly brain's snap is what turns the query into
a brain-view vector, and the cosine argmax against four precomputed
prototypes is the biological analogue of four MBONs competing for a
winner — exactly the circuit the real fly evolved for olfactory decision
making.

Same substrate. Same prototype table. Four different queries. Four
different behaviors. The programmer writes vector transformations, not
control flow.""")


if __name__ == "__main__":
    main()
