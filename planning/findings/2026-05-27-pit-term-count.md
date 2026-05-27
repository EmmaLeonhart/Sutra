# 2026-05-27 — PIT term-count honesty for the FV §3.4 claim

## Result summary

The FV paper's "polynomial identity testing replaces path enumeration"
claim is *true* per the general checker (`fv_obligation_checker.py`),
but the cost is not free: the expanded Kleene polynomial's term count
grows roughly geometrically in nesting depth. Measured wall on this
machine:

- depth 1 (any var pool): **6 terms**, < 1 ms
- depth 2 vp=2: **66 terms**, 23 ms
- depth 2 vp=3: **177 terms**, 42 ms
- depth 2 vp=4 or 5: **312 terms**, 62 ms (caps at 4 distinct vars
  because the balanced tree has 4 leaves at depth 2)
- depth 3 vp=2 (balanced and negated): **1054 terms**, 56 s each
- depth 3 vp ≥ 3: the per-row sympy.expand work exceeded a 5-minute
  per-row budget on this machine before the script was killed (~770 MB
  resident); a single deeper / wider row exceeds wall budgets we'd
  honor in CI

This is the honest scaling, not a regression. PIT removes branch /
path enumeration from equivalence checking and replaces it with
*monomial* enumeration; the term count is the cost transparently
exposed.

## Why this matters for the FV paper

The recurring AI-reviewer con is "you say path explosion is removed
but you don't characterise the term-count cost of the expanded
polynomial." The current §3.4 reads (approximately) that polynomial
identity testing decides equivalence cheaply in the Kleene fragment
and that the bounder's degree-growth wall is the only cost surface.
That understates: term count grows fast even at modest depth, and
sympy's `expand` is the bottleneck in practice (not a polynomial-
identity check per se).

Concretely: at depth 3 var-pool 2, the polynomial has 1054 terms and
takes 56 s to expand. At depth ≥ 3 var-pool ≥ 3 the expansion does
not complete in any budget we'd accept for a CI gate. That is the
real cost wall, and naming it precisely is what "PIT honesty" means.

## Method

`experiments/fv_pit_term_count.py` builds balanced binary trees
alternating `&&` (even depth) / `||` (odd depth) over a cyclic pool
of variable names, plus a `!`-wrapped variant. Each expression is
fed to `extract_truth_polynomial` — the SAME pipeline the obligation
checker uses (`Lexer` → `Parser` → `inline_stdlib_calls` → walk into
sympy → `sympy.expand`). Term count = `len(poly.args)` when the
polynomial is an `Add` (single-monomial case = 1).

This is a per-program polynomial, not a per-pair-of-programs
comparison. Equivalence checking via `reduces_to_same_graph(p, q)` is
`expand(p - q) == 0`, which costs O(len(p.args) + len(q.args)) once
both polynomials are in expanded form — the same wall as the
extraction step here.

Honest scope: the measurement covers *balanced* Kleene trees with a
deterministic shape. Real Sutra programs may be smaller / shallower /
more lopsided and so cheaper, OR may compose multiple deep gates and
hit the wall sooner. The number to cite in the paper is "term-count
grows geometrically in depth; on balanced shapes a single sympy
expand at depth ≥ 3 var-pool ≥ 3 exceeds a 5-minute per-row budget."

## What this is NOT claiming

- NOT a claim that term count is the *only* cost of PIT. The expand
  step dominates wall time on the shapes measured; a different
  representation (e.g. BDD-shaped) might trade term-count growth for
  cycle-count or memory growth — left untouched here.
- NOT a claim that all real Sutra programs hit this wall. Most
  programs in the corpus are shallow; the depth at which the wall
  bites is precisely what this measurement quantifies.
- NOT a regression. The general checker still discharges what it
  always did — `reduces_to_same_graph`, `kleene_equivalent`,
  `range_sound_by_composition`. This finding sharpens the *cost*
  framing in the paper; the *correctness* framing is unchanged.

## Reproduction

```bash
python experiments/fv_pit_term_count.py
```

Single-row probe (cheap):

```bash
python -c "
import sys
sys.path.insert(0, 'experiments')
from fv_pit_term_count import measure, gen_balanced_and_or, _vars
vs = _vars(2)
print(measure(gen_balanced_and_or(2, vs), vs))  # (66, 2)
"
```

Single-row probe (the wall):

```bash
python -c "
import sys, time
sys.path.insert(0, 'experiments')
from fv_pit_term_count import measure, gen_balanced_and_or, _vars
vs = _vars(2)
t = time.time()
n, d = measure(gen_balanced_and_or(3, vs), vs)
print(f'depth=3 vp=2: n_terms={n} t={time.time()-t:.1f}s')  # (1054, ~56s)
"
```

## What lands in the FV paper

A short addition to §3.4 (or its successor): cite the depth-1 / 2 / 3
term-count datapoints and the per-row wall, position the measurement
as the cost-side complement to the correctness-side equivalence
result, and note explicitly that beyond depth 3 the sympy `expand`
step is the practical wall. The honest framing replaces any
unqualified "path explosion is removed" wording with "branch
enumeration is replaced by monomial enumeration, whose term count
grows geometrically in depth — measured."
