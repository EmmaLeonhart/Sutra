# Extended state vector + rotation binding + canonical axes

**Date:** 2026-04-21.
**Status:** Design decision, not yet implemented or empirically validated. Captures the user's framing from the 2026-04-21 `/remote-control sutra` session. Needs a capacity experiment before it is committed to the spec.

## Summary

Sutra's program state is reframed as a **single extended vector**
with two structurally-separated subspaces:

```
state = [ semantic_dims | synthetic_dims ]
```

- **Semantic subspace** — the real embedding dimensions of the
  chosen frozen LLM substrate (e.g. 768-d for nomic-embed-text,
  1024-d for GTE-large). Carries meaning. Operated on by learned-
  matrix bind (semantic role matrices fit from corpus data).
- **Synthetic subspace** — a small number of additional dimensions
  appended by the compiler. Carries computational/symbolic state.
  Operated on by rotation bind using axes allocated at compile time.

The two subspaces are structurally orthogonal: operations in one
cannot contaminate the other. Sutra stays functional throughout —
a variable assignment is a pure transform of the extended state
vector, not a mutation of named memory.

The model retires sign-flip binding as the structural-storage kind.
Rotation binding in the synthetic subspace subsumes sign-flip's use
cases while giving strictly better properties (zero cross-talk by
construction, ordinal structure for sequences, reversibility).

## Why this framing

The previous framing had two binding kinds — semantic (learned
matrix) and structural (sign-flip) — both living in the real
embedding subspace. That had three problems:

1. **Cross-talk between semantic and structural.** A sign-flip
   key in the embedding subspace has some nonzero projection onto
   every semantic direction, and every bundle built with it picks
   up statistical noise in those directions. Cross-talk scales as
   1/√d — small, but present, and structural.
2. **No natural home for truth / bool values.** Truth has to be
   either a learned direction (which correlates with semantic
   content) or a random direction (which has the same cross-talk
   problem). Neither is clean.
3. **No mechanism for ordered / positional binding.** Sign-flip
   keys are unordered; there's no way to say "position i" or
   "next slot" or iterate through array positions.

Appending a synthetic subspace and switching to rotation binding
there solves all three:

1. Rotation axes can be allocated to truly orthogonal subspaces
   (e.g. a separate 2D rotation plane per variable) so cross-talk
   is zero by construction rather than statistical.
2. Truth can be a designated canonical axis in the synthetic
   subspace, orthogonal to semantic content by construction.
3. Rotation is intrinsically ordered — `R^i` indexes positions in
   a sequence, supports iteration, supports "next slot" and slice
   queries.

## The two binding kinds in the new model

### Semantic binding (unchanged)

`bind(filler, R) = R @ filler` where `R` is a matrix learned from
`(input, output)` embedding pairs. Acts in the semantic subspace.
Roles carry meaning. This is the Sutra-distinctive innovation; the
three-step research arc runs on this kind.

See `planning/sutra-spec/binding.md` §"Semantic binding" for the
fitting procedure and examples.

### Rotation binding (new, replaces sign-flip)

Role is `R^i` for a fixed base rotation R and an integer index `i`.
Each variable / array slot / positional role gets an allocated
rotation axis in the synthetic subspace. Applying the role rotates
the filler into the slot; applying the inverse rotates it out.

The concrete implementation is **one 2D Givens rotation plane per
slot**, which keeps cost O(d) per bind op and makes each slot's
subspace literally orthogonal to every other slot's subspace — so
retrieval from slot i cannot leak content from slot j, regardless
of what was stored.

Use cases rotation binding covers:

- **Opaque variable storage.** Assign a value under a name, retrieve
  it later. What sign-flip used to cover.
- **Array / sequence positions.** Store item at position i as `R^i`
  applied within the slot. Iterate positions by repeated rotation.
- **Reversible imperative state.** A sequence of assignments is a
  sequence of rotations on the synthetic subspace. Every rotation
  has an inverse; the whole program is reversible by construction.
- **Variable assignment as a pure transform.** `x = v` is a function
  from state to state that replaces the content at x's slot with v.
  Sutra stays functional; no memory cells, no mutation.

## Canonical axes in the synthetic subspace

Some axes in the synthetic subspace are **designated by the language
itself**, not allocated per-program. Currently specified:

- **Truth axis.** One canonical axis. `true` is `+1` along it,
  `false` is `-1`, fuzzy values are continuous between. Boolean and
  fuzzy values are scalars on this axis. Multiple booleans are
  stored by putting them in distinct variable slots whose projected
  value onto the truth axis is the scalar.

  Key property: because the truth axis is in the synthetic subspace
  and the semantic subspace is structurally orthogonal to it, every
  semantic vector has zero projection onto the truth axis. Semantic
  content is decorrelated from truth by construction — nothing
  "looks more true" because of what it means.

Candidates for other canonical axes (open — the user flagged that
canonical axes open the door to native support for other data types
through VSA):

- Integer axis / integer subspace.
- Enum axes per enum type.
- Time or sequence-position axis.
- Probability / confidence axis separate from truth.

The commitment is that canonical axes are **designated, not learned**.
The compiler and spec know their layout; two runs of the same program
get identical canonical-axis placement. No corpus data is involved.

## Allocation of non-canonical synthetic axes

Synthetic-subspace axes that aren't canonical (variable slots,
positional rotation axes for arrays) are **allocated at compile
time**. The compiler assigns each variable / slot to a 2D rotation
plane in the synthetic subspace from a fixed budget of synthetic
dimensions. Allocation is deterministic and reproducible — two
compilations of the same source get the same axis layout.

"Learned" is not the right word for this allocation — it's systematic
compile-time assignment, not fit from data. The earlier framing that
said "the axes have to be learned" has been superseded.

## Sign-flip phase-out

Sign-flip binding is retired as a design kind. Rotation binding
strictly dominates it for Sutra's use cases:

| Property | Sign-flip | Rotation (in synthetic subspace) |
|---|---|---|
| Opaque storage | ✓ | ✓ |
| Ordered / sequential | ✗ | ✓ |
| Cross-talk | 1/√d statistical | Zero by construction |
| Reversibility | Self-inverse | Inverse = R^-i |
| Cost per op | O(d) | O(d) with structured rotation |
| Cleanness for imperative state | Awkward | Natural |

The one thing sign-flip uniquely has (element-wise commutativity of
bind) has no load-bearing customer in Sutra — bind composition is
handled semantically by learned matrices, where non-commutativity is
a *feature* (`color-of-shape` ≠ `shape-of-color`).

**Phase-out timing.** Sign-flip is what the three demo programs
currently compile to. The plan is: reframe docs now (this note +
the doc-reversal pass described below), implement rotation binding
in the compiler, migrate the demos, remove sign-flip support once
migration is complete. Not an immediate code rip-out.

### Doc-reversal work implied

As of 2026-04-21 morning (commits `a2a5bd0`, `cf08ad3`, `621d2ed`)
the repo explicitly says sign-flip and learned-matrix are *both
first-class binding kinds with their own legitimate use cases*. That
framing is now stale. The following need to be updated once the
rotation-binding design is confirmed:

- `STATUS.md` queue item 1 — rewrite to "implement rotation binding
  in the synthetic subspace; migrate demos off sign-flip."
- `STATUS.md` pinned items 4, 5, 6 — rewrite binding-related language
  around the two-kinds model (semantic + rotation), sign-flip as legacy.
- `planning/sutra-spec/binding.md` — rewrite "Kinds of binding" and
  subsections. Add "Extended state vector" section. Retire the
  structural/sign-flip-is-first-class text.
- `planning/sutra-spec/vision.md` — same updates.
- `planning/sutra-spec/equality-and-defuzzification.md` — incorporate
  the canonical-truth-axis design.
- `planning/open-questions/binding-kind-surface-syntax.md` — the
  candidates need re-evaluation with the new two-kinds model. The
  structural/semantic framing survives but "structural" now means
  rotation, not sign-flip.
- Memory file `feedback_no_sign_flip.md` — rewrite to match the
  phase-out decision. The "both first-class" framing from earlier
  today is superseded.

## What remains to validate empirically

1. **Capacity in high-d.** How many variable slots can a synthetic
   subspace of N dimensions support before cross-talk kicks in? With
   2D-rotation-plane-per-slot allocation, the theoretical answer is
   N/2 clean slots. Verify empirically that practical cleanup (snap,
   cosine readout) holds at that capacity under realistic noise.
2. **Truth-axis orthogonality under operation.** Confirm that under
   learned-matrix bind and bundle operations, semantic content stays
   cleanly orthogonal to the truth axis. Verify that fuzzy scalar
   values on the truth axis compose under `and`/`or`/`not` without
   picking up semantic drift.
3. **Reversibility of imperative state.** Verify a program that
   does `x = a; x = b; x = a` ends up with the same state vector as
   the one-line `x = a` version (or cleanly distinguishable within
   a predictable bounded error).
4. **Budget.** Empirically determine the synthetic-subspace size
   needed for realistic programs. The user's intuition: tens to a
   hundred dimensions. Verify.

A concrete experiment for (1) could be: pick N ∈ {16, 32, 64, 128},
allocate N/2 variable slots with 2D-rotation-plane allocation,
bundle random fuzzy values across all slots, read back each slot,
measure recovery accuracy vs capacity.

## Open questions

1. **Budget for the synthetic subspace.** Fixed at the language
   level, set per-program, or grown dynamically by the compiler?
2. **Relationship to the fly-brain substrate.** The synthetic
   subspace is easy to append to a numpy vector. On the Shiu
   whole-brain LIF model, "appending dimensions" is not as free —
   there's no spare neuron population reserved for synthetic state.
   Does this design target the numpy/embedding substrate only, or
   does the fly-brain substrate get a corresponding synthetic-
   population design?
3. **Surface syntax with two kinds (semantic + rotation).** The
   candidates in `planning/open-questions/binding-kind-surface-syntax.md`
   were drafted for sign-flip vs. learned-matrix. They mostly still
   apply, but "structural" there means sign-flip; re-read with
   rotation in mind and decide which candidate still wins.
4. **Canonical-axis inventory.** Truth is committed. What other
   canonical axes does the language want to designate from the
   start vs. leave to be added later?
5. **How does equality / `is_true` compose with the truth axis?**
   `is_true(x)` is a learned map from semantic subspace to the
   truth axis scalar. What's the spec for how multiple `is_true`
   values compose, and how does a boolean variable (a scalar stored
   at a rotation slot) get its truth scalar extracted at a `select`
   dispatch site?

## Prior-art audit pending

VSA is a small field (roughly a dozen active researchers) and
dev-velocity matters, so no serious literature sweep has been done
before writing this note. Before any of this becomes a publication
claim, the following specific priors need to be checked:

- **Rotation as a binding operator** — Plate's HRR uses circular
  convolution, which is rotation in the Fourier domain. Frady &
  Sommer's *fractional power encoding* uses continuous-valued
  rotation for position codes. Eliasmith's Semantic Pointer
  Architecture (Neural Engineering Framework, Nengo) uses rotation
  for some bindings. The specific "one 2D Givens plane per
  variable slot, zero cross-talk by construction" allocation may be
  novel, but the underlying idea is not.
- **Extended state with dedicated symbolic dimensions** — VSA
  literature has "role space" vs. "filler space" separations.
  Neural-symbolic integration (Rocktäschel, Garcez, etc.) routinely
  concatenates learned symbolic dimensions onto base embeddings.
  Kanerva's SDM has some of this flavor. The specific subspace-
  orthogonality-by-construction framing used here may be closer to
  novel but builds on an existing pattern.
- **Canonical truth axis with structural semantic/truth
  decorrelation** — fuzzy logic generally has designated membership
  scalars, and representation-learning routinely reserves
  dimensions for specific features. The structural-subspace-
  orthogonality argument (truth orthogonal to semantic content by
  construction of the subspaces, not by learned decorrelation) is
  less clearly located in prior work but has not been searched for.
- **Variable assignment as a rotation on state** — touches
  reversible computing (Bennett, Fredkin), some quantum-circuit-
  inspired classical frameworks, and various academic reversible-
  programming languages (Janus, etc.). The VSA-specific framing
  where assignment is a rotation on an extended embedding state
  vector hasn't been located in a direct prior, but the underlying
  reversible-computing tradition is established.
- **Rotation-binding-based eigenrotation loops** — Sutra's
  `loop(cond)` compiles iteration to rotation in the substrate
  (`state ← R · state` terminating on prototype match). This is
  closer to novel as a programming-language construct, but the
  continuous-space analog of counter-based iteration has touched
  points in neural computation literature that should be checked.
- **TransE vs. VSA** — TransE (Bordes et al. 2013) is from the
  knowledge-graph-embedding community; relations as translations
  `h + r ≈ t`, trained with a margin loss on triples. VSA is a
  distinct lineage (Plate 1995, Kanerva) with different primitives
  and different goals. Sutra's displacement-vector foundation is
  closer to VSA than to TransE despite surface similarity. Earlier
  confusion between the two has drawn reviewer objections; papers
  on this work should explicitly situate Sutra in the VSA tradition
  and distinguish from TransE at the framing level.

The working assumption until this audit happens is that **most
individual moves here have priors in some VSA or adjacent tradition**
but the *combination* (functional language with extended state
vector, rotation binding in a dedicated synthetic subspace,
canonical truth axis, learned-matrix semantic binding all in one
compiler-backed design) is what Sutra contributes. Dev proceeds at
dev pace; the audit happens before publication, not before the next
commit.

## Pedagogical note

Rotation is conceptually heavier than sign-flip. A reader new to
VSA will take longer to pick up "bind is a rotation in a designated
2D plane of the synthetic subspace" than "bind flips signs by a
±1 pattern." The design commitment is to carry that teaching cost
in the docs and tutorials — worked 2D diagrams, step-by-step
walkthroughs of variable-assignment-as-rotation, side-by-side
comparisons with imperative languages — rather than compromise the
design by keeping sign-flip around.

The user is one of a small number of people actively evangelizing
VSA (the field being in roughly the state of Mendel's genetics
paper pre-rediscovery), and Sutra is likely to be a primary entry
point for new readers. Docs quality is load-bearing for the
design's reach.
