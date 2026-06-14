# Randomized PIT (Schwartz–Zippel) escapes the FV equivalence-check wall

**2026-06-14.** The FV obligation checker decides "do two Kleene programs compile to
the same tensor graph?" by polynomial identity. The exact route — `expand(p_a - p_b)
== 0` — is the scalability wall reviewers repeatedly flagged (clawRxiv v64–v67: ">1000
terms at depth 3", "geometric explosion", "impractical"). This finding records the
substantive fix and its measured scaling.

## Why the exact route blows up — it is NOT just `sympy.expand`

The Kleene lowering **duplicates operands**: the inliner emits, for the connectives,

- `!a = -a`
- `a && b = (a²b² − a² + ab + a − b² + b) / 2`
- `a || b = (−a²b² + a² − ab + a + b² + b) / 2`

so each `&&`/`||` mentions each operand several times. Nesting therefore makes the
*inlined arithmetic tree itself* exponential in depth — before any `expand`. Measured
on the SAME `extract_truth_polynomial` pipeline the checker uses (balanced &&/|| trees,
var pool 3; `experiments/randomized_pit_scaling.py`):

| depth | leaves | monomials of `expand(E)` | `expand` time |
|------:|-------:|-------------------------:|--------------:|
| 1 | 2 | 6 | 0.6 s |
| 2 | 4 | 312 | 0.07 s |
| 3 | 8 | **INFEASIBLE** | **> 30 s** (killed) |

## The fix — evaluate the ORIGINAL tree by formula in F_p

`reduces_to_same_graph_randomized` decides the SAME identity by **Schwartz–Zippel**:
evaluate `p_a − p_b` at random points and check it vanishes. The key to scaling is to
evaluate the **un-inlined** Kleene expression by applying each connective's polynomial
formula to its children's *values* (mod a 61-bit prime `p = 2^61 − 1`) — one number per
node, O(tree size), no duplication, no `expand`, no sympy on the hot path. Soundness is
one-sided: any nonzero evaluation is an **exact disproof** (with a witness point); all-zero
over `k` trials certifies identity with false-positive probability `≤ (degree/(p−1))^k`.

Measured (same script, 32 trials):

| depth | leaves | randomized time | degree bound | verdict |
|------:|-------:|----------------:|-------------:|:--------|
| 4 | 16 | 0.004 s | 256 | correct |
| 6 | 64 | 0.017 s | 4 096 | correct |
| 8 | 256 | 0.039 s | 65 536 | correct |
| 10 | 1 024 | 0.152 s | 1 048 576 | correct |
| 12 | 4 096 | **0.822 s** | 16 777 216 | correct |

So the procedure decides at **depth 12 (4096 leaves) in under a second** what `expand`
cannot do at **depth 3**. Verdicts agree with the exact check wherever the exact check is
still
feasible (the unit tests cross-check De Morgan / commutativity / distributivity /
absorption; `test_fv_general_checker.py`).

## Honest scope

- **One-sided probabilistic, not certain.** The exact check is a certain decision (when it
  terminates); randomized PIT trades certainty for a negligible, *quantified* error. With
  `p = 2^61−1`, 32 trials, degree ≤ 1.7×10⁷ (depth 12), the false-positive bound is
  ~`(10⁷/2⁶¹)³² ≈ 10⁻³⁶⁰`.
- **Degree vs. prime.** The degree quadruples per `&&`/`||` level (≈ 4^depth), so beyond
  ~depth 30 the degree approaches `p` and the per-trial margin shrinks; a larger prime, or
  CRT over several primes, restores it. Not needed for any realistic Kleene nesting.
- **Integrity guard.** The hard-coded connective formulas are checked against the
  compiler's own inliner (`test_kleene_connective_formulas_match_inliner`), so the
  randomized check decides the same polynomial as `reduces_to_same_graph`, not a drift.

Implementation: `sdk/sutra-compiler/sutra_compiler/fv_obligation_checker.py`
(`reduces_to_same_graph_randomized`, `_eval_kleene_ast`, `_kleene_degree_bound`).
