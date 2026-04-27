# Open question: a single learned matrix `is_converter` that produces `is_X` from `X`?

## The question

Sutra's semantic-binding spec (`planning/sutra-spec/binding.md`) treats
each learned role matrix as fit individually from corpus data. `R_is_cat`
is fit on `(thing_emb, is_that_cat_label)` pairs, `R_is_dog` is fit on
`(thing_emb, is_that_dog_label)` pairs, etc. — one matrix per relation.

Is there instead a *single* learned matrix `is_converter` such that
for any concept vector `c` in the substrate,

```
M_is_c = is_converter @ outer(c)         // or some reshape
```

produces the test matrix `M_is_c` whose application to any other
vector `v` returns a fuzzy truth value of "is `v` an instance of
`c`?" If `is_converter` exists and is universal across concepts, the
binding spec's per-relation fitting story collapses to a single
amortized fit, and the language gains a generic `is/2` constructor:

```
matrix is_dog = is_converter * dog;
fuzzy result  = is_dog * input;  // ≈ true if input ≈ dog-shaped
```

This is structurally a meta-binding: a learned operator that takes
*concepts as input* and emits *binders as output*. At rank-1 the
construction degenerates to an outer product `c ⊗ c^T`, which is
what a naive concept-projector would be — but the user's framing is
that `is_converter` is the *learned* full-rank generalization that
also captures the equivalence neighborhood (puppy/canine/Labrador
all firing on `is_dog`), not just the projection onto `c` alone.

## Why this is interesting (and not yet captured anywhere)

The current spec commits to learned matrices per-relation. The
meta-matrix idea would change the **economics of learning roles**:
instead of fitting N matrices for N relations, fit one matrix and
read off all N. If it works, it would also unify `is_X` predicates
(currently sketched in `equality-and-defuzzification.md` as semantic
binding operators) under a single substrate-level construction
rather than as N independent fits.

The construction is closest in spirit to:

- **Hypernetworks** — networks that emit weights for other networks.
  `is_converter` would be the rank-3 / matrix-output analog.
- **TransE-style relation embeddings** — but relations are matrices
  not displacements, and the "embedding" of a relation is itself
  produced from a concept embedding rather than fit independently.
- **The cartography work's "displacement is a function of the
  predicate name embedding"** observation. If the rank-0 case
  (predicate → displacement vector) admits a learned converter,
  the rank-N case (concept → projector matrix) might too.

## What we currently do

Nothing. The binding spec assumes per-relation fitting; no meta-
matrix construction is implemented or sketched in the live spec.
The deferred learned-matrix-binding work (`STATUS.md`'s "Deferred"
section) targets the per-relation form.

## What would need to be true to close this

- **Empirical:** does an `is_converter` exist that generalizes across
  held-out concepts? Train on `(c_train, M_is_c_train)` pairs for
  some training concepts, test on whether `is_converter * c_test`
  gives a useful test matrix for unseen concepts.
- **Capacity:** how does the meta-matrix's expressivity scale with
  substrate dim and training-set diversity? A single matrix has to
  encode every "is X" projector — does that fit?
- **Spec impact:** if it works, does the language surface need a
  `meta_role` or `concept_to_role` declaration form, or does it
  stay implicit in the runtime as an optimization of the per-
  relation fitting?
- **Bias risk:** an `is_converter` fit on a fixed corpus would bake
  in that corpus's category structure as the universal "what counts
  as instancehood" operator. That's the same risk per-relation
  fitting has, but concentrated in one operator instead of spread
  across N. Worth surfacing in the failure-mode discussion.

## Why this stays an open question rather than a commitment

The user-stated framing in the originating chat treats `is_converter`
as plausible-but-untested ("I think you might be able to do
something like this"). No experiment has been run against the
current substrate. The per-relation fitting story is what the spec
is built on, and replacing it with a meta-matrix construction is a
research bet, not a known-good engineering move.

The honest current state: **per-relation fitting is the spec's
binding implementation; a universal `is_converter` is a
parameterization optimization that may or may not be realizable
empirically on real substrates.** Close this question with either
an experiment that produces `is_converter` and validates it
out-of-distribution, or with a reasoned argument for why no such
operator can exist (e.g., capacity / orthogonality / substrate-
geometry argument).

## Related

- `planning/sutra-spec/binding.md` §"Semantic binding" — the
  per-relation form this would amortize.
- `planning/sutra-spec/equality-and-defuzzification.md` — `is_X` as
  semantic binding operators; meta-matrix would generate these
  from concept vectors directly.
- `planning/sutra-spec/types.md` open-question "First-class matrix
  subtypes" — `rotation_matrix`, `defuzz_matrix`, `is_X_matrix`.
  The meta-matrix is what would mechanically *produce* an `is_X_matrix`.
- The cartography work's predicate-displacement consistency result
  (sibling repo `latent-space-cartography`) is the rank-0 analog;
  if it generalizes to rank ≥ 1, the meta-matrix is the natural
  construction.
