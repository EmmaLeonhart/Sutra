# Magnitude preservation as a substrate requirement

**Date:** 2026-04-21.
**Status:** Design-reflection finding — captures context behind
Sutra's substrate choices (nomic-embed-text with mean-centering,
GTE-large, magnitude-aware cartography operations). Not an
experiment writeup; a piece of framing that explains *why* the
substrate question is load-bearing for Sutra and likely adversarial
to most of today's embedding ecosystem.

## The observation

The ML community's standardization on **cosine similarity with
unit-normalized embeddings** as the default retrieval metric is a
substantial part of why TransE-style and VSA-style compositional
vector work hasn't been integrated into the mainstream of
embedding-based systems. Cosine strips magnitude from the signal.
Once magnitude is discarded — either by the retrieval metric or,
worse, by the embedding model's output normalization — the
compositional arithmetic that TransE and VSA both depend on
**stops being tractable on the resulting substrate**.

Sutra's choices of substrate (nomic-embed-text with mean-
centering, GTE-large, magnitude-aware displacement arithmetic in
the cartography work) are specifically the choices that push back
against this convention — not an arbitrary preference but a
substrate requirement for the language to function.

## The three-year window

The user's framing, worth preserving verbatim: *"there was a
three-year window or something where this could have become the
standard, and it just didn't. It takes somebody very persistent
to actually push through and say, 'Screw all this stuff. Give
me embeddings with magnitude.'"*

Rough chronology of how the window opened and closed (dates
approximate, worth verifying in the prior-art audit):

- **~2013-2015.** word2vec and GloVe ship with meaningful
  magnitudes — the norm of a word vector carries information about
  word frequency and specificity. TransE (Bordes et al. 2013)
  ships and explicitly uses L1/L2 distance for `||h + r - t||`;
  the relation vector `r` has a *real magnitude* that encodes how
  far `h` must move to reach `t`. Compositional arithmetic on
  embeddings is tractable in this era because the substrate
  preserves magnitude information.
- **~2016-2018.** BERT-era dense retrieval takes off. Cosine
  similarity becomes the dominant similarity function because it
  works well for retrieval, classification, and semantic search
  at scale. The extra degree of freedom (magnitude) is invisible
  to cosine, so model designers start unit-normalizing embeddings
  by default — the magnitude doesn't help the benchmark, so it's
  treated as wasted capacity.
- **2018+.** The convention entrenches. Most public embedding
  APIs unit-normalize their outputs. Cosine becomes the
  lingua-franca similarity function. Compositional arithmetic in
  the TransE/VSA tradition becomes much harder because the
  substrate has been flattened to the unit sphere, and any work
  that needs magnitude has to either find a non-normalized
  exception or train custom embeddings from scratch.

The technical mechanism that kills magnitude-aware work once
unit-normalization is the default: **displacement arithmetic
requires that `h + r` can land anywhere in the space, with `r`'s
magnitude carrying information.** If the substrate expects
embeddings on the unit sphere and `h + r` isn't on the sphere,
you have two bad options — leave it off-sphere (breaks every
downstream cosine comparison) or renormalize (destroys the `r`
magnitude information you just encoded). Similarly, learned role
matrices for anything beyond pure rotation (scaling, projection,
general linear maps) all depend on the embeddings *not* being
collapsed to a single norm. Cosine-normalized substrates are
structurally hostile to these operations.

It's not that the community made a wrong choice — cosine-based
retrieval genuinely worked great for the dominant use cases of
the late-2010s. It's that the convention had large
**unintended-downstream consequences** for compositional
embedding work, and the people positioned to notice (TransE
people, VSA people) were in separate enough communities that
neither organized a pushback. So the magnitude-preserving
substrate became the exception rather than the default, and
TransE/VSA-style work has been pushed into a corner that most
practitioners don't even know exists.

## Why this matters for Sutra specifically

Sutra's whole computational model depends on magnitude-aware
substrate:

- **Learned-matrix bind** (`R @ filler`) produces outputs whose
  magnitude generally isn't unity. On a unit-sphere substrate,
  every bind is either off-manifold or has to be renormalized
  (destroying the information the bind just encoded).
- **Displacement vectors** (rank-0 learned role matrices, the
  foundation of the cartography work) specifically need the
  ability to express "move filler by a fixed displacement d" with
  d having meaningful magnitude. On a cosine-normalized substrate,
  two displacement vectors with the same direction but different
  magnitudes are indistinguishable.
- **Fuzzy scalars on the truth axis** need magnitude — the whole
  point of +0.7 vs +0.3 vs +0.1 vs -0.9 is the magnitude along
  the axis. A "unit-normalized" boolean would collapse the fuzzy
  distinction.
- **Bundle-and-retrieve** operations rely on the relative
  magnitudes of different bound terms to let cleanup pick out the
  right one. Unit-normalizing after each bundle destroys the
  discriminative information.

The upshot: **Sutra's substrate cannot be arbitrary.** The
substrate must either come with magnitude preserved, or provide
explicit mean-centering (which preserves relative magnitudes
after subtracting the global centroid) rather than aggressive
unit-normalization. This is why CLAUDE.md specifies
nomic-embed-text with mean-centering as the demo substrate, and
why GTE-large (also mean-centering friendly) has been the
fallback when nomic collapses.

**Rotation binding in the synthetic subspace is norm-preserving
by design** — rotations don't destroy magnitude. So the
computational-state half of the extended state vector is immune
to the magnitude-stripping problem; the semantic half is where
the substrate choice matters.

## What "magnitude-preserving" means for an embedding model

Not a single spec; three related properties, any combination of
which can be present:

1. **Output is not unit-normalized.** The raw output of the
   embedding model has varying L2 norm across inputs, and that
   variation carries information (word frequency, sentence
   specificity, etc.).
2. **Mean-centering rather than unit-normalization.** The model
   subtracts a global or corpus-dependent centroid but does not
   force unit norm. nomic-embed-text is a canonical modern
   example; after centering, the remaining vector has meaningful
   magnitude relative to the center. This is the practical middle
   path — compatible with cosine-based retrieval (since
   mean-centering is a linear transform that can be applied
   per-call) while preserving magnitude for VSA-style arithmetic.
3. **Training objective preserves magnitude.** The model is
   trained with a loss that depends on magnitude (e.g. L2
   distance in the training objective), so the learned
   embeddings have magnitude as a trained-in feature rather than
   an accidental byproduct.

For Sutra, property (2) is sufficient for most operations and
happens to be the common-case behavior of modern embedding models
that aren't *aggressively* unit-normalizing. Property (1) is
stronger but rarer.

## Implications for substrate search

When evaluating a candidate embedding model for Sutra work, the
first question to ask is: **does it preserve magnitude?** If the
model's output is unit-normalized at the API boundary, it's
probably not usable for learned-matrix bind without custom
de-normalization tricks that may or may not recover the magnitude
signal.

Concretely, the `sdk/sutra-compiler/sutra_compiler/codegen_numpy.py`
embedding config should be read as "this is the substrate we have
validated works for Sutra-style arithmetic" — substituting a
differently-normalized model is not a free swap, it's a substrate
change that invalidates the validation.

## Prior-art audit pending

- The exact dates of the "three-year window" are approximate; a
  careful chronology of when unit-normalization became the
  dominant convention needs a specific literature search.
- The claim that "cosine is dominant because it kills magnitude"
  has corners — some embedding models are unit-normalized but for
  other reasons (numerical stability, training dynamics) and
  retain some magnitude information in other ways.
- Work that has pushed back against unit-normalization in public:
  probably some. Candidates to search: Frady, Sommer and colleagues
  on hyperdimensional computing explicitly address capacity and
  magnitude; the "Matryoshka embeddings" line (Kusupati et al.)
  keeps magnitude structure across nested sub-dimensions; nomic's
  and Snowflake's blog posts on why they don't normalize.
- The framing of "community agreed to not care about magnitude"
  is rhetoric for a distributed convention that no one agreed to
  explicitly. A more neutral phrasing for publication might be:
  "the dominant dense-retrieval use case rewards cosine similarity,
  which creates systematic pressure toward unit-normalized
  embeddings, which in turn makes compositional-arithmetic work
  structurally harder on off-the-shelf embedding models."

## Implications for the sutra paper's framing

The cartography paper already implicitly depends on
magnitude-aware substrate. The sutra paper should **name this
dependency explicitly**: the three-step arc (displacements →
consolidation → full role matrices) works at all only because the
substrate preserves magnitude, and the reader should know
up-front that Sutra is not going to be a drop-in replacement for
OpenAI-ada-style unit-normalized pipelines. Naming this at the
start prevents a reviewer-level objection that "but my embeddings
are normalized, so this doesn't apply to me" — the correct
response to that is "yes, your embeddings are in the wrong shape
for this work; the question is whether you want magnitude back."
