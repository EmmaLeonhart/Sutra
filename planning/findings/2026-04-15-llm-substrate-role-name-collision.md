# LLM substrate + lexically-similar role names = binding collapse

Date: 2026-04-15
Context: wired frozen-LLM (Ollama, `nomic-embed-text`, 768-dim) into
`codegen_numpy.py` per STATUS.md item 1.

## What was measured

`examples/_smoke_test.py` under the LLM substrate (Ollama live):

- Examples 1–8: **pass** (23/23 role-filler records, 25/25 codebook
  lookups — including noisy variants).
- Example 9 (`sequence.su`, position-bound bundle): **3/11**.
  - `decode_at(seq_fox, pos_1..4)` all return `"the"` (first token).
  - `sim(seq_fox, seq_dog) = 0.939` — nearly identical bundles despite
    disjoint content (shared only at `pos_2 = brown`).

Baseline with seeded-random vectors (same test): 11/11.

## Cause

`sequence.su` binds fillers to roles named `pos_0`, `pos_1`, …,
`pos_4`. Under the LLM substrate, `embed("pos_0")` and `embed("pos_1")`
are lexically near-identical tokens and the LLM returns near-identical
vectors. After mean-centering, cosine between adjacent positional role
vectors is still high enough that `sign(pos_i) ≈ sign(pos_j)` — which
collapses sign-flip binding into "bind everything with roughly the
same sign pattern." Unbinding any position recovers the bundle's
first-loaded token, not the position-specific filler.

The other examples pass because their role names are semantically
distinct (`agent`, `patient`, `color`) or there is no binding at all
(codebook lookup).

## Why mean-centering wasn't enough

The `embed()` helper already mean-centers vectors before normalization
(sign-flip's algebra needs approximately zero-mean). That fixes the
"all vectors in a common cone" problem but does not fix lexical
similarity between role names — two near-identical inputs give two
near-identical outputs regardless of centering.

## Implication

This is a **substrate-program interaction**, not a compiler bug. The
LLM substrate implements semantic embedding, which is exactly the
wrong thing for structural roles that need to be near-orthogonal. Two
principled fixes, both at the program level:

1. Use semantically distinct role names (`first`, `second`, `third`…)
   instead of serialized ones (`pos_0`, `pos_1`…). Still LLM-backed.
2. Introduce a `role("name")` primitive distinct from `embed("name")`
   that draws a seeded-random near-orthogonal vector regardless of the
   substrate. This matches what `sutra-paper/scripts/sutra_runtime.py`
   does in its `EmbeddingSubstrate.random_roles()` — content comes
   from the LLM, roles come from an RNG. That split is load-bearing
   for any VSA system backed by a natural embedding space.

The second is the right answer and belongs in the spec. Open question
added to `examples/todo.md`.

## What got committed

- `codegen_numpy.py`: Ollama-backed `embed()` with mean-centering and
  graceful fallback to seeded-RNG when Ollama is unavailable.
- Default model: `nomic-embed-text` (avoids mxbai diacritic
  attention-sink defect per CLAUDE.md).
- Default dim: 768 (the LLM's native dim, not 256).

## What did not get committed

- A fix for `sequence.su`. The example genuinely does not work on the
  LLM substrate as written, and rewriting it to pick role names that
  happen to LLM-disambiguate would be papering over the real finding.
  Left failing; recorded here so a later session doesn't rediscover
  it.
