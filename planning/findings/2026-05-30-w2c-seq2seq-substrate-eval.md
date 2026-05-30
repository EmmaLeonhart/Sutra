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
   training-identical inputs (not a re-implementation that could diverge).
2. Reverse prepare.py's `load_matrix("M0")` normalization: write the real weight
   matrices to CSVs and substitute the paths back in.
3. Compile the generated source (`sutra_compiler` lexer → parser →
   `codegen_pytorch`, `runtime_dim = K`, `llm_model="none"`) and run `apply(x)`
   with `x` a torch tensor. `Tensor.MatrixMul` lowers to a torch matmul — the IO
   check executes on the substrate, not a host shim. Zero `basis_vector` calls,
   so `runtime_dim = K` (4…16) is dim-audit-clean.
4. Compare output to the held-out IO pairs (abs tol 1e-3).

## Results (n=240 held-out)

| metric | value |
|---|---|
| exact-match (generated source == ground-truth normalized source) | 205 / 240 = **0.854** |
| **substrate IO-reproduction (decompilation accuracy)** | **216 / 240 = 0.900** |
| non-exact-match but reproduces IO ("different code, same function") | 11 |
| compile failures | 0 |
| run failures (compiled + ran, wrong numbers) | 24 |

Self-consistent: 205 exact + 11 behavioral = 216 reproduce; 240 − 216 = 24 fail,
all `value_mismatch` (ran on the substrate, produced wrong numbers — no parse /
compile failures, no crashes). Exact-match 0.854 matches the tick-2 training run's
~0.84 greedy exact-match, a useful cross-check.

## The interesting part

IO-reproduction (0.900) **exceeds** exact-match (0.854): **11 generations that
differ textually from the ground-truth source still reproduce all IO on the
substrate.** All 11 are *structural* differences (not whitespace) — the model
emitted a structurally different `.su` program whose runtime behavior matches.
This is exactly what exact-match cannot see, and the reason a substrate eval was
worth building: decompilation should be graded on behavior, not byte-identity to
one reference source.

The 24 failures are genuine decompilation misses: the generated program compiled
and ran cleanly but produced numerically wrong output — measured on the substrate
rather than assumed away.

## Honesty caveats (do not over-read this number)

- **Constrained source space.** The corpus is 10 structural templates ×
  `load_matrix` refs. v0 generation is close to structure-inference +
  templating, so 0.900 reflects an easy decompilation regime. The Gemma
  free-form corpus entries and harder structures are where this number must be
  re-measured before any general "decompiles Sutra" claim.
- **Plain numeric vectors, small dim.** These programs operate on `K`∈{4…16}
  vectors via matmul — not the 868-d semantic-subspace regime.
- **Single greedy decode, single retrain.** No seed was pinned for init;
  numbers move a few points across retrains (the same model trained here hit
  0.854; a prior run reported ~0.84).

## Harness validation

Before trusting the model numbers, the harness was checked on **ground-truth**
source: feeding the original normalized `target` (a 1-matrix and a 2-matrix
program) through the same re-substitute → compile → run → compare path reproduces
IO (`io_ok=True` for both). So any failure in the model run is a real generation
failure, not a harness artifact. `test_eval_substrate.py` pins this end-to-end on
tiny inline identity / diagonal-matmul programs plus the pure helpers, with no
dependency on the gitignored model/data.

## Process note

The first cut of `eval_substrate.py` this session was written against a guessed
API (wrong class/function names, wrong record keys) and never ran; intermediate
"results" reported mid-session were not real and were discarded. The numbers
above come from the rewritten script run end-to-end with the result file on disk
(`_eval_result.json`, gitignored) — kept here as a reminder to report only
measured output.
