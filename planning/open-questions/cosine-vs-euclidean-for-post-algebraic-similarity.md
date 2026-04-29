# Cosine vs Euclidean for post-algebraic similarity

## The question

Sutra uses **cosine similarity** as its single similarity metric across
the runtime: `_VSA.similarity`, equality (`==`) projected onto the
truth axis, `argmax_cosine` for codebook lookup, defuzzification's
`f = f == true` iteration, and the vector-keyed `map<K,V>` fallback.
All of these are cosine-based.

The user has an old recorded reservation that **Euclidean distance
might be the right metric for post-algebraic-operation comparison**,
not cosine. The reservation was raised early (originally captured in
the `vsa-bundle-bind-permute-and-metric-choice` chat, harvested
2026-04-29) and has never been tested or resolved.

The chat-raw form: *"I always felt like intuitively Euclidean
distance is best, and dot product magnitude is kinda good-ish. I
don't know."* And earlier, on cosine specifically: *"cosine
similarity does a very good job at indicating if two simple things
are relatively similar to each other. It really breaks down once you
start engaging in any kinds of algorithmic operations like these."*

## What Sutra currently does

Cosine, everywhere. Concrete touch points (in
`sdk/sutra-compiler/sutra_compiler/codegen.py`):

- **`_VSA.similarity(a, b)`** — `dot(a,b) / (||a|| * ||b|| + eps)`.
- **`_argmax_cosine(query, candidates)`** — stacked cosines via
  matmul, argmax.
- **Equality `==`** — cosine projected onto the truth axis (per
  `equality-and-defuzzification.md`).
- **Defuzzification `f = f == true`** — iterates the cosine-based
  equality.
- **Vector-keyed `map<K,V>`** — identity check, then cosine
  fallback.

Cosine is deeply baked in. Switching would touch a substantial chunk
of the runtime.

## Why the current choice has force

- **Normalization-friendliness.** Cosine is bounded `[-1, 1]`
  regardless of vector magnitudes. The truth-axis projection
  machinery, `is_true` polarization, defuzzification thresholds, and
  the various places fuzzy values are compared all assume a bounded
  similarity score. Switching to Euclidean would force every
  threshold-using site to also know the relevant magnitude scale.
- **Embedding-substrate convention.** Frozen-LLM embedding spaces
  are conventionally compared with cosine. The frozen substrate's
  geometry was learned under cosine-based loss in many cases; using
  cosine at inference matches what the substrate is "trained for."
- **Magnitude-stability.** After bundle / bind / rotate operations,
  vector magnitudes drift in ways that don't necessarily correspond
  to semantic distance. Cosine ignores those magnitude wobbles by
  construction.
- **Speed.** `dot(a,b) / (||a|| ||b||)` parallelizes trivially to
  one matmul + two norms (and norms can be precomputed for
  codebooks). Euclidean is comparably cheap but the
  threshold-bookkeeping is the real cost.

## Why the alternative has force

- **Magnitude carries information that bind/bundle put there.** A
  bundle of N vectors has magnitude that scales with N (modulo
  normalization choices). A bound vector's magnitude reflects the
  binding-operator scaling. Cosine throws all of that away and
  reports "direction match" only. The user's intuition: after
  algebraic ops, the magnitude *is* part of the semantic answer,
  not noise to be normalized out.
- **Post-bind / post-bundle vectors live in regions where direction
  alone is ambiguous.** Two different bundles can land at similar
  angles but very different magnitudes; cosine sees them as the
  same. Whether that "sameness" is a feature (fuzzy-match) or a bug
  (false positive) depends on the use case.
- **Defuzzification semantics**. The truth-axis projection has a
  specific magnitude meaning (`+1` = true, `-1` = false, `0` =
  unknown). Cosine collapses the magnitude back to direction-only,
  which means a defuzzed truth value of `0.3` and one of `0.9` look
  similar in cosine terms but mean different things in defuzz
  terms. There's a tension here.

## What we don't know

1. **Does it actually matter for the demos that ship?** None of the
   three current demos (hello world, fuzzy branching, role-filler
   record) clearly stress the cosine-vs-Euclidean distinction. A
   capacity-style experiment that compares the two metrics on
   bundle-decode after N items, or on chained bind-then-unbind
   recall, would settle whether the choice is observable on real
   programs.
2. **Where does the user's intuition come from?** The reservation
   was raised in the abstract. Is there a specific operation
   sequence where cosine empirically failed? Without that, the
   intuition is unfalsified rather than tested.
3. **Could Sutra support both?** Either as a runtime knob (the
   user picks per-similarity-call) or as a per-axis design
   (truth-axis ops use one, semantic-block ops use the other).
   Mixed-metric runtimes are uncommon for a reason — the
   threshold bookkeeping gets tangled — but the truth-axis split
   may make it tractable here.
4. **Does the answer change for the synthetic vs semantic
   subspace?** The synthetic subspace is structurally orthogonal
   and has reserved canonical axes; cosine and Euclidean may
   diverge less there than in the noisy semantic subspace.

## What would resolve it

A direct comparison experiment: take an existing demo (the
role-filler record decode is the cleanest candidate) and instrument
the runtime to emit both metrics at every comparison point.
Characterize where they agree and where they disagree, on real
program execution rather than synthetic vectors. If they agree
within tolerance everywhere the demos exercise, the user's
reservation is empirically refuted and we keep cosine. If they
disagree on real demo behavior, that's the moment to decide whether
to switch the default, expose a knob, or per-axis-split.

This is **not** blocking any current work. It's a recorded design
gap that should be revisited before Sutra makes any "we picked the
right metric for our use case" claim publicly. Until tested, that
claim isn't backed by anything.
