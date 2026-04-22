# Equality and defuzzification

## Equality as matrix multiplication

Equality in Sutra is not a comparison on two atomic values. It is
a matrix-mediated operation:

1. A function maps a vector to a **matrix** that acts as an
   "is-this-thing" test.
2. To test whether `x` equals `cat`, you use that function on `cat`
   to get the **`is_cat` matrix**, then multiply that matrix by `x`.
3. The result is a scalar on the canonical truth axis — how much
   `x` is `cat`, read as a fuzzy truth value.

So "x == cat" is not a single scalar comparison — it's the
function-of-vector → matrix → matrix-vector-product pipeline.
`is_cat` is itself a reusable object; once you have it, you can
apply it to many candidate `x`s.

This is the reason many Sutra functions compile to matrices (see
`types.md` — "Functions and matrices"). An "is-X" predicate is
literally a matrix, and its output lands on the truth axis.

## Canonical axes in the synthetic subspace

The synthetic subspace hosts **canonical axes** — dimensions
designated by the language rather than allocated per-program. Two
are committed as of 2026-04-22:

- **Truth axis** (antipodal, detail below).
- **Number axis** — a single dimension, going up, that scalar /
  integer / float / number-typed values live on. See
  `types.md` §"The number axis and the integer class" for the
  type-level commitment. The user's framing (2026-04-22 evening):
  "everything is a float in this language because everything is a
  vector" — the number axis is where those floats sit, and the
  `int` class is a compile-time tag on values that should behave
  integer-like (augmented assignment first; future compile-time
  integer-specific checks ride on the same tag).

More canonical axes may be designated later (enum, position, time)
as the extended-state-vector implementation matures.

## The canonical truth axis

Truth has its own **canonical axis** in the synthetic subspace of
the extended state vector (see `binding.md` for the extended-state
design). The axis is antipodal:

- `true = +1` along the truth axis.
- `false = -1` along the truth axis.
- Fuzzy values are the continuous range between.

Because the synthetic subspace is **structurally orthogonal** to
the semantic subspace, every semantic vector has zero projection
onto the truth axis by construction. Semantic content is
**decorrelated from truth by construction, not by learned
statistics** — nothing "looks more true" because of what it means.

A boolean or fuzzy value in Sutra is a scalar on the truth axis.
Multiple boolean variables don't share the axis directly — each
boolean is stored at its own rotation-bound variable slot in the
synthetic subspace, and *the value at that slot is the scalar on
the truth axis*. So `bool a; bool b` gets two separate rotation
slots; reading `a` de-rotates out of its slot and projects onto
the truth axis for the scalar.

Fuzzy logic operations (`and`, `or`, `not`, t-norms) act on the
truth-axis scalar directly. `not` is negation along the axis.
`and` and `or` are standard fuzzy t-norms / t-conorms applied to
the scalars.

## Defuzzification

Defuzzification is a matrix operation that **polarizes** a fuzzy
truth scalar toward `+1` (true) or `-1` (false) along the truth
axis. The user's working picture: a **defuzz matrix** exists such
that multiplying a fuzzy value by it produces a defuzzified-by-a-
certain-amount version of that fuzzy. Repeated application drives
a fuzzy value toward a bool, and the compile-time defuzz counter
on `bool` tracks how many rounds it has been through.

The rule: defuzzification **polarizes** — it sharpens a fuzzy
value along the truth axis — but it **does not binarize**. The
output is still fuzzy, still differentiable, still a scalar (not
a crisp 0/1). A value that has been defuzzified "fully" is a
`bool` (subclass of `fuzzy`) with the defuzz counter recording how
many polarization steps it has been through.

`is_true` is the operation that performs this polarization. It
can be applied repeatedly; each application increments the counter.

## Alternative: undersymbolic-realm placement on substrates without a synthetic subspace

The canonical-truth-axis design depends on the substrate supporting
an appended synthetic subspace — a handful of extra dimensions
reserved for computational state, orthogonal by construction to
the semantic content. This works naturally for numpy / embedding-
vector substrates: you just allocate a longer vector.

Some substrates cannot append dimensions cheaply. The fly-brain
Shiu whole-brain LIF model, for instance, has a fixed neuron
population with no spare "computational" neurons reserved for
synthetic axes. For substrates like these, the **undersymbolic
realm** approach is the fallback:

LLM embedding spaces are **anisotropic**: natural-language content
concentrates in a cone (or a narrow manifold) that occupies only
a small fraction of the full d-dimensional space. The rest of the
space — directions roughly orthogonal to the content cone — is
**sparsely populated**: no natural word or sentence embeds near
those directions. The user's earlier working name for this region
is the **undersymbolic realm**.

This empty region is a resource, not a problem. On substrates
without a dedicated synthetic subspace, Sutra uses it for
structural markers that should not collide with any natural
concept — truth axis, variable-slot rotations, identity sentinels.

Mechanically, this means Sutra does **not** use `embed("true")`
for the truth direction on such substrates. Candidates for finding
empty directions include:

- Principal components with small eigenvalues in a corpus-wide
  embedding covariance matrix — directions LLM content does not
  span.
- Random unit vectors followed by projecting out the content
  subspace (approximated by the top-k principal components of a
  sample corpus).
- Explicitly orthogonalizing synthetic points against each other
  and against a reference corpus of natural embeddings.

On substrates where the undersymbolic-realm approach applies, the
truth axis becomes an empirical rather than constructed direction —
the canonical-axis commitment is relaxed, and the compiler picks a
direction that is empirically empty in the substrate.

The default substrate (numpy + frozen LLM + appended synthetic
subspace) uses the constructed approach. The undersymbolic-realm
approach is the substrate-specific fallback for constrained
targets.

## Open questions

- What is the exact construction of the "is-X" matrix? Is it a
  single canonical function per type, or user-definable per
  predicate?
- What is the exact construction of the defuzz matrix? Is it
  substrate-dependent? Does it act specifically on the truth axis
  or does it involve the whole state vector?
- Does the defuzz counter have a ceiling (after N defuzz steps
  the value is in a distinguished state)? Or is it open-ended?
- Is `is_true` the only defuzzification primitive, or are there
  others (e.g. `is_false`, `is_near`, `is_in`)?
- Equality as matrix multiplication produces a truth-axis scalar.
  Is that scalar typed as `fuzzy` until defuzz is applied, at
  which point it becomes `bool` (with defuzz counter ≥ 1)? The
  type flow needs to be spelled out.
- On substrates using the undersymbolic-realm fallback (no
  appended synthetic subspace), how stable is the "empty direction"
  against shifts in the corpus over time? If the substrate's
  underlying embedding drifts, does the truth axis need to be
  re-derived?
- **Canonical-axis inventory beyond truth.** The synthetic subspace
  can host other canonical axes (integer, enum, position, time) for
  native support of other data types through VSA. Which of these
  are committed, and on what timeline?
