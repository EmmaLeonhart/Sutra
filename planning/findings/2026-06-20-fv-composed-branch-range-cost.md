# FV branch-range: the closed-form direct bounder walls at depth 2; composition is the discharge (2026-06-20)

## Question

The Pillar-2 **branch-range obligation** (`planning/sutra-spec/formal-verification.md`;
`paper/formal-verification/paper.md` §3.2) is discharged in closed form for the three atomic
connectives `&&`/`||`/`!` — `bound_polynomial_over_box` proves each has exact range `[-1,+1]` over the
truth box (`test_fv_poly_obligation_checker.py`). `todo.md` carried an open remainder:

> Remaining: run the bounder on the *composed* polynomials of whole reduced programs (degree grows with
> branch-nesting; characterise the numerical cost there).

This characterises that cost, and resolves what "running the bounder on composed polynomials" should
actually be.

## Measurement

`experiments/fv_composed_branch_range_cost.py` runs `check_branch_range` (extract the composed Kleene
polynomial → `bound_polynomial_over_box`) on nested expressions of increasing depth, each in a worker
process with a 30 s hard timeout. Dev machine:

| case | range | sound | deg | crit pts | time |
|---|---|---|---|---|---|
| `a && b` (1 connective) | `[-1,1]` | True | 4 | 5 | 97 ms |
| `(a && b) || c` (depth 2) | — | — | — | — | **TIMEOUT >30 s** |
| `(a && b) || (c && d)` (depth 2) | — | — | — | — | **TIMEOUT >30 s** |
| `!((a && b) || c)` (depth 2) | — | — | — | — | **TIMEOUT >30 s** |
| `((a&&b)||(c&&d)) && !e` (depth 3) | — | — | — | — | **TIMEOUT >30 s** |
| `((a&&b)||(c&&d)) && (!e||(a&&c))` (depth 4) | — | — | — | — | **TIMEOUT >30 s** |

**The direct closed-form route falls off a cliff immediately.** A single connective bounds in ~0.1 s;
the very first composition (depth 2) is already intractable (>30 s). This is not a gentle degree-growth
curve — it is a wall at depth 2. The cause is `bound_polynomial_over_box`'s exact critical-point search:
it enumerates the faces/edges/vertices of the `n`-box and solves the polynomial critical-point system on
each, and both the face count and the per-face system blow up once the composed polynomial's degree and
arity climb past one connective.

## Resolution — composition, not direct bounding (already built; this confirms WHY)

The whole-program obligation is **not** discharged by bounding the composed polynomial. It is discharged
by **structural induction on the expression tree** (`range_sound_by_composition`,
`fv_obligation_checker.py`): each connective is proven (by the closed-form bounder above, the per-connective
lemma) to map `[-1,+1]^k → [-1,+1]` exactly, so any expression built solely from connectives over
truth-axis inputs in `[-1,+1]` has range within `[-1,+1]` by induction — **degree-insensitively**, at any
nesting depth, instantly. The check refuses (returns False) if the expression uses any non-connective
operator (a comparison, arithmetic, a call), so the `[-1,+1]` conclusion is never asserted where it does
not follow — sound, not vacuous.

So "run the bounder on the composed polynomials" was the wrong target: the direct route is intractable at
depth 2, and the right discharge (composition) was already built and is what the paper §3.2 describes
("Range-soundness scales to arbitrary depth by composition, the bounder is NOT on the critical path for
depth"). The closed-form bounder stays the exact tool for the **per-connective lemma** the induction rests
on — exactly the regime (single connective) where it is fast.

## What shipped

- `experiments/fv_composed_branch_range_cost.py` — the timeout-guarded cost probe (reproduces the table).
- `test_fv_poly_obligation_checker.py`: `test_composed_range_sound_by_structural_induction` (composition
  discharges depth-2..4 nestings), `test_composition_refuses_non_connective_operators` (refuses `+` and
  comparisons — sound, not vacuous), `test_composition_agrees_with_direct_bound_where_tractable` (on a
  depth-2 case the closed-form direct bound — when it can be run at all — agrees, anchoring the lemma).
- `todo.md` branch-range remainder updated: the composed obligation is discharged by composition (built),
  with this measured wall as the reason the direct route is not used.

## Caveat / honest scope

This is the **structural** (algebraic) argument: every composition of the connectives is range-sound on
the ideal `[-1,+1]` truth domain. It says nothing about VSA **substrate noise** accumulating at increasing
bundle width — that is a separate concern the FV paper handles in its §4 (the per-connective lemma is
"leaky" once realised on noisy substrate vectors). The cost result here is about the *verification
method's* scaling, not about runtime numerical fidelity.
