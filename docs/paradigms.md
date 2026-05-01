---
title: Paradigms — Sutra is not Java
description: Sutra reads like Java but compiles to nothing like Java. Three side-by-side examples — assignment, loops, classes — and what changes underneath.
---

# Paradigms — Sutra is not Java

!!! note "Draft — needs review"
    This page is a stub focused on the Java contrast. It will grow as the language matures.

Sutra's surface looks like Java. `var`, `=`, `+=`, curly braces, `class` declarations. To anyone coming from Java, Python, JavaScript, C++, the syntax reads like ordinary imperative-OO code.

It is not that. The point of this page is to make that disconnect visible.

Java is the right comparison because **Java is imperative — it just happens to also be object-oriented.** Variables are memory cells; assignment mutates them; loops have a runtime counter and a back-edge; classes package mutable state behind methods. That whole mental model is what Sutra throws out. Haskell programmers will already recognize most of what's left once it's gone.

Three examples, side by side.

---

## 1. Assignment is not mutation

**Java:**

```java
int n = 0;
n = n + 1;
n = n + 1;
```

`n` names a memory cell. The cell holds 0, then is overwritten with 1, then with 2. The program's story is the sequence of writes to that one address.

**Sutra:**

```sutra
var n : int = 0;
n += 1;
n += 1;
```

There is no cell. The compiler reads the three statements as three distinct values — `n₀ = 0`, `n₁ = n₀ + 1`, `n₂ = n₁ + 1` — that share a name only as a convenience for the human reader. The simplifier folds the chain into one expression and the runtime never holds a "current `n`" anywhere. There is no mutation; there is no underlying address being overwritten.

**Every reassignment in Sutra is, as far as the compiler is concerned, a fresh variable.**

---

## 2. Loops do not have a counter

**Java:**

```java
int n = 0;
for (int i = 0; i < 5; i++) {
    n += i;
}
// n == 10
```

`i` is a memory cell counting from 0 to 4. Each iteration: load `i`, compare to 5, add to `n`, increment `i`, branch back to the top. The program executes the body repeatedly under control of a runtime counter and a back-edge.

**Sutra:**

```sutra
iterative_loop sumToN(5, int n) {
    pass n + iterator;
}

slot int n = 0;
loop sumToN(5, n);
// n == 1 + 2 + 3 + 4 + 5 == 15
```

`iterative_loop sumToN(...)` declares a loop function whose recurrent state is the named param `n`. The body uses `pass` to yield the next iteration's value. There is no runtime counter on the host — the unrolled cell runs five times on the substrate as part of one tensor-op forward pass. `iterator` inside the body is the (1-based) iteration index, substituted in at unroll time.

For data-dependent termination, the form is different:

```sutra
while_loop converge(sim(state, target) < 0.95, vector state) {
    pass R * state;
}

loop converge(sim(state, target) < 0.95, state);
```

A `while_loop` (or `do_while`) compiles to **iterated multiplication by a fixed rotation matrix `R` on the substrate**. The "loop counter" is the angular position on a helix; termination is a similarity check between the rotated state and the target prototype, evaluated as a soft-halt mask on the substrate. Each iteration produces a fresh `state` vector — the previous one is unreferenced. There is no host-side `i++`.

---

## 3. Classes do not package mutable state

**Java:**

```java
class Counter {
    private int count = 0;
    public void increment() { this.count += 1; }
    public int  value()     { return this.count; }
}

Counter c = new Counter();
c.increment();
c.increment();
int v = c.value();  // 2
```

A `Counter` is a bundle of fields. The methods read and mutate the fields. The point of the class is that `count` lives *inside* the object and only the methods can touch it. **Encapsulated mutable state is what the class system is for.**

**Sutra (intended end state — bodies are deferred today):**

```sutra
class Country extends vector {
    function Capital get_capital() {
        return this + capital_of;
    }
}

vector japan = "Japan";
vector tokyo = japan.get_capital();
```

Today the MVP only allows empty class bodies (`class Country extends vector { }`); the method-on-class form above is the deferred design (see [the ontology page](ontology.md) and `todo.md` § "Ontology — make the class system real").

**Sutra structurally cannot package mutable state.** There are no fields. There is no "inside" of an instance to encapsulate. An instance of `Country` is *just* a vector — the same kind of vector everything else in the program is. The class declaration adds no per-instance storage.

What the Sutra class system *does* do is name a region of embedding space, declare claims about that region (which can be wrong), and express behavior as pure vector transformations. `get_capital()` is a single vector add — `this + capital_of` — that generalizes across all countries the embedding model has ever seen, including ones never explicitly enumerated. No constructor, no fields, no mutation.

The shape borrowed from Java; the semantics borrowed from RDF/OWL.

---

## What's actually happening underneath

Java is honest about what's happening on the computer. Variables are names for specific memory cells; the cells live somewhere — on the stack, in a register, at an address — and the program's whole story is the story of which cell holds what value at each point. Every variable is a pointer in the small.

**Sutra has no memory points at all.** It has variables, but they don't refer to memory cells. The compilation target is tensor algebra, and tensor algebra has no notion of a pointer at any level.

The right way to describe what the compiler is doing: **beta-reducing every variable reference into one mathematical expression.** The whole program collapses to a single algebraic expression over vectors — variables get substituted away at compile time and what's left is pure math. This is the lambda-calculus dream taken seriously: a program is an expression, and computation is reduction of that expression.

This is *more radical* than what Haskell does. Haskell is purely functional at the language level, but compiles to a runtime with stack slots, heap cells, and indirection — the language refuses to *expose* the pointers, but the pointers are there. Sutra has no pointers anywhere — surface, runtime, or implementation.

### Non-locality

The deeper foreign thing: information in Sutra is not stored at a place. It is stored as the **coordinates** of a point in a high-dimensional space. A vector value lives across all 768 (or 868) dimensions of the substrate at once, and **no single dimension carries any of the meaning on its own.** You cannot ask "where is the value of `cat`?" because the answer is "spread across all 768 coordinates, with no single one carrying any of it." The information is the geometric structure of the whole point — its position relative to other points, the angles it makes with named directions, its distance from learned prototypes — not the contents of any particular slot.

This is the property mainstream languages most lack. Java's field lives at one offset in one heap object; even Haskell's value, however abstractly the language presents it, lives in a heap cell at one location. In every case, you can in principle point at the storage. **In Sutra, there is no storage to point at.** There is only the position of a point in space and the geometric transformations the program applies to it.

The right analogy: information storage in Sutra is to memory cells as the Turing tape in Conway's Game of Life is to RAM. Conway's Life is famously Turing-complete — you *can* build a computer in it, you *can* store information, you *can* implement a tape — but the "cells" of that computer are gliders and oscillators, patterns of live squares interacting under the rules of the universe. There is no address you can read from; there is only the global state of the grid.

Sutra works the same way. The whole program state, at any moment, is one geometric point in a high-dimensional substrate. **The information is the computation.** A Java program separates state (memory) from operations (instructions) — operations read and write the state. A Sutra program does not. The act of computing *is* the act of moving the state-point through the substrate, and the result of computing *is* the position of that point at the end. There is no read step. There is no write step. There is just geometry.

The simplifier closes the loop on all of this: most of the apparent geometric trajectory factors out at compile time. The compiler sees a chain of binds-and-bundles-and-rotations and folds it into one cached matrix or one final vector. The "writes" never happen at runtime because the answer was known at compile time.

Java's program *is* its memory writes. Sutra's program is an algebraic expression that the compiler resolves geometrically. The syntactic resemblance is convenience, not equivalence.

---

## Related reading

- [What is Sutra?](what-is-sutra.md) — the geometric-compilation pitch.
- [The ontology](ontology.md) — the class system in detail.
- [Loops](loops.md) — how the four declared-function loop kinds lower as substrate-pure RNN cells.
- [Memory without control flow](memory.md) — how binding and bundling replace imperative array/map patterns.
- [Compilation](compilation.md) — how the simplifier strips surface sugar down to polynomial and matrix arithmetic.
