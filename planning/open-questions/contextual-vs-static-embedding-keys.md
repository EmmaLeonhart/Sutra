# Contextual vs static embedding keys

## The question

Sutra's `embed()` and `basis_vector()` primitives take a **string
key** and return the substrate's fixed embedding for that string —
one string, one vector, no context. This is a static-embedding
model: `embed("bank")` always returns the same vector regardless of
whether the program is reasoning about rivers or finance.

The user has expressed interest in **context-dependent embedding**:
the more contextuality, the better. Specifically (from a triaged
chat, originally `chats/vsa-operations-explained.md`, harvested
2026-04-29): *"In my original, I think it's very important that it
be contextual. The more granularity of contextualness, the
better… In my original implementation, I wasn't able to do
anything with word sense, but I explicitly sought out to do so and
then found I was unable to do so."*

The question: should Sutra grow a surface-level mechanism for
context-dependent embedding lookup, or stay with string-keyed fixed
embeddings forever?

## What Sutra currently does

`embed()` and `basis_vector()` take a string and return the
substrate's embedding of that string. The lookup is:

1. Check the on-disk cache `~/.cache/sutra/embeddings/<model>-d<dim>.npz`
   for the string.
2. If miss, call the substrate (Ollama, locally) with the bare
   string and store the result.
3. Return the vector.

Two `embed("bank")` calls in the same program return the same
vector, even if one appears in a sentence about rivers and the
other in a sentence about money. The substrate's contextual
capacity (if any) is not exposed — the surface API is
fundamentally static-keyed.

## Why the current choice has force

- **Cache stability.** A static key → vector mapping caches
  trivially. Compile-time fetch and on-disk cache work because
  the key is enough to identify the answer; no context state to
  carry.
- **Compile-time embedding folding.** Novelty 1 of the paper
  draft (beta reduction to tensor normal form) depends on
  literal embeddings being known at compile time. Context-
  dependent embeddings would push embedding work to runtime
  (or require compile-time context inference, which is hard).
- **Substrate compatibility.** Most of Sutra's targets so far
  (nomic-embed-text, mxbai-embed-large, all-minilm) are
  *sentence* / *passage* embedding models, not contextual-token
  models. They take a string in and produce one vector out —
  there is no per-token-in-context API.
- **Determinism for testing.** Static keys make demos
  reproducible across runs without pinning context.

## Why the alternative has force

- **Word sense.** `bank` (river) ≠ `bank` (money). With static
  embeddings the senses are smushed into one averaged vector and
  Sutra cannot distinguish them. Any program that needs to
  reason about polysemy is structurally blocked at the embedding
  layer.
- **The user's stated goal.** "More contextuality is better" was
  named explicitly. The current implementation is the *opposite
  pole* of this preference, by accident of which substrates were
  cheap to integrate.
- **What modern LLMs offer that sentence-embedders don't.** A
  GPT-2-style model produces context-dependent vectors at every
  layer. Sutra deliberately chose dedicated embedding models
  ("dissection pain isn't worth it" — see the same chat) but
  that choice closed a door rather than just a side route.
- **Some demos likely need it.** A program that classifies
  sentences ("the bank is by the river" → location) genuinely
  cannot work without context. Sutra's surface API forces such
  programs to do their own context plumbing or fail.

## What we don't know

1. **Does any current demo actually exhibit a word-sense bug?**
   The three demos (hello world, fuzzy branching, role-filler
   record) don't stress polysemy. A concrete program that fails
   on a word-sense ambiguity would make this a real blocker; in
   its absence it's a hypothetical issue.
2. **What would the surface syntax look like?** Candidates:
   - `embed("bank", context="river")` — explicit second arg
   - `embed("bank in river context")` — encode context in the
     string and let the substrate handle it
   - `embed_in_context("the bank is by the river", target="bank")`
     — full-sentence input, target-token output
   - A separate `tokenize` / `contextual_embed` primitive
3. **Substrate constraint.** Most dedicated embedding models
   don't expose per-token-in-context output. Sutra would either
   need to add an LLM-internals substrate (the GPT-2 dissection
   route the chat explicitly avoided), use the
   "encode-context-in-the-string" approach (which works on
   dedicated embedders but is fuzzy), or stay static.
4. **Compile-time foldability.** If `embed(string, context)` is
   a runtime call, the literal-folding pass (paper draft novelty
   1) loses one of its biggest wins. The fold could still
   happen if the context is a compile-time constant, but the
   surface API would have to make that distinction visible.
5. **Caching strategy.** The cache key would have to include
   context — possibly a hash of context string. Storage growth
   becomes proportional to (term × context) combinations, which
   could blow up for richly-contextual programs.

## What would resolve it

A demo program that *needs* word-sense disambiguation, written
twice — once in current Sutra (and demonstrated to fail), once
with a proposed contextual-embedding surface (and demonstrated to
work). The proposed surface choice would then be evaluated on
compile-time-foldability, cache impact, and substrate
compatibility against the alternatives above.

Until that demo exists, this is a recorded design gap rather than
a forced decision. Static-keyed embeddings work fine for the
language-correctness work that's currently the focus. The
question becomes load-bearing when Sutra tries to claim it can
handle natural-language reasoning beyond toy domains.

This is **not** blocking current work. It's a known limitation
that should be acknowledged in any public claim about Sutra's
ability to reason over natural-language input.
