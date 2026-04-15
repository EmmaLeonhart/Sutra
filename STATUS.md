# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

1. **Pick the two example programs.** Example 1 is `fly-brain/fuzzy_conditional.su` (already compiles; has reference outputs in `test_codegen_e2e_fuzzy.py` — extract to a committed golden file). Example 2 TBD: must exercise something distinct from example 1 (candidates in `planning/runtime-inventory-2026-04-14.md` §Decisions). Write sources + expected outputs under `examples/` (or surface the fly-brain file there).
3. **Codegen V1 carryover: close feature gaps needed by the two examples.** 6/13 illustrative `.su` files currently hit `CodegenNotSupported` (method/operator decls, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`). Only fix the ones the two chosen examples actually need — do not try to clear all 6. Breakdown: `planning/open-questions/codegen-v1-feature-coverage.md`.
4. **End-to-end run: example 1.** Source → matrix ops → output, matching the expected output committed in step 2.
5. **End-to-end run: example 2.** Same.
6. **Repo cleanup.** README with one-paragraph "what this is," install command, single command to run both examples. License file. No dead TODOs in paths the README hits. Fresh-clone reproducibility test.
7. **Paper assembly.** Pull from existing `sutra-paper/` material into the claw4s-scope structure (abstract / background / language / runtime / demonstrations / discussion / limitations / reproducibility appendix). No rewrite, just assembly.
8. **Honesty pass.** Red-pen the paper for any claim of brain execution, latent-space execution, or citations that don't exist. Fix paper IDs (clawRxiv `2604.01127`). "Preprinted" not "published."
9. **Submit.** Push triggers `papers-ci.yml` → clawRxiv. Buffer day Apr 20.

**Hard stop:** if by end of Apr 17 the runtime isn't executing at least one example end-to-end, stop pushing for Claw4S (per `claw4s-scope.md`). Fellows application Apr 26 is higher priority.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. Spec: `planning/sutra-spec/03-control-flow.md`.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Permute → sign_flip rename.** The op does `a * sign(role)`, not dimension permutation. Spec's `permute` means shuffle. Aliases preserved.

## Pointers

- Strategic scope & Apr 20 build list: `claw4s-scope.md`.
- Formal Sutra grammar (EBNF): `planning/sutra-spec/grammar.md`.
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
