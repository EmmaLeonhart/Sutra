# The vision of Sutra

Sutra is not a variant of Vector Symbolic Architecture. **It inverts
VSA's foundational assumption.**

Conventional VSA (HRR, MAP, BSC, HDC and descendants) treats the
"roles" in role-filler binding as **random** — vectors or matrices
drawn from a controlled distribution specifically chosen so they
carry no semantic content. The whole point of the classical VSA
program is that composition emerges from statistics: near-orthogonal
random hypervectors, with algebra designed around their statistical
properties. Semantics live in the fillers; the roles are scaffolding.

Sutra reverses this. **The role matrices are learned from the
embedding substrate and carry real semantic content.** "Object of a
sentence" is a matrix you fit on `(sentence_embedding, object_embedding)`
pairs from a corpus; it is not random. "Capital of" is a matrix fit
on `(country_embedding, city_embedding)` pairs. `is_cat` is a matrix
fit on `(thing_embedding, is_that_cat_label)` pairs. These matrices
are the semantic core of the language — the thing programs operate
with.

The empirical ground for this inversion is the latent-space cartography
result (Leonhart, *Latent space cartography applied to Wikidata*):
86 predicates across three frozen LLM embedding spaces realized as
**consistent displacement vectors**, with r = 0.861 between
geometric consistency and held-out prediction accuracy. A displacement
is the rank-0 (translation-only) special case of a learned role
matrix. That paper shows the simplest form of learned role lives in
LLM embedding spaces with measurable consistency across models.
Sutra generalizes: if rank-0 role matrices are real and consistent,
the full-rank case is the natural extension, and a programming
language that treats them as first-class primitives is what falls
out.

## The three-step research arc

The Sutra research program has three phases, each building on the
previous:

1. **Isolate regular displacements** in frozen LLM embedding spaces.
   This is the cartography paper, already published — 86 predicates,
   r=0.861 across GTE / BGE / Jina-v2. Step 1 is settled.
2. **Convert these into regular/canonical displacements** —
   consolidate the dirty empirical findings into clean primitive
   forms. Which displacements are fundamental, which are composites,
   which are noise, which correspond to known linguistic roles.
3. **Find the common learned matrices** underlying the displacements —
   generalize from rank-0 (translation-only) to full-matrix operators.
   Not every relation is a translation; some are rotations, some are
   rank-constrained linear maps, some may not be linear at all. Where
   linearity holds, the matrix is the Sutra primitive.

The sutra paper is supposed to be about steps 2 and 3. The language
itself is what you build on top of step 3.

## Binding has two kinds, both matrix-based

Every `bind` operation in Sutra is matrix-vector multiplication:
`bind(filler, R) = R @ filler`. The matrix `R` comes in two kinds,
and Sutra programs use both:

- **Semantic binding** — `R` is *learned* from corpus data and
  corresponds to a real semantic relation. Inverting it recovers a
  meaningful decomposition. These are the role matrices above:
  "object of," "capital of," `is_cat`, verb-role, subject-role, etc.
  This is the primary kind — the thing Sutra exists to work with.
- **Non-semantic binding** — `R` is *arbitrary* and carries no
  semantic content. Used for structural markers, position in a
  sequence, identity sentinels, and other infrastructure where you
  just need a key that decorrelates. Classical VSA random roles
  fall here. Sign-flip binding (`a * sign(role)` as a diagonal ±1
  matrix) falls here. These are valid and useful — just not the
  interesting part of the language.

The distinction is important because it explains what the sign-flip
and Hadamard and permutation work in the literature *is* relative
to Sutra: that work characterizes non-semantic binding. Sutra uses
non-semantic binding where structure is needed and uses semantic
binding everywhere else. The two are not competing; they are filling
different jobs.

Non-semantic markers should live in empty regions of the substrate's
embedding space — the "undersymbolic realm" documented in
`equality-and-defuzzification.md`. If a non-semantic key collided
with a real content direction, it would contaminate every structure
built with it. So the runtime mints non-semantic markers in
directions no natural embedding occupies (low-eigenvalue PCA
directions, or random directions projected out of the content
subspace). This keeps the two kinds cleanly separated.

## Objects track which learned matrices bound their fields

An object in Sutra is a bundled record — a vector built by binding
fillers to role matrices and summing. The semantic content of the
object is carried by the *learned* matrices that bound its fields.

A sentence object, for instance, is built as:

```
sentence = R_subject @ subject_emb
         + R_verb    @ verb_emb
         + R_object  @ object_emb
```

To extract the object word as a plain embedding:

```
residual = sentence - R_subject @ known_subject - R_verb @ known_verb
object_emb ≈ R_object⁻¹ @ residual
```

The object's purpose is to carry enough structure that the compiler
and runtime know which role matrices were used in building it — so
extraction is just structured inversion. This generalizes to nested
objects: a field of an object can itself be an object, and the
inverse chain walks back out.

This is what makes Sutra a *programming language* rather than a
VSA library. The language tracks, at compile time and at runtime,
which learned matrices are in play. Binding and unbinding are
first-class operations with semantic meaning because the matrices
are semantic.

## What this is not

- **Not a refinement of VSA for LLM embedding spaces.** That framing
  traps Sutra in the sign-flip / Hadamard / capacity-curve literature.
  The real contribution is replacing random roles with learned roles.
- **Not a proof of Turing completeness via external memory.** That
  was an artifact of a prior, over-ambitious draft and is not part
  of the core claim.
- **Not a claim that all relations admit clean learned matrices.**
  Step 3 above is the open empirical question. We expect some
  relations to be linear (the displacements are), some to be
  non-linear, some to require rank constraints, and some to be
  partially non-compositional. The spec does not assume every role
  fits cleanly; it treats "does this role admit a clean learned
  matrix?" as an empirical question to be answered substrate by
  substrate.
- **Not a rejection of sign-flip binding.** Sign-flip is a valid
  non-semantic binding — a diagonal ±1 matrix. It lives in the
  structural/scaffolding kind, not the semantic kind. Sutra uses it
  where structure is needed and learned matrices where semantics
  are needed.

## Why this matters for the papers

- `sutra-paper/` should be reorganized around the three-step arc.
  Headline: learned matrices in frozen embedding spaces. Side note:
  standard VSA binding (Hadamard) fails, various workarounds exist,
  sign-flip among them; these are infrastructure for non-semantic
  binding, not the contribution.
- `fly-brain-paper/` is on target. It demonstrates that a compiled
  Sutra program — a four-way conditional — executes on a whole-brain
  LIF model wired from the FlyWire connectome, with no host-side
  `if` running at decision time. That paper is about the language's
  ability to compile to a biological substrate.
- The spec files in this directory should describe the two kinds of
  binding explicitly, describe objects as learned-matrix records,
  and describe the research program as the three-step arc above.
