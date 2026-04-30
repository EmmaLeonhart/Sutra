# Capacity experiment: rotation binding in a synthetic subspace

**Date:** 2026-04-21.
**Status:** Experiment **design** — not yet run. Validates the
rotation-binding + extended-state-vector design before it moves
into the spec. Companion to
`2026-04-21-extended-state-and-rotation-binding.md`.

## What we're validating

The rotation-binding design (see companion doc) claims three
properties that need empirical backing in high dimensions before
they are committed to the spec:

1. **Zero cross-talk between variable slots.** Allocating each slot
   to its own orthogonal 2D rotation plane should make retrieval
   from slot i completely insensitive to content stored at slot j.
   Theoretical claim, needs confirmation under practical cleanup
   (cosine readout + snap) and realistic noise.
2. **Truth-axis orthogonality under operations.** Semantic content
   operated on by learned-matrix bind and bundled should keep zero
   projection onto the canonical truth axis. And fuzzy scalars on
   the truth axis composed under `and`/`or`/`not` should not pick
   up semantic drift.
3. **Reversibility of imperative-style state.** A sequence of
   variable assignments `x = a; x = b; x = a` should produce a
   final state vector that matches (to within bounded round-trip
   error) the one-line `x = a` version.

Plus one **practical capacity question**: how many variable slots
does a given synthetic-subspace size `N` actually support under
realistic conditions? Theory says `N/2` clean slots with 2D-Givens-
per-slot allocation; empirically, how does retrieval accuracy degrade
as we approach that limit?

## Experiment 1 — slot cross-talk at full capacity

**Goal.** Verify zero cross-talk at the theoretical `N/2` capacity
for each `N ∈ {16, 32, 64, 128}`.

**Setup.**
- Build an extended state vector of length `N` (synthetic subspace
  only for this experiment — no semantic content).
- Allocate `N/2` variable slots, each as one 2D Givens rotation
  plane in disjoint pairs of coordinates: slot 0 uses dims (0,1),
  slot 1 uses dims (2,3), …, slot `N/2 - 1` uses dims (N-2, N-1).
- Generate a codebook of 16 distinct "values" per slot — random
  unit vectors projected into each slot's 2D plane.
- For each trial: pick a random permutation assigning one codebook
  value to each slot; bundle (sum) all `N/2` bound values into a
  single state vector; query each slot by de-rotation and nearest-
  codebook-entry cleanup; measure recovery accuracy per slot.

**Success criterion.** Recovery accuracy ≥ 99% per slot across 100
trials for each `N`. Any systematic cross-talk indicates the design
needs revisiting.

**What would fail this.** If cross-talk appears, it likely means the
rotation allocation leaked between planes — either because the
"bundled sum" step introduces numerical cross-talk the theory missed,
or because cleanup (nearest-cosine) has a bias that reintroduces
contamination. A failure here is a design signal, not an
implementation nit.

## Experiment 2 — capacity curve

**Goal.** Map the recovery accuracy vs. number-of-slots curve
beyond `N/2` to see how degradation behaves when slots start
overlapping.

**Setup.**
- Fix `N = 64`.
- Vary `k = number of active slots ∈ {8, 16, 24, 32, 40, 48, 56, 64}`.
- When `k ≤ N/2 = 32`, each slot gets its own disjoint 2D plane.
- When `k > N/2`, start *sharing* 2D planes among slots — simulate
  a compiler that ran out of dimensions and had to double up. Each
  shared plane uses a different rotation angle per slot
  (`R^1, R^2, …`).
- Run 100 trials per `k`, measure mean recovery accuracy.

**Success criterion.** No single threshold — this is a
characterization curve. We want to see:
- Essentially perfect recovery for `k ≤ 32`.
- Graceful degradation for `k > 32` (not catastrophic).
- A specific crossover point where accuracy falls below 90%, so we
  can recommend a practical per-program budget.

## Experiment 3 — truth-axis orthogonality under bind/bundle

**Goal.** Verify that semantic-subspace operations don't leak onto
the truth axis.

**Setup.**
- Extended state vector: `[semantic_dims (d=768) | synthetic_dims (N=64)]`.
- Designate the first synthetic dimension (index 768) as the truth
  axis.
- Generate a random learned-matrix role `R_semantic` acting only on
  the semantic subspace (a 768×768 matrix with zeros in the other
  blocks of the full (768+64)×(768+64) matrix).
- Generate 100 random semantic-subspace filler vectors.
- For each: apply `R_semantic @ filler`; verify the truth-axis
  coordinate (index 768) is exactly zero (up to floating-point
  epsilon).
- Bundle (sum) multiple such bindings; verify the bundled vector's
  truth-axis coordinate is still exactly zero.

**Success criterion.** Truth-axis coordinate magnitude ≤ 1e-14
across all trials. This should be trivially true if the subspace
structure is enforced by block-diagonal matrices, but it's worth
confirming the compiler / runtime actually maintains the block
structure end-to-end.

## Experiment 4 — reversibility round-trip

**Goal.** Verify that a sequence of variable assignments is
reversible (round-trip to within bounded error).

**Setup.**
- Extended state vector with synthetic subspace of `N = 32` and
  8 allocated variable slots.
- Sequence of 100 random operations: pick a random slot, pick a
  random codebook value, assign.
- After the 100 operations, apply the inverse of each operation
  in reverse order.
- Measure L2 distance between the final state and the initial
  (all-zero) state.

**Success criterion.** Final-vs-initial L2 distance ≤ 1e-10 for
orthogonal-rotation-exact operations. If we use numerical rotations
(not exact), budget 1e-6 per operation (100 ops × 1e-6 = 1e-4 total).

**What would fail this.** Accumulated floating-point error beyond
the budget would tell us rotation-binding implementations need to
renormalize periodically or use higher-precision arithmetic.
Non-reversibility (beyond the FP budget) would indicate a design
error — every rotation should have an exact inverse.

## Experiment 5 — fuzzy composition on the truth axis

**Goal.** Verify that fuzzy operations (`and`, `or`, `not`)
compose correctly on the truth-axis scalar without picking up
contamination from the rest of the synthetic subspace or from
semantic content.

**Setup.**
- Extended state with synthetic subspace of `N = 32` and 4 boolean
  variable slots.
- Assign each slot a fuzzy scalar on the truth axis (e.g. `+0.7`,
  `-0.3`, `+0.9`, `+0.1`).
- Implement `and` as fuzzy t-norm (min or product) on the
  extracted truth-axis scalars.
- Compute `a AND b`, `a OR b`, `NOT a` for various pairs.
- Verify results match fuzzy logic expectations: `min(0.7, -0.3) = -0.3`
  (both need to be true; one is false-ish, so AND is false-ish); etc.

**Success criterion.** Results within 1e-10 of the expected fuzzy-
logic value. Also: changing the semantic-subspace content (which
should not affect truth) does not change the computed fuzzy-logic
result.

## Implementation notes

- Single Python script with numpy, runnable in seconds per
  experiment.
- Save under `fly-brain/` or a new `experiments/` dir? Given the
  CLAUDE.md "avoiding fly-brain/ Python sprawl" rule, put it in
  a new `experiments/` dir at repo root, with a single file per
  experiment or (better) a single file exercising all five.
- Each experiment prints a result summary and returns pass/fail.
- Record results as a follow-up `planning/findings/` doc once run.

## What happens after the experiments

- If all five pass: the rotation-binding + extended-state design is
  validated. Move the relevant sections from the design note into
  `planning/sutra-spec/binding.md` as committed spec (not "pending
  experimental validation"), and close out queue.md queue item 2.
- If experiment 1 or 2 fails: the allocation scheme needs revisiting.
  Candidates: different rotation-plane choices (e.g. Fourier basis),
  cleanup procedure tuning, or giving up on the zero-cross-talk
  claim and framing the design as "low-statistical-cross-talk"
  instead.
- If experiment 3 fails: the block-diagonal structure isn't being
  maintained end-to-end — probably an implementation bug in how the
  learned-matrix bind is projected. Fix before it's wired into any
  demo.
- If experiment 4 fails beyond FP budget: rotation binding is not
  truly reversible under the chosen implementation; either switch
  to exact orthogonal rotations, add periodic renormalization, or
  reframe the design as "approximately reversible."
- If experiment 5 fails: `is_true` / defuzzification / fuzzy
  composition on the truth axis is entangling with other synthetic
  dims — either the axis extraction is wrong or the composition
  rule is doing something not-just-on-the-axis.

## Prior-art audit pending

The capacity question specifically has a well-developed theoretical
literature in VSA (Plate 1995 chapter 3 on HRR capacity, Frady et
al. on information capacity of hyperdimensional computing, Kleyko
et al. on capacity of bundle codes). Before publication, these need
to be cited and the empirical results compared. Dev-level validation
does not wait on the audit.
