# Control Flow: `select` and `select else` — Sutra Has No Control Flow

This document supersedes `03-control-flow.md` for the control-flow model. `03-control-flow.md` remains as historical/implementation context for eigenrotation loops; the present document is the canonical statement of what control flow is in Sutra.

> **2026-04-15 spec move.** This document previously described two control-flow primitives, `select` and `gate`. `gate` is dropped. `select` (with an optional `else` clause) is the one branching primitive. The reasoning: `gate` was a defuzz-then-commit construct, and defuzzification in Sutra is a differentiable matrix polarization, not a non-differentiable commit — so the work `gate` was doing collapses into `select`. There is no separate "commit" primitive, no backprop discontinuity at a branch, and no second name to learn. See "What this supersedes" below for the migration of prior `gate`-shaped uses.

## The thesis

**Sutra has no control flow.**

There are no branches, no jumps, no stop-and-test loop heads, no return-address stack, no program counter that can skip over code. Every traditional control-flow construct is absorbed into geometry:

- A conditional is a continuous weighted sum of outputs, not a decision about which one to run.
- A loop is a rotation that keeps moving, not a stop-check-branch cycle.
- A loop exit is a softmax-weighted readout that increasingly favors the exit option as the trajectory's match to a target prototype increases — the substrate keeps moving either way; the readout determines which regime the output is read from.

The consequences follow from the premise, not the other way around:

1. **GPU-native and connectionist-native execution.** Everything is a matmul, a sum, or a cosine. No branch predictor, no divergent warps, no tail-call stack — which is exactly the shape a GPU or a connectionist substrate wants.
2. **End-to-end differentiable.** The usual things that break backprop (discrete branches, `if` predicates, `while` condition tests) are not in the language. A Sutra program — including its defuzzification step — is a composition of differentiable operations, because defuzzification is itself a differentiable matrix polarization (see `04-defuzzification.md` and the note below).
3. **Decompilable from connectionist systems, at least in principle.** Because the language primitives are geometric rather than symbolic, a trained connectionist system can, in principle, be characterized as a specific composition of Sutra primitives — the same way a compiled binary can be decompiled to a specific C program modulo naming. This is an interpretability claim, not a universal one.

The cost of this premise is that Sutra is not a portable general-purpose language. You do not write a GUI event loop in it. You do not write `os.walk`. What you write in it is a narrow, useful, substrate-resident program — a conditional, a lookup, a bounded trajectory — on whatever connectionist substrate is available.

## The one control primitive

Sutra has exactly one control-flow primitive, `select`, in two forms.

### `select(scores, options)` — softmax-weighted superposition

```
select(scores: vector[k], options: vector[k][d]) -> vector[d]

w = softmax(scores)          // w_i = exp(scores_i) / sum_j exp(scores_j)
return sum_i w_i * options_i
```

`select` chooses *which process to apply* to something. It produces a weighted continuous blend of the `options`, where the weights come from a softmax over a scores vector. Properties:

- **Differentiable** in `scores`, `options`, and the implicit softmax temperature.
- **No defuzzification at the branch.** The result is itself a vector in the substrate, usable as the input to further operations without ever becoming a crisp choice. Confidence propagates through the computation as geometry.
- **Substrate-resident.** The softmax is computed on the substrate (for the connectome target: drive the branches simultaneously at softmax-weighted rates, read the superposed output). The host compiles the program but does not execute the selection.
- **Total weight is 1 across the k options.** A single `select` block has an *implicit blank else* — there is no leftover mass routed elsewhere.
- **Commutative up to labeling.** `select([s₁, s₂], [a, b]) = select([s₂, s₁], [b, a])` — the correspondence of scores to options is the only thing that matters.

### `select(scores, options) else fallback` — softmax with a "none of the above" sink

```
select(scores: vector[k], options: vector[k][d]) else fallback : vector[d] -> vector[d]

s_else = else_score(scores)             // implicit "how unlike any of these is the input"
w = softmax([scores, s_else])           // length k+1, sums to 1
return sum_i w_i * options_i  +  w_{k+1} * fallback
```

`select … else` extends `select` with a `(k+1)`-th implicit option whose score is "how unlike any of the named options the input is." When no real score dominates, mass flows to the fallback. The fallback is the default for search-shaped statements, where "none of the candidates is a match" is a meaningful answer.

- **Still differentiable**, with the `else_score` participating in the softmax just like the named scores.
- **Not the same as appending a fifth option with score 0.** The else-score is supposed to *measure absence*: it should grow when no named option matches, not contribute a constant baseline. The choice of `else_score` formula is open — see "What this document does not settle" below.
- **Implicit at the end of every single-block `select`.** A bare `select(...)` with no `else` clause has an implicit blank `else` (mass sums to 1 across the k named options, no fallback term). That is the default when there is no `else` keyword. As soon as `else` is written, it is the explicit `(k+1)`-th term.

### Why one primitive instead of two

The earlier version of this document defined a second primitive, `gate`, whose job was to defuzzify a condition via `is_true` and commit the trajectory to one regime or the other. That job is now done by `select` for two reasons:

1. **Defuzzification is a differentiable matrix polarization, not a non-differentiable commit.** What `is_true` does is sharpen the substrate state along a target axis (see `04-defuzzification.md`). The output is still a vector; backprop still flows through it; subsequent operations can still consume a near-binary state without a discrete branch. So a "commit primitive" was solving a problem (loss of gradient at the branch) that no longer exists.
2. **A loop exit is just a `select` whose options are "stay in the loop body" and "leave with the current state," with scores that depend on the trajectory's match to a target prototype.** The trajectory always keeps moving; the readout shifts from one option to the other as the match grows. There is no stop-and-test, just as there was not under `gate` — but there is also no second primitive name to learn.

The state-change framing that motivated `gate` is preserved by convention rather than by syntax: when a programmer writes a `select` whose options are qualitatively different regimes (one continues the current computation, one moves to a different mode), readers should treat it as a regime transition. The compiler does not warn on this; the programmer is expected to mean what they wrote.

## The usage rule

- **Use bare `select(scores, options)` to choose among k named processes.** All k options are meaningful; total mass is 1; there is no fallback. Four-program-variant conditional branching (fly-brain paper §6.6, Shiu conditional) is a `select` over four behavior codebooks with scores from cosine against four prototype codebooks.
- **Use `select(...) else fallback` when "none of the candidates is a match" is itself a valid answer.** Search statements are the canonical case: the named options are candidate matches; the fallback is "no match" or "default behavior."
- **Use `select` for loop exits as well.** The two options are the loop body's continuation and the loop's exit value; the score on the exit option grows as the trajectory's match to a target prototype grows. No second primitive is needed. (See `03-control-flow.md` for the eigenrotation mechanics on the substrate; the readout layer is a `select`.)

## What this supersedes

The previous version of this document (and `03-control-flow.md`) documented several constructs that all collapse into `select`:

1. **Fuzzy-superposition conditional** (`result = condition * branch_true + (NOT condition) * branch_false`) — a special case of `select` with two options.
2. **Cone traversal** (discrete navigation through a codebook graph) — a codebook operation (see `02-operations.md`). When used for branching it is a `select` with a one-hot score; the mechanism is codebook lookup, not softmax weighting.
3. **Eigenrotation loop** (`loop (condition) body` iterates `state ← R·state` and terminates on prototype match) — the operational realization on the connectome substrate. The rotation is the "keep moving"; the exit readout is a `select` between continuation and exit, with the exit score driven by KC Jaccard overlap.
4. **`gate(condition, through, else_through)`** — dropped. Migration: rewrite as `select([is_true(condition), 1 - is_true(condition)], [through, else_through])`, or — when "neither" is meaningful — as `select([is_true(condition)], [through]) else else_through`. The `is_true` call remains a differentiable matrix polarization (`04-defuzzification.md`); it does not introduce a non-differentiable commit.

The grammar (`24-grammar.ebnf`, `24-grammar.md`) currently has a `select`-shaped `if` form. Adding the explicit `select(...)` and `select(...) else fallback` productions, and removing any `gate(...)` production that was added during the §26 v1 work, is a follow-on grammar edit (see todo.md item below).

## What this document does not settle

1. **The `else_score` formula in `select(...) else fallback`.** The current working default is **a fixed bias of `0`** — `s_else = 0`, so the else option only wins when every real score is negative. This is a placeholder. The user has flagged it as discouraged because it is not clear what `s_else = 0` actually *means*: a constant baseline does not measure "how unlike any of the named options the input is," which is what the else clause is supposed to capture. Plausible alternatives include `1 - max(scores)`, `-logsumexp(scores)`, or a substrate-computed novelty score. The choice has to be made before any production demo relies on `select … else` semantics. Tracked in `todo.md` under "Pre-Y-Combinator pitch."
2. **Threshold semantics in loop-exit `select`s.** Whether the exit score is a compile-time constant, a runtime vector, or something the substrate discovers (e.g., the trajectory naturally settling into a basin) is unresolved. The existing §3.4 defuzzification has compile-time θ; eigenrotation-loop exits may want runtime θ for interesting cases.
3. **Differentiability across the polarization.** `is_true` is a matrix polarization and is differentiable in the standard sense, but the gradient is sharp near the polarization axis. Whether a temperature schedule, a Gumbel relaxation, or just plain backprop is sufficient is an open implementation question.
4. **Decompilation of trained connectionist systems into Sutra.** Asserted as a consequence of no-control-flow above; not formalized here. A separate exploratory doc in `planning/exploratory/` is the right place for that thesis — this spec is not the place to overclaim it.
5. **Relationship to the existing `is_true` threshold conditional.** Now that there is no `gate`, the §3.4 "thresholded defuzzification" is just a use of `is_true` as input to a `select`. The naming question (deprecate the threshold-conditional name, or keep it as syntactic sugar) is deferred.

## Landing this in the papers

The papers (`sutra-paper/paper.md`, `fly-brain-paper/paper.md`) currently describe fuzzy-superposition branching and eigenrotation loops as two separate mechanisms. Under this spec they are two uses of one primitive (`select`), unified under the "no control flow" thesis. The Sutra paper's §3.3 should be rewritten around this — one primitive, two forms (with/without `else`), defuzz framed as differentiable polarization.
