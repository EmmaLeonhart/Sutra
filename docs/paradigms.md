---
title: Paradigms — where Sutra sits
description: How Sutra relates to functional, array-oriented, declarative, logic, object-oriented, and imperative programming, and what it borrows from each.
---

# Paradigms — where Sutra sits

People who pick up a new language want to know what shape it is. Is it functional like Haskell? Array-oriented like APL? Logic like Prolog? Object-oriented like Java? Imperative like C?

Sutra has a clear ordering. Going from most-load-bearing to least:

> **Functional ≈ Array-oriented > Declarative (with strong logic-programming flavor) > Object-Oriented > Imperative**

Functional and array-oriented are the foundation, nearly tied. Declarative is the surface a programmer reads and writes — and it inherits a logic-programming flavor (continuous-space reasoning under uncertainty, closer to Prolog than to Python). Object orientation is real but it's *declarative* object orientation, not imperative. The imperative-looking surface (`var n += 1;`, `slot x = expr;`, `loop`) is a thin convenience layer over a functional-algebraic core — the compiler lowers all of it to tensor operations on the substrate.

This page walks each paradigm in order, says what Sutra takes from it, and compares against a representative language for each.

---

## Functional — the foundation

A Sutra program is a tree of expressions over vectors. Functions are pure; values are immutable; there is no IO primitive inside the language. The only escape from the pure region is the final return value at the program's edge. This is the same shape as Haskell, ML, or Lean — pure functions composed into bigger pure functions, with side effects pushed to the boundary.

What Sutra borrows from the functional tradition:

- **Pure functions.** A `function vector f(vector x) { ... }` body cannot mutate global state, cannot do IO, cannot raise. Given the same input it produces the same output.
- **Expression-orientation.** Almost everything is an expression that produces a value. The few statement forms (`var x = ...;`, `slot x = ...;`, `return ...;`) exist because vectors have to be named to be reused, not because Sutra wants imperative sequencing.
- **Referential transparency as a compiler enabler.** Because every operation is a pure tensor function with no hidden state, the simplifier can rewrite the program freely — fold matrix chains, fuse `bundle(bind(r1,f1), bind(r2,f2))` into a single batched einsum, hoist constant subexpressions, dead-code-eliminate. None of this is safe in a language with implicit side effects. Sutra's "global efficiency, not local" story (the compiler treats the whole program as one tensor dataflow graph) only works because the language is functional underneath.

**Comparison — Haskell vs Sutra:**

| | Haskell | Sutra |
|---|---|---|
| Pure functions by default | yes | yes |
| Immutable values | yes (no mutation outside `IORef`) | yes (no mutation outside `slot`) |
| Lazy evaluation | yes | no — strict, tensor-eager |
| Algebraic data types | yes (sum types) | no — every value is a vector |
| IO monad / effect tracking | yes | no — no IO inside the language at all |
| Compiler folds pure expressions | yes | yes, more aggressively (matrix-chain fusion) |

The biggest divergence: Haskell uses ADTs to represent structured data; Sutra uses bound-and-bundled vectors. A Sutra "record" is `bundle(bind(role_name, value_a), bind(role_age, value_b))` — a single vector that carries the structure as geometry, decoded by `unbind` at the read site. This is closer to the VSA (vector symbolic architecture) tradition than to ML-family functional languages.

---

## Array-oriented — also the foundation

This is the paradigm Sutra is most secretly indebted to. The whole-array philosophy of APL (and J, K, BQN, and to a lesser extent NumPy) — *every value is a uniform array, every operation acts on the whole array at once, you get global efficiency from uniform shape* — is essentially Sutra's "global efficiency, not local" rule restated. Sutra is in some ways more APL-shaped than Haskell-shaped.

What Sutra borrows from the array-oriented tradition:

- **Uniform value shape.** Every value is a vector in the substrate. There is no scalar/array distinction at the language level — `1 + 1` and `"cat" + "dog"` go through the same primitive (a tensor add on 868-dimensional vectors). Just as APL has no "loop over the elements" because every primitive is already whole-array, Sutra has no "loop over the dimensions" because every primitive is already a tensor op.
- **Global efficiency from uniform shape.** APL programs are dense one-liners that the interpreter can evaluate as fused whole-array operations because there are no scalar branches breaking the array shape. Sutra programs compile to dense tensor expressions that the simplifier can fuse end-to-end (matrix-chain composition, batched einsum for `bundle(bind(r1,f1), ..., bind(rN,fN))`) for the same reason — no scalar escape, so the optimizer can always see the whole graph.
- **Locally wasteful, globally efficient.** APL doing `2 + 3` as a one-element array operation is wasteful at the leaf. Sutra doing `1 + 1` as 868-dimensional vector addition is wasteful at the leaf. The trade in both cases is that the *whole program* has uniform shape, no type-dispatch layer, no JIT-vs-interpreter switch in the hot path.
- **Operators over operations.** APL's reduce / scan / outer-product family produces new operations from old ones. Sutra's combinators (`select`, `argmax_cosine`, `bundle`-of-binds) play a similar role — they describe a whole-array transformation in one symbol.

**Comparison — APL vs Sutra:**

| | APL | Sutra |
|---|---|---|
| Every value is an array/vector | yes | yes |
| Whole-array primitives, no element loops | yes | yes (tensor ops, no scalar extraction) |
| Uniform shape enables global fusion | yes (interpreter) | yes (compile-time simplifier) |
| Reduce / scan / outer product | yes (built-in operators) | partial (`bundle`, `argmax_cosine`, planned reductions) |
| Substrate | dense numeric arrays | dense embedding-space vectors |
| Truth values | numeric (0/1, sometimes broader) | fuzzy `[-1, +1]` truth axis |
| Element type | uniform numeric | uniform geometric (every value is a 768/868-d vector) |
| Notation | terse glyphs (`+/`, `⌽`, `⍳`) | C-family keywords (`bundle`, `bind`, `loop`) |
| Records / structured data | nested arrays | bundled role-filler bindings |

The biggest divergence: APL's element type is a number, and APL's substrate is a dense numeric array. Sutra's element type is a *geometric vector in embedding space*, and the substrate is the frozen LLM's latent space. APL primitives like `+/` (sum-reduce) translate cleanly to Sutra's `bundle` (sum-and-normalize); APL's `⍳` (iota) translates loosely to a basis-vector enumeration; APL's outer product translates to bind-against-each-of-many. The shape of the language — uniform values, whole-array ops, fusion-friendly straight-line code — is the same.

This is also why "vectors and matrices as primitives" appears in CLAUDE.md as a core design point. The right reference for that decision isn't NumPy (which is a *library* in a non-array-oriented host) — it's APL, where the array is the *language*.

---

## Declarative — also the foundation

A Sutra source file reads top-to-bottom as a sequence of *declarations*: codebooks of named vectors, role declarations, function definitions, class definitions. There is no main control loop the way an imperative program has one — the runtime evaluates declarations at module-load time, and the entry point (`main`) is itself a declaration whose body is more declarations and expressions.

The control flow is also declarative:

- **`select`** describes a decision shape ("here are the named options, here is the score for each, here is the fallback") rather than commanding a branch. The runtime computes a softmax-weighted superposition; commitment to a discrete answer happens at the final `argmax_cosine` or map lookup at the edge.
- **`loop`** describes a fixed-point relation (`state ← R · state` until cleanup matches a prototype) rather than an iteration counter. The "loop counter" lives on the substrate as the angular position on a helix; there is no host-side `i++`.
- **Fuzzy conditionals** are weighted superposition: `result = (cond * branch_true) + (NOT cond * branch_false)`. All branches contribute; the weights decide how much. See [`examples/fuzzy_branching.su`](https://github.com/EmmaLeonhart/Sutra/tree/master/examples/fuzzy_branching.su).

Sutra also has a strong **logic-programming undertone**. CLAUDE.md describes the language as "a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space." The ontology layer (named regions of embedding space, learned relations between them) is the same conceptual move RDF/OWL made for the semantic web — it describes *what exists* in the representation, not *how to compute over it*.

**Comparison — Prolog and SQL vs Sutra:**

| | Prolog | SQL | Sutra |
|---|---|---|---|
| Computation as relation/query | yes | yes | yes (similarity, argmax_cosine) |
| Discrete symbolic substrate | yes (terms) | yes (rows) | no — continuous (vectors) |
| Boolean truth values | yes | yes (3-valued: T/F/NULL) | no — fuzzy `[-1, +1]` truth axis |
| Pattern matching as primary control | yes (unification) | yes (joins) | no — softmax superposition |
| User-defined predicates / functions | yes | yes (UDFs) | yes |
| Closed-world vs open-world | configurable | closed | open — embedding space carries semantics from training |

Where Sutra differs sharply: Prolog and SQL operate on discrete tuples and resolve queries via exact unification or set algebra. Sutra operates on continuous vectors and resolves "queries" via cosine similarity and softmax-weighted superposition. Truth is graded, not Boolean. A Sutra program *describes* the geometric relations among named vectors, then asks the substrate to evaluate those relations — much like SQL describes a relational query and lets the planner figure out execution.

---

## Logic programming — a sub-family of declarative, worth its own section

Sutra's connection to logic programming is strong enough that the SQL/Prolog table above doesn't do it justice. CLAUDE.md describes the language as "a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space." That phrasing is deliberate. Several of Sutra's load-bearing ideas are logic-programming ideas relocated to a continuous substrate.

What Sutra borrows from the logic-programming tradition:

- **Programs as relations, not procedures.** A Prolog program is a set of facts and rules describing relations; the runtime resolves queries against that relational structure. A Sutra program is a set of vector declarations and pure functions describing geometric relations; the runtime resolves queries (similarity, argmax_cosine, select) against that geometric structure. In neither case do you write "do this, then this, then this."
- **Predicates as first-class structure.** Prolog's `parent(alice, bob)` is a relation between two terms. Sutra's `is_parent_of` is a learned matrix (or, today, a rotation) that relates two embedded objects. Both are "predicates" — claims about how things relate — that the language treats as primary objects.
- **Reasoning under uncertainty.** Pure Prolog gives Boolean answers; extensions like ProbLog and Stochastic Logic Programs add probability. Sutra is *built* with uncertainty as the ground truth — fuzzy truth on the canonical truth axis, similarity scores in `[-1, +1]`, defuzzification that polarizes without binarizing. Confidence is first-class; certainty is the special case.
- **Open-world semantics.** Datalog and SQL default to closed-world (anything not asserted is false). Sutra defaults to open-world — the embedding space carries semantics from training, so questions like "is `tomato` more like `fruit` or `vegetable`?" have answers before any program declares them. The language is a thin layer over a much larger learned ontology.

**Comparison — Prolog vs Sutra:**

| | Prolog | Sutra |
|---|---|---|
| Programs as relations / facts / rules | yes | yes (declarations + pure functions over geometric relations) |
| Resolution via unification | yes (exact) | no — replaced by similarity + softmax superposition |
| Truth values | Boolean (extensions: probabilistic) | fuzzy `[-1, +1]` by default |
| Substrate | discrete terms | continuous vectors in embedding space |
| Open-world reasoning | configurable | default — semantics inherited from frozen LLM |
| Backtracking search | yes (built-in control) | no — replaced by weighted superposition over options |
| Cut (`!`) and explicit control | yes | no — there is no execution order to cut |
| Higher-order / metaprogramming | limited | partial (compile-time simplifier rewrites the program) |
| Negation | negation-as-failure | fuzzy NOT (truth-axis sign flip), polarizing not binarizing |

The biggest divergence: Prolog *searches* a discrete space via unification + backtracking; Sutra *computes* in a continuous space via tensor algebra. Where Prolog asks "is there a binding of variables that makes this query true?", Sutra asks "what does the geometry say about how close this is to true?" — and gets back a graded answer rather than a yes/no. Both are declarative; both treat predicates as first-class; both reason about relations rather than procedures. The substrate change (discrete terms → continuous vectors) is what makes Sutra's primitives look so different from Prolog's even though the underlying paradigm relationship is close.

The same comparison applies, in muted form, to **Datalog** (Prolog without function terms — closer to SQL but still relational) and to **Answer Set Programming** (Prolog with declarative semantics around stable models). Sutra's relationship to all three is: same paradigm family, different substrate, graded truth instead of Boolean.

---

## Object-oriented — but declarative OO

Sutra has classes. `class Cat extends Animal { }` parses, validates, and runs today (2026-04-25 MVP, empty bodies only — the [ontology page](ontology.md) covers what's deferred). The intent is real: a `Currency` base class with `Dollar` and `Yen` subclasses that inherit "addable to same currency only" semantics, the F#-units-of-measure replacement story.

But — and this is the key framing — **Sutra's object orientation is declarative, not imperative.**

In imperative OO (Java, C++, Python), an object is a *bundle of mutable state plus methods that mutate it*. `cat.eat(fish)` advances the cat's internal state; calling it twice produces a different cat than calling it once. Identity is built from a chain of mutations.

In Sutra, an object is **a vector in a region of embedding space**, and a class declaration **names that region and asserts which operations make sense on it**. There is no mutable state. A "method" on a class — when class bodies land — will be a pure function from a vector (the receiver) to a vector (the result). `cat.get_capital()` (in the country/capital example from the ontology page) is `cat + capital_of`, a single vector addition. No hidden state, no mutation, no constructor side effects.

The class declaration is a **claim about the world** — that there is a coherent region of the embedding space worth naming `Cat` — not a recipe for *building* cats out of fields. This is the same move RDF/OWL ontologies make: classes describe what exists, not how to construct it. See the [ontology page](ontology.md) § "Emerging classes: the inverse of OOP" for the full treatment.

**Comparison — Java vs Sutra:**

| | Java | Sutra |
|---|---|---|
| Classes | yes | yes (MVP: empty body, single inheritance) |
| Inheritance | single + interfaces | single (deferred: more) |
| Mutable instance state | yes (fields) | no — instance is a vector |
| Methods | yes (mutating + non-mutating) | deferred — when landed, pure |
| Constructors | yes | no — values come from `basis_vector` / arithmetic |
| Operator overloading | no | deferred (per-class operator tables) |
| Class boundaries | discrete (instanceof is bool) | fuzzy (instanceof is a graded similarity) |
| Class can be *wrong* | no — true by fiat | yes — claim can disagree with embedding |
| What a class organizes | code + state | regions of geometric space |

The "class can be wrong" line is the deepest difference. A Java `Dog` class is correct by definition: whatever fields you put on it is what `Dog` means in your program. A Sutra `Dog` class makes a claim about *where in the embedding space `Dog` sits*, and that claim can disagree with the model's clustering, with another model's, or with reality. Class membership has truth conditions.

---

## Imperative — a thin, intentionally-limited surface

Sutra has imperative-looking syntax in three places:

- **`var x : int = 0; x += 1;`** — augmented assignment. Looks like mutation.
- **`slot TYPE name = expr;`** — reversible writes into 2D-Givens slots in the synthetic subspace. Looks like assignment.
- **`loop[N] { ... }` / `loop(condition) { ... }`** — looks like a while loop.
- **`wait`** — looks like a thread primitive.

**All of these are surface conveniences over a functional-algebraic core.** The compiler lowers each one to tensor operations:

- `x += 1` compiles to a fresh vector representing the new value, not in-place mutation. The variable name rebinds; the old vector is unreferenced and collected.
- `slot` writes are *reversible* — they correspond to 2D-Givens rotations on disjoint planes in the synthetic subspace. The whole sequence `slot x = a; slot x = b; slot x = a;` produces the same final substrate state as a single `slot x = a;` because rotations compose to the identity. This is *imperative-looking*, *algebraic underneath*.
- `loop[N]` unrolls at compile time — the compiler emits `N` copies of the body and there is no runtime iteration counter.
- `loop(condition)` lowers to iterated multiplication by a fixed rotation `R`. The "loop counter" is the angular position on a helix in the substrate, not a host-side integer.

CLAUDE.md's rule "no scalar extraction inside an operation, no Python control flow inside an operation" is the hard ceiling on how imperative the language is allowed to get. An operation that pulled a scalar out of a vector, did Python arithmetic on it, and packed the result back would break the property the simplifier depends on (every Sutra operation is a tensor operation; the whole program is one tensor dataflow graph). The imperative surface exists exactly to the extent that it can be lowered to that graph without breaking it.

**Comparison — C vs Sutra:**

| | C | Sutra |
|---|---|---|
| Mutable variables | yes (real memory writes) | surface-only — rebinds, no in-place mutation |
| Goto / break / continue | yes | no |
| Pointers | yes | no — every value is a vector |
| Manual memory management | yes | no — runtime is host-managed |
| Side effects everywhere | yes | no — confined to slot writes (which are reversible) |
| `for` / `while` | yes (host-side counter) | `loop[N]` (compile-time unroll) or `loop(cond)` (substrate eigenrotation) |
| Functions as first-class values | no | partial (planned: lambdas) |
| Control flow visible at runtime | yes | no — straight-line tensor work after compilation |

C is the canonical imperative language: control flow lives at runtime, mutation is everywhere, the program advances by stepping through statements. Sutra's surface looks superficially similar in places — there is a `loop` keyword, there is `+=` — but the lowering target is *tensor algebra*, not a sequence of memory writes. The runtime sees no branches, no loops with host-side counters, no mutable cells.

---

## So what is Sutra, in one sentence?

Sutra is a **functional, array-oriented language with a strong declarative / logic-programming bias, a real-but-declarative class system, and an intentionally thin imperative surface** — all of which lower to tensor operations on a frozen-LLM embedding substrate at compile time.

Or, said differently: Sutra is a [geometrically compiled language](what-is-sutra.md) where every paradigm contributes something specific. The functional core gives the simplifier the algebraic freedom it needs. The array-oriented design gives every value the same shape, so the whole program is one tensor dataflow graph the simplifier can fuse. The declarative / logic surface is where the programmer expresses intent — codebooks, roles, relations, decisions, fixed points. The object-oriented layer organizes regions of embedding space into named, queryable ontological structure. The imperative surface is convenience — slot-based reversible state and loop-shaped fixed points — that lowers cleanly to the same tensor graph as the rest.

The ordering — functional ≈ array-oriented > declarative (with logic flavor) > OO > imperative — is not arbitrary. It's the order in which each layer constrains the others. The functional and array-oriented core are load-bearing for compilation; remove either and the simplifier collapses. The declarative / logic surface is load-bearing for semantics; remove it and the language becomes syntax without a story. The OO layer is load-bearing for *organizing* large programs over many embedding regions; remove it and you can still compute, but you can't structure. The imperative surface is convenience; remove it and you write more verbose programs, but nothing fundamental breaks.

---

## Related reading

- [What is Sutra?](what-is-sutra.md) — the geometric-compilation pitch.
- [The ontology](ontology.md) — the class system and the inverse-of-OOP framing in detail.
- [Loops](loops.md) — how `loop[N]` and `loop(condition)` lower.
- [Memory without control flow](memory.md) — how binding and bundling replace the control flow patterns imperative languages use for arrays and maps.
- [Compilation](compilation.md) — how the simplifier strips surface sugar down to polynomial and matrix arithmetic.
