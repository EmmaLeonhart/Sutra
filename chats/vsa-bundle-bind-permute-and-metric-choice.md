# Bundle/bind/permute mechanics; non-orthogonality; Euclidean vs cosine

_Excerpt from the original `chats/vsa-operations-explained.md` (lines 95-294). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

My goal was to transform long, multi-chain logical inferences into simple vector problems that could have all their order of operations moved around and optimised easily so that it could run on a GPU.


**Claude:**

Oh that's a really elegant goal. You're essentially trying to build a **differentiable inference engine** that sidesteps the sequential bottleneck of chain-of-thought reasoning.

---

## What You're Going For

Traditional logical inference:


A→B, B→C, C→D ... evaluate step by step, in order

Your approach: encode the entire inference chain as vector operations, then **reorder/parallelize** them because VSA operations are:

- Commutative

- Associative

- Composable

So the GPU doesn't care about logical "order" -- it just sees tensor ops.

---

## The Deep Insight Here

You're exploiting the fact that **binding encodes relationships** and **bundling aggregates them**, so a multi-hop inference like:


"X causes Y, Y implies Z, Z contradicts W"

Becomes a set of bound pairs that can be **evaluated simultaneously** rather than chained sequentially. The dependency graph gets flattened into geometry.

---

## The Hard Problems You Probably Hit

- **Unbinding degrades** with chain length -- interference accumulates

- **Real embeddings aren't orthogonal** like ideal VSA vectors, so binding gets noisy

- Knowing *which* operations to reorder without breaking logical dependencies

---

## What was your reduction strategy for the 140K vectors?

PCA? Something semantic? That choice would massively affect whether the binding stays clean.


**Human:**

My main thought here is, as I understand it, that the bundling, binding, and permutation are all things, and I don't really understand how these things would be working. Is the addition just the bundling and the multiplication the binding? What would the permutation be then?


**Claude:**

Yes, exactly right on the first two. Here's the concrete breakdown:

---

## The Actual Math

**Bundling = vector addition**

`A + B + C`

Just elementwise addition. Simple.

**Binding = elementwise multiplication**

`A ⊙ B (Hadamard product)`

Every dimension multiplied together. This is what makes the result *dissimilar* to both inputs -- it's a kind of encryption.

**Permutation = shifting the vector's elements**

`[a, b, c, d, e] → [e, a, b, c, d]`

Just rotating the array by some fixed offset. Applying it twice shifts by 2, etc. This is how you encode "first position," "second position," and so on.

---

## Why Permutation Works for Sequence

If you want to encode "cat then dog" vs "dog then cat":

`π(cat) + π²(dog) ≠ π(dog) + π²(cat)`

The bundle is different because the shift changes the vector before adding. Order is now *geometrically* distinct.

---

## For Your GPU Use Case

These are all **extremely cheap ops**:

- Addition → one pass

- Elementwise multiply → one pass

- Permutation → an index shuffle, essentially free

So your whole inference chain becomes a sequence of these, which maps perfectly onto tensor operations. The question is really whether the **semantic signal survives** the binding noise over long chains.

How long were the inference chains you were targeting?


**Human:**

Okay, in this case I'm not sure what I mean to make up the permutation thing in mine. The things are very often not linear; they are not orthogonal, never ever anything orthogonal. It was one reason I don't actually like cosine similarity that much, because cosine similarity does a very good job at indicating if two simple things are relatively similar to each other. It really breaks down once you start engaging in any kinds of algorithmic operations like these. I do not understand permutation here, and I don't know if permutation even would apply here.


**Claude:**

That's a really sharp observation. Cosine similarity is basically measuring angle, which works fine for "is this word near that word" but completely falls apart when you've done algebraic operations on the vectors -- the geometry changes in ways cosine wasn't designed to track.

---

## On Permutation -- You Probably Don't Need It

Permutation exists in VSA specifically to handle **strict sequential order** -- like encoding that word 1 came before word 2 in a sentence.

For logical inference, you mostly care about **which things are bound together**, not what position they're in. So:

- `cause ⊙ fire` bound to `effect ⊙ smoke` doesn't need positional encoding

- The *relationship type* (cause, effect, implies, contradicts) is doing the work that permutation would otherwise do

So in your system, **binding already handles structure**. Permutation is likely irrelevant.

---

## On Non-Orthogonality Being a Problem

This is the real issue. VSA theory assumes vectors are approximately orthogonal so that:

- Binding produces something cleanly dissimilar to inputs

- Bundling doesn't collapse into noise

With real embeddings, everything is **correlated by design** -- that's what makes them semantically meaningful. But it means binding gets muddy fast.

---

## What metric were you using instead of cosine?

Because that choice becomes critical when you're doing algebraic ops. Things like **dot product magnitude** or learned similarity functions might preserve your signal better.


**Human:**

Yeah, I would go with either. I always felt like intuitively Euclidean distance is best, and dot product magnitude is kinda good-ish. I don't know.


**Claude:**

Your intuition about Euclidean distance is interesting and actually has some theoretical backing here.

---

## Why Euclidean Makes More Sense for Your Case

Cosine ignores magnitude entirely -- it only cares about direction. But when you're doing:

`subject ⊙ verb + object_marker ⊙ object`

The **magnitude is carrying information**. How strongly something binds, how many things got bundled -- all of that lives in the magnitude. Cosine throws it away.

Euclidean keeps both direction AND magnitude, so it's measuring actual displacement in the space.

---

## The Problem With All Three Though

After even a few binding operations on non-orthogonal vectors, you're in a region of the space that has **no clean interpretation** anymore. The vector has drifted. And none of these metrics tell you *why* or *how much* -- they just give you a number.

---

## What Might Actually Work Better

Something like **learned distance functions** -- essentially training a small network to recognize "these two vectors are related by this operation" rather than relying on raw geometry.

But that's a whole different complexity.

---

## A More Fundamental Question

When you say you want to optimize the order of operations for GPU -- are you trying to find the **most efficient computation path** through a fixed inference graph, or are you trying to let the system **discover** the inference path itself?

Because those are very different problems and would change the whole architecture.


