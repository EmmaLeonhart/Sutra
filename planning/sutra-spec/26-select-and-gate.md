# Control Flow: `select` and `gate` — Sutra Has No Control Flow

This document supersedes `03-control-flow.md` for the control-flow model. `03-control-flow.md` remains as historical/implementation context for eigenrotation loops; the present document is the canonical statement of what control flow is in Sutra.

## The thesis

**Sutra has no control flow.**

There are no branches, no jumps, no stop-and-test loop heads, no return-address stack, no program counter that can skip over code. Every traditional control-flow construct is absorbed into geometry:

- A conditional is a continuous weighted sum of outputs, not a decision about which one to run.
- A loop is a rotation that keeps moving, not a stop-check-branch cycle.
- A loop exit is a gate that opens on a defuzzified trajectory state — the substrate keeps moving either way; the gate determines which regime the output is read from.

The consequences follow from the premise, not the other way around:

1. **GPU-native and connectionist-native execution.** Everything is a matmul, a sum, or a cosine. No branch predictor, no divergent warps, no tail-call stack — which is exactly the shape a GPU or a connectionist substrate wants.
2. **End-to-end differentiable.** The usual things that break backprop (discrete branches, `if` predicates, `while` condition tests) are not in the language. A Sutra program minus the final defuzzification step is a composition of differentiable operations.
3. **Decompilable from connectionist systems, at least in principle.** Because the language primitives are geometric rather than symbolic, a trained connectionist system can, in principle, be characterized as a specific composition of Sutra primitives — the same way a compiled binary can be decompiled to a specific C program modulo naming. This is an interpretability claim, not a universal one.

The cost of this premise is that Sutra is not a portable general-purpose language. You do not write a GUI event loop in it. You do not write `os.walk`. What you write in it is a narrow, useful, substrate-resident program — a conditional, a lookup, a bounded trajectory — on whatever connectionist substrate is available. (See also: "sprinkler with connectionist infrastructure" as the framing the user has articulated for this.)

## The two control primitives

Sutra has exactly two control-flow primitives. They are distinguished by how they treat their condition.

### `select` — fuzzy, softmax-weighted, no defuzz

```
select(scores: vector[k], options: vector[k][d]) -> vector[d]

w = softmax(scores)          // w_i = exp(scores_i) / sum_j exp(scores_j)
return sum_i w_i * options_i
```

`select` chooses *which process to apply* to something. It produces a weighted continuous blend of the `options`, where the weights come from a softmax over a scores vector. It is:

- **Differentiable** in `scores`, `options`, and the implicit softmax temperature.
- **No defuzzification.** The result is itself a vector in the substrate, usable as the input to further operations without ever becoming a crisp choice. Confidence propagates through the computation as geometry.
- **Substrate-resident.** The softmax is computed on the substrate (for the connectome target: drive the branches simultaneously at softmax-weighted rates, read the superposed output). The host compiles the program but does not execute the selection.
- **Commutative up to labeling.** `select([s₁, s₂], [a, b]) = select([s₂, s₁], [b, a])` — the correspondence of scores to options is the only thing that matters.

**When to reach for `select`:** to route vectors through alternative transformations — "apply process A or process B depending on the query, and let the substrate blend them." Four-program-variant conditional branching (fly-brain paper §6.6, Shiu conditional) is a `select` over four behavior codebooks with scores from cosine against four prototype codebooks.

Open spec question: is softmax the right defuzz-free normalizer, or is clipped-cosine-then-normalize (what the current Shiu implementation does) preferable on substrates where exponentials are expensive? Softmax is the canonical mathematical answer; the current fly-brain implementation uses `max(0, cos)` + sum-normalize because it is what the substrate can drive cheaply. Both satisfy "convex combination of options"; softmax is sharper and differentiable everywhere with a temperature. This doc picks softmax as the spec; implementations may approximate it and must report the approximation.

### `gate` — defuzzifies the condition, commits to a direction

```
gate(condition: vector, through: vector, else_through: vector) -> vector

t = is_true(condition)        // scalar in [-1, 1]
// once t has been read, the substrate commits to one direction:
if t >= threshold:
    output trajectory = <continue through the "through" regime>
else:
    output trajectory = <continue through the "else_through" regime>
```

`gate` changes *fundamentally from one thing to another*. It defuzzifies its condition via `is_true` and commits the trajectory to one regime or the other. The operational story is not "the substrate stops and branches"; it is "the substrate keeps moving, and the gate determines which direction the trajectory continues in after the gate point." The defuzzification happens once, at the gate; everything downstream of the gate runs in one regime without re-evaluating.

- **Partially differentiable.** Differentiable in `condition` up to the threshold crossing; not differentiable across the crossing itself. The standard straight-through-estimator or Gumbel-softmax relaxation applies if end-to-end gradients are required, at the cost of some of the "commit" semantics.
- **Loop exit is the canonical use.** A `loop (cond) body` is an eigenrotation of `body` through the substrate, gated on `cond`: the trajectory keeps rotating, and when `is_true(cond)` crosses threshold the gate opens and the output trajectory leaves the loop regime. There is no back-branch, no host-side iteration counter, no stop-and-test.
- **State-change is the canonical semantics.** `gate` is for situations where the program is moving from one *kind of thing* to another — exiting a loop, committing to a decision, crossing a boundary from "considering" to "answered." The defuzz is justified because the subsequent computation is in a regime where the fuzzy state would be meaningless (e.g., "I am inside the loop with condition half-true" is not a state the next phase can consume).

**When to reach for `gate`:** for loop exits. For final decision commits at the end of a trajectory (the thresholded `is_true` at the top of `04-defuzzification.md`). For "the program is now in a different mode" transitions. Not for choosing among processes — that is what `select` is for.

## The usage rule

The two primitives look superficially similar — both take a condition-like input and produce a vector output — but they are not interchangeable. The rule:

- **`select` chooses *which process* to apply.** The program stays in the same mode; it just dispatches differently. Use `select` whenever multiple alternative transformations are meaningful simultaneously.
- **`gate` changes *what the program is doing*.** The program moves from one regime to another. Use `gate` whenever the computation downstream of the control point is qualitatively different from the computation upstream, or whenever continued fuzzy blending is semantically wrong.

If you find yourself reaching for `gate` to pick among processes, you want `select`. If you find yourself reaching for `select` to exit a loop, you want `gate`. The compiler should warn on swaps but not reject them — there are edge cases (soft loop exits, hard process dispatch) where the "wrong" primitive is genuinely what's wanted.

## What this supersedes

The previous `03-control-flow.md` documented two constructs:

1. **Fuzzy-superposition conditional** (`result = condition * branch_true + (NOT condition) * branch_false`) — this is a special case of `select` with two options and two scores. `select` is the generalization and the name under which it now lives in the spec.
2. **Cone traversal** (discrete navigation through a codebook graph) — this is **not** `gate`. Cone traversal is a codebook operation (see `02-operations.md`). When it is used for branching, it is closer to `select` with a one-hot score (the argmax over cone candidates), but the mechanism is codebook lookup, not softmax weighting.
3. **Eigenrotation loop** (`loop (condition) body` iterates `state ← R·state` and terminates on prototype match) — this is the operational realization of `gate` on the connectome substrate. The rotation is the "keep moving"; the termination check is the "gate opens when `is_true(cond) ≥ θ`" in the form of "KC Jaccard overlap ≥ θ." The math in §03 is correct; the framing here (the gate opens and the trajectory leaves the loop regime) supersedes the earlier framing of "the loop terminates."

The language currently implements `select` (as the four-way fuzzy conditional in `fly-brain/fuzzy_conditional.py` and §6.6) and an eigenrotation-loop form of `gate` (as `loop (condition)` in `03-control-flow.md`). There is no standalone `gate` primitive in the grammar yet; adding it is spec-open work. The grammar at `planning/sutra-spec/24-grammar.md` / `24-grammar.ebnf` will need a `gate(…)` production alongside the existing `select`-shaped `if` / `select` forms.

## What this document does not settle

In the user's words: the spec documents here are not as well-audited as they might appear. This doc is the headline thesis and the primitive inventory. The following are deliberately left open:

1. **Softmax vs clipped-cosine-and-normalize** as the canonical `select` weighting. Pinned above; see the open spec question.
2. **Threshold semantics for `gate`.** Is the threshold a compile-time constant (`confidence: 0.9`), a runtime vector (`gate(cond, through, else, θ=...)`), or something the substrate discovers (e.g., by the trajectory naturally settling into a basin)? The existing §3.4 defuzzification has compile-time θ; the new `gate` primitive may want runtime θ for interesting cases.
3. **Differentiability across a gate in practice.** The straight-through estimator and Gumbel-softmax are both documented as "apply if gradients are needed across the gate," but neither is wired into any current backend. This is a real implementation gap if the differentiability thesis is going to be demonstrated empirically.
4. **Decompilation of trained connectionist systems into Sutra.** Asserted as a consequence of no-control-flow above; not formalized here. A separate exploratory doc in `planning/exploratory/` is the right place for that thesis — this spec is not the place to overclaim it.
5. **Relationship to the existing `is_true` threshold conditional.** The current §3.4 "thresholded defuzzification" is arguably already `gate`. Whether to treat it as a deprecated name for `gate`, a lowered form of `gate`, or a separate construct is a naming decision this doc does not make.

## Landing this in the papers

The papers (`sutra-paper/paper.md`, `fly-brain-paper/paper.md`) currently describe fuzzy-superposition branching and eigenrotation loops as two separate mechanisms. Under this spec they are two uses of two primitives (`select` for branching, `gate` for loop exit), unified under the "no control flow" thesis. The Sutra paper's §3.3 should be rewritten around this, replacing the two-construct description with the one-thesis-two-primitives description. This is pre-mortem-flagged structural work, not a reviewer-response patch — see `planning/findings/2026-04-14-sutra-paper-pre-mortem.md`.
