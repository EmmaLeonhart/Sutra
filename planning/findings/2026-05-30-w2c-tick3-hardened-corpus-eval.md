# weight→code seq2seq, tick 3 on the HARDENED corpus: coefficient recovery is the wall

**Date:** 2026-05-30
**Scripts:** `experiments/w2c_seq2seq/{prepare,model,eval_substrate}.py`
**Corpus:** hardened 3600-program corpus (`corpus/` submodule `03336b9`; 15
structures incl. 5 inference-forcing families)
**Supersedes context:** `planning/findings/2026-05-30-w2c-seq2seq-substrate-eval.md`
(the v0 result on the 2400-program / 10-structure corpus: 0.842 / 0.842)

## What changed

Emma's option-A call: the v0 0.842 was inflated by a small, templated program
space, so the model was largely template-matching, not inferring. Tick-3
hardening added 5 families that force inference — `chain4` (deeper chain) and
four families carrying a per-program **discrete coefficient** `a`/`b` ∈
{0.5,1.0,1.5,2.0,3.0} rendered as a source literal: `scaled_res` (`a·M@x + x`),
`gen_affine` (`a·M@x + b·x`), `scaled_diff` (`a·M@x − b·x`), `two_mat_affine`
(`a·M0@x + b·M1@x`). A coefficient is recoverable only from IO+weights
(`a = (y−x)/(M@x)`), so it cannot be templated. Same model/training as v0
(1.48M-param `W2CSeq2Seq`, 40 epochs, CUDA), re-run on the bigger split
(train 3240 / val 360).

## Results (n=360 held-out, real measured)

| metric | v0 (2400 corpus) | tick-3 (3600 hardened) |
|---|---|---|
| exact-match | 202/240 = **0.842** | 244/360 = **0.678** |
| substrate IO-reproduction | 202/240 = **0.842** | 254/360 = **0.706** |
| non-exact-but-IO-ok ("different code, same function") | **0** | **10** |
| compile failures | 0 | 0 |
| run-stage exceptions | 0 | 0 |

Exact-match dropped 0.842 → 0.678 and IO-reproduction 0.842 → 0.706, **as
predicted** — the harder space defeats templating, which was the point of the
hardening.

> **Correction (follow-up #1, same day).** The "10 non-exact-but-IO-ok" cases
> above are **not** genuine "different code, same function" wins — they are
> entirely a scoring artifact. The generator renders a unit coefficient as the
> redundant literal `1.0 * EXPR`; the model correctly simplifies it to `EXPR`,
> which raw exact-match counts as a miss. Adding a canonical exact-match that
> strips `1.0 * ` (`eval_substrate.canonicalize_source`) lifts exact-match from
> 244 → **254**, exactly closing the gap, and **canonical exact-match == IO-
> reproduction (254 = 0.7056) in every one of the 15 families**. So after
> canonicalization there are **zero** genuine behavioral wins: textual and
> behavioral correctness coincide here, same as v0. The `io_rate > exact_rate`
> entries in the per-structure table below are all unit-coeff mis-scoring; the
> `exact_canon_rate` column (now emitted) equals `io_rate` throughout.

## Per-structure breakdown (the actual story)

| structure | n | exact_rate | io_rate | note |
|---|---|---|---|---|
| bundle2, bundle3, chain3, **chain4** | 24 ea | 1.000 | 1.000 | structural, solved |
| sum2 | 24 | 0.958 | 0.958 | |
| affine, chain2 | 24 ea | 0.917 | 0.917 | |
| diff | 24 | 0.833 | 0.833 | |
| linear | 24 | 0.708 | 0.708 | degraded vs v0 |
| scaled | 24 | 0.708 | 0.708 | degraded vs v0 |
| **two_mat_affine** | 24 | 0.333 | 0.542 | coeff family |
| **residual** | 24 | 0.333 | 0.333 | `M@x + x` |
| **gen_affine** | 24 | 0.250 | 0.333 | coeff family |
| **scaled_diff** | 24 | 0.125 | 0.208 | coeff family |
| **scaled_res** | 24 | 0.083 | 0.125 | coeff family |

Two findings fall straight out:

1. **Depth is not the hard axis; coefficients are.** `chain4` (the deepest,
   4-matrix chain) is solved perfectly (1.000). Every collapse is in a family
   that carries a learned scalar coefficient. The model recovers arbitrarily
   deep *structure* but not a single non-trivial *number*.

2. **Cross-family interference.** Simple `linear` and `scaled` *degraded* (≈0.96
   → 0.708) even though they are unchanged from v0. Adding confusable neighbors
   (`scaled_res`, `gen_affine`, …) made the model mis-classify the simple cases.
   The capacity wasn't free.

## Coefficient recovery — the wall, measured

Splitting the 96 coeff-family val programs by whether *all* their coefficients
equal 1.0 (re-decoded against the corpus `coeffs`):

| bucket | n | exact-match |
|---|---|---|
| all coefficients == 1.0 | 17 | **0.000** |
| any coefficient != 1.0 | 79 | **0.241** |

Both buckets are hard for exact-match, for **different** reasons:

- **Unit coefficients (exact 0.000):** the generator renders `1.0 * M@x + x`
  with the redundant `1.0 *` literal, but the model *correctly simplifies* it to
  `M@x + x` — behaviorally identical, textually different, so never an exact
  match. These correct simplifications are exactly the 10 IO-wins (e.g.
  `two_mat_affine` a=b=1 → `M0@x + M1@x`; `gen_affine` a=3,b=1 →
  `3.0*M0@x + x`, dropping only the unit term). **This is a corpus artifact:**
  exact-match mis-penalizes a correct simplification. IO-reproduction is the
  metric that credits it.
- **Non-unit coefficients (exact 0.241):** genuine hard inference — read
  0.5/1.5/2.0/3.0 off weights+IO — and the model mostly fails (value-mismatch:
  compiles + runs, wrong number).

## What this validates / what it opens

- **Validates option A.** v0's 0.842 *was* templating. On a space that needs
  inference, the same model drops to 0.678 exact / 0.706 IO, and the drop is
  localized entirely to the coefficient axis. Structure transfer is real and
  near-perfect (chain4 = 1.0); scalar-coefficient inference is the open problem.
- **Follow-up #1 — DONE (eval-side canonicalization).** `eval_substrate.py`
  now reports `exact_match_canonical` (strips `1.0 * `) alongside raw exact, and
  `exact_canon_rate` per structure. Measured: it lifts exact 244 → 254 = IO-
  reproduction exactly, confirming the unit-coeff gap was a pure scoring
  artifact (see Correction above). This makes the metric honest without a corpus
  regen. The *generator-side* canonicalization (emit the bare form when a
  coefficient is 1.0) is now **optional** — it improves published-corpus
  cleanliness but has no further metric impact; deferred unless we regen for
  another reason.
- **Follow-up #2 — open (the real research lever).** Recovering a discrete
  *non-unit* coefficient (exact 0.241) is a classification the char-decoder does
  poorly; an explicit coefficient-prediction head (or a coefficient-augmented
  input feature) is the model-side lever. This is the item the hardening
  surfaced and the next substantive W2C step.

## Honesty caveats

- **Single greedy decode, single retrain, no seed pin on the data split churn.**
  The corpus regen drew fresh random weights (Python hash salt per process), so
  this is not the identical weight set as any prior run; numbers move a few
  points across retrains. The *direction* (coefficient families collapse) is the
  robust signal, not the third decimal.
- **Still small-K (4…16) plain-numeric matmul**, not the 868-d semantic regime.
- The per-structure breakdown is now emitted by `eval_substrate.py`
  (`summary.per_structure`); the unit/non-unit split was a one-off re-decode
  against the corpus `coeffs` (not committed).
