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

The empirical ground for this inversion is the latent-space
cartography work (Leonhart, *Latent space cartography applied to
Wikidata* — published in the sibling `latent-space-cartography`
repo), which showed that predicates across frozen LLM embedding
spaces can be realized as **consistent displacement vectors**, with
a measurable geometric-consistency / held-out-prediction-accuracy
correlation across multiple embedding models. *(Specific numerical
results — predicate counts, correlation values — should be cited
from the cartography source itself rather than quoted from memory;
see CLAUDE.md note on prior-work claims.)* A displacement is the
rank-0 (translation-only) special case of a learned role matrix.
That work shows the simplest form of learned role lives in LLM
embedding spaces. Sutra generalizes: if rank-0 role matrices are
real and consistent, the full-rank case is the natural extension,
and a programming language that treats them as first-class
primitives is what falls out.

## The three-step research arc

The Sutra research program has three phases, each building on the
previous:

1. **Isolate regular displacements** in frozen LLM embedding spaces.
   This is the cartography work, already published in the sibling
   `latent-space-cartography` repo. Step 1 is settled. (For the
   specific numbers — how many predicates, which embedding models,
   what correlation — verify against that repo directly per the
   CLAUDE.md instruction on prior-work claims.)
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

## Binding is a family, with (at least) two populated kinds

Every `bind` operation in Sutra is matrix-vector multiplication:
`bind(filler, R) = R @ filler`. The matrix `R` comes in multiple
kinds — two are currently populated, and the family is open to more.
Sutra programs pick the kind that fits the job:

- **Semantic binding** — `R` is *learned* from corpus data and
  corresponds to a real semantic relation. Inverting it recovers a
  meaningful decomposition. These are the role matrices above:
  "object of," "capital of," `is_cat`, verb-role, subject-role, etc.
  Use this kind when the role *means something* — when the bind is
  expressing a logical or relational claim. This is the innovation
  Sutra is built around; the three-step research arc runs on it.
- **Structural binding** — `R` carries no semantic content. The
  role is a handle, not a meaning. Use this kind for **opaque
  variable storage** — stashing a filler under a label and
  retrieving it exactly later, where the role↔filler relationship
  is not supposed to mean anything. Sign-flip binding
  (`filler * sign(role)`, a diagonal ±1 matrix) is the canonical
  instance; classical VSA random roles, random orthogonal
  rotations, and permutations also live here. Sign-flip is cheap,
  exactly self-inverse, and commutative-friendly — which is why
  it's the right default for the storage-and-retrieval case. A
  learned-matrix bind would be the wrong tool here, smearing the
  stored value through semantic space.

The two kinds do different jobs. Trying to use structural binding
where a logical relation is meant is a type error in program design;
trying to use semantic binding for opaque storage is overkill. The
spec's `binding.md` specifies the kinds in full; `operations.md`
specifies what each operation on each kind computes.

Structural keys should live in empty regions of the substrate's
embedding space — the "undersymbolic realm" documented in
`equality-and-defuzzification.md`. If a structural key collided
with a real content direction, it would contaminate every structure
built with it. So the runtime mints structural markers in directions
no natural embedding occupies (low-eigenvalue PCA directions, or
random directions projected out of the content subspace). For
sign-flip specifically, the key is a ±1 pattern and the
undersymbolic concern shows up as "the sign pattern should not
correlate with any semantic content direction." This keeps the two
kinds cleanly separated.

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
- **Not a rejection of sign-flip binding.** Sign-flip is the
  canonical structural binding — a diagonal ±1 matrix — and it's
  positively good for the job it's for (opaque variable storage,
  exact retrieval by handle). It is not a placeholder or tolerated
  infrastructure; it is a first-class binding kind. What Sutra
  rejects is *using sign-flip where a logical/semantic relation is
  meant*, because then the bind silently strips the meaning from
  the role.

## Why this matters for the papers

- `sutra-paper/` should be reorganized around the three-step arc.
  Headline: learned matrices in frozen embedding spaces. Structural
  binding (sign-flip and friends) is a second, non-headline kind
  with its own legitimate uses (opaque variable storage); mention
  it, but don't make it the contribution.
- `fly-brain-paper/` is on target. It demonstrates that a compiled
  Sutra program — a four-way conditional — executes on a whole-brain
  LIF model wired from the FlyWire connectome, with no host-side
  `if` running at decision time. That paper is about the language's
  ability to compile to a biological substrate.
- The spec files in this directory should describe the two kinds of
  binding explicitly, describe objects as learned-matrix records,
  and describe the research program as the three-step arc above.
