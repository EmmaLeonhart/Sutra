---
title: "Paradigms: familiar syntax, foreign semantics"
description: Sutra's syntax reads like an imperative language, but it compiles to nothing like one. Three side-by-side examples — assignment, loops, classes — show what changes underneath.
---

# Paradigms: familiar syntax, foreign semantics

Sutra's surface looks like an ordinary imperative-OO language: `var`, `=`, `+=`, curly braces, `class` declarations. To anyone coming from Java, Python, JavaScript, or C++, it reads like familiar code. Underneath, it is something else entirely — and this page shows where the two come apart.

Imperative languages make the cleanest comparison, so the examples below put Sutra next to Java. The imperative model is built on memory: variables are cells, assignment mutates them, loops run a counter and a back-edge, and classes package mutable state behind methods. Sutra keeps the syntax and discards that whole model — and once it's gone, what remains looks a lot like a purely functional language.

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
for (int i = 1; i <= 5; i++) {
    n += i;
}
// n == 15
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

**Sutra:**

```sutra
class Counter extends vector {
    field int count;

    method void bump(int amount) {
        return this + embed("bump");
    }
}

function int main() {
    Counter c = embed("counter");
    c.count = 2;
    return c.count;  // 2
}
```

The surface looks like Java — fields, methods, dot-access. The semantics are not. A field is not a memory slot inside the object: `c.count = 2` is an *augmented assignment* that lowers to `c = axon_add(c, "count", 2)` — it produces a **fresh vector** with the value rotation-bound into it, exactly the way every reassignment in §1 produces a fresh value. A method call statement `c.bump(1);` likewise rewrites to `c = Counter.bump(c, 1)`. Nothing is ever overwritten; there is no cell.

**Sutra structurally cannot package a mutable cell.** An instance of `Counter` is *just* a vector — the same kind of vector everything else in the program is. What looks like encapsulated mutable state is a pure transformation chain over immutable values, with the field storage riding along *inside the vector itself* via rotation binding.

What the Sutra class system *does* do is name a region of embedding space, declare claims about that region (which can be wrong), and express behavior as pure vector transformations that generalize across everything the embedding model has ever seen (see [the ontology page](ontology.md)). No constructor, no hidden storage, no mutation — just rebinding.

The shape borrowed from Java; the semantics borrowed from RDF/OWL.

---

## 4. Tail recursion is a loop function (the Haskell / OCaml contrast)

Functional languages express iteration as tail recursion with an accumulator. Sutra has the
same model — spelled as a declared loop function whose state parameters are the accumulator,
and whose `pass` is the tail call.

**Haskell:**

```haskell
go acc n | n <= 0    = acc
         | n == 1    = acc
         | otherwise = go (acc + n) (n - 1)
```

**Sutra:**

```sutra
while_loop go((n > 0) && (n != 1), int acc, int n) {
    acc = acc + n;
    pass acc, n - 1;
}

function int main() {
    (acc, n) = loop go((3 > 0) && (3 != 1), 0, 3);
    return acc;                                   // 5
}
```

The guards become the loop condition (negated — *continue while no base case matches*), the
recursive call's arguments become the `pass` list, and the base-case return is just the final
state, bound here with the tuple-destructure call form. Multi-value `pass` assigns in
parallel, exactly like simultaneous recursion equations — Fibonacci is literally its
recurrence:

```sutra
iterative_loop fib(8, int a, int b) {
    pass b, a + b;
}

function int main() {
    (a, b) = loop fib(8, 1, 1);
    return a;                                     // 34
}
```

The difference from Haskell is what the "call" compiles to. There is no call stack and no
branch: the loop is a fixed tensor cell, the guards evaluate as signed truth values on the
substrate, and a soft-halt mask freezes the state when the condition goes false. Tail
recursion isn't *optimized into* a loop, as in a functional compiler's TCO pass — the loop
function *is* the recurrence, stated directly.

Both programs above compile and run today with exactly the outputs shown.

---

## What's actually happening underneath

Java is explicit about what's happening on the computer. Variables are names for specific memory cells; the cells live somewhere — on the stack, in a register, at an address — and the program's whole story is the story of which cell holds what value at each point. Every variable is a pointer in the small.

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

## Literal-driven compilation: where Sutra sits in the design space

Sutra leans on literals more aggressively than most languages — string literals fold into embedded vectors at compile time, integer and complex literals bake into synthetic-axis writes, role names become precomputed Haar rotations, the codebook crystallizes into an `.sdb` that ships with the artifact. The runtime never sees most of the program's "data" because the data was absorbed into the weights during compilation. A simple `is this a cat?` check doesn't store the cat embedding alongside the code — the cat embedding *is* part of the evaluation function.

This is rarer than it sounds. Most languages with rich literal systems (Python lists, JavaScript objects, Clojure data structures) treat literals as ergonomics, not as a performance steering mechanism — a Python list literal `[1, 2, 3]` is still a mutable runtime allocation, and the compiler can't fold it because it could be modified later. The languages that genuinely use literals as compile-time leverage are a smaller and more interesting group:

- **Zig** — `comptime`-known values are first class. The compiler folds and specializes aggressively when a value is marked `comptime`. Sutra's `.su` literals are implicitly comptime; Zig requires the annotation but has the same philosophy.
- **Forth / Factor** — values on the stack at compile time get folded as a side effect of the concatenative evaluation model. Different mechanism, same outcome: literals become weight, not runtime data.
- **SQL** — query planners treat literals in `WHERE` clauses structurally, picking different indices and join orders than they would for bound parameters. Probably the closest mainstream analogue: literals carry information the engine can use that runtime values cannot.
- **APL / J / Q-kdb+** — array-oriented languages with rich literal forms specifically because their entire model is built around dense, statically-shaped data. Literals carry shape information the compiler can exploit. This is the closest analogue given Sutra's vectors-and-matrices-as-substrate model. (Sutra's user-facing programming model differs — APL exposes arrays as the manipulation surface, while Sutra hides them as the execution substrate — but the literal-leverage philosophy is the same.)

The theoretical ancestor is **partial evaluation** research from the 1980s and 90s, particularly the Futamura projections, which formalized "what can a compiler do when it commits to a value being statically known." Sutra is a partial evaluator in the Futamura sense: it specializes the program against compile-time-known embeddings, role names, and codebook entries, and emits the residual as a tensor graph.

The cost of leaning this hard on literals is that runtime-computed values are a second-class concern by design — you steer users toward expressing things as literals where possible, and they pay a noticeably different price when they can't. Most language designers reject that tradeoff in favor of generality (a construct should work the same whether the value is known at compile time or not). Sutra inverts the priority: the compile-time path is the privileged one, and the runtime path is what you fall to when you can't avoid it. That's a coherent design philosophy but a deliberate one — it shapes which problems the language is well-suited for.

The discrete-to-continuous handoff is where this all pays off. Compile time is where the *discrete* phase lives — type checking, ontology constraints, beta reduction, literal folding, all crisp and decidable. Runtime is where the *continuous* phase lives — the resulting tensor graph, weighted approximate similarity, cosine, softmax. The compiler's whole job is to supervise that handoff cleanly: every literal absorbed into weights is one less discrete decision the runtime has to make, and one more degree of freedom for the continuous phase to carry.

---

## Related reading

- [What is Sutra?](what-is-sutra.md) — the geometric-compilation pitch.
- [The ontology](ontology.md) — the class system in detail.
- [Loops](loops.md) — how the four declared-function loop kinds lower as substrate-pure RNN cells.
- [Memory without control flow](memory.md) — how binding and bundling replace imperative array/map patterns.
- [Compilation](compilation.md) — how the simplifier strips surface sugar down to polynomial and matrix arithmetic.
