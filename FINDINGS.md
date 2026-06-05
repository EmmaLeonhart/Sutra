# FINDINGS — Replicating Percepta `transformer-vm` ("Can LLMs Be Computers?")

**Verdict: REPLICATED.** A transformer with **analytically-computed, untrained
weights** correctly simulates a WebAssembly VM on every test program — all 6/6
reproduce their reference WASM execution traces token-for-token. Throughput is
~18K tok/s on a WSL CPU box (the authors report ~30K, likely native/Accelerate)
— the same order of magnitude.

- **Target:** [Percepta-Core/transformer-vm](https://github.com/Percepta-Core/transformer-vm)
  (no arXiv; published as code + blog). Submodule pinned at `6cfee30`.
- **This replication:** https://github.com/EmmaLeonhart/replicating-transformer-vm
- **Method:** recipe-first. The repo ships its own reproduction recipe
  (`uv run wasm-run`); we provisioned the toolchain, ran it, and checked its
  output against the blog/README headline claims. We did **not** reimplement —
  the gap we filled was purely environmental (toolchain + host).

## What the system is

The program is **not trained**. Its weights are *constructed analytically* from a
computation-graph DSL: a C program is compiled to WebAssembly, the 35 supported
WASM opcodes are encoded as byte-level arithmetic over a residual stream that acts
as machine memory (stack / locals / memory / cursor / call-depth), a MILP solver
schedules graph nodes onto transformer layers, and the resulting tensors are
written out. A standard softmax-ReGLU transformer then runs that bytecode
autoregressively, one byte of machine state per token. An O(log n) "hull" KV-cache
(incremental 2D convex hull + hardmax) replaces O(n) softmax attention.

## Reproduced vs. reported

| Claim | Reported | This replication | |
|-------|----------|------------------|---|
| Analytic (untrained) weights simulate a WASM VM on arbitrary programs | correct on all programs | **6/6 PASS**, token-for-token vs. reference | ✅ |
| 35 WASM opcodes via computation-graph DSL | 35 | all programs compile (incl. lowering of MUL/DIV/AND/OR/XOR/SHL/SHR) and run | ✅ |
| Real algorithms incl. Sudoku ~900K tokens | sudoku ~900K | **sudoku 1,055,417 tokens, solved correctly** | ✅ |
| Inference throughput | ~30K tok/s | **18K–24K tok/s** (mean 18,049 over 1.29M tokens) | ◑ same order |
| O(log n) hull KV cache | yes | exercised in the C++ engine (hull = 39.9% of runtime) | ✅ |
| First Futamura projection (program baked into weights) | yes | collatz baked into weights (d_ffn=1630, 1.69M params); specialized model output correct | ✅ |

### Per-program measurements (`uv run wasm-run`, C++ engine)

Analytic model: `d_model=38, n_layers=7, n_heads=19, d_ffn=44, vocab=915`
(MILP solved to optimality in 5.5s; head projection 85% sparse).

| Program | Result | Tokens | tok/s | Output |
|---------|--------|-------:|------:|--------|
| hello | PASS | 1,034 | 22,090 | `Hello World!` |
| addition | PASS | 4,362 | 23,384 | `19134` |
| fibonacci | PASS | 9,104 | 23,626 | `55` |
| collatz | PASS | 44,589 | 22,002 | `7 22 11 34 17 52 26 13 40 20 10 5 16 8 4 2 1` |
| min_cost_matching | PASS | 178,226 | 19,178 | Hungarian algorithm, `optimal cost: 9` |
| sudoku | PASS | 1,055,417 | 17,684 | `534678912672195348198342567859761423426853791713924856961537284287419635345286179` |
| **total** | **6/6** | **1,292,732** | 18,049 mean | 269,858 wasm-ops in 71.6s |

The graph evaluator (`wasm-eval`, exact arithmetic, no weights) independently
generated the reference traces and confirmed `addition: PASS`; the C++-engine PASS
results above are the stronger check (they exercise the actual analytic weights).
The repo's own fast test suite also passes — `pytest -m "not slow"`: **4 passed,
7 deselected** (graph-evaluator hello + collatz, WASM-machine build, graph
imports).

## What the recipe covered vs. what we filled

- **Recipe covered (everything substantive):** compilation C→WASM, opcode
  lowering, MILP scheduling, analytic weight construction, the C++ inference
  engine, the hull cache, reference-trace generation, and PASS/FAIL verification.
  The replication is essentially "make the authors' recipe run and confirm its
  self-check passes," which it does.
- **We filled (environment only):** chose **WSL Ubuntu 24.04** as the host
  (Windows lacks uv/clang/MSVC and the repo documents only macOS/Ubuntu);
  installed `uv`, `build-essential clang lld cmake`, and synced deps (torch 2.10,
  HiGHS, pybind11). On Linux the C++ engine builds with plain
  `g++ -std=c++17 -O3` — **no BLAS** (that path is Apple-only). Added
  `scripts/run.py` to emit `results/metrics.json` for CI.

## Gaps / divergences

1. **Throughput ~60–80% of the claim** (18K vs ~30K tok/s). Plausible causes: WSL
   CPU + filesystem overhead, no Accelerate/BLAS on Linux (the engine uses a plain
   matvec fallback), and no machine-spec given for the authors' 30K figure. The
   *qualitative* claim (real-time execution of million-token programs on commodity
   CPU) holds.
2. **Python `hull_ext` extension did not build** — it needs `Python.h`
   (`python3-dev` / `python3.12-dev`), which was not installed, so `wasm-eval`
   fell back to brute-force O(n) attention (~30 tok/s) and is impractical for the
   large programs. This does **not** affect the headline path: the C++ engine
   embeds the hull cache as a header (`hull2d_cht.h`) and needs no Python.h.
   Installing `python3-dev` would let the Python inference path and `wasm-eval
   --hull` run fast too.
3. **First Futamura projection** confirmed: `wasm-specialize` baked collatz (813
   instructions) into a specialized model (`d_model=40, 8 layers, d_ffn=1630`,
   1.69M params, 13.5 MB) — MILP solved to optimality in ~20 min — and the
   specialized model reproduced the correct collatz sequence. Throughput drops to
   ~1.2K tok/s (projection becomes 93% of runtime since the program lives in the
   FFN), the expected size/speed trade. The harness labels it "RAN" not "PASS"
   only because the specialized input ships no `_ref` auto-compare file; the
   output matches the known-correct reference trace.
4. **Sudoku token count** 1.06M vs the README's "~900K" — same order of magnitude;
   exact count is puzzle-dependent.

## Reproducing this

Prereqs (Ubuntu/WSL): `sudo apt install -y build-essential clang lld cmake`, plus
[`uv`](https://docs.astral.sh/uv/). Then:

```bash
git submodule update --init
( cd replication_target/transformer-vm && uv sync )
python scripts/run.py            # runs the recipe, writes results/metrics.json
# or directly:
cd replication_target/transformer-vm && uv run wasm-run
```
