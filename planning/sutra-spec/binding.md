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

## Two kinds of binding

The role matrix `R` comes in two kinds. Programs use both.

### Semantic binding (learned matrices)

`R` is **learned from corpus data** and corresponds to a real semantic
relation. These are the Sutra-distinctive bindings — the whole point
of the language is that programs operate with them.

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

### Non-semantic binding (arbitrary matrices)

`R` is **arbitrary** and carries no semantic content. Used where you
just need a key that decorrelates — structural markers, positions in
a sequence, identity sentinels, bundling slots that don't correspond
to any real relation.

Classical VSA's random roles are non-semantic bindings in this sense.
Sign-flip binding (`a * sign(role)` = a diagonal ±1 matrix) is a
non-semantic binding. Random orthogonal rotations, random Gaussian
matrices, permutation matrices — all non-semantic.

Non-semantic keys should live in empty regions of the substrate's
embedding space ("the undersymbolic realm," see
`equality-and-defuzzification.md`) so they do not contaminate
semantic structure. If a non-semantic key collided with a real
content direction, every record built with it would pick up noise
in that direction. So the runtime (or empirical-initiation phase)
mints non-semantic keys in directions no natural embedding occupies
— low-eigenvalue PCA directions, random directions with the content
subspace projected out, or explicitly-orthogonalized synthetic
points.

### Why the distinction matters

Conventional VSA (HRR, MAP, BSC, HDC) uses only non-semantic roles,
by design: random vectors were chosen *precisely because* they
carry no semantic content, and all of VSA's composition properties
assume near-orthogonality from random statistics. Sutra inverts
this — the interesting binding is semantic, and non-semantic binding
is just infrastructure. See `vision.md` for the framing.

Practically:

- Default to semantic binding when writing a program. If you're
  binding "the object of this sentence" to a filler, you want the
  learned object-role matrix, not a random role.
- Use non-semantic binding when you need a structural slot that
  carries no meaning of its own (e.g. positions in an unordered
  collection, temporary sentinels, keys in a hash-like lookup).
- The compiler can in principle detect the distinction: named
  semantic roles resolve to learned matrices from a library;
  anonymous or numerically-indexed slots resolve to non-semantic
  matrices minted in the undersymbolic realm.

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

For non-semantic bindings, the inverse is definitional: sign-flip
is self-inverse (`sign(role)` squared is all-ones); permutation
inverts by permuting back; random orthogonal matrices invert via
transpose; random Gaussian matrices invert via matrix inverse
(expensive and noisy).

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

- Which fitting procedure for semantic role matrices? Lstsq is the
  default; ridge, Procrustes, and low-rank alternatives are likely
  needed depending on substrate data/dimension ratios.
- Do learned matrices need to be orthogonal for clean unbinding?
  Substrate-dependent.
- Which empirical-space directions qualify as "undersymbolic" for
  non-semantic key placement? Low-eigenvalue PCA is the default;
  whether other constructions are better is open.
- Are there roles that are genuinely non-linear (and so cannot be
  captured as a matrix)? The spec currently assumes linearity; some
  roles may require quadratic or attention-style operations.
