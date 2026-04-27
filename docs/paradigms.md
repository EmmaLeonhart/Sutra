---
title: Paradigms — where Sutra sits
description: How Sutra relates to functional, declarative/logic, object-oriented, and imperative programming, shown through code comparisons.
---

# Paradigms — where Sutra sits

!!! note "Draft — needs review"
    This page is being actively reworked.

People who pick up a new language want to know what shape it is. This page picks one small task per paradigm, writes it in the canonical language for that paradigm, then writes it in Sutra. The goal is to make the influences visible: what Sutra borrowed in shape, and what it changed by moving the substrate from "memory cells / discrete terms" to "vectors in a frozen LLM's embedding space."

The elevator pitch first:

> **Sutra is roughly Haskell + Prolog, with C-family syntax so people can actually read it — and it goes further than either by compiling all the way down to tensor algebra with no pointers anywhere.**

Haskell gives the functional core (pure functions, immutable values, the simplifier-friendly straight-line shape). Prolog gives the declarative-relational surface (programs as relations, predicates as first-class objects, reasoning under uncertainty). The C-family braces and keywords are the surface ergonomics so the result reads like something a working programmer recognizes instead of like a paper. The piece that's *more* radical than either Haskell or Prolog: **both Haskell and Prolog have pointers in their runtime — they just refuse to expose them.** GHC compiles Haskell to a runtime with heap cells and indirection; Prolog implementations have term references everywhere. The user-facing language is pure / relational; the implementation underneath is still a graph of pointers. Sutra has no pointers at any level — surface, runtime, or implementation. The compilation target is tensor algebra, and tensor algebra has no notion of a pointer.

The ranking, going from most-load-bearing to least:

> **Functional > Declarative (Prolog-flavored) > Object-Oriented > Imperative**

Functional is the foundation. Declarative is the surface a programmer reads and writes — and it inherits a strong logic-programming flavor (continuous-space reasoning under uncertainty, closer to Prolog than to Python). Object orientation is real but it's *declarative* OO, not imperative — Sutra's class system names regions of embedding space; it doesn't package mutable state. The imperative-looking surface (`var n += 1;`, `slot x = expr;`, `loop`) is the thinnest layer of all, a convenience over a functional-algebraic core that **has no memory points** (see the imperative section for what that means — and for why it's the hardest thing on this page to internalize).

---

## Functional — Haskell

**Task.** Take a string greeting, look it up among known phrases, return the human-readable name.

**Haskell:**

```haskell
data Phrase = Hello | Goodbye | Question

phraseName :: Phrase -> String
phraseName Hello    = "hello world"
phraseName Goodbye  = "goodbye"
phraseName Question = "are you there"

classify :: String -> Phrase
classify "hello_world"   = Hello
classify "goodbye"       = Goodbye
classify "are_you_there" = Question
classify _               = Question  -- fallback

greet :: String -> String
greet = phraseName . classify
```

**Sutra:**

```sutra
vector v_hello    = "hello_world";
vector v_goodbye  = "goodbye";
vector v_question = "are_you_there";

map<vector, string> PHRASE_NAME = {
    v_hello:    "hello world",
    v_goodbye:  "goodbye",
    v_question: "are you there"
};

function string greet(vector name) {
    vector winner = argmax_cosine(name, [v_hello, v_goodbye, v_question]);
    return PHRASE_NAME[winner];
}
```

**What Sutra borrows from Haskell.** Pure functions; no IO inside the body; the only side effect is the final return value at the program's edge. The function is a composition of two stages (classify, then look up the name), exactly like `phraseName . classify`. Both languages let the simplifier rewrite the body freely because there are no hidden side effects to preserve.

**Where it diverges.** Haskell carries structure with **algebraic data types** and dispatches with **pattern matching**. Sutra carries structure with **vectors in embedding space** and dispatches with **cosine similarity**. The Haskell version needs an exhaustive match plus a fallback case; the Sutra version needs no `_` clause because cosine over a finite codebook always returns *something* — there is no "no match" failure mode, only a weakest-fit answer. This is the gradient-vs-discrete divide showing up in the small.

---

## Declarative — Prolog

**Task.** Express a `capital_of` relation and query it.

**Prolog:**

```prolog
capital(france,  paris).
capital(japan,   tokyo).
capital(brazil,  brasilia).
capital(norway,  oslo).

?- capital(japan, X).
% X = tokyo
```

`capital` is a relation; the `?-` query asks the runtime to find a binding for `X` that makes the relation hold. The whole program is *declarations* of facts and rules — there is no main loop, no "do this then this," no mutable state. Resolution happens by unification + backtracking.

**Sutra:**

```sutra
// The relation lives in the embedding space as a displacement,
// learned from one or more (country, capital) pairs.
vector capital_of = displacement(v_paris, v_france);

// "Query" the relation by applying it geometrically.
vector tokyo_pred = v_japan + capital_of;

// Snap to the nearest candidate.
vector winner = argmax_cosine(
    tokyo_pred,
    [v_tokyo, v_paris, v_brasilia, v_oslo]
);
```

**What Sutra borrows from Prolog.** Programs are sets of *declarations* about how things relate, not procedures for how to compute. Predicates and relations are first-class — `capital_of` in Sutra plays the same role as `capital/2` in Prolog: a named thing the language treats as a primary object you can apply, compose, and reason about. Both languages support **reasoning under uncertainty** — Prolog through extensions like ProbLog and Stochastic Logic Programming, Sutra through fuzzy similarity scores native to the substrate. Both default to **open-world semantics**: Prolog's open-world variants and Sutra's embedding-inherited semantics both assume there's more out there than what's been asserted.

**Where it diverges.** Prolog resolves queries with **unification + backtracking** over discrete terms. Sutra resolves queries with **vector arithmetic + nearest-neighbor** over continuous embeddings. Two consequences:

- **Generalization.** Prolog needs a `capital(X, Y)` fact for every pair you want to answer. Sutra needs a *single* `capital_of` displacement vector and the query generalizes — even if `capital(germany, _)` was never asserted, `v_germany + capital_of` lands somewhere in the capital region of embedding space and `argmax_cosine` returns the nearest candidate.
- **Truth shape.** Prolog's truth is Boolean (extensions: probabilistic). Sutra's truth is graded `[-1, +1]` by default — when you ask "is Tokyo the capital of Japan?" you get back *how true*, not *whether*. The `is_true` operator polarizes the answer toward ±1 without ever binarizing it.

The same comparison applies in muted form to **Datalog**, **Answer Set Programming**, and **SQL** — all are declarative-relational languages over discrete tuples, all share the "describe what, not how" shape, and all differ from Sutra in the same direction (discrete substrate, exact resolution, Boolean or 3-valued truth).

---

## Object-oriented — Java

**Task.** Model a country with a method that returns its capital.

**Java:**

```java
class Country {
    private String name;
    private String capital;

    public Country(String name, String capital) {
        this.name    = name;
        this.capital = capital;
    }

    public String getCapital() {
        return this.capital;
    }
}

Country japan = new Country("Japan", "Tokyo");
String c = japan.getCapital();  // "Tokyo"
```

A `Country` is a bundle of fields. Construction sets the fields; the method reads them. The class encapsulates *state* (the fields) behind an interface (the methods).

**Sutra (intended end state — bodies are deferred today):**

```sutra
class Country extends vector {
    function Capital get_capital() {
        return this + capital_of;
    }
}

vector japan = "Japan";        // an instance is just a vector
vector tokyo = japan.get_capital();
```

Today the MVP only allows empty class bodies (`class Country extends vector { }`); the method-on-class form above is the deferred design (see [the ontology page](ontology.md) and `todo.md` § "Ontology — make the class system real"). The empty-body form is enough to *name* `Country` as a region of embedding space; the bodies will add behavior.

**What Sutra borrows from Java.** Class declarations, single inheritance, the dotted-method-call surface. Going from `class Country` to `class Country extends vector` to a subclass like `class IslandNation extends Country` reads the same way as Java. The ontology grows the way a Java class hierarchy grows — by extending an existing class, by introducing new ones beside it.

**Where it diverges — and the honest version.**

Classical OO's signature feature is **encapsulated mutable state behind a method interface**. A Java `Counter` packages an `int count` field with `increment()` and `value()` methods that read and mutate it. The point of the class is that the state lives *inside* the object and only the methods can touch it.

**Sutra structurally cannot do this.** There are no fields to mutate. There is no "inside" of an instance to encapsulate. An instance of `Country` is *just* a vector — the same kind of vector everything else in the program is. The class declaration adds no per-instance storage. (See the next section on memory points for why.)

What Sutra's class system *does* do is something Java cannot do as cheaply:

- **Name a region of embedding space.** `class Country` asserts that there's a coherent geometric region the model has already organized; the declaration names it.
- **Make claims about that region that can be wrong.** A Java `Dog` class is true by fiat. A Sutra `Dog` class makes a claim about *where in embedding space `Dog` sits*, and that claim can disagree with the model's clustering, with another model's, or with reality. Class membership has truth conditions.
- **Express behavior as pure vector transformations.** `get_capital()` is a single vector add — `this + capital_of` — that generalizes across all countries the embedding model has ever seen, including ones that were never in the seed pairs. No per-country case analysis, no lookup table, no constructor.

So the right way to read the OO comparison is not "Sutra is OO with a different syntax." It's that **Java and Sutra are doing different things with the word "class"** — Java is packaging mutable state with the methods that mutate it; Sutra is naming geometric regions and declaring the pure transformations that act on them. Neither one does what the other does. The shape borrowed from Java; the semantics borrowed from RDF/OWL.

---

## Imperative — C

**This is the hardest section on the page to internalize, and it's the most important.** Sutra's surface looks imperative — `var`, `+=`, `loop`, curly braces. To anyone coming from C, Java, Python, JavaScript, Rust, anything in that family, the surface reads like normal imperative code. It is not. The disconnect between how it reads and what it actually compiles to is the deepest single foreign thing about the language, and the rest of the divergences on this page (no constructors, no mutable fields, fuzzy truth) are smaller in comparison.

C is the right counterpoint because C is honest about what's happening on the computer. Almost everything C *is* about, Sutra *isn't*.

**Task.** Increment a variable five times.

**C:**

```c
int n = 0;
for (int i = 0; i < 5; i++) {
    n++;
}
// n == 5
```

A counter `i` lives in memory and takes values 0 through 4. A second cell `n` gets mutated each iteration. Each `n++` is a load, an add, a store at a known address. The program *is* this sequence of memory operations; running the program means executing them in order.

**Sutra:**

```sutra
var n : int = 0;
loop[5] {
    n += 1;
}
```

That's roughly what the surface looks like. (For "use the iteration index in the body," the language is going to grow an `iterator` keyword inside `loop[N]` — see the [loops doc](loops.md) for that design.)

What the compiler does:

- `loop[5] { ... }` *unrolls at compile time*. The emitted code is the body five times in sequence — no runtime counter, no comparison, no back-edge.
- `n += 1` does not mutate a memory cell. It rebinds the name `n` to a fresh vector representing the new value.
- The whole program lowers to straight-line tensor work that the simplifier can fuse. There is no host-side loop in the emitted code at all — and the five additions will likely be folded into `n + 5` before the runtime ever runs.

For data-dependent termination, the form is different:

```sutra
loop(state ~ target) {
    state = R * state;
}
```

This `loop(condition)` lowers to **iterated multiplication by a fixed rotation matrix `R` on the substrate**. The "loop counter" is the angular position on a helix; termination is a similarity check between the rotated state and the target prototype. Still no host-side `i++`.

**What Sutra borrows from C.** Surface ergonomics. `var`, `+=`, `loop`, the curly braces. People know what these mean and the language doesn't fight that intuition.

### Where it diverges — Sutra has no memory points

This is the deepest claim on the page.

C is honest about what's happening on the computer. `i` and `n` are names for specific cells; the cells live somewhere — on the stack, in a register, at an address — and the program's whole story is the story of which cell holds what value at each point in execution. Every variable is a pointer in the small.

**Sutra has no memory points at all.** It has variables, but the variables don't refer to memory cells. The language operates in a state of weirdness about where information lives.

The first piece of this is the part imperative programmers find hardest to swallow: **every reassignment in Sutra is a fresh variable as far as the compiler is concerned.** When you write

```sutra
var n : int = 0;
n += 1;
n += 1;
```

an imperative reading is "one variable `n`, mutated three times." That's not what's happening. Conceptually, this is three separate values — call them `n₀ = 0`, `n₁ = n₀ + 1`, `n₂ = n₁ + 1` — that share a name only as a convenience for the human reader. The compiler factors the chain into a straight-line algebraic expression and the runtime never holds a "current `n`" in any cell. There is no mutation; there is no underlying address being overwritten; the sequence of `n`s is a sequence of distinct values related by addition.

This is *more radical* than what either Haskell or Prolog do. Both are, at the language level, declarative — Haskell is purely functional, Prolog is purely relational. But both compile to runtimes that have pointers under the hood: GHC has stack slots, heap cells, and indirection; Prolog implementations have term references everywhere. The languages refuse to *expose* the pointers, but the pointers are there.

Sutra's compilation target is tensor algebra, and tensor algebra has no notion of a pointer at any level. The right way to describe what the compiler is doing: **beta-reducing every variable reference into one mathematical expression.** The whole program collapses to a single algebraic expression over vectors — variables get substituted away at compile time and what's left is pure math. This is the lambda-calculus dream taken seriously: a program is an expression, and computation is reduction of that expression. There is no "under the hood" with cells. The runtime values are vectors that get added and rotated and bundled, and that's it.

The CPU contrast makes the shift concrete. **In a CPU, the value of a variable is bits at a specific memory address.** The variable name is a reference to that address; the value is what's stored there; reading and writing are accesses to that location. **In Sutra, the value of a variable is the coordinates of a point in the substrate.** There is no address. There is no location. The "value" is a position in a high-dimensional space, and the program advances by transforming that position geometrically.

The rest of the no-memory-points story:

- The `loop[5]` doesn't have a counter at runtime. The unrolled bodies have no shared variable connecting them — each one is independent.
- `n += 1` doesn't mutate a memory cell. It rebinds the name `n` to a fresh vector. There is no cell to point at and say "the value of `n` lives here."
- Even the `slot` primitive — Sutra's nearest thing to a writable cell — **is not a memory point either**. A `slot` write is a 2D-Givens rotation on a disjoint plane in the synthetic subspace. The "address" being written to is *unrooted*: it doesn't correspond to a memory location, it corresponds to a geometric operation. The sequence `slot x = a; slot x = b; slot x = a;` produces the same final substrate state as a single `slot x = a;` — rotations compose and the round trip cancels.
- The one place the language has anything resembling time-evolving state is the `loop(condition)` eigenrotation form — `state = R * state` iterated until a similarity threshold is met. Even there, each iteration produces a *fresh* `state` vector; the previous one is unreferenced. It's a sequence of distinct vectors related by rotation, not one cell that gets overwritten N times. That's as close as Sutra gets to imperative state, and it's still not a memory cell.

### The deepest weirdness: non-locality

If the no-pointers thing is the headline, **non-locality is the part that will mess with people most.** People can mostly swallow "no pointers" by squinting at it as "a stricter functional language." Non-locality has fewer analogs in mainstream programming, and it's the thing that doesn't squint away.

Information in Sutra is not stored at a place. It is stored as the **coordinates** of a point in a high-dimensional space. A vector value lives across all 768 (or 868) dimensions of the substrate at once, and **no single dimension carries any of the meaning on its own.** You cannot ask "where is the value of `cat`?" because the answer is "spread across all 768 coordinates, with no single coordinate carrying any of it." The information is the geometric structure of the whole point — its position relative to other points, the angles it makes with named directions, its distance from learned prototypes — not the contents of any particular slot.

This is the property mainstream languages most lack. C's variable lives at one address; Java's field lives at one offset in one heap object; even Haskell's value, however abstractly the language presents it, lives in a heap cell at one location. In every case, you can in principle point at the storage. **In Sutra, there is no storage to point at.** There is only the position of a point in space and the geometric transformations the program applies to it.

That's why the earlier framing — "the information is the computation" — is the literal selling point. Information is not stored in places that the computation reads and writes. Information *is* the position of the point, and computation *is* the geometric trajectory of that point through the substrate. The two are not separable; the program does not "do something to" some stored data, it moves a single coordinate-bundle through a sequence of transformations and the answer is wherever the bundle ends up.

The right analogy: **information storage in Sutra is to memory cells as the Turing tape in Conway's Game of Life is to RAM.** Conway's Game of Life is famously Turing-complete — you *can* build a computer in it, you *can* store information, you *can* implement a tape. But the "cells" of that computer are not memory cells in any conventional sense. They are gliders and oscillators and patterns of live squares interacting under the rules of the universe. There is no address you can read from; there is only the global state of the grid and the way information moves through it.

Sutra's information storage works the same way. Every value in the program — every vector — is a single coordinate point in a high-dimensional substrate. The *whole* program state, at any given moment, is one geometric point in that space. Information is encoded **diffusely and non-locally**: no single coordinate "is" a piece of information; the information is a geometric structure spread across all 768 (or 868) dimensions of the point at once. You cannot point at a cell, because there are no cells. There is just the position of the point and the geometric transformations the program applies to it.

This is the selling point Sutra is built around: **the information is the computation.** A C program separates state (memory) from operations (instructions); the operations read and write the state. A Sutra program does not — the act of computing *is* the act of moving the state-point through the substrate, and the result of computing *is* the position of that point at the end. There is no read step. There is no write step. There is just geometry.

The simplifier closes the loop on all of this: most of the apparent geometric trajectory factors out at compile time. The compiler sees a chain of binds-and-bundles-and-rotations and folds it into one cached matrix or one final vector. The "writes" never happen at runtime because the answer was known at compile time. So when you see something in a Sutra program that looks like a write or a counter, the right mental model is not "this stores a value somewhere." The right mental model is "this contributes a geometric step in the algebraic expression the compiler will resolve before the runtime ever touches a value."

C's program *is* its memory writes. Sutra's program is an algebraic expression that the compiler resolves geometrically. They are different *kinds* of artifact; the syntactic resemblance is convenience, not equivalence.

---

## So what is Sutra, in one sentence?

Sutra is **Haskell + Prolog with C-family syntax, compiled all the way down to tensor algebra with no pointers anywhere.** Or, more carefully: a functional language with a strong declarative / logic-programming bias, a real-but-declarative class system, and an intentionally thin imperative surface — all of which lower to tensor operations on a frozen-LLM embedding substrate at compile time, with no memory points at runtime.

The paradigm ordering (functional > declarative+logic > OO > imperative) is the order in which each layer constrains the others. The functional core is load-bearing for compilation; remove it and the simplifier collapses. The declarative / logic surface is load-bearing for semantics; remove it and the language becomes syntax without a story. The OO layer organizes large programs over many embedding regions; remove it and you can still compute, but you can't structure. The imperative surface is convenience and recognition — it's the layer that makes the language *readable* by people whose first language wasn't Haskell or Prolog — but it doesn't add any computational power, and the simplifier strips it all the way down before runtime ever runs.

---

## Related reading

- [What is Sutra?](what-is-sutra.md) — the geometric-compilation pitch.
- [The ontology](ontology.md) — the class system and the inverse-of-OOP framing in detail.
- [Loops](loops.md) — how `loop[N]` and `loop(condition)` lower.
- [Memory without control flow](memory.md) — how binding and bundling replace the control flow patterns imperative languages use for arrays and maps.
- [Compilation](compilation.md) — how the simplifier strips surface sugar down to polynomial and matrix arithmetic.
