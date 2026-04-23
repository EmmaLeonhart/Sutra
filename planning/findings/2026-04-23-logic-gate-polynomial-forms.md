# Simplified polynomial forms for every standard logic gate

**Date:** 2026-04-23.
**Status:** Derivation + empirical verification on the three-valued
grid `{-1, 0, +1}²`. Relevant to compile-time simplification passes
that want to fold composed logic expressions into direct polynomial
forms.

## Context

The shipped primitives (commit 54ff1a0) use Lagrange polynomials over
the three-valued grid:

```
not(a) = -a
and(a, b) = (a + b + ab − a² − b² + a²b²) / 2
or (a, b) = (a + b − ab + a² + b² − a²b²) / 2
```

{not, and, or} is functionally complete for three-valued logic. Any
other connective can be written as a composition. But the composition
can then be symbolically simplified to a **single polynomial** in `a`
and `b`. This is the "factorable logic" the user flagged —
compositions collapse under standard polynomial algebra.

## The eight standard connectives

All derivations verified against their compositional definitions on
the full three-valued truth table (9 grid points each, 45 points
total, all exact match).

| connective | composed form | simplified polynomial | degree |
|---|---|---|---|
| `not(a)` | primitive | `-a` | 1 |
| `and(a, b)` | primitive | `(a + b + ab − a² − b² + a²b²) / 2` | 4 |
| `or(a, b)` | primitive | `(a + b − ab + a² + b² − a²b²) / 2` | 4 |
| `nand(a, b)` | `!(a && b)` | `-(a + b + ab − a² − b² + a²b²) / 2` | 4 |
| `nor(a, b)` | `!(a || b)` | `-(a + b − ab + a² + b² − a²b²) / 2` | 4 |
| `xor(a, b)` | `(a && !b) || (!a && b)` | **`-a · b`** | 2 |
| `iff(a, b)` | `(a → b) && (b → a)` | **`a · b`** | 2 |
| `implies(a, b)` | `!a || b` | `(-a + b + ab + a² + b² − a²b²) / 2` | 4 |

## Notable collapses

The eye-catchers are XOR and IFF. Each is a *four-level nested
composition* of primitives — the kind of thing a naive interpreter
evaluates as 5+ polynomial operations — but both simplify to a single
multiplication:

```
xor(a, b) = (a && !b) || (!a && b)
          = OR( AND(a, NOT(b)), AND(NOT(a), b) )
          = -a · b                                       # three-line expand
```

```
iff(a, b) = (a → b) && (b → a)
          = AND( OR(NOT(a), b), OR(NOT(b), a) )
          = a · b                                        # same
```

This is the signed-scale identity: on `{-1, 0, +1}`, "the two values
agree" is exactly `a · b` (product of signs), and "they disagree" is
`-a · b`. The polynomial AND/OR machinery vanishes into the product
after simplification.

## What this buys us

1. **Runtime cost.** A program that writes `xor(a, b)` out of
   primitives evaluates 5 polynomials (NOT, NOT, AND, AND, OR). The
   simplified form evaluates 1 multiplication. On CUDA this is 1
   kernel launch vs. 5; on numpy it's one broadcast op vs. five.
   For XOR-heavy programs the constant factor matters.

2. **Compile-time simplification.** A pass that recognizes the
   composition patterns (e.g. match `OR(AND(a, NOT(b)), AND(NOT(a),
   b))` → rewrite to `-a·b`) is mechanical algebra, not special
   cased. The input and output are both pure polynomial expressions.

3. **Algebraic reasoning.** Programs using derived connectives
   maintain a closed-form representation all the way down. No kinks,
   no case splits, no abs-value machinery. Differentiating a program
   that builds up logical expressions is just differentiating a
   multivariate polynomial.

## What ships now vs. what's a follow-on

**Ships now** (commit 54ff1a0 and this commit):
- The three primitives `!`, `&&`, `||` in polynomial form.
- Corpus test `35_derived_logic.su` that writes XOR, NAND, NOR,
  IMPLIES, IFF in terms of the primitives. They run correctly as
  compositions.

**Follow-on** (not yet):
- A simplifier pattern-matcher that recognizes `OR(AND(a, NOT(b)),
  AND(NOT(a), b))` and emits `-a · b` directly. The target forms in
  the table above are the rewrite destinations.
- Same for NAND/NOR (fold the outer NOT into a sign flip on the
  AND/OR polynomial).
- Benchmarking: measure whether on the sizes and workloads we care
  about the 5x-to-1x reduction actually shows up vs. constant-factor
  noise.

## Derivation notes

All of these were derived by Lagrange interpolation on the full 3×3
grid of values. The method is mechanical: build the truth table in
`{-1, 0, +1}³`, use Lagrange basis functions
`L_{-1}(x) = (x²-x)/2`, `L_0(x) = 1-x²`, `L_1(x) = (x²+x)/2`, and
read off the coefficient polynomial. For any n-ary connective on
this grid, there is a unique polynomial of degree ≤ 4 per variable.
The polynomials here are the smallest-degree representatives.

For a k-ary connective the polynomial grows as `O(4^k)` terms in the
worst case, but sparsity is common (XOR is degree 2, IFF is degree 2).
The specific binary connectives in the table above are the most common
ones programs actually use.

## Programmatic verification

```python
import itertools
def NOT(a): return -a
def AND(a, b): return (a + b + a*b - a*a - b*b + a*a*b*b) / 2
def OR(a, b):  return (a + b - a*b + a*a + b*b - a*a*b*b) / 2

# Compositions
def XOR_comp(a, b): return OR(AND(a, NOT(b)), AND(NOT(a), b))
def IFF_comp(a, b): return AND(OR(NOT(a), b), OR(NOT(b), a))

# Claims
def XOR_simple(a, b): return -a*b
def IFF_simple(a, b): return  a*b

for a, b in itertools.product([-1, 0, 1], repeat=2):
    assert abs(XOR_comp(a, b) - XOR_simple(a, b)) < 1e-12
    assert abs(IFF_comp(a, b) - IFF_simple(a, b)) < 1e-12
```

Passes. Same verification extends to NAND, NOR, and implication —
each of the 45 grid point comparisons matches exactly.

## Pointers

- Primitive polynomials shipped in commit `54ff1a0`.
- `planning/open-questions/zero-as-explicit-neutrality.md` — why the
  neutral point is a first-class value (required for these formulas
  to behave sensibly at `a=0` or `b=0`).
- `docs/primitive-classes.md` — the three-valued-bool framing these
  truth tables follow.
