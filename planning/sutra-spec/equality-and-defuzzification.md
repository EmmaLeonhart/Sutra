# Equality and defuzzification

## Equality as matrix multiplication

Equality in Sutra is not a comparison on two atomic values. It is
a matrix-mediated operation:

1. A function maps a vector to a **matrix** that acts as an
   "is-this-thing" test.
2. To test whether `x` equals `cat`, you use that function on `cat`
   to get the **`is_cat` matrix**, then multiply that matrix by `x`.
3. The result is a truth-valued vector (fuzzy / bool) that says
   how much `x` is `cat`.

So "x == cat" is not a single scalar comparison — it's the function-
of-vector → matrix → matrix-vector-product pipeline. `is_cat` is
itself a reusable object; once you have it, you can apply it to
many candidate `x`s.

This is the reason many Sutra functions compile to matrices (see
`types.md` — "Functions and matrices"). An "is-X" predicate is
literally a matrix.

## Defuzzification

Defuzzification is also a matrix operation. The user's working
picture: a **defuzz matrix** exists such that multiplying a fuzzy
value by it produces a defuzzified-by-a-certain-amount version of
that fuzzy. Repeated application drives a fuzzy value toward a
bool, and the compile-time defuzz counter on `bool` tracks how
many rounds it has been through.

The rule: defuzzification **polarizes** — it sharpens a fuzzy value
along a target axis — but it **does not binarize**. The output is
still fuzzy, still differentiable, still a vector. A value that has
been defuzzified "fully" is not a crisp 0/1; it is a bool
(subclass of fuzzy) with the defuzz counter recording how many
polarization steps it has been through.

`is_true` is the operation that performs this polarization. It can
be applied repeatedly; each application increments the counter.

## The undersymbolic realm — where `true` and `false` live

LLM embedding spaces are **anisotropic**: natural-language content
concentrates in a cone (or a narrow manifold) that occupies only a
small fraction of the full d-dimensional space. The rest of the
space — directions roughly orthogonal to the content cone — is
**sparsely populated**: no natural word or sentence embeds near
those directions. The user's earlier working name for this
region is the **undersymbolic realm**.

This empty region is a resource, not a problem. Sutra uses it for
structural markers that **should not collide with any natural
concept**:

- **`v_true` and `v_false`** live outside the populated cone.
  If `v_true` were just `embed("true")`, it would be close to
  "yes", "correct", "affirmative", "right", and a thousand other
  content-bearing words — every one of which would contaminate the
  truth-axis with its own semantic baggage. Putting `v_true` in
  an uninhabited direction keeps the polarization axis clean.
- **Arbitrary synthetic points** (identity markers for role
  matrices, sentinels for "no answer," structural separators) get
  the same treatment: assign them a direction no natural embedding
  occupies, and they stay uncontaminated.

Mechanically, this means Sutra does **not** use `embed("true")` for
`v_true`. The runtime (or the empirical-initiation phase) should
**characterize which directions are empty in the target substrate**
and mint synthetic points there. Concretely, candidates for finding
empty directions include:

- Principal components with small eigenvalues in a corpus-wide
  embedding covariance matrix — directions LLM content does not
  span.
- Random unit vectors followed by projecting out the content
  subspace (approximated by the top-k principal components of a
  sample corpus).
- Explicitly orthogonalizing synthetic points against each other
  and against a reference corpus of natural embeddings.

Defuzzification toward `v_true` and `v_false` is then polarization
along an axis that is empirically empty in the substrate — the
"is this true" question doesn't get confounded by "is this
reminiscent of the word 'true'."

## Open questions

- What is the exact construction of the "is-X" matrix? Is it a
  single canonical function per type, or user-definable per
  predicate?
- What is the exact construction of the defuzz matrix? Is it
  substrate-dependent?
- Does the defuzz counter have a ceiling (after N defuzz steps the
  value is in a distinguished state)? Or is it open-ended?
- Is `is_true` the only defuzzification primitive, or are there
  others (e.g. `is_false`, `is_near`, `is_in`)?
- Equality as matrix multiplication gives a truth-vector. Is that
  vector itself a `fuzzy`, a `bool`, or something else in the
  type system? (Presumably `fuzzy` if no defuzz has been applied,
  `bool` if one has — but this needs to be stated.)
