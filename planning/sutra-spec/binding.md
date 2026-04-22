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

## Kinds of binding

The role matrix `R` comes in multiple kinds. Two are currently
populated — **semantic** (learned-matrix) and **structural**
(sign-flip and its generalizations). They are not interchangeable
and they are not ranked: each is good at a job the other is bad at.
Programs use whichever kind fits the job, and the surface syntax
must make the choice visible at role-declaration time.

The family is open. Other kinds (sparse-code bindings, attention-
style, hybrid) may be added as Sutra matures; the commitment of the
language is that binding is a *family of operations distinguished by
kind*, not a single operation.

### Semantic binding (learned matrices)

`R` is **learned from corpus data** and corresponds to a real
semantic relation. Use this kind when the role *means something* —
when the bind expresses a logical or relational claim about the
filler in the substrate.

These are the Sutra-distinctive bindings. The whole innovation story
of the language — displacement → consolidation → full role matrix —
runs on this kind.

Examples:

- `R_object_of_sentence` — fit on `(sentence_emb, object_emb)` pairs.
  Applied to a sentence embedding, it produces something close to the
  sentence's object word as a vector; inverted, it extracts the
  object from a sentence-shaped bundle.
- `R_capital_of` — fit on `(country_emb, city_emb)` pairs. Applied to
  a country vector it gives that country's capital.
- `R_is_cat` — fit on `(thing_emb, is_that_cat_label)` pairs. The
  equality-test matrix from `equality-and-defuzzification.md` is a
  semantic binding operator.

How the matrices are fit is substrate-dependent. Least-squares
regression on paired embeddings is the obvious starting point;
low-rank constraints, Procrustes-style orthogonality, or ridge
regularization may be needed depending on the substrate's data/
dimension ratio and noise structure. The fitting procedure is
compile-time (the empirical-initiation phase), not runtime.

A **displacement vector** is the rank-0 (translation-only) special
case of a learned role matrix: `R @ v = v + d` for a fixed `d`. The
cartography work (Leonhart, *Latent space cartography applied to
Wikidata*) validated 86 predicates as consistent displacement
vectors across three embedding models (r=0.861 consistency–accuracy
correlation). Displacements are known to live in LLM spaces.
Whether the full-matrix generalization is equally clean for every
role is the open empirical question — see
`planning/findings/2026-04-15-nomic-object-matrix-identity-wins.md`
for the first attempt and its (confounded, data-starved) null
result.

### Structural binding (sign-flip and other non-semantic matrices)

`R` **carries no semantic content**. The role is a handle, not a
meaning. Use this kind for **opaque variable storage**: stashing a
filler under a label and retrieving it exactly later, where the
role↔filler relationship is not supposed to mean anything. This is
what dictionary keys, record fields, stack slots, and named
variables look like when expressed as bind.

The canonical instance is **sign-flip binding**:

```
bind_signflip(filler, role) = filler * sign(role)
```

where `sign(role)` is a ±1 pattern indexed by the role name. A
diagonal ±1 matrix is the degenerate structural case of a role
matrix. Sign-flip is cheap, exactly self-inverse, and
commutative-friendly — which is exactly why it's the right default
for storage-and-retrieval. The job is: "let me get my X back, given
the name I stored it under." Semantic machinery would be noise here.

Other structural bindings exist — random orthogonal rotations,
permutation matrices, random Gaussian matrices, classical VSA's
random HRR roles — but sign-flip is Sutra's preferred structural
binding for most storage cases. HRR-style random roles remain
available where decorrelation of arbitrarily many keys is needed and
the ±1 family is too coarse.

**Sign-flip is not a placeholder for learned-matrix bind.** It is
the right answer when you want a handle, not a meaning. Trying to
use it for logical relations (where the role *should* mean
something) is a type error in program design; trying to use
learned-matrix bind for opaque storage is overkill and less clean.
Pick by use case.

Non-semantic keys should live in empty regions of the substrate's
embedding space ("the undersymbolic realm," see
`equality-and-defuzzification.md`) so they do not contaminate
semantic structure. If a non-semantic key collided with a real
content direction, every record built with it would pick up noise
in that direction. The empirical-initiation phase mints non-semantic
keys in directions no natural embedding occupies — low-eigenvalue
PCA directions, random directions with the content subspace
projected out, or explicitly-orthogonalized synthetic points. For
sign-flip specifically, the keys are ±1 patterns rather than
embedded points, and the undersymbolic-realm concern shows up as
"the sign pattern should not be correlated with any semantic
content direction."

### Why the distinction matters

Sutra's contribution relative to classical VSA is the **existence of
semantic binding**. HRR/MAP/BSC/HDC uses only non-semantic (random)
roles by design — their composition properties depend on random
near-orthogonality. Sutra adds a whole new binding kind whose role
matrices carry real semantic structure, fitted from the substrate.
See `vision.md` for that framing.

But adding the semantic kind does not retire the structural kind.
They are **different tools for different jobs**:

- **Logical / relational operations** → semantic (learned-matrix)
  bind. If you're expressing "X is the object of sentence S" or "Y
  is located in country Z," the role should mean something, and a
  learned matrix is what makes that work.
- **Opaque variable storage** → structural (sign-flip) bind. If
  you're storing a value under a handle and only need exact
  retrieval later — the "give me my X back" use case — sign-flip
  is the sharper tool. You don't want a learned matrix smearing the
  value through semantic space.

Programs choose the binding kind explicitly at role declaration.
The compiler does not try to guess from context: a sign-flip role
and a learned-matrix role are different declarations with different
source-level markers. The exact surface syntax is an open question
(see `planning/open-questions/` when the doc exists) but the
commitment is that **the choice is visible to the programmer**.

## Unbinding

For a semantic role matrix `R` learned by regression, `R⁻¹` may not
be clean — the matrix can be rank-deficient, ill-conditioned, or
very non-orthogonal. The substrate's structure constrains which is
acceptable. Candidate handlings:

- **Orthogonal roles.** Fit under an orthogonality constraint
  (Procrustes regression); then `R⁻¹ = R^T`.
- **Low-rank roles.** Fit as `R = U V^T` with `U, V ∈ ℝ^(d×k)` and
  `k ≪ d`; pseudo-inverse via SVD.
- **Arbitrary roles.** `R⁻¹ = pinv(R)` at compile time; the runtime
  just applies the precomputed inverse.

For structural bindings, the inverse is definitional: sign-flip is
self-inverse (`sign(role)` squared is all-ones), which is one of
the reasons it's the preferred default for opaque storage —
retrieval is a rebind with the same role. Permutation inverts by
permuting back; random orthogonal matrices invert via transpose;
random Gaussian matrices invert via matrix inverse (expensive and
noisy).

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
Cosine, dot, and normalized dot are the candidates; Sutra's preferred
default is not yet fixed.

## Open questions specific to binding

- **Surface syntax for binding-kind choice.** How does a `.su`
  program distinguish a sign-flip role from a learned-matrix role
  at declaration? Candidates: explicit keyword (`role foo semantic`
  vs. `role foo structural`), inferred from presence/absence of
  training-data declaration, type-annotation style. Must be visible
  and obvious to the programmer. Open.
- Which fitting procedure for semantic role matrices? Lstsq is the
  default; ridge, Procrustes, and low-rank alternatives are likely
  needed depending on substrate data/dimension ratios.
- Do learned matrices need to be orthogonal for clean unbinding?
  Substrate-dependent.
- Which empirical-space directions qualify as "undersymbolic" for
  structural key placement? Low-eigenvalue PCA is the default;
  whether other constructions are better is open.
- Are there roles that are genuinely non-linear (and so cannot be
  captured as a matrix)? The spec currently assumes linearity; some
  roles may require quadratic or attention-style operations.
- Are there other binding kinds worth populating beyond semantic
  and structural? Sparse-code bindings, attention-style bindings,
  hybrid kinds — the family is declared open, but no concrete third
  kind is specified yet.
