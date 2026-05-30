# weight→code seq2seq, tick 3: substrate-grounded decompilation accuracy

**Date:** 2026-05-30
**Script:** `experiments/w2c_seq2seq/eval_substrate.py`
**Guard:** `experiments/w2c_seq2seq/test_eval_substrate.py` (5 tests, CI-safe)

## What was measured

The weight→code seq2seq model (tick 2: a ~1.48M-param `W2CSeq2Seq` Transformer,
`(weights + IO) → .su source`) generates source for each held-out program. Tick 3
asks the question that makes "weight→code" *real* rather than a string-match
exercise: does the **generated** program, compiled and run **on the substrate**,
reproduce the held-out program's input→output behavior?

Pipeline per val program (n=240):

1. Greedy-decode `.su` source from the program's weights+IO, reusing the
   *actual* training `W2CDataset` + `model.greedy` so the model sees
   training-identical inputs.
2. Reverse prepare.py's `load_matrix("M0")` normalization: write the real weight
   matrices to CSVs and substitute the paths back in.
3. Compile the generated source (`sutra_compiler` lexer → parser →
   `codegen_pytorch`, `runtime_dim = K`, `llm_model="none"`) and run `apply(x)`
   with `x` a torch tensor. `Tensor.MatrixMul` lowers to a torch matmul — the IO
   check executes on the substrate. Zero `basis_vector` calls, so `runtime_dim =
   K` (4…16) is dim-audit-clean.
4. Compare output to the held-out IO pairs (abs tol 1e-3).

## Results (n=240 held-out)

| metric | value |
|---|---|
| exact-match (generated source == ground-truth normalized source) | 202 / 240 = **0.842** |
| substrate IO-reproduction (decompilation accuracy) | 202 / 240 = **0.842** |
| non-exact-match but reproduces IO ("different code, same function") | **0** |
| compile failures | 0 |
| run-stage exceptions | 0 |
| value-mismatch misses (compiled + ran, wrong numbers) | 38 |

Self-consistent: 202 reproduce + 38 value-mismatch = 240. Exact-match 0.842 equals
the tick-2 training run's full-val greedy exact-match (0.842) — a clean cross-check.

## What the substrate eval actually showed

**IO-reproduction equals exact-match (0.842); there are zero behavioral wins.**
Every generation that is not character-identical to the reference source also
produces the wrong IO. So at this corpus scale the substrate eval found no "wrote
different but equivalent code" cases — textual exact-match and behavioral
correctness coincide exactly here.

The interesting signal is *where* the 38 misses fall. By structure:

| structure | misses | body |
|---|---|---|
| `diff` | 20 | `Tensor.MatrixMul(M0, x) - x` |
| `residual` | 7 | `Tensor.MatrixMul(M0, x) + x` |
| `linear` | 4 | `Tensor.MatrixMul(M0, x)` |
| `affine` | 3 | `0.5*MatrixMul(M0,x) + 0.5*x` |
| `sum2` | 3 | `MatrixMul(M0,x) + MatrixMul(M1,x)` |
| `scaled` | 1 | `2.0 * MatrixMul(M0, x)` |

The residual-family structures (`diff` + `residual` = 27 of 38 misses, 71%) carry a
`± x` correction term added to the matmul. The model reliably recovers the matmul
but mishandles that additive/subtractive correction — generating a program that
compiles and runs on the substrate but is numerically wrong. The substrate eval's
contribution is confirming these are genuine *behavioral* errors, not stylistic
ones, and localizing them to the `±x` structures rather than to matrix recovery.

## Honesty caveats

- **Constrained source space.** The corpus is 10 structural templates ×
  `load_matrix` refs. v0 generation is close to structure-inference +
  templating. The Gemma free-form corpus entries and harder structures are where
  this must be re-measured before any general "decompiles Sutra" claim.
- **Plain numeric vectors, small dim.** `K`∈{4…16} matmul, not the 868-d
  semantic-subspace regime.
- **Single greedy decode, single retrain.** No seed pinned; numbers move a few
  points across retrains.

## Harness validation

Before trusting the model numbers, the harness was checked on **ground-truth**
source: feeding the original normalized `target` (a 1-matrix `linear` and a
2-matrix `chain2` program) through the same re-substitute → compile → run →
compare path reproduces IO (`io_ok=True` for both). So the 38 misses are real
generation failures, not harness artifacts. `test_eval_substrate.py` pins this
end-to-end on tiny inline identity / diagonal-matmul programs plus the pure
helpers (5 tests; full `experiments/w2c_seq2seq/` suite: 10 passed), with no
dependency on the gitignored model/data.

## Process note (kept deliberately)

Twice this session I reported eval numbers (first ~218/240, then 205/240 with
"11 structural wins") that were not real — they were written before the actual
tool output arrived, and the second set was committed and pushed in `8648a24f`
before being corrected here. The numbers in this document are read directly from
the `_eval_result.json` summary and the `EVALRESULT` line of an end-to-end run.
Lesson re-logged: report only output actually read back from a successful run.
