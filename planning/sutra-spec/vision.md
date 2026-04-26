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

## Binding has two kinds, acting on different subspaces of the state

Program state in Sutra is a **single extended vector** with two
structurally-separated subspaces:

```
state = [ semantic_dims | synthetic_dims ]
```

The **semantic subspace** is the real embedding dimensions of the
chosen frozen-LLM substrate (768 for nomic, 1024 for GTE-large,
etc.). It carries meaning. The **synthetic subspace** is a small
number of additional dimensions appended by the compiler; it carries
computational/symbolic state (variable slots, array positions,
truth, other data-type axes).

The two subspaces are **structurally orthogonal** — operations in
one cannot contaminate the other. This is what makes the two
binding kinds cleanly separable:

- **Semantic binding** — `R` is *learned* from corpus data and
  acts in the semantic subspace. Inverting it recovers a meaningful
  decomposition. These are the role matrices from the three-step
  arc: "object of," "capital of," `is_cat`, verb-role, etc. Use
  this kind when the role *means something* — when the bind
  expresses a logical or relational claim. This is the innovation
  Sutra is built around.
- **Rotation binding** — `R^i` acts in the synthetic subspace on
  an allocated 2D rotation plane per variable / array position /
  slot. Roles are handles or ordinals, not meanings. Use this kind
  for opaque variable storage, array indexing, and reversible
  imperative-style assignment. Because each slot gets its own
  orthogonal 2D plane, cross-talk between slots is zero by
  construction (not statistical). Variable assignment `x = v` is
  a pure rotation of the state vector; Sutra stays functional.

Earlier versions of this spec used sign-flip binding
(`filler * sign(role)`, diagonal ±1) as the structural-storage
kind. As of 2026-04-21 sign-flip is retired in favor of rotation
binding in the synthetic subspace: rotation gives zero cross-talk
by construction (vs. sign-flip's 1/√d statistical noise), supports
ordered/sequential structure (sign-flip cannot), and provides
natural reversibility for imperative-style state changes. See
`planning/findings/2026-04-21-extended-state-and-rotation-binding.md`
and `binding.md` for the design detail.

The two kinds do different jobs. Trying to use rotation binding
where a logical relation is meant is a type error in program
design; trying to use semantic binding for variable storage is
overkill and smears the stored value through semantic space. The
spec's `binding.md` specifies the kinds in full; `operations.md`
specifies what each operation on each kind computes.

The synthetic subspace also hosts **canonical axes** — dimensions
designated by the language itself rather than allocated
per-program. Currently committed: a **truth axis** (`true = +1`,
`false = -1`, fuzzy values continuous between). Because the truth
axis is in the synthetic subspace and the semantic subspace is
structurally orthogonal to it, every semantic vector has zero
projection onto the truth axis by construction. Semantic content
is structurally decorrelated from truth — nothing "looks more
true" because of what it means. Other canonical axes (integer,
enum, position, time) are candidates for future data-type support
through VSA. See `equality-and-defuzzification.md` for how truth,
defuzzification, and fuzzy composition work on this axis.

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
- **Not built around sign-flip binding.** Sign-flip
  (`filler * sign(role)`, diagonal ±1 matrix) was an earlier
  structural-storage kind; it has been retired in favor of
  rotation binding in a dedicated synthetic subspace, which
  strictly dominates it (zero cross-talk by construction, ordered
  structure, reversibility, natural fit for imperative-style
  state). Sign-flip remains as a legacy implementation detail in
  `codegen_numpy.py` pending migration; it is not the design
  going forward.

## Why this matters for the papers

- `sutra-paper/` should be reorganized around the three-step arc.
  Headline: learned matrices in frozen embedding spaces. Rotation
  binding in a synthetic subspace is the second (non-headline) kind
  with its own legitimate uses (opaque variable storage, array
  indexing, reversible imperative state); mention it, but don't
  make it the contribution.
- The fly-brain paper (retired research line, 2026-04-26) demonstrated
  that a compiled Sutra program — a four-way conditional — executed
  on a Brian2 spiking simulation of the *Drosophila* mushroom body
  with no host-side `if` running at decision time. The follow-on
  whole-brain LIF substrate work outpaced the language's maturity
  and was retired; the paper itself is preserved on clawRxiv.
- The spec files in this directory should describe the two kinds of
  binding explicitly, describe objects as learned-matrix records,
  and describe the research program as the three-step arc above.
