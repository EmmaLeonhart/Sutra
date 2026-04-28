# Turing-completeness, null permutation, non-algebraic graph hops

_Excerpt from the original `chats/vsa-operations-explained.md` (lines 295-466). Split into topic-scoped chunks for triage — the original was too large to triage in a single pass._

---

**Human:**

Yeah, I don't know what to make of this. I'm not 100% confident this would work, but what I did tend to get is that I think the logical operations actually are maintained much better than a lot of people think. I think the logical operations are often, like, legitimately work better than people think. Like, it doesn't break down as badly as you might think because things tend to be relatively regular. The main thing I would say here is that I don't know about trying to let the most efficient computational path or discover it. I don't really know what you mean about this, but I have other traversal methods that I've also worked on to be perhaps done in addition to this.

I'm generally much more interested in the embedded, using the embedding space as kind of a space to do certain kinds of computations. What I would really like, and I feel like probably this isn't true, is for this organic embedding space, for a semi-implementation of vector symbolic algebra in this kind of embedding space to be Turing complete, which I don't think it would be.


**Claude:**

Your empirical finding that logical operations hold up better than expected is really interesting -- and honestly plausible, because real embedding spaces have a lot of **implicit regularity** baked in from training data. The geometry isn't random noise, it reflects actual structure in how concepts relate.

---

## On Turing Completeness

You're right to be skeptical, and here's why it almost certainly falls short:

The core requirement for Turing completeness is **unbounded memory and arbitrary conditional branching**. VSA in a fixed-dimensional vector space has:

- **Fixed capacity** -- you can only bundle so many things before the signal degrades

- **No true conditionals** -- you can't say "if this vector resembles X, do Y, else do Z" purely within the algebra

- **No unbounded loops** -- you can't iterate until an arbitrary condition is met

So it's more like a **very powerful finite state machine** than a Turing machine.

---

## But Here's What It Might Actually Be

It could be a form of **circuit complexity** -- like a bounded-depth boolean circuit but over continuous vectors. Which is still enormously useful, just not universal.

---

## The Interesting Middle Ground

What you're describing sounds less like Turing completeness and more like a **differentiable approximation of first-order logic** -- which is actually a well-studied and valuable thing, and your traversal methods on top could potentially patch the gaps.

What are the traversal methods you've been working on?


**Human:**

Yeah, I'm assuming that for people who say that VSA is turn complete, it's always a null permutation. Although I'm just thinking, I think it might be able to be turn complete with my implementation with a couple of sort of non-algebraic equations. I wanted differentiable. What does even mean for something to be different? I don't know if that's your voice or my voice. I don't know the traversal mechanisms here.


**Claude:**

Ha, good question -- "differentiable" is one of those words that gets thrown around a lot. Let me break it down simply.

---

## What Differentiable Actually Means

It just means: **you can compute a gradient through it.**

In practical terms -- if you have an operation f(x), differentiable means you can ask "if I nudge x slightly, how does the output change?" That's all a gradient is. And if every step in your pipeline is differentiable, you can use **backpropagation** to optimize the whole thing end-to-end.

So "differentiable inference" means the inference process itself can be *learned and optimized*, not just executed.

---

## Why It Matters for Your System

Your three operations:

- Addition ✅ trivially differentiable

- Elementwise multiply ✅ trivially differentiable

- Any index shuffle/permutation ❌ not differentiable -- discrete operation

That's actually another reason permutation is awkward for your use case.

---

## On Turing Completeness With Non-Algebraic Extensions

This is genuinely interesting. The classic result is that VSA alone isn't TC, but if you add something like a **stack** or **unbounded external memory** even in a minimal way, you potentially get there. That's basically what Neural Turing Machines did.

What kind of non-algebraic additions were you thinking? Even vaguely -- I'm curious whether your intuition is pointing somewhere real.


**Human:**

The non-neural operations would be the ability to hop to the next spot in the vector space through a kind of graph representation of a vector transformation thing. This is how I model many-to-many relationships, which can't really be done with this algebraically.


**Claude:**

Oh that's clever. So you're essentially using the vector algebra for the **computation within nodes**, but then using a graph structure to handle the **relational topology between them** that the algebra can't express.

---

## What You're Describing

Something like:

- Each node in the graph = a vector or a bound VSA expression

- Edges = transformations between vector states

- Traversal = hopping along edges, where each hop applies some transformation to the current vector

So it's not pure VSA anymore -- it's **VSA plus a routing mechanism**. The algebra handles local computation, the graph handles global structure.

---

## Why This Patches the Turing Completeness Gap

Pure VSA fails TC because it can't do unbounded conditional branching. But if your graph traversal can:

- Choose the next hop **based on the current vector state**

- Loop back to previous nodes

- Have unbounded depth

Then you potentially have the missing ingredient. The graph is acting like the **control flow** that VSA alone lacks.

---

## On Many-to-Many Relationships

This is exactly right -- binding is fundamentally pairwise. You can bundle many bindings together but the relationships collapse into each other. A graph edge can represent a clean many-to-many relationship without that interference problem.

---

## The Really Interesting Question

Is your graph structure **fixed ahead of time**, or does the vector state itself influence which edges get traversed? Because the latter would be much more powerful -- and much closer to something Turing complete.


**Human:**

Basically, there's the loading and unloading and stuff like this. Some people say they just straight up. As far as the graph structure, I'm not entirely sure I would say that I think it would influence the edges that get traversed. Is it really like a pseudo-graph thing used to model many-to-many relationships?

The basic traversal mechanism is that it essentially creates a kind of 10,000-dimensional cone going in a certain direction, coming out of a point in a certain direction. Depending on the exact way that you do it, it'll jump from one to many points or whatever. In the normal one, it will essentially just jump to the first point, but the thing is that this can go to multiple different points because of many relationships. If something were to move on the graph in the graph space, obviously they can move onto whatever points and stuff like that.


**Claude:**

Oh that's a really vivid way to describe it. So the cone is essentially a **directed neighborhood query** in the high-dimensional space -- you're not just asking "what's nearest" like a flat similarity search, you're asking "what's nearest in this specific direction with this specific spread."

---

## What the Cone Is Doing

From a point in 10,000-dimensional space, you're defining:

- A **direction** -- the vector you're coming from or moving toward

- An **angle/spread** -- the width of the cone, which controls how many points fall inside it

- Whatever falls inside that cone = valid next hops

So it's like a **directed beam** rather than a radial search. That's geometrically much richer than cosine similarity because direction AND position both matter.

---

## Why This Handles Many-to-Many Naturally

A single cone can capture multiple destination points simultaneously -- you don't have to pick one. The many-to-many relationship just *is* whatever points fall within the cone. You don't need to encode it algebraically at all.

---

## The Loading/Unloading Thing

This sounds like it might be about **entering and exiting** the VSA algebra -- converting between graph position and vector representation and back. Is that roughly right? Because that boundary between the graph traversal and the algebraic computation is probably the most delicate part of the whole system.


