# Embedding choice — JEPA, contextual, GPT-2/3, Wikidata BFS indexing

_Excerpt from the original `chats/vsa-operations-explained.md` (lines 691-922). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

I'll get it later. My vision of this is that I don't think I'm entirely sure how 100% I will do it, because I didn't run it off of JEPA embeddings. I ran it off of just the random embedding models that I managed to come across online that are typically used.

Will it work on large language model embeddings? I don't have JEPA's embeddings, so I'm not 100% sure, but I'm leaning towards probably yes because I'd imagine there would be more granularity in a large lang. I'd imagine JEPA would have more granularity than these.


**Claude:**

That's a reasonable intuition. Let me think through this with you.

---

## Why LLM Embeddings Probably Work Fine

The embeddings you used were likely things like Word2Vec, GloVe, sentence transformers, or similar -- and your VSA operations worked on those. LLM embeddings are:

- **Higher dimensional** typically

- **Contextual** rather than static -- the same word gets different vectors depending on context

- **Much richer** in the relationships they encode

All of those things should make the algebra work *better* not worse, because there's more structure to exploit.

---

## The JEPA Question

JEPA embeddings would be interesting because they're specifically trained to represent **abstract relational structure** between states rather than surface features. So they might be more naturally VSA-friendly.

But honestly your empirical result suggests the VSA structure emerges from **any** sufficiently rich learned representation. JEPA might be cleaner but probably not necessary.

---

## The Contextual Embedding Wrinkle

The one genuinely new challenge with LLM embeddings is that they're contextual. So `dog` in one sentence isn't the same vector as `dog` in another. That means your binding operations are working on **moving targets** rather than fixed concept vectors.

That could either be a problem or actually richer and more expressive depending on how you approach it.

How did you handle word sense in your original implementation?


**Human:**

In my original, I think it's very important that it be contextual. The more granularity of contextualness, the better. Does this mean that the more granularity of a contextualist, the better? In my original implementation, I wasn't able to do anything with word sense, but I explicitly sought out to do so and then found I was unable to do so.


**Claude:**

That's an honest and interesting limitation to hit. Let me think about why that probably happened.

---

## Why Word Sense Was Probably Inaccessible

In static embeddings like Word2Vec or GloVe, `bank` is one vector -- it's the average of all its senses smooshed together. So when you tried to do VSA operations that depend on which *sense* of a word you mean, the vector wasn't giving you that information. It was already collapsed.

You couldn't do word sense disambiguation because **the disambiguation information wasn't there to extract.**

---

## Why LLM Embeddings Fix This

In contextual embeddings, `bank` next to `river` and `bank` next to `money` are **genuinely different vectors**. The sense is already resolved before you even start your VSA operations.

So moving to LLM embeddings doesn't just give you more granularity -- it gives you the specific thing you were missing. The word sense problem potentially **disappears automatically.**

---

## On More Contextuality Being Better

Your intuition is probably right, with one caveat. More contextual means:

- ✅ Richer, more precise bindings

- ✅ Word sense resolved automatically

- ✅ Relationships encoded more accurately

- ⚠️ Harder to build a stable **vocabulary** of concept vectors since nothing is fixed

That last point is the tricky one. How were you indexing your 140K vectors originally?


**Human:**

Oh, yeah, I was originally indexing them using a breadth-first search through Wikidata.


**Claude:**

Oh that's a really clean way to build the vocabulary. Wikidata gives you:

- **Structured relationships** already encoded in the graph

- **Broad coverage** across domains

- **Hierarchical structure** from the BFS ordering

So your 140K vectors weren't random -- they had implicit relational structure from Wikidata's graph baked into the selection. That probably helped your VSA operations work better than you might have expected from a random sample.

---

## The Interesting Synergy

Wikidata's graph structure and your cone traversal mechanism are actually **doing the same thing at different levels**:

- Wikidata encodes what concepts are related

- Your cone traversal navigates those relationships in vector space

So your graph traversal was probably rediscovering structure that was already implicit in how you sampled the vocabulary. They were reinforcing each other.

---

## The LLM Migration Challenge

This is where moving to LLM embeddings gets complicated. With static embeddings you could have a stable index of 140K Wikidata concepts. With contextual embeddings there's no fixed vector for `bank` or `river` -- it depends on context every time.

So you'd need a different indexing strategy. Something like:

- Using LLM embeddings but with **canonical contexts** for each Wikidata entity

- Or abandoning the fixed vocabulary entirely and working dynamically

Which direction feels more natural to you for what you're trying to do?


**Human:**

Yeah, I'm not really sure about it. This is going to be a challenge. I wanted to just do it with GPT-2 or GPT-3 or something, but the issue I've run into is that even models with open weights are kind of relatively difficult to dissect.


**Claude:**

Yeah that's a real practical barrier. Even with open weights, getting at the internal embedding representations in a useful way is surprisingly fiddly.

---

## The Dissection Problem

With GPT-2 for example, you have choices like:

- **Token embeddings** -- the input layer, static, not contextual yet

- **Hidden states** at various layers -- contextual but which layer?

- **Final layer** -- most contextual but also most task-specific

- **Residual stream** at a specific layer -- what mechanistic interpretability people use

None of these are obviously "the right" embedding to use and they all behave differently.

---

## The Layer Question Is Probably Your Biggest Decision

There's decent evidence that:

- **Early layers** encode syntactic structure

- **Middle layers** encode semantic relationships

- **Later layers** encode task-specific predictions

For VSA operations on concepts and relationships, middle layers are probably what you want. But finding exactly which layer requires experimentation.

---

## Easier Starting Points

Rather than dissecting GPT-2 internals, you might get further faster with models that are **explicitly designed to produce meaningful embeddings**:

- `all-mpnet-base-v2` from sentence transformers

- `text-embedding-ada-002` if you have API access

- `E5` or `BGE` embedding models

These are contextual, high quality, and you don't need to dissect anything -- they just output the embedding directly.

Would that kind of model work for what you need, or do you specifically need the internal representations?


**Human:**

Well, I mean, that's what I was trying to do. I mean, I was already using models like that. I guess those are just more advanced than MXBI embed large and stuff like that.


**Claude:**

Ah right, so you were already using proper embedding models like mxbai-embed-large -- that's actually a really solid choice. Those are specifically trained to produce meaningful, rich embedding spaces, which explains why your VSA operations worked as well as they did.

---

## mxbai-embed-large Is Actually Good For This

It's a large embedding model trained with contrastive learning, which means:

- Semantically similar things are **genuinely close** in the space

- Relationships between concepts are **geometrically consistent**

- It has enough dimensions to support your VSA operations without too much interference

That's probably a big part of why binding and unbinding worked -- the space is well-structured enough to support it.

---

## The Models You Mentioned Are All in the Same Family

Things like:

- mxbai-embed-large

- all-mpnet-base-v2

- E5, BGE

These are all dedicated embedding models doing roughly the same job, just with different training approaches and sizes. Newer ones like E5-large or BGE-m3 would give you more dimensions and potentially more granularity but probably similar behavior.

---

## So Your Real Question Is

Whether moving to something like **LLM internal representations** would give you qualitatively different and better VSA behavior -- or whether a good dedicated embedding model is already capturing everything you need.

Honestly given that your operations already work on mxbai, I'm not sure the dissection pain of GPT-2 internals is worth it. What specifically were you hoping to gain from going deeper into an LLM?


