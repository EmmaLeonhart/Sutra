# Binding

Every `bind` in Sutra is **matrix-vector multiplication**:

```
bind(filler, R) = R @ filler
unbind(record, R) = R⁻¹ @ record
```

A record is the sum of bound role-filler pairs:

```
record = R_subject @ f_alice
       + R_color   @ f_red
       + R_shape   @ f_circle
```

and unbinding by one role matrix approximately recovers the matching
filler (cross-terms decorrelate into noise when the role matrices
and/or the fillers are close to orthogonal in the relevant sense).

## Extended state vector

Before describing the binding kinds, the state they act on:

Sutra program state is a **single extended vector** with two
structurally-separated subspaces:

```
state = [ semantic_dims | synthetic_dims ]
```

- **Semantic subspace** — the real embedding dimensions of the
  chosen frozen LLM substrate (e.g. 768-d for nomic-embed-text,
  1024-d for GTE-large). Carries meaning. Operated on by
  *semantic binding* (learned matrices).
- **Synthetic subspace** — a small number of additional dimensions
  appended by the compiler. Carries computational/symbolic state
  (variable slots, array positions, truth, other data-type axes).
  Operated on by *rotation binding* with axes allocated at compile
  time.

The two subspaces are **structurally orthogonal**: operations in
one cannot contaminate the other. This is what makes the kinds of
binding cleanly separable — a rotation on the synthetic subspace
cannot smear semantic content, and a learned-matrix bind on the
semantic subspace cannot touch computational state.

Sutra stays functional. An assignment `x = v` is a pure transform
of the extended state vector; no named memory cells, no mutation.

See `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`
for the full design and the capacity/reversibility/truth-axis
experiments that validate it.

## Kinds of binding

Sutra has two binding kinds, each acting in its own subspace:

1. **Semantic binding** (learned matrices) — acts in the semantic
   subspace. `R` is fit from `(input, output)` embedding pairs;
   roles carry meaning. This is the Sutra-distinctive innovation.
2. **Rotation binding** — acts in the synthetic subspace. `R^i`
   for a fixed base rotation and an integer index `i` allocated to
   a variable, array position, or other computational slot. Roles
   are handles / positions / ordinals, not meanings. This is the
   structural-storage kind.

Surface syntax must make the choice visible at role-declaration
time; see `planning/open-questions/binding-kind-surface-syntax.md`
(pending re-evaluation under the two-kinds-as-of-2026-04-21 model).

The family is open. Other kinds (sparse-code bindings, attention-
style, hybrid) may be added as Sutra matures; the commitment of
the language is that binding is a *family of operations
distinguished by kind*, not a single operation.

### Semantic binding (learned matrices)

`R` is **learned from corpus data** and corresponds to a real
semantic relation. Use this kind when the role *means something* —
when the bind expresses a logical or relational claim about the
filler in the substrate.

These are the Sutra-distinctive bindings. The whole innovation
story of the language — displacement → consolidation → full role
matrix — runs on this kind.

Examples:

- `R_object_of_sentence` — fit on `(sentence_emb, object_emb)`
  pairs. Applied to a sentence embedding, it produces something
  close to the sentence's object word as a vector; inverted, it
  extracts the object from a sentence-shaped bundle.
- `R_capital_of` — fit on `(country_emb, city_emb)` pairs. Applied
  to a country vector it gives that country's capital.
- `R_is_cat` — fit on `(thing_emb, is_that_cat_label)` pairs. The
  equality-test matrix from `equality-and-defuzzification.md` is
  a semantic binding operator.

How the matrices are fit is substrate-dependent. Least-squares
regression on paired embeddings is the obvious starting point;
low-rank constraints, Procrustes-style orthogonality, or ridge
regularization may be needed depending on the substrate's
data/dimension ratio and noise structure. The fitting procedure
is compile-time (the empirical-initiation phase), not runtime.

A **displacement vector** is the rank-0 (translation-only) special
case of a learned role matrix: `R @ v = v + d` for a fixed `d`.
The cartography work (Leonhart, *Latent space cartography applied
to Wikidata* — published in the sibling `latent-space-cartography`
repo) showed that predicates across frozen LLM embedding spaces
can be realized as consistent displacement vectors, with a
measurable consistency / prediction-accuracy correlation across
multiple embedding models. *(Specific numerical results —
predicate counts, correlation values — should be cited from the
cartography source itself rather than quoted from memory; see
CLAUDE.md note on prior-work claims.)* That work shows the
simplest form of learned role lives in LLM embedding spaces.
Whether the full-matrix generalization is equally clean for every
role is the open empirical question — see
`planning/findings/2026-04-15-nomic-object-matrix-identity-wins.md`
for the first attempt and its (confounded, data-starved) null
result.

### Rotation binding

**Status: empirically validated and runtime-supported as of
2026-04-24.** Earlier drafts of this section described the 2D-
Givens-per-slot design as a target with experimental validation
pending. The validation landed:

- `experiments/synthetic_subspace_validation.py` +
  `planning/findings/2026-04-24-synthetic-subspace-validation.md`
  — five tests passed end-to-end. Zero cross-talk at N/2 slots,
  capacity curve characterized past overlap, truth-axis
  orthogonality under semantic ops, 100-op reversibility at FP
  roundoff, fuzzy composition clean.
- `experiments/slot_rotation_reversibility.py` +
  `planning/findings/2026-04-24-slot-rotation-runtime.md` — the
  2D-Givens-per-slot design landed as runtime primitives
  `slot_store` / `slot_load` / `rotate_slot` on `_VSA`
  (`codegen.py`). 48 independent slots, exact reassignment,
  9e-16 rotation roundtrip, zero semantic-block drift.

The remaining `.su`-surface-syntax work — how a Sutra program
declares a slot-bound variable in source — is tracked separately
in queue.md "Sutra-language surface syntax for slot primitives"
and is independent of the spec design here.

`R` is a **rotation in the synthetic subspace**. Each variable /
array position / computational slot gets a dedicated 2D rotation
plane in the synthetic subspace. Applying the role rotates the
filler into the slot; applying the inverse rotates it out.

Concretely: the synthetic subspace of dimension `N` is partitioned
into `N/2` orthogonal 2D planes. Each plane is allocated to one
slot (one variable, one array position, or other designated role).
A rotation binding into slot `i` is the 2D Givens rotation acting
on plane `i`. Because each plane is its own 2D subspace orthogonal
to every other plane, **cross-talk between slots is zero by
construction** — retrieval from slot i cannot leak content from
slot j regardless of what was stored.

Use cases rotation binding covers:

- **Opaque variable storage.** Assign a value under a name,
  retrieve it later. The classical "bag of variables" pattern.
- **Array / sequence positions.** Store item at position i as
  `R^i` applied within the slot, or as a distinct position-i
  rotation plane. Iteration over positions is repeated rotation.
- **Reversible imperative state.** A sequence of assignments is
  a sequence of rotations on the synthetic subspace. Every
  rotation has an inverse; the whole program is reversible by
  construction.
- **Variable assignment as a pure transform.** `x = v` is a
  function from state to state that replaces the content at x's
  slot with v. Sutra stays functional; no mutation.

Cost is O(d) per rotation bind when implemented as structured 2D
rotations (one Givens plane per op), matching sign-flip's O(d)
cost without sign-flip's statistical cross-talk or lack of
ordinal structure.

**"Learned" does not apply here.** Rotation-binding axes in the
synthetic subspace are **designated by the compiler at compile
time**, not fit from data. The synthetic subspace is constructed
for this purpose; its axes are an allocation decision, not an
empirical one. The compiler reserves `N/2` planes from a fixed
budget of `N` synthetic dimensions and assigns each slot
deterministically.

### Sign-flip is retired

Earlier versions of this spec treated sign-flip binding
(`filler * sign(role)`, a diagonal ±1 matrix) as a first-class
structural binding kind. As of 2026-04-21 sign-flip is retired in
favor of rotation binding in a synthetic subspace. The rotation
alternative strictly dominates sign-flip for Sutra's use cases:

| Property | Sign-flip | Rotation (in synthetic subspace) |
|---|---|---|
| Opaque storage | ✓ | ✓ |
| Ordered / sequential | ✗ | ✓ |
| Cross-talk | 1/√d statistical | Zero by construction |
| Reversibility | Self-inverse | Inverse = R^-i |
| Cost per op | O(d) | O(d) with structured rotation |
| Cleanness for imperative state | Awkward | Natural |

Sign-flip's one unique property — element-wise commutativity of
bind — has no load-bearing customer in Sutra. Semantic-bind
composition is handled by learned matrices where non-commutativity
is a *feature* (`color-of-shape` ≠ `shape-of-color`); structural
storage doesn't need commutative bind because bundle is already
commutative.

Sign-flip is retired from the codegen as of 2026-04-22 (commit
history). `codegen.py` and `codegen_pytorch.py` both compile `bind`
to role-seeded Haar-random orthogonal rotation. The retirement is
also recorded as pinned semantic correction #6 in queue.md so it
doesn't get reintroduced.

### Why the distinction matters

Sutra's contribution relative to classical VSA is the **existence
of semantic binding**. HRR/MAP/BSC/HDC uses only non-semantic
(random) roles by design — their composition properties depend on
random near-orthogonality. Sutra adds a whole new binding kind
whose role matrices carry real semantic structure, fitted from
the substrate. See `vision.md` for that framing.

The two kinds are **different tools for different jobs**:

- **Logical / relational operations** → semantic (learned-matrix)
  bind. If you're expressing "X is the object of sentence S" or
  "Y is located in country Z," the role should mean something, and
  a learned matrix is what makes that work.
- **Opaque variable storage and computational state** → rotation
  bind in the synthetic subspace. If you're storing a value under
  a handle, indexing an array position, or expressing imperative-
  style assignment, rotation gives you reversible, structurally-
  decorrelated state changes without contaminating semantic
  content.

Programs choose the binding kind explicitly at role declaration.
The compiler does not try to guess from context: a rotation-bound
variable and a semantically-bound role are different declarations
with different source-level markers. The exact surface syntax is
an open question — see
`planning/open-questions/binding-kind-surface-syntax.md`.

## Surface syntax

The binding kind is chosen at **declaration time**, with two
distinct declaration keywords — one for each kind:

```
// Semantic binding — role matrix fit from corpus data
role capital_of    = learned_from("cities_and_countries.tsv");
role object_of     = learned_from("sentence_object_pairs.tsv");
role is_cat        = learned_from("thing_is_cat_labels.tsv");

// Rotation binding — opaque variable storage in the synthetic subspace
var x         : vector;                    // unassigned (zero state)
var name      : vector = embed("Alice");   // initialized
var flag      : fuzzy  = +0.7;             // fuzzy scalar on the truth axis
var[16] slots : vector;                    // array of 16 rotation slots
```

**Why two keywords.** `role` and `var` do different jobs, and the
source-level distinction reflects that directly:

- **`role`** declares a semantic-subspace binding operator. The RHS
  produces a learned matrix (typically via `learned_from(...)` with
  training data). Roles carry meaning; they're the Sutra-distinctive
  innovation. `role` is reserved for this usage.
- **`var`** declares a rotation-bound slot in the synthetic subspace.
  The compiler allocates a 2D Givens rotation plane to the slot. A
  `var` is the familiar variable from imperative languages — you can
  read from it, assign to it, and the assignment is a pure rotation
  on the state vector (Sutra stays functional). `var[N]` allocates
  an array of N slots.

Compiler semantics:

- A `role R = learned_from(data);` declaration triggers the
  **empirical-initiation phase**: the compiler reads `data`, fits
  the matrix, and stores it. The matrix is fixed at runtime.
- A `var x : T` declaration **allocates** a 2D rotation plane in
  the synthetic subspace. If the synthetic subspace budget is
  exceeded, the compiler errors.
- A `var x = expr;` initialized declaration evaluates `expr`,
  projects into the synthetic subspace, and stores at `x`'s slot.
- Reading `x` applies `R^{-i_x}` to the state and extracts the
  stored content (or projects onto the truth axis for fuzzy/bool
  types).
- The canonical axes (truth, and any future canonical axes for
  other data types) are **language-level constants, not user
  declarations**. They don't need their own keyword; they just
  exist as part of the synthetic subspace layout.

Usage at bind sites stays uniform — a single `bind(X, filler)`
call compiles to the right operation based on how `X` was declared:

```
bind(capital_of, paris)   // learned matrix @ paris_emb (semantic subspace)
bind(x, v)                // rotation into x's slot (synthetic subspace)
```

The compiler checks the kind from the declaration and emits the
correct primitive. Mixing a `role` into a call site where a `var`
is expected (or vice versa) is a compile-time type error.

See `planning/open-questions/binding-kind-surface-syntax.md` for
the history of this decision — five candidates were considered and
Candidate B (`role` / `var`) was chosen on 2026-04-21 for
pedagogical clarity (`var` reads the same in every imperative
language; `role` is the one new term readers need to learn).

## Unbinding

For a semantic role matrix `R` learned by regression, `R⁻¹` may
not be clean — the matrix can be rank-deficient, ill-conditioned,
or very non-orthogonal. The substrate's structure constrains which
is acceptable. Candidate handlings:

- **Orthogonal roles.** Fit under an orthogonality constraint
  (Procrustes regression); then `R⁻¹ = R^T`.
- **Low-rank roles.** Fit as `R = U V^T` with `U, V ∈ ℝ^(d×k)`
  and `k ≪ d`; pseudo-inverse via SVD.
- **Arbitrary roles.** `R⁻¹ = pinv(R)` at compile time; the
  runtime just applies the precomputed inverse.

For rotation bindings, the inverse is definitional: `R^i`'s
inverse is `R^-i`, which is `R^T^i` for orthogonal `R`. The
structured 2D-Givens-per-slot implementation makes both directions
O(d) per op.

## `bundle`

`bundle` is how records are composed:

```
bundle(v1, v2, ...) = v1 + v2 + ...
```

A record is `bundle(bind(f1, R1), bind(f2, R2), ...)`. The exact
semantics (straight sum, weighted sum, sum-then-normalize,
substrate-specific superposition) remain an open question — see
`operations.md` open-questions section.

## `similarity`

Similarity falls out of the vector space; see `operations.md`.
Cosine, dot, and normalized dot are the candidates; Sutra's
preferred default is not yet fixed.

## Open questions specific to binding

- **Surface syntax for binding-kind choice.** How does a `.su`
  program distinguish a rotation-bound variable from a semantic
  role at declaration? See
  `planning/open-questions/binding-kind-surface-syntax.md`.
  Re-evaluation pending under the new two-kinds model.
- **Synthetic-subspace budget.** How many synthetic dimensions
  does a program get? Fixed at language level, set per-program,
  or grown dynamically by the compiler? See the 2026-04-21 design
  note for the open question.
- **Canonical-axis inventory.** Truth is committed as a canonical
  axis in the synthetic subspace. What other canonical axes does
  the language want to designate from the start (integer, enum,
  position, time)? Open — and it's an opening for native support
  of other data types through VSA.
- Which fitting procedure for semantic role matrices? Lstsq is
  the default; ridge, Procrustes, and low-rank alternatives are
  likely needed depending on substrate data/dimension ratios.
- Do learned matrices need to be orthogonal for clean unbinding?
  Substrate-dependent.
- Are there roles that are genuinely non-linear (and so cannot
  be captured as a matrix)? The spec currently assumes linearity;
  some roles may require quadratic or attention-style operations.
- **Rotation binding on alternative substrates.** The synthetic
  subspace is easy to append to a tensor in the PyTorch backend.
  On any alternative substrate where "appending dimensions" is
  not as free (the retired fly-brain LIF substrate, or any future
  neuromorphic target with a fixed-size population), a corresponding
  synthetic-population design would have to be worked out. Out of
  scope while the canonical target is the PyTorch tensor backend.
