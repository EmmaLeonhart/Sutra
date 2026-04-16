# Primitive operations

The primitive vector operations used across the `.su` examples and
accepted by the compiler are:

- **`bind`** — apply a role to a filler, producing a tagged vector.
- **`unbind`** — invert `bind` given the role.
- **`bundle`** — superpose multiple vectors into a single vector.
- **`similarity`** — score how close two vectors are.
- **`embed`** — map a string literal to a vector via the substrate's
  embedding function.
- **`argmax_cosine`** — given a vector and a codebook of vectors,
  return the codebook entry whose cosine similarity is highest.
  This is the numpy-backend form of "clean up to the nearest known
  prototype."

## Roles are matrices; `bind` is matrix-vector multiplication

A **role** in Sutra is a matrix, not a vector. Binding a filler to a
role is the matrix acting on the filler:

```
bind(filler, R) = R @ filler
unbind(record, R) = R⁻¹ @ record
```

A record built from multiple role-filler pairs is the sum of the
bound results, and unbinding extracts one filler approximately:

```
record = R_name @ f_alice + R_color @ f_red + R_shape @ f_circle
R_name⁻¹ @ record
   = f_alice + (R_name⁻¹ R_color) @ f_red + (R_name⁻¹ R_shape) @ f_circle
  ≈ f_alice   (if the cross-terms decorrelate into noise)
```

This framing is consistent with the rest of the spec. Equality is
already specified as a matrix operation (`is_cat @ x` in
`equality-and-defuzzification.md`); defuzzification is already
specified as a matrix operation (`types.md`). Roles being matrices
means a large fraction of Sutra's first-class objects are matrices
in the same sense — a uniform design rather than three different
algebras glued together.

### Roles are learned from the substrate, not random

The VSA literature treats roles as random vectors (HRR uses random
Gaussians; MAP uses random binary/ternary; classic circular-
convolution bind is the circulant matrix of such a random vector).
**Sutra does not.** A role matrix is **learned** from the embedding
substrate. "Object of a sentence" is the matrix you get by fitting
a linear map on `(sentence_embedding, object_embedding)` pairs;
"capital of" is the matrix you get by fitting on
`(city_embedding, country_embedding)` pairs; `is_cat` is the
matrix you get by fitting on `(thing_embedding, is_that_cat_label)`
pairs.

This is a meaningful departure from VSA tradition:

- HRR: roles are random; bind is circular convolution over vectors.
  Roles are semantically empty.
- MAP / sparse VSA: roles are random binary/ternary patterns.
  Again semantically empty.
- **Sutra:** roles are matrices fit to the corpus. Each role
  matrix carries real semantic content.

### Empirical grounding and honest gap

Two prior papers are load-bearing here and **must not be conflated**.
Naming is treacherous; the user's terminology:

- **"VSA paper" = "latent space cartography paper"** — published
  elsewhere (`EmmaLeonhart/latent-space-cartography`), clawRxiv
  post 1127. Found 86 predicates as consistent **displacement
  vectors** across three embedding models, r = 0.861 between
  geometric consistency and held-out prediction accuracy. A
  displacement is the rank-0 (translation-only) special case of
  a role matrix. This paper establishes that the **simplest** form
  of learned role lives in LLM embedding spaces with measurable
  consistency. It also identified the mxbai diacritic defect.

- **"sutra paper" = "embedding paper"** — `sutra-paper/` in this
  repo. Tested sign-flip binding vs alternatives on GTE-large,
  BGE-large, Jina-v2, and mxbai. Roles here were **random
  vectors**, not learned. Sign-flip achieved 3–5× capacity vs
  Hadamard. This paper builds on the cartography result but does
  **not** extend it to full learned matrices; it uses the spaces
  as generic VSA substrates.

**What neither paper proves:** that the full-matrix generalization
— sentence-level semantic roles like "object of a sentence" —
admits clean, consistent learned matrices in any given embedding
space. That is a plausible extrapolation from cartography's
rank-0 result, not a settled finding. See
`planning/findings/2026-04-15-nomic-object-matrix-identity-wins.md`
for the first attempt and its (confounded, data-starved) null
result.

**Substrate coverage gap:** the current demo path runs on
**nomic-embed-text**, which appears in neither paper. mxbai is
known-broken (diacritic attention sink); GTE / BGE / Jina-v2 passed
the paper's validation gates; nomic's status is unknown. Before
interpreting a failure on nomic (e.g. `examples/sequence.su` scoring
`sim(fox, dog) = 0.939`) as a failure of the Sutra operation, the
substrate itself should be validated — otherwise we are attributing
a substrate defect to the language.

### What `bind` is *not*

- **Not sign-flip.** `a * sign(role)` is the current implementation
  in `codegen_numpy` and `codegen_flybrain`, and it is explicitly
  rejected (2026-04-15). It does not match the matrix-for-a-role
  framing — a sign vector is a diagonal ±1 matrix, the degenerate
  form. And it fails empirically: `examples/sequence.su` scores
  `sim(fox, dog) = 0.939` on nomic when disjoint sequences should
  score below 0.5.
- **Not circular convolution unless the role is learned as a
  circulant.** HRR is the special case "role matrix is the
  circulant of a random vector." Sutra does not restrict to
  circulants, and does not use random roles.

## Similarity

Similarity is "something we just kind of get" — it falls out of the
vector space rather than being a specially-designed operation. Three
concrete candidates exist:

1. **Dot product** — raw.
2. **Cosine similarity** — normalized.
3. **Normalized dot product** — different from cosine in detail.

The user's position: **cosine similarity is overused**, and
**normalized dot product might be the one Sutra should prefer**. Not
settled. The tradeoffs depend on what the substrate gives you
cheaply and what the rest of the language ends up needing.

## `embed` and the substrate

`embed("string")` is the bridge from source literals to vectors. On
the numpy backend this calls the frozen LLM (nomic-embed-text, 768
dims, mean-centered) at runtime. Different substrates implement
`embed` differently — a fly-brain substrate maps a string to a KC
pattern via the mushroom body, for example. `embed` is therefore a
Sutra operation whose semantics depend on the substrate, but whose
*role* in a program (string-literal → vector) is fixed.

## `argmax_cosine` vs `snap`

Earlier spec drafts listed `snap` as a primitive. `snap` is not
called anywhere in `examples/*.su`; the demo-path operation for
"clean up to the nearest known prototype" is `argmax_cosine(vec,
codebook)`. `snap` remains meaningful as a name for the same
conceptual operation on a substrate that has a real cleanup circuit
(e.g. a Hopfield-like attractor), but the numpy demo substrate does
not have one, so the callable primitive surfaced to Sutra programs
on that backend is `argmax_cosine`.

Whether the language should expose a single name (`snap`) that
lowers to `argmax_cosine` on numpy and to the real cleanup circuit
on a connectome substrate, or whether the two should stay as
distinct names, is an open question.

## `select` is not a primitive vector operation

`select` is the conditional-branching mechanism, which is a different
kind of thing from bind/bundle/unbind/similarity. Spec for `select`
lives in `control-flow.md`, not here.

## Open questions

- Which similarity operation does Sutra adopt as its default? Dot,
  cosine, normalized dot, or something else? Is it substrate-
  dependent (e.g. whichever the backend can give cheaply)?
- How are role matrices actually fit at compile time? Least-squares
  regression on `(input_emb, target_emb)` pairs is the obvious
  starting point, but the substrate may constrain this (rank, PSD,
  orthogonality). Tracked as a follow-up to the matrix-framing
  position above.
- Do role matrices need to be orthogonal (so `R⁻¹ = Rᵀ` is cheap
  and the inverse is well-conditioned), or is arbitrary-matrix
  tolerated as long as the fit is stable? Probably substrate-
  dependent.
- Do "clean" learned role matrices exist for sentence-level roles
  (object, subject, agent) in nomic-embed-text? Open empirical
  question — to be answered by a finding in `planning/findings/`
  before the spec hardens.
- What does `bundle` compute exactly? Elementwise sum is the
  operational default; whether it should be a weighted sum, a
  sum-then-normalize, or a substrate-specific superposition is
  still open.
- Are there other primitive operations that deserve first-class
  status (e.g. rotation, projection, scalar multiplication)?
- Should `snap` and `argmax_cosine` unify under a single name that
  lowers differently per substrate, or stay distinct?
