# Open question: can conditional branching execute on the remote substrate?

## The question

`fuzzy_conditional.su` demonstrates spec-aligned 4-way weighted superposition and hits 16/16 + 80/80 across hemibrain seeds. But the *branch decision itself* — the argmax over behavior-codebook similarities that converts the fuzzy result vector into a discrete behavior — runs in host Python. What would it mean for that decision to happen on the substrate, not on the host?

Phrased differently: right now the substrate produces a superposed result vector, and the host reads it out and picks a winner. Is there a formulation where the winner is selected *by* the circuit, such that the host just observes which MBON fires?

## What we currently do

In the generated fuzzy_conditional pipeline:

1. `bind(smell, hunger)` — input-space sign-flip, then `snap()` through the MB (substrate).
2. `similarity(brain_query, proto_i)` for each prototype — Jaccard on KC patterns (substrate).
3. `result = Σ wᵢ · behavior_vecᵢ` — weighted sum in host numpy (see sibling open question).
4. `argmax_cosine(result, behavior_codebook)` — host-side loop over 4 candidates, picking the max cosine.
5. `BEHAVIOR_NAME[winner]` — map lookup in host.

Steps 4 and 5 are the "branching" part. They are completely host-side.

## Why this matters

The paper's claim is "programs execute on the fly brain." If the substrate's job is to produce a 140-D float vector that the host then argmaxes and dictionary-looks-up, a skeptical reviewer can reasonably say the decision is a host-side classifier reading a substrate-derived feature vector. True; not the most aggressive claim we could make.

A fully on-substrate formulation would look something like:

- The behavior codebook is encoded as 4 prototype KC patterns (one per behavior — `approach`, `ignore`, `search`, `idle`).
- The fuzzy result vector is snapped into KC space.
- A winner-take-all MBON readout ("highest Jaccard to which behavior prototype") runs as a differential-activation race in a small downstream population, not as `max(dict.items())`.
- The host observes MBON firing rates and reads out the winning behavior by which MBON spiked hardest.

## What's uncertain

1. **Is the MB the right place for WTA?** Hemibrain MBON output is already read out linearly via ridge regression in our pipeline (see `spike_vsa_bridge.py`). We don't have a winner-take-all circuit in the simulated substrate. The lateral horn and FB/MBON lateral inhibition are real candidates in the biological fly, but not in our current simulation.
2. **Does this remove host Python entirely, or just move the final step?** Even with MBON-WTA, *someone* has to translate MBON identities back into behavior names ("approach" etc.). That lookup is linguistic — it lives wherever the agent's motor program lives, not on the MB. So maybe "branch decision on substrate" just means "argmax-as-circuit" and naming stays in host. Fine, but worth being explicit.
3. **How does this interact with loops?** `loop(condition)` already needs to evaluate "did we match the prototype yet?" on the substrate at each iteration (Jaccard over KC patterns, ≥ threshold). Branching-on-substrate and loop-termination-on-substrate are probably the same primitive — a substrate-side comparator/WTA — wearing different hats.
4. **How does this interact with `is_true`?** `planning/sutra-spec/04-defuzzification.md` defines `is_true` as cosine similarity to a reserved true-vector, thresholded. That's the single-prototype case of the same comparator. If we build WTA on substrate, `is_true` and `argmax_cosine` and loop termination all become instances of one substrate op.

## Concrete next steps (when picked up)

- Sketch the minimal "KC-pattern argmax over N behavior prototypes" circuit. Even a 4-neuron lateral-inhibition network would do.
- Replace the generated `_argmax_cosine` helper with a call into that circuit.
- Measure: does it match the host argmax on the same inputs? Where does it break?
- Decide whether to promote this into a tier-3 op in the spec, alongside `snap` / cone traversal / hop.

## Status

Unresolved. Not blocking the Claw4S paper — the paper is careful to call the current pipeline "substrate does prototype matching and similarity; host does final argmax." Blocks a stronger later claim. Worth thinking about alongside the tier-2-bundle open question, since both are instances of "how much of this pipeline is physically happening on neurons?"
