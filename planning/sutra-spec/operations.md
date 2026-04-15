# Primitive operations

The primitive vector operations in Sutra are:

- **`bind`**
- **`bundle`**
- **`unbind`**
- **`snap`**
- **`similarity`**

What each one computes in detail is spec work still to be done; this
section records what the user has stated so far about them as a set.

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

## Backend-specific availability

> **NOTE — drift flagged 2026-04-15 (consistency audit):** The
> numpy backend (`codegen_numpy.py`) **rejects `snap()` at codegen
> time** — the pure-numpy demo substrate has no cleanup circuit,
> so programs that need `snap` target the fly-brain backend
> instead. The spec lists `snap` as a primitive without qualifying
> this, which is technically accurate for the language but misses
> that primitive availability is per-backend. Whether this is a
> gap that needs to be closed by giving the numpy backend a real
> `snap` (e.g. argmax-cosine against a codebook) or acknowledged
> in the spec as a known substrate restriction is an open
> question.

## `select` is not a primitive vector operation

`select` is the conditional-branching mechanism, which is a different
kind of thing from bind/bundle/unbind/snap/similarity. Spec for
`select` lives in `control-flow.md`, not here.

## Open questions

- Which similarity operation does Sutra adopt as its default? Dot,
  cosine, normalized dot, or something else? Is it substrate-
  dependent (e.g. whichever the backend can give cheaply)?
- What does each of `bind`, `bundle`, `unbind`, `snap` compute
  exactly? The current implementations are sign-flip-based (see
  high-priority item in `todo.md` — the user has flagged that the
  sign-flip-as-`bind` status should be revisited with user input).
- Are there other primitive operations that deserve first-class
  status (e.g. rotation, projection, scalar multiplication)?
