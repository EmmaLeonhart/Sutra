# Primitive operations

The primitive vector operations used across the `.su` examples and
accepted by the compiler are:

- **`bind`** — combine two vectors into a role-filler pair.
- **`unbind`** — recover a filler given a role (inverse of `bind`).
- **`bundle`** — superpose multiple vectors into a single vector.
- **`similarity`** — score how close two vectors are.
- **`embed`** — map a string literal to a vector via the substrate's
  embedding function.
- **`argmax_cosine`** — given a vector and a codebook of vectors,
  return the codebook entry whose cosine similarity is highest.
  This is the numpy-backend form of "clean up to the nearest known
  prototype."

What each one computes in detail is spec work still to be done; this
section records what is known from example usage and user statements.

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
- What does each of `bind`, `bundle`, `unbind` compute exactly? The
  current implementations are sign-flip-based (see high-priority
  item in `todo.md` — the user has flagged that the sign-flip-as-
  `bind` status should be revisited with user input).
- Are there other primitive operations that deserve first-class
  status (e.g. rotation, projection, scalar multiplication)?
- Should `snap` and `argmax_cosine` unify under a single name that
  lowers differently per substrate, or stay distinct?
