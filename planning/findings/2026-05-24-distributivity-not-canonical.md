# Distributivity is Kleene-equivalent but does NOT reduce to the same graph

**Date:** 2026-05-24
**Status:** Confirmed by a real run (`tests/test_fv_general_checker.py`).
**Surfaced by:** building the general polynomial-obligation checker
(`sutra_compiler/fv_obligation_checker.py`) and running its equivalence checks.

## The two findings

### 1. Two equivalence notions are genuinely different

The general checker extracts the polynomial of an arbitrary Kleene expression
(via the compiler's real inliner) and offers two equivalence checks:

- **`reduces_to_same_graph`** — polynomial identity, `expand(p_a − p_b) == 0`.
  The two reduce to the *same tensor graph* (agree everywhere on [−1,1]ⁿ).
- **`kleene_equivalent`** — agree at every point of the {−1, 0, +1}ⁿ grid
  (three-valued logic equivalence).

Measured results (all from the passing test):

| law | `reduces_to_same_graph` | `kleene_equivalent` |
|---|---|---|
| double negation `!!a` ≡ `a` | **True** | True |
| commutativity `a&&b` ≡ `b&&a` | **True** | True |
| De Morgan `!(a&&b)` ≡ `!a\|\|!b` | **True** | True |
| **distributivity `a&&(b\|\|c)` ≡ `(a&&b)\|\|(a&&c)`** | **False** | **True** |
| `a&&b` vs `a\|\|b` | False | False |

### 2. Distributivity is the witness that reduction ≠ logical canonicalisation

Distributivity holds in three-valued Kleene logic (it is a distributive
lattice: `min`/`max` over {−1,0,+1}), so the two sides agree at all 27 grid
points — `kleene_equivalent` is True. But their **polynomial interpolants differ
off-grid**: `a && (b || c)` and `(a && b) || (a && c)` reduce to *different*
polynomials (different degree and coefficients away from the grid), so
`reduces_to_same_graph` is False. De Morgan and commutativity, by contrast,
produce *identical* polynomials.

## Why this matters for the FV paper

The paper's claim is "semantically equivalent programs reduce to the same
graph." This finding **sharpens the honest scope** of that claim (already
softened in the §2 revision):

- The polynomial reduction canonicalises *some* logical equivalences (those
  that are polynomial identities — De Morgan, commutativity, double negation)
  but **not all** of them. Distributivity is a concrete counterexample: two
  logically-equivalent programs that do **not** reduce to the same graph.
- So "reduce to the same graph" is **strictly stronger** than "logically
  equivalent." The reduction is a sound, partial canonicaliser, not a complete
  decision procedure for logical equivalence — which is exactly what the
  reviewer pushed on and what §2 now says.
- The checker still *decides* both notions exactly for the Kleene fragment
  (identity is a polynomial test; grid-equivalence is a finite evaluation), so
  the obligation is discharged — we just report which notion holds.

## Companion finding: the bounder does not scale to deep nesting

`check_branch_range` solves a critical-point system per box face with sympy.
For the primitive connectives and shallow 2-variable nestings it returns the
exact range fast. For **deeply nested 4+-variable** expressions the reduced
polynomial's degree grows (the §3.4 expression/degree growth), and the sympy
solve becomes intractable — the test run **hung** on
`((a && b) || (c && d)) && !(a || d)` until killed. This is not a bug to hide;
it is the §3.4 cost made concrete: removing path explosion buys degree growth,
and the closed-form critical-point method has a practical ceiling. The
equivalence checks have no such limit (identity / grid evaluation are cheap).

**Action taken:** the range-bounding tests cover only the tractable cases; the
scalability wall is stated in the module docstring and here, not papered over.
Future work: a bounder that scales (interval branch-and-bound, or
defuzzification between nesting levels to cap degree — see §3.4).
