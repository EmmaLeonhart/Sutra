# Logical operations

Most languages treat logic as a crisp, two-valued afterthought: `true` and `false`, wired to control flow, never differentiable. Sutra does the opposite. Logic is **fuzzy-first**, lives on a real-valued axis, and is expressed in pure polynomial arithmetic — so every connective is a smooth function you can differentiate, simplify algebraically, and run on CUDA.

This page explains how that works: the truth axis, the three primitive connectives as polynomials, why polynomials are the right choice, and how every other standard logic gate falls out as a simplification.

---

## The truth axis

All truth-valued types in Sutra live on a single coordinate — `synthetic[AXIS_TRUTH]`, one scalar in `[-1, +1]`. Three primitive classes view this axis through different lenses:

```mermaid
graph TD
    TA[truth axis — synthetic 2]
    TA --> B[bool<br/>values at the poles ±1]
    TA --> F[fuzzy<br/>any value in &#91;-1, +1&#93;]
    TA --> T[trit<br/>{-1, 0, +1} as first-class poles]

    classDef ax fill:#512da8,color:#fff,stroke:#311b92
    classDef leaf fill:#d1c4e9,color:#311b92,stroke:#512da8
    class TA ax
    class B,F,T leaf
```

The runtime representation is identical — a truth-axis scalar — but the compile-time tag controls what the language expects from the value:

| class | range | meaning of `0` | defuzzification |
|---|---|---|---|
| `bool` | `{-1, +1}` at rest | sharpens to nearest pole | binary |
| `fuzzy` | continuous `[-1, +1]` | explicit uncertainty | binary, with `0` as discontinuity |
| `trit` | continuous, `{-1, 0, +1}` attractors | **first-class neutral** | three-way, preserves `0` |

Literals:
- `true` → `+1`
- `false` → `-1`
- `unknown` (or `unk`) → `0`
- Plain numeric literals like `0.7` in a fuzzy-typed slot → `+0.7`

These are all truth-axis *vectors* at runtime — there is no hidden Python-bool path. That fact is what makes differentiable logic possible: every value in a logical expression is a substrate vector, and every operator is vector arithmetic.

---

## Three primitives, polynomial forms

Sutra's logical operators are expressed as smooth polynomials on the truth axis:

```
!a       = -a
a && b   = (a + b + ab − a² − b² + a²b²) / 2
a || b   = (a + b − ab + a² + b² − a²b²) / 2
```

All pure element-wise arithmetic — no `abs`, no branches, no special case at `a = b`. The polynomials were derived by Lagrange interpolation on the three-valued grid `{-1, 0, +1}²`, which guarantees they produce exact `min` / `max` on any grid point while staying `C^∞` everywhere in between.

### Verification on the three-valued grid

```mermaid
graph LR
    subgraph AND[a && b — smooth min]
        direction LR
        TT[T &amp;&amp; T = T<br/>+1]:::pos
        TF[T &amp;&amp; F = F<br/>-1]:::neg
        TU[T &amp;&amp; U = U<br/>0]:::neu
        FF[F &amp;&amp; F = F<br/>-1]:::neg
        UU[U &amp;&amp; U = U<br/>0]:::neu
    end

    classDef pos fill:#7e57c2,color:#fff,stroke:#512da8
    classDef neg fill:#ab47bc,color:#fff,stroke:#7e1bb2
    classDef neu fill:#ffb74d,color:#311b92,stroke:#f57c00
```

The full `3 × 3` AND and OR tables match **Kleene's K₃** (strong three-valued logic) exactly. `true && unknown` is `unknown`. `false && unknown` is `false` (a false premise collapses the conjunction regardless of what the other side is). `unknown || unknown` stays `unknown`.

Kleene's K₃ and Łukasiewicz's Ł₃ agree on AND and OR, but they differ on implication: Łukasiewicz has `U → U = T` (a metaphysical move to preserve identity of propositions about future contingents), while Kleene has `U → U = U` (a computational reading of "U" as "undefined / unknown truth value"). Sutra's derived implication `a → b = !a || b` follows Kleene — our "unknown" is an epistemic gap, not a metaphysical indeterminacy.

### Continuous behavior

For values off the grid, the polynomials are approximations to `min` / `max`, not exact. For example:

```
min(0.7, 0.3) = 0.3                     # true min
a && b  where a = 0.7, b = 0.3  = 0.337  # polynomial
```

The approximation is monotone (ordering preserved), same-sign, and correct at every pole. For three-valued logic — which is what the `bool` / `trit` classes usually do — the approximation is exact. For interpolating continuous fuzzy values, it's a smooth substitute.

---

## Why polynomials

The standard textbook fuzzy-logic formulas use `min` and `max` directly:

```
min(a, b) = (a + b − |a − b|) / 2
max(a, b) = (a + b + |a − b|) / 2
```

These work, but the `|·|` creates a **kink at `a = b`** — the derivative is undefined at the corner, and autograd frameworks paper over it with subgradient dispatch. That's acceptable for training. It's not acceptable for two other things Sutra cares about:

**1. Compile-time simplification.** Polynomial rewriting is trivial — it's just algebra. `abs(x)` is a branch, and recognizing compositions of `abs` requires case analysis. The polynomial form lets the simplifier treat every logical expression as a multivariate polynomial, which is the kind of thing algebraic systems are *built* to manipulate.

**2. Differentiability everywhere.** With the polynomial form, `∂(a && b)/∂a = (1 + b − 2a + 2ab²)/2` — a single closed-form expression with no discontinuity, no subgradient. You can compose operators, differentiate the composition, and get a clean expression out. That matters when the compiler (or a learned pass) wants to analyze or optimize the expression.

```mermaid
graph LR
    SRC["a && b<br/>surface syntax"]
    POLY["(a + b + ab - a² - b² + a²b²) / 2<br/>polynomial form"]
    GRAD["∂/∂a = (1 + b - 2a + 2ab²) / 2<br/>closed-form gradient"]
    CUDA["torch element-wise ops<br/>on self.device"]

    SRC --> POLY
    POLY --> GRAD
    POLY --> CUDA

    classDef node fill:#7e57c2,color:#fff,stroke:#512da8
    class SRC,POLY,GRAD,CUDA node
```

On the pytorch backend the emission is literally:

```python
av + bv + av * bv - a2 - b2 + a2 * b2) * 0.5
```

Five element-wise tensor ops, one kernel launch each on CUDA, full autograd support, no `abs` anywhere.

---

## Functional completeness

`{!, &&, ||}` is functionally complete for three-valued logic. Every other connective is a composition — and because everything is a polynomial, compositions **symbolically simplify** into more compact direct polynomials.

### Why this specific primitive set

Classical Boolean logic usually picks a single primitive for completeness:

- **NAND alone** is functionally complete — Henry Sheffer showed this in 1913. Most digital hardware is built on NAND gates because every other gate can be wired out of them. `NOT(a) = NAND(a, a)`, `AND(a, b) = NAND(NAND(a, b), NAND(a, b))`, and so on.
- **NOR alone** is likewise complete — Charles Peirce noted this earlier. Some hardware uses NOR-only logic.

Sutra picks a **three-primitive** set instead — `{!, &&, ||}` — for two reasons:

1. **Each has a simple polynomial form.** NAND and NOR happen to just be the negations of AND and OR polynomials, so we gain nothing polynomial-complexity-wise by making one of them primitive. But `!` alone is degree-1 (`-a`), and AND / OR are symmetric degree-4 polynomials. Three short polynomials instead of one composite one.
2. **Matches programming-language surface syntax.** Every programmer already has `!` / `&&` / `||` from C / Java / JS / Python. No re-training required.

The choice of primitives only affects *how* you build the other connectives — the set of expressible connectives is the same.

### The eight standard connectives, with full polynomial forms

Each row shows the composition in terms of the three primitives **and** the simplified polynomial you get after symbolic expansion. All eight are verified to agree with their intended three-valued truth tables on every point of the `{-1, 0, +1}²` grid.

| connective | surface composition | simplified polynomial | degree |
|---|---|---|---:|
| `!a` | primitive | `-a` | 1 |
| `a && b` | primitive | `(a + b + ab − a² − b² + a²b²) / 2` | 4 |
| `a \|\| b` | primitive | `(a + b − ab + a² + b² − a²b²) / 2` | 4 |
| `a → b` | `!a \|\| b` | `(−a + b + ab + a² + b² − a²b²) / 2` | 4 |
| `nand(a, b)` | `!(a && b)` | `(−a − b − ab + a² + b² − a²b²) / 2` | 4 |
| `nor(a, b)` | `!(a \|\| b)` | `(−a − b + ab − a² − b² + a²b²) / 2` | 4 |
| `xor(a, b)` | `(a && !b) \|\| (!a && b)` | **`−a · b`** | **2** |
| `iff(a, b)` | `(a → b) && (b → a)` | **`a · b`** | **2** |

### The NAND / NOR polynomials are just negations

The simplified NAND / NOR polynomials are hard to read at first because they have six terms with mixed signs. The easier way to see them: NAND is the negation of AND, NOR is the negation of OR, and Sutra's negation is just multiplication by `-1`. So:

```
AND(a, b)  =  (a + b + ab − a² − b² + a²b²) / 2

NAND(a, b) =  !(a && b)
           =  -AND(a, b)
           =  -(a + b + ab − a² − b² + a²b²) / 2
           =  (−a − b − ab + a² + b² − a²b²) / 2
```

Every sign in the AND polynomial flipped. That's the whole derivation — nothing happens term by term, the outer `-` distributes across everything.

The same is true for NOR:

```
OR(a, b)   =  (a + b − ab + a² + b² − a²b²) / 2

NOR(a, b)  =  !(a || b)
           =  -OR(a, b)
           =  (−a − b + ab − a² − b² + a²b²) / 2
```

Again, just sign flips. You don't need to memorize two new polynomials; just remember "NAND = negated AND polynomial, NOR = negated OR polynomial." At the substrate level Sutra can also run NAND as a composition `!(a && b)` — two runtime ops (an AND polynomial plus a sign flip). Same answer, slightly more hops.

### XOR and IFF collapse to single products

XOR and IFF are the striking cases — five-op nested compositions that symbolically reduce to a single multiplication:

```
xor(a, b) = (a && !b) || (!a && b)   =   -a · b
iff(a, b) = (a → b) && (b → a)       =    a · b
```

Why: on a signed truth scale where `-1 = false`, `+1 = true`, the **product of signs** is `+1` when the signs agree and `-1` when they disagree. That's exactly the IFF truth table. Negate it and you get XOR. When either value is `0` (unknown), the product is `0`, which is the right answer under Kleene semantics (unknown propagates).

So "logical equivalence on the signed truth scale" isn't just *like* multiplication — it **is** multiplication. The degree-4 composition of AND / OR / NOT collapses because the AND / OR polynomials' quadratic terms cancel out in precisely the right way, leaving a degree-2 monomial.

### Example: writing the derived connectives in Sutra

```c
// Shipped in tests/corpus/valid/35_derived_logic.su.
// Each of these is a composition of the three primitives.

function fuzzy Xor(fuzzy a, fuzzy b) {
    return (a && !b) || (!a && b);    // simplifies to -a·b
}

function fuzzy Iff(fuzzy a, fuzzy b) {
    return (!a || b) && (!b || a);     // simplifies to a·b
}

function fuzzy Implies(fuzzy a, fuzzy b) {
    return !a || b;
}

function fuzzy Nand(fuzzy a, fuzzy b) {
    return !(a && b);                  // simplifies to -AND polynomial
}

function fuzzy Nor(fuzzy a, fuzzy b) {
    return !(a || b);                  // simplifies to -OR polynomial
}
```

Each runs as written — the polynomial primitives compose exactly the way the source code says. A future compile-time simplifier pass can recognize the common patterns and rewrite them to their direct polynomial forms, saving runtime ops. That's just algebra on the polynomial expressions; no special-case machinery.

### Worked expansion: NAND from the composition

Just to show the step-by-step:

```
NAND(a, b)  =  !(a && b)
            =  !((a + b + ab − a² − b² + a²b²) / 2)       # expand AND
            =  -(a + b + ab − a² − b² + a²b²) / 2         # ! is multiply by -1
            =  (−a − b − ab + a² + b² − a²b²) / 2         # distribute
```

Three algebraic steps, no case analysis. Compare to classical truth-table derivation where you'd enumerate nine cases and prove each one — the polynomial form lets you do it in three lines.

### Verification

All the polynomial-vs-composition equivalences are verified on the `{-1, 0, +1}²` grid (9 points × 5 connectives × 2 forms = 90 comparisons). See the derivation and verification in [`planning/findings/2026-04-23-logic-gate-polynomial-forms.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/findings/2026-04-23-logic-gate-polynomial-forms.md).

---

## Ordered comparison

`>`, `<`, `>=`, `<=` on truth-family values (bool / fuzzy / trit) follow the same "polynomial exact on the grid, smooth everywhere off it" approach as AND / OR / NOT. The derived polynomial:

```
gt(a, b) = (a − b) · (2 + ab) / 2          (polynomial form of "a > b")
lt(a, b) = −gt(a, b)                         (polynomial form of "a < b")
```

Degree 3, smooth everywhere, fully differentiable (`∂gt/∂a = 1 + ab − b²/2`).

### Grid behavior

|  | `b = −1` | `b = 0` | `b = +1` |
|---|:---:|:---:|:---:|
| **`a = −1`** | 0 | −1 | −1 |
| **`a = 0`** | +1 | 0 | −1 |
| **`a = +1`** | +1 | +1 | 0 |

Ties produce `0` (unknown) — a continuous truth value can't strictly exceed itself, so "strict greater than on the truth axis" has the honest answer "indeterminate" at `a = b`.

### Strict vs. non-strict collapse on the fuzzy scale

`>` and `>=` give the same answer on this scale, since the only case where they'd differ classically is the tie, and the tie is `0` (unknown) in both forms. The same holds for `<` and `<=`. So the codegen emits the same polynomial for strict and non-strict variants:

```
a >  b   →   _VSA.gt(a, b)
a >= b   →   _VSA.gt(a, b)      (same)
a <  b   →   _VSA.lt(a, b)
a <= b   →   _VSA.lt(a, b)      (same)
```

This collapse is what you want on continuous truth values — the strict-vs-non-strict distinction is really a statement about a discrete partial order, and it stops carrying information once the values are continuous.

### Scalar comparisons are unchanged

For `int > int` and `float > float` — comparisons on plain number-axis values that aren't on the truth axis — the codegen falls through to Python's scalar comparison. `5 > 3` is still `True` (a Python bool), because the type-directed dispatch only routes comparisons through the polynomial form when at least one operand is provably truth-family. Scalar arithmetic stays on the fast path.

---

## How it fits together

```mermaid
graph TB
    LIT["true / false / unknown / 0.7<br/>truth-axis literal"]
    OP["! / && / ||<br/>polynomial primitive"]
    DER["xor / iff / nand / nor / →<br/>derived by composition"]
    SIMP["compile-time simplifier<br/>(future) folds to direct polys"]
    EQ["a == b<br/>cosine similarity"]
    DEF["defuzzy(x)<br/>project + iterate eq"]
    GRAD["gradient flows through<br/>as clean polynomials"]
    CUDA["emitted as torch ops<br/>on the selected device"]

    LIT --> OP
    OP --> DER
    DER --> SIMP
    EQ --> OP
    OP --> DEF
    OP --> GRAD
    OP --> CUDA

    classDef input fill:#d1c4e9,color:#311b92,stroke:#512da8
    classDef op fill:#7e57c2,color:#fff,stroke:#512da8
    classDef down fill:#ffb74d,color:#311b92,stroke:#f57c00
    class LIT,EQ input
    class OP,DER op
    class SIMP,DEF,GRAD,CUDA down
```

Equality `a == b` on vectors is cosine similarity projected onto the truth axis — a differentiable tensor reduction — producing a fuzzy that flows back into the same polynomial pipeline. `defuzzy(x)` projects onto the truth axis and iterates `x = x == true` to sharpen toward `{true, false, unknown}`. The whole logic layer is one continuous vector/tensor computation from literal to decision.

---

## Summary

- **Logic is fuzzy-first.** `bool`, `fuzzy`, and `trit` are views of one truth-axis coordinate.
- **Three primitive polynomials** (`!`, `&&`, `||`) give you functional completeness on the three-valued grid.
- **No kinks.** Polynomial forms instead of `abs(·)` — smooth gradients, simplifier-friendly, CUDA-native.
- **Derived gates compose, and compositions simplify.** XOR and IFF collapse to single products; NAND / NOR fold negation into the AND / OR polynomial; implication is a rewrite of `!a || b`.
- **The whole pipeline is differentiable.** From literal through composed connective through defuzzification, every step is polynomial or reduction. Gradients flow end-to-end as closed-form expressions.

---

## Related reading

- [Primitive classes](primitive-classes.md) — the broader "everything is a vector" picture.
- [Simplified polynomial forms for every logic gate](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/findings/2026-04-23-logic-gate-polynomial-forms.md) — derivation and 45-point verification.
- [`tests/corpus/valid/32_logical_operators.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/sdk/sutra-compiler/tests/corpus/valid/32_logical_operators.su) — polynomial primitives in Sutra source.
- [`tests/corpus/valid/35_derived_logic.su`](https://github.com/EmmaLeonhart/Sutra/blob/master/sdk/sutra-compiler/tests/corpus/valid/35_derived_logic.su) — XOR / NAND / NOR / IMPLIES / IFF derived in Sutra.
