# Replication target — sources

## What we are actually replicating

**NOT** the arXiv paper "Neural Computers" (arXiv:2604.06425, Zhuge/Schmidhuber et
al.). That paper was downloaded by the scaffolder only because the original
`cleanvibe replicate` flow expects an arXiv ID, and it is the nearest-arXiv
relative of the real target. It is kept as **related work only**.

The **actual target** is Percepta's **`transformer-vm`**: a *standard
softmax-ReGLU transformer whose weights are computed analytically (not trained)*
that **correctly simulates a WebAssembly virtual machine on arbitrary programs**.
It has no arXiv paper — only a GitHub repo, a company blog post, a LinkedIn post,
and a third-party Medium write-up.

Remote repo name requested by the user: **`replicating-pertepta`** (sic — likely
a typo for "percepta"; confirm before creating the public repo).

## Primary sources

| # | Source | URL | Role |
|---|--------|-----|------|
| 1 | GitHub repo (authoritative — ships the recipe) | https://github.com/Percepta-Core/transformer-vm | **Primary** |
| 2 | Percepta blog: "Can LLMs Be Computers?" | https://www.percepta.ai/blog/can-llms-be-computers | Claims / framing |
| 3 | LinkedIn post (Vlad Larichev) | https://www.linkedin.com/posts/vladlarichev_a-major-shift-is-happening-in-the-llm-activity-7439246178526892032-poGU | Announcement |
| 4 | Medium: "I built a tiny computer inside a transformer" (Sean Moran) | https://medium.com/data-science-collective/i-built-a-tiny-computer-inside-a-transformer-e3000a0019b3 | Third-party explainer (a *simpler* compile-program-into-weights variant, not the Percepta interpreter) |
| — | arXiv:2604.06425 "Neural Computers" | https://arxiv.org/abs/2604.06425 | Unrelated paper the scaffolder wrongly extracted; **purged from repo + history**. Not our target. |

## The GitHub repo (transformer-vm) — structure & recipe

Blog subtitle: *"Executing programs inside transformers with exponentially faster
inference."* Blog authors include Christos Tzamos et al. at Percepta (2026-03-11).
Repo license: Apache-2.0. ~201 stars / 38 forks. 80% Python, 10% C++, 9% C.

### Architecture
- **Computation Graph DSL** (`transformer_vm/graph/core.py`) — 5 primitive types:
  InputDimension, ReGLUDimension, PersistDimension, LookUpDimension,
  CumSumDimension. Composes into a DAG of gated-FFN units + conditional logic.
- **WASM machine** (`transformer_vm/wasm/interpreter.py`) — encodes **35 WASM
  opcodes** entirely through the computation graph using byte-level arithmetic;
  tracks stack / memory / locals / cursor / call-depth via attention + cumulative
  sums.
- **Two execution modes**:
  1. *Universal interpreter*: program bytecode is input; instruction-fetch
     attention retrieves opcodes.
  2. *First Futamura projection*: program baked into FFN weights (specialized).
- **O(log n) "Hull" KV cache** (`transformer_vm/attention/`) — 2D convex hull +
  hardmax (argmax) instead of O(n) softmax; needed for million-token traces.
- **C++ inference engine** (`transformer_vm/model/transformer.cpp`) — loads binary
  weights, uses the hull cache + BLAS; auto-built on first use.
- **MILP scheduler** (`transformer_vm/scheduler/`) — assigns gates to layers.
- **C→WASM compilation** (`transformer_vm/compilation/`, `lower.py`) — lowers
  unsupported opcodes (MUL/DIV/MOD/AND/OR/XOR/SHL/SHR) into the supported set.

### Supported opcodes (≈35)
HALT, RETURN, CALL, BR, BR_IF, DROP, SELECT, LOCAL_GET/SET, GLOBAL_GET/SET,
LOAD, LOAD8_S/U, LOAD16_S/U, STORE, STORE8, STORE16, CONST, EQZ, EQ, NE,
LT_S/U, GT_S/U, LE_S/U, GE_S/U, ADD, SUB, OUTPUT.

### Headline claims to reproduce
- A standard transformer with **analytic (untrained) weights** correctly
  simulates a WASM VM on **arbitrary** programs.
- **~30K tokens/second** inference throughput.
- Runs real algorithms: **Sudoku** solver (~900K tokens), fibonacci, collatz, etc.
- O(log n) hull attention vs O(n) softmax.

### Reproduction recipe (ships in the repo — recipe-first replication)
Prereqs: Python 3.11+, `uv`, LLVM/Clang with **wasm32** target, C++17 compiler.
```bash
uv sync                       # install deps
uv run wasm-run               # full pipeline: compile C examples -> WASM ->
                              #   build weights -> build C++ engine -> execute all
uv run wasm-compile transformer_vm/examples/collatz.c --args 7
uv run wasm-run transformer_vm/data/collatz.txt
uv run wasm-eval              # graph evaluator, exact arithmetic, no weights
uv run wasm-specialize transformer_vm/data/collatz.txt --save-weights=collatz.bin
uv run pytest -m "not slow"   # fast tests
```

## Replication strategy (recipe-first)
1. **GATED**: get user consent to run third-party code + confirm remote repo name.
2. Add the repo as a git submodule under `replication_target/transformer-vm`.
3. Stand up the toolchain (uv + LLVM/clang wasm32 + C++17). **Windows feasibility
   is the main risk** — clang/wasm32 + a C++17 build + BLAS may need WSL/Linux.
4. `uv run wasm-eval` (no weights) and `uv run pytest -m "not slow"` first — these
   validate the graph/VM logic without the heavy C++ engine.
5. `uv run wasm-run` — capture stdout + any tokens/sec into `results/`.
6. Verify headline claims: VM-simulation correctness on the example programs,
   throughput order-of-magnitude, that real algorithms (collatz/fibonacci/sudoku)
   produce correct outputs.
7. `FINDINGS.md`: reproduced vs claimed; what the recipe covered; gaps/divergences
   (esp. anything we couldn't build on Windows).
