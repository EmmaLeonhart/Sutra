# VSA primitives explained + 140K-vector methodology

_Excerpt from the original `chats/vsa-operations-explained.md` (lines 1-94). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

# Vector symbolic architecture operations


**Human:**

Explain these and how they work


**Claude:**

# Vector Symbolic Architecture (VSA) Operations

These are the three core operations used in **Vector Symbolic Architectures** -- a framework for representing and manipulating structured information using high-dimensional vectors.

## Bundling (+)

**"This AND this"** -- combines multiple vectors into one by adding them together (superposition). The result is *similar* to all the inputs, which means you can later check "is concept X in this bundle?" It's like creating a set or bag of items. Commutative and associative, so order doesn't matter.


Example: `red + circle + small` → a vector that resembles all three concepts

## Binding (⊗)

**"This WITH this"** -- pairs two vectors together, usually via element-wise multiplication or a similar operation. The result is *dissimilar* to both inputs, creating a unique "token" that only makes sense when you unbind it. This is how you encode relationships or key-value pairs.


Example: `color ⊗ red` → encodes "the color IS red" -- distinct from both `color` and `red` alone

## Permutation (π)

**"This THEN this"** -- reorders the elements of a vector to encode **sequence and order**. Applying permutation once means "position 1," twice means "position 2," etc. This is how VSA handles temporal or sequential structure.


Example: `π(word1) + π²(word2) + π³(word3)` → encodes a sentence in order

---

## Why This Matters

Together, these three operations let you build complex structured representations -- like sentences, graphs, or records -- entirely within a fixed-size vector, enabling **neurally-plausible symbolic reasoning**.


**Human:**

I was attempting to do a thing with real-world, non-trained vectors that I just found in embedding models. I had a methodology where this was like 140,000 vector points, and I reduced it. Basically, the way that I did it is that the sentences would be subject plus verb plus object marker times object, so what kinds of things would actually be


**Claude:**

This is a really interesting application! You're essentially trying to do **VSA-style compositional encoding** using *real* pretrained embeddings rather than random hypervectors. Let me make sure I understand what you built:

---

## Your Methodology (as I understand it)

You encoded sentences as:

**subject ⊗ verb + object_marker ⊗ object**

So something like:


"The dog chases the cat"
→ `dog ⊗ chases + OBJ ⊗ cat`

With 140K vectors reduced down to something workable.

---

## What This Would Actually Capture

Since your vectors come from a **real embedding model**, they carry semantic geometry, so your compositions would be meaningful in ways random VSA vectors aren't:

- **Synonyms cluster** -- `dog ⊗ chases` and `dog ⊗ pursues` would be close

- **Role swapping is detectable** -- `cat ⊗ chases + OBJ ⊗ dog` would be measurably different

- **Analogical structure** -- the binding relationships might generalize

---

## What were you trying to do with it?

Were you trying to:

- **Query** the space ("find sentences similar to X")?

- **Decode** back to words?

- Build some kind of **knowledge retrieval** system?

That would help me understand what kinds of results or problems you were hitting.


