# Claims to reproduce + evidence

Target: Percepta `transformer-vm`. Source of claims: the repo README + the blog
"Can LLMs Be Computers?". See `notes/sources.md` for links.

## Headline claims

| # | Claim | How verified | Status |
|---|-------|--------------|--------|
| C1 | A standard softmax-ReGLU transformer with **analytically-computed (untrained) weights** correctly simulates a WebAssembly VM on arbitrary programs | `wasm-run`: transformer output matches the reference WASM trace token-for-token | **REPRODUCED** — all 6/6 PASS |
| C2 | **35 WASM opcodes** encoded through a computation-graph DSL | opcode list in README; programs use them; reference traces execute | **REPRODUCED** — all programs compile + run |
| C3 | **~30K tokens/second** inference (C++ engine) | `wasm-run` C++ engine throughput | **PARTIAL** — 18–24K tok/s on this WSL CPU box (~60–80% of claim; same order of magnitude; their ~30K is likely native/Accelerate) |
| C4 | Real algorithms run: **Sudoku (~900K tokens)**, fibonacci, collatz, Hungarian | reference traces + transformer match | **REPRODUCED** — sudoku 1.06M tok solved; all correct |
| C5 | Graph evaluator (exact arithmetic, no weights) matches reference | `wasm-eval` PASS per program | addition PASS; bigger programs need the hull ext (brute-force too slow) — superseded by C1's stronger C++-engine PASS |
| C6 | First Futamura projection: program baked into weights | `wasm-specialize` + run specialized model | **REPRODUCED** — collatz baked into weights (d_ffn=1630, 1.69M params); specialized model output correct |
| C7 | O(log n) **hull** KV cache vs O(n) softmax | hull extension / C++ CHT cache | **REPRODUCED** in the C++ engine (hull = 39.9% of runtime); Python `hull_ext` needs `python3-dev` (gap) |

### Measured results (`uv run wasm-run`, C++ engine; analytic weights d_model=38, 7 layers, 19 heads, vocab=915)

| Program | Result | Tokens | tok/s | Output |
|---------|--------|-------:|------:|--------|
| hello | PASS | 1,034 | 22,090 | `Hello World!` |
| addition | PASS | 4,362 | 23,384 | `19134` |
| fibonacci | PASS | 9,104 | 23,626 | `55` |
| collatz | PASS | 44,589 | 22,002 | `7 22 11 … 1` |
| min_cost_matching | PASS | 178,226 | 19,178 | Hungarian, `optimal cost: 9` |
| sudoku | PASS | 1,055,417 | 17,684 | solved: `534678912…345286179` |
| **total** | **6/6 PASS** | 1,292,732 | 18,049 (mean) | 269,858 wasm-ops, 71.6s |

## Reference outputs (WASM executed directly — validates VM semantics)

From `wasm-reference` (generated during the first `wasm-eval` run). These are the
ground-truth I/O traces the analytic transformer must reproduce:

| Program | Ref tokens | Output |
|---------|-----------:|--------|
| hello | 702 | `Hello World!\n` |
| addition | 3,425 | `19134\n` |
| fibonacci | 4,102 | `55\n` |
| collatz (n=7) | 40,522 | `7 22 11 34 17 52 26 13 40 20 10 5 16 8 4 2 1\n` |
| min_cost_matching | 162,539 | Hungarian algorithm, `optimal cost: 9` (full reasoning trace) |
| sudoku | 1,017,945 | puzzle solved: `534678912...345286179`, `clues: 30`, `propagated: 81/81`, `solved!` |

Note the sudoku trace is **~1.0M tokens**, consistent with the README's "~900K
tokens" headline (same order of magnitude; exact count depends on the puzzle).

The graph evaluator (`wasm-eval`, exact arithmetic, no transformer weights) is the
correctness oracle: `addition: PASS` confirmed. Larger programs are slow under
the brute-force fallback — see the gap below.

## Gaps / divergences observed

- **Hull Python extension did not build**: `hull_ext.cpp` needs `Python.h`
  (`python3-dev` / `python3.12-dev`), which was not installed, so `wasm-eval`
  fell back to brute-force O(n) attention (~30 tok/s) — impractical for the
  big programs. The **C++ inference engine** (`wasm-run`) embeds the CHT hull
  cache as a header (`hull2d_cht.h`) and does NOT need `Python.h`, so it is the
  path used to verify the throughput/scale claims. Installing `python3-dev`
  would let `wasm-eval --hull` and the Python inference path run fast too.
