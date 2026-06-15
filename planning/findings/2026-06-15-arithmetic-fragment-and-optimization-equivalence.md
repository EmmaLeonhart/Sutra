# The FV decision procedure covers integer arithmetic — and verifies optimization equivalence

**2026-06-15.** Two related results (Emma's "keep pushing FV substantively" call, attacking
the recurring "fragment too narrow / demos too small / not real-world" reviewer cons).

## The verified fragment is *polynomial expressions*, not just AND/OR/NOT

`reduces_to_same_graph` / `reduces_to_same_graph_randomized` decide equivalence over the
whole **polynomial fragment**: the Kleene connectives `&&`/`||`/`!` AND integer arithmetic
`+`/`-`/`*`, freely mixed. The exact route always did (the inliner leaves `+`/`-`/`*`
alone); the **randomized PIT** evaluator (`_eval_kleene_ast`) was extended to cover the
arithmetic operators + int literals + unary minus, so the *scalable* poly-time route now
handles arithmetic and mixed Kleene+arithmetic identity too (was Kleene-only).

Clean contrast: arithmetic distributivity `(a+b)·c = a·c + b·c` **is** a same-graph identity
(equal polynomials), the exact mirror of Kleene distributivity, which is only grid-equivalent.
One checker decides both. (`test_decision_procedure_covers_integer_arithmetic`.)

## A real-world use: verifying that a compiler optimization preserves semantics

Because arithmetic equivalence reduces to the same polynomial-identity test, the checker
verifies **optimization soundness** on arithmetic programs — measured
(`test_verifies_arithmetic_optimization_equivalence`, exact ⟺ randomized agree):

| optimization | naive | optimized | verdict |
|---|---|---|---|
| Horner's method (deg 3) | `a·x³ + b·x² + c·x + d` | `((a·x + b)·x + c)·x + d` | **same graph** (sound) |
| identity folding | `(x + 0)·1` | `x` | same graph |
| reassociation | `2·x + 3·x` | `5·x` | same graph |
| sign bug ("optimization") | `a·x² + b·x + c` | `a·x² − b·x + c` | **different graph** (caught) |

The decision procedure is unchanged; only the inputs differ. This is a concrete answer to
"the fragment is too narrow / the demos don't prove real-world utility": semantics-preserving
compiler-rewrite checking is exactly the kind of property a trusted base needs, and it is the
same polynomial-identity test — now decidable in poly time at depth via Schwartz–Zippel.

Implementation: `sdk/sutra-compiler/sutra_compiler/fv_obligation_checker.py`. Paper §3.
