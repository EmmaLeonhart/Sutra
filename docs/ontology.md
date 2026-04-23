# The ontology

Sutra has a class system. Everything in the language is a vector, and new classes inherit from `vector` or from each other. That much is conventional object-oriented programming.

What makes it unconventional is **what the hierarchy is for.** In a typical OOP language, the class tree is a *code organization* tool — you put shared behavior on a parent class and specializations on children. In Sutra, the class tree is a map of *what kinds of things can exist in the vector space*. Each class is a claim about which axes of the extended-state vector carry meaning for values of that class, and which operations are valid on them.

That's an ontology, not a type system. The word isn't borrowed metaphorically — it's the same sense used in knowledge representation (OWL, RDF), information science, and formal philosophy: a structured account of what exists and how the things that exist relate. Sutra's "class tree" is a small ontology, and it's designed to connect to larger external ontologies through the embedding layer.

This page walks through the ontology top-down.

---

## The root: vector

```mermaid
graph TD
    V[vector]
    V --> NUM[numeric family]
    V --> TRU[truth family]
    V --> CHR[char]
    V --> SEM[embeddings / semantic vectors]
    V --> USER[user-defined classes]

    NUM --> INT[int]
    NUM --> FLT[float]
    NUM --> CPX[complex]

    TRU --> BOOL[bool]
    TRU --> FUZ[fuzzy]
    TRU --> TRIT[trit]

    SEM --> TXT["text<br/>via LLM embedding"]
    SEM --> IMG["image / video parts<br/>via vision embedding"]
    SEM --> MOL["molecules<br/>via chemical embedding"]
    SEM --> OTHER["…anything else with an<br/>embedding model"]

    USER --> EX1[role: agent]
    USER --> EX2[relation: is_parent_of]
    USER --> EX3[object schemas,<br/>learned categories, …]

    classDef root fill:#512da8,color:#fff,stroke:#311b92
    classDef fam fill:#7e57c2,color:#fff,stroke:#512da8
    classDef leaf fill:#d1c4e9,color:#311b92,stroke:#512da8
    classDef embed fill:#ffb74d,color:#311b92,stroke:#f57c00

    class V root
    class NUM,TRU,CHR,SEM,USER fam
    class INT,FLT,CPX,BOOL,FUZ,TRIT,EX1,EX2,EX3 leaf
    class TXT,IMG,MOL,OTHER embed
```

Every node in this tree is a vector. What changes going down the tree is **which parts of the vector carry meaning** and **which operations are defined on it**. The `vector` itself is the bare substrate — a flat array of real numbers (868-dimensional in the demo) — with no semantic claims about what any of it means. Every subclass is a commitment about structure.

---

## Internal vector types — the left side of the tree

These are the classes where the language knows the full interpretation of every relevant axis.

### Numeric family (`int`, `float`, `complex`)

Values occupy the real and imaginary synthetic axes (`synthetic[0]` and `synthetic[1]`). The class tag tells the compiler what to permit:

- `int` — real axis only; fractional and imaginary literals are rejected.
- `float` — real axis only; fractional literals allowed.
- `complex` — both real and imaginary axes.

One multiplication rule (the complex product) covers all three — when the imaginary parts are zero it reduces to scalar multiplication. See [Numeric math](numeric-math.md) for the details.

### Truth family (`bool`, `fuzzy`, `trit`)

Values occupy the truth axis (`synthetic[2]`). All three are views of the same coordinate, differentiated by what defuzzification does:

- `bool` — expected at the poles (±1); `defuzzify` snaps there.
- `fuzzy` — any value in `[-1, +1]`; `defuzzify` still polarizes to the two poles.
- `trit` — any value in `[-1, +1]` with `0` as a first-class neutral attractor; `defuzzify_trit` preserves the middle.

See [Primitive classes](primitive-classes.md) and [Logical operations](logical-operations.md) for the details.

### `char`

A character is an integer with a flag: code point at the real axis (same as `int`), and a `1.0` at a dedicated char-flag axis (`synthetic[3]`) that lets downstream code distinguish `'a'` from the plain int `97`.

---

## Embeddings — the right side of the tree

This is the interesting half.

An **embedding** is a vector produced by a model that has been trained to place similar things near each other in some high-dimensional space. Text embeddings are the most familiar kind — a model like [nomic-embed-text](https://docs.nomic.ai/embeddings/) takes a string and produces a 768-dimensional vector such that `"cat"` and `"kitten"` are close together in the space, and both are far from `"algebra"`.

But text is just the most convenient example. Models exist that do the same thing for:

- **Images** (CLIP, SigLIP) — a picture of a cat and the word "cat" land near each other.
- **Parts of images** (SAM-style segment embeddings) — a specific object in a picture gets its own vector.
- **Video clips** (VideoCLIP and successors) — a motion pattern embedded as a vector.
- **Audio** (Whisper-style acoustic embeddings).
- **Molecules** (MolFormer, ChemBERTa) — a chemical structure as a vector, with similar structures near each other.
- **Code** (StarCoder-style code embeddings) — semantically-equivalent code snippets cluster.
- **Proteins**, **genomes**, **brain recordings** — anywhere a sufficiently-trained model exists.

For Sutra, all of these are the same kind of thing: they're *branches of the ontology tree under the `vector` root that don't have a specific internal interpretation the way `int` or `bool` do*. Instead, they inherit their structure from whatever model produced them, and the language knows how to operate on them — similarity, binding, bundling — via the substrate operations.

### The semantic claim

This is where the language makes a strong statement: **an embedding is a representation of the thing itself, not of a name for the thing.**

When Sutra writes

```c
vector cat = "cat";
```

the `vector` variable holds a vector in the frozen LLM's embedding space. That vector isn't pointing at the word "cat" as a string — it's pointing at a location in a geometric space that the LLM has arranged so that "cat-nearby" things (kittens, meows, whiskers) are literally geometrically nearby. The variable is the closest thing this language has to "the concept of a cat, as a value."

This is why every operation in the language works on vectors: there's no "looking things up in a dictionary by string key" layer, because the string never entered the language in the first place. The value is always geometric, and the operations are always geometric.

### What's open about embeddings

We don't know the best way to use embeddings in a programming language yet. That's honest: this language is an exploration of what *becomes possible* when a programming language can directly manipulate vectors in a frozen LLM's space, and the exploration is early.

What we have committed to:

- The four-operation core — `bind`, `unbind`, `bundle`, `similarity` — is well-understood from the VSA / hyperdimensional-computing literature and carries over essentially unchanged to frozen-LLM vectors.
- Cosine similarity between embeddings is a useful truth signal (this is what makes `a == b` work as a fuzzy-valued operator).
- Control flow through embeddings can be written as algebra rather than branching (see [Memory without control flow](memory.md)).

What we're still figuring out:

- How much structure in the embedding space is *reliably usable* vs. an artifact of a specific model. The cartography work in the sibling repo has empirical findings here, some of which hold up across models and some of which don't.
- Which VSA operations keep working when the vectors are trained embeddings instead of random hyperdimensional vectors. Some work beautifully; some fall apart. We know binding and bundling carry over; we know rotation-as-role does in 768-d; we're less sure about some of the more exotic primitives.
- How to make the language's type system aware of *which* embedding space a value lives in. A nomic vector and a CLIP vector shouldn't be mixed silently. The current implementation has one default model and a single-substrate compile-time declaration; a richer multi-substrate type system is on the roadmap.

The ontology is a *structural* commitment, not a semantic one. The structure is: vector → (internal primitive classes) and (embedding classes). The specific ways you use the embedding branch are still being invented.

---

## User-defined classes

A Sutra program can define its own classes that inherit from `vector` or from any existing class. A class declaration is essentially a statement about which axes of the vector carry meaning for values of that class, plus any operators the class overrides.

Three categories show up repeatedly:

1. **Roles** — things like `agent`, `location`, `object-of-sentence`. A role is a class whose values are rotation matrices (or, in the future, learned matrices) that act on other vectors via `bind`. `role Agent = ...; bind(Agent, cat)` places `cat` in the agent slot.
2. **Relations** — `is_parent_of`, `causes`, `implies-conceptually`. A relation is a learned transformation that takes one vector and produces another. This is the "predicate" layer of the ontology.
3. **Schemas** — compound structures like `Person { name, age, occupation }`. These are bundles of role-filler bindings, and the language treats them as vectors that can be bound, unbound, and compared like any other vector.

This is where Sutra's ontology connects to traditional knowledge-representation ontologies. OWL-style `Class(Person) hasPart(name, string) hasPart(age, int)` translates directly into a Sutra class with role-bindings for each field. The difference is that Sutra's classes live in embedding space, so a `Person` value doesn't just *satisfy* the schema — it's geometrically located near other `Person`s, and operations like similarity between two `Person` values are meaningful.

We are early in exploring this.

---

## Why call it an ontology

To circle back to the naming question:

- A **type system** tells the compiler which operations it's allowed to emit.
- A **class hierarchy** tells the programmer how to organize code.
- An **ontology** tells both what *kinds of things can exist* in a representation, and how those kinds *relate* to each other.

Sutra's class tree does the first two by virtue of being a type system + class hierarchy in the usual programming sense. It does the third because the representation IS vectors in embedding space, and the tree is describing which regions of that space are "allowed" for each class. The numeric family occupies two specific axes; the truth family occupies one; embeddings occupy the semantic block; user-defined classes carve out further structure via role bindings.

"Ontology" captures that third sense. "Type hierarchy" or "class hierarchy" doesn't — those words assume the hierarchy is just organizing syntax. Sutra's hierarchy is organizing *geometry*, and geometry in embedding space means "the structure of what exists."

---

## Related reading

- [Primitive classes](primitive-classes.md) — the numeric and truth families in detail.
- [Logical operations](logical-operations.md) — the truth-family arithmetic.
- [Numeric math](numeric-math.md) — the numeric-family arithmetic.
- [Memory without control flow](memory.md) — how binding / bundling replace traditional array and hashmap control flow, using only the substrate's algebra.
- [Hello Sutra tutorial](tutorials/01-hello-sutra.md) — a first program using the embedding layer.
