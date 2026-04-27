---
title: Paradigms — where Sutra sits
description: How Sutra relates to functional, array-oriented, declarative, logic, object-oriented, and imperative programming, shown through code comparisons.
---

# Paradigms — where Sutra sits

People who pick up a new language want to know what shape it is. This page picks one small task per paradigm, writes it in the canonical language for that paradigm, then writes it in Sutra. The goal is to make the influences visible: what Sutra borrowed in shape, and what it changed by moving the substrate from "memory cells / discrete terms / arrays of numbers" to "vectors in a frozen LLM's embedding space."

The ranking, going from most-load-bearing to least:

> **Functional ≈ Array-oriented > Declarative (with strong logic-programming flavor) > Object-Oriented > Imperative**

Functional and array-oriented are the foundation, nearly tied. Declarative is the surface a programmer reads and writes — and it inherits a logic-programming flavor (continuous-space reasoning under uncertainty). Object orientation is real but it's *declarative* OO, not imperative. The imperative-looking surface (`var n += 1;`, `slot x = expr;`, `loop`) is a thin convenience layer over a functional-algebraic core.

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

## Array-oriented — APL

**Task.** Compute a weighted sum of four behavior options based on four weights.

**APL:**

```apl
⍝ W is a 4-element weight vector, B is a 4-element behavior vector
result ← +/W×B
```

That's it. `×` multiplies the two arrays element-wise; `+/` reduces with addition. No loop, no index variable.

**Sutra:**

```sutra
// w_PH..w_AF are scalars; b_PH..b_AF are vectors
vector result =
    w_PH * b_PH +
    w_PF * b_PF +
    w_AH * b_AH +
    w_AF * b_AF;
```

Or, when the structure is more uniform:

```sutra
vector result = bundle(
    bind(role_1, filler_1),
    bind(role_2, filler_2),
    bind(role_3, filler_3)
);
```

**What Sutra borrows from APL.** Whole-array primitives. `bundle` is `+/` for embedding vectors. There is no "for each dimension, do x" loop in either language — the operation is whole-vector. Both languages get **global efficiency from uniform shape**: APL fuses through the interpreter because every value is an array; Sutra fuses through the compile-time simplifier because every value is a tensor. The first form (`w * b + w * b + ...`) lowers to one batched matmul under the hood, just like the APL one-liner runs as one fused reduction.

**Where it diverges.** APL's element type is a *number*. Sutra's element type is a *vector in embedding space* — every "element" is itself 768-dimensional. APL's `⍳5` enumerates `1 2 3 4 5`; Sutra's nearest equivalent enumerates basis vectors. APL's notation is glyph-dense (`+/`, `⌽`, `⍳`); Sutra's is keyword-dense (`bundle`, `bind`, `loop`). The shape of the language — uniform values, whole-array ops, fusion-friendly straight-line code — is the same.

---

## Declarative — SQL

**Task.** Find the capital of Japan.

**SQL:**

```sql
SELECT capital FROM countries WHERE country = 'Japan';
```

You describe *what* you want; the planner figures out *how*.

**Sutra:**

```sutra
vector japan         = "Japan";
vector capital_of    = displacement(v_paris, v_france);  // learned

vector predicted_capital = japan + capital_of;
vector winner = argmax_cosine(
    predicted_capital,
    [v_tokyo, v_paris, v_berlin, v_oslo]
);
return CITY_NAME[winner];
```

**What Sutra borrows from SQL.** A program describes a relation, not a procedure. SQL says "the relation `country → capital` exists in this table; resolve it." Sutra says "the relation `country → capital` exists as a displacement vector in embedding space; apply it." In both, the runtime figures out the lookup; the programmer only declares the structure.

**Where it diverges.** SQL's table is **a finite list of pairs**. To answer "capital of Japan" SQL needs a row containing Japan. Sutra's `capital_of` is **a single vector** that generalizes — it produces a plausible answer for countries that were never in the seed set, because `country + capital_of` lands somewhere in the capital-region of embedding space and `argmax_cosine` snaps to whatever's nearest in the candidate set. This is the same shift as: from lookup table to learned model.

---

## Logic programming — Prolog

**Task.** Express the same capital-of relation, but using the logic-programming style.

**Prolog:**

```prolog
capital(france, paris).
capital(japan,  tokyo).
capital(brazil, brasilia).
capital(norway, oslo).

?- capital(japan, X).
% X = tokyo
```

`capital` is a relation; the `?-` query asks the runtime to find a binding for `X` that makes the relation hold.

**Sutra:**

```sutra
// The relation lives in the embedding space as a displacement.
vector capital_of = displacement(v_paris, v_france);

// "Query" the relation by applying it geometrically.
vector tokyo_pred = v_japan + capital_of;

// Snap to the nearest candidate.
vector winner = argmax_cosine(
    tokyo_pred,
    [v_tokyo, v_paris, v_brasilia, v_oslo]
);
```

**What Sutra borrows from Prolog.** Predicates and relations are first-class. `capital` in Prolog is a thing you can declare, query, and reason about; `capital_of` in Sutra is a thing you can compute, name, and apply. Both are **declarative**: you describe what relates to what, not how to traverse a search tree. Both support **reasoning under uncertainty** — Prolog through extensions like ProbLog, Sutra through fuzzy similarity scores native to the substrate.

**Where it diverges.** Prolog resolves queries with **unification + backtracking** over discrete terms. Sutra resolves queries with **vector arithmetic + nearest-neighbor** over continuous embeddings. Prolog needs a fact for every (country, capital) pair you want to answer; Sutra needs a *single* `capital_of` vector and the query generalizes. Prolog's truth values are Boolean (extensions: probabilistic); Sutra's are graded `[-1, +1]` by default — when you ask "is Tokyo the capital of Japan?" you get back *how true*, not *whether*.

The same comparison applies in muted form to **Datalog** and **Answer Set Programming** — same paradigm family, different substrate, graded truth instead of Boolean.

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

A `Country` is a bundle of fields. Construction sets the fields; the method reads them.

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

**What Sutra borrows from Java.** Class declarations, single inheritance, the dotted-method-call surface. Going from `class Country` to `class Country extends vector` to a subclass like `class IslandNation extends Country` reads the same way as Java.

**Where it diverges — and this is the deepest divergence on the page.**

- **No mutable instance state.** Java's `this.capital = "Tokyo"` mutates the object. Sutra has no such operation on a class instance — there are no fields to assign to.
- **No constructor.** Java needs `new Country("Japan", "Tokyo")` to bring an instance into being. Sutra's instances *already exist* in the embedding space; the language only names them. `vector japan = "Japan"` doesn't *construct* Japan, it *resolves* the existing geometric position.
- **Methods are pure vector transformations.** `get_capital()` in Sutra is a single vector add: `this + capital_of`. There's no internal state to consult, no field to read.
- **Classes can be wrong.** A Java `Dog` class is true by fiat — whatever you put in it is what `Dog` means in your program. A Sutra `Dog` class makes a claim about *where in the embedding space `Dog` sits*, and that claim can disagree with the model's clustering, with another model's, or with reality. Class membership has truth conditions.

This is what "declarative OO" means: a class is a *claim* about a region of embedding space, not a *recipe* for building instances out of fields. The shape borrowed from Java; the semantics borrowed from RDF/OWL.

---

## Imperative — C

**Task.** Sum the integers from 1 to 5.

**C:**

```c
int sum = 0;
for (int i = 1; i <= 5; i++) {
    sum += i;
}
// sum == 15
```

Memory cells, mutation, a counter, a comparison, a branch back.

**Sutra:**

```sutra
var n : int = 0;
loop[5] {
    n += 1;
}
```

Looks imperative. **Isn't, underneath.**

What the compiler does:

- `loop[5] { ... }` *unrolls at compile time*. The emitted code is the body five times in sequence — no runtime counter, no comparison, no back-edge.
- `n += 1` does not mutate a memory cell. It rebinds the name `n` to a fresh vector representing the new value. The old vector is just unreferenced.
- The whole program lowers to straight-line tensor work that the simplifier can fuse. There is no host-side loop in the emitted code at all.

For data-dependent termination, the form is different:

```sutra
loop(state ~ target) {
    state = R * state;
}
```

This `loop(condition)` lowers to **iterated multiplication by a fixed rotation matrix `R` on the substrate**. The "loop counter" is the angular position on a helix in the substrate; termination is a similarity check between the rotated state and the target prototype. There is no host-side `i++`.

**What Sutra borrows from C.** Surface ergonomics. `var`, `+=`, `loop`, the curly braces. People know what these mean and the language doesn't fight that intuition.

**Where it diverges.** Lowering target. C compiles to memory writes, branches, and a CPU counter. Sutra compiles to a tensor expression with no runtime control flow. CLAUDE.md's "no scalar extraction inside an operation, no Python control flow inside an operation" rule is the hard ceiling on how imperative the language is allowed to get — an operation that pulled a scalar out of a vector, did Python arithmetic on it, and packed the result back would break the property the simplifier depends on (the whole program is one tensor dataflow graph). The imperative surface exists exactly to the extent that it can be lowered to that graph without breaking it.

---

## So what is Sutra, in one sentence?

Sutra is a **functional, array-oriented language with a strong declarative / logic-programming bias, a real-but-declarative class system, and an intentionally thin imperative surface** — all of which lower to tensor operations on a frozen-LLM embedding substrate at compile time.

The paradigm ordering (functional ≈ array-oriented > declarative+logic > OO > imperative) is the order in which each layer constrains the others. The functional and array-oriented core are load-bearing for compilation; remove either and the simplifier collapses. The declarative / logic surface is load-bearing for semantics; remove it and the language becomes syntax without a story. The OO layer organizes large programs over many embedding regions; remove it and you can still compute, but you can't structure. The imperative surface is convenience; remove it and you write more verbose programs, but nothing fundamental breaks.

---

## Related reading

- [What is Sutra?](what-is-sutra.md) — the geometric-compilation pitch.
- [The ontology](ontology.md) — the class system and the inverse-of-OOP framing in detail.
- [Loops](loops.md) — how `loop[N]` and `loop(condition)` lower.
- [Memory without control flow](memory.md) — how binding and bundling replace the control flow patterns imperative languages use for arrays and maps.
- [Compilation](compilation.md) — how the simplifier strips surface sugar down to polynomial and matrix arithmetic.
