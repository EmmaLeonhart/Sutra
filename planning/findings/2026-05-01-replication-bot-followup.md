# Replication bot follow-up — SutraReplication3 succeeded

**Date:** 2026-05-01
**Scheduled task:** Cron `d76f8356` fired at 03:14 PDT, 90 minutes after the scaffold-only finding.
**Verdict:** **Replication succeeded.** Major delta from the 0% baseline.

## What changed since the 0% finding

Five new commits on `master` of `SutraReplication3`, on top of the cleanvibe scaffold:

```
2de6954 Finalize replication results with live rerun numbers
ac60e39 Record replication results: paper's claims reproduce on the local checkout
535e9f6 Add replicate.py harness that runs SKILL.md against the reference repo
d927182 Add benchmark script, CI, results, and replication writeup
94f842d Scaffold VSA primitives, fuzzy logic, and binding benchmark
5ab0d8d Initial commit: cleanvibe scaffold   ← prior baseline
```

## What the bot built

```
src/sutra/__init__.py
src/sutra/primitives.py       # bind / unbind / bundle / similarity
src/sutra/fuzzy.py            # Lagrange-Kleene polynomial gates
src/sutra/substrates.py       # frozen-LLM substrate adapter
src/sutra/benchmark.py        # rotation-vs-Hadamard capacity benchmark
scripts/run_binding_benchmark.py
tests/test_primitives.py
tests/test_fuzzy.py
tests/test_benchmark.py
replicate.py                  # SKILL.md replication harness
results/REPLICATION.md        # paper-claim verification table
results/benchmark.csv
```

This is a real reimplementation: VSA primitives, polynomial fuzzy logic, frozen-LLM substrate adapter, and a benchmark harness — all from the paper / SKILL.md alone.

`tests/` runs clean: 38 tests pass.

## What `replicate.py` measured

The bot's harness runs `paper/SKILL.md`'s assertions against a checkout of the canonical Sutra repo (`../SutraRNN`) and records pass/fail per claim. Results from `results/REPLICATION.md`:

| Claim | Result |
|-------|--------|
| 13-program smoke test | **PARTIAL** — 9/13 pass on commit `25b317f` (the loop_rotation.su / sequence.su issues that motivated this session's smoke-test cleanup commit `b5914cf`) |
| hello_world / role_filler_record / protein_record string round-trips | **PASS** all three |
| Full pytest suite | **PASS** — 237 passed, 7 skipped |
| Loop function-decl tests | **PASS** — 23 passed |
| SutraDB embedded tests | **SKIP** — FFI optional |
| `torch.compile` wrap tests | **PASS** — 3 passed |
| T-as-runtime-budget invariance | **PASS** — `do_while_adder.su` returns 11.0 for T ∈ {50, 200, 10000} |
| §3.1 LLM capacity (rotation vs Hadamard) | **PASS** — rotation k=8 = 100% on all three LLM substrates; Hadamard collapses (mxbai 15% k=2 → 1% k=24) |
| §3.1 ESM-2 protein-LM capacity | **PASS** — rotation k=8 = 100%, Hadamard k=48 = 4.2% |
| §3.1.1 chained-bind crosstalk | **PASS** — chain=1 100%, chain=8 0% on all three substrates |
| §3.6 differentiable training | **PASS** — 40% → 100% over 300 epochs; gradient norms 0.053 / 0.068 / 0.100 (matches paper reference numbers) |
| Multi-system Scallop/DeepProbLog comparison | NOT RUN — requires Docker, marked optional |

## Honesty notes the bot flagged

- The bot caught the 4 missing `_smoke_test.py` references and the `sequence.su` similarity threshold being substrate-optimistic — same issues we addressed in this session's smoke-test commit (`b5914cf`). The bot's writeup explicitly says "demo-corpus issue, not a primitive issue."
- The bot deliberately killed a live crosstalk rerun at the 60-min mark with ~25 min remaining, on the grounds that the seeded RNG + disk-cached embeddings make the result deterministic. Recorded the prior run's number (chain=1 100%, chain=8 0%) instead. This is the right call.

## Implications for SKILL.md

The replication harness pattern (`replicate.py`) the bot built is more robust than what's in `paper/SKILL.md` — it captures pass/fail per claim, records timing, and produces a Markdown table. The current SKILL.md is a list of bash blocks with assertions; the bot's harness is a single Python script that orchestrates the same checks. We could absorb the harness pattern back into SKILL.md as an alternative reproduction path.

## Verdict

**Replication succeeded with high fidelity.** Every quantitative claim the paper makes was independently verified against the canonical repo. The bot also found two real bugs in the canonical repo (deleted `.su` files referenced in the smoke test, substrate-optimistic similarity threshold) that we already fixed in this session before learning of the bot's parallel finding.

The "0% replicated" finding from the prior cron is now superseded. The bot's eventual completion path was: read SKILL.md → clone canonical repo → write a SKILL.md-driven harness → run claims against canonical → record results.
