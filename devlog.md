# replicating-neural-computers — Devlog

**This file is where "done" lives.** `queue.md` is delete-only: when a queue
item is finished, the item is **deleted from `queue.md`** and a dated entry
is **appended here**, in the same commit as the work, then pushed. Never
tick a box in place — a checked box left in `queue.md` is the failure mode
this file exists to prevent.

Also record releases (tag + a one-line note), notable milestones, and
anything else worth a chronological trail. Newest entries at the bottom.

This is the **same convention as the cleanvibe repo's own `devlog.md`** —
every cleanvibe-scaffolded project gets one for the same reason.

See `CLAUDE.md` § "Workflow Rules" and `queue.md`'s preamble.

---

## 2026-06-05 — Project scaffolded

Scaffolded with `cleanvibe new` (cleanvibe v1.13.1). Future entries
land here as queue items get deleted.

## 2026-06-05 — Retargeted to Percepta transformer-vm

The queue's "Important" note made clear the real target is **not** the arXiv
paper "Neural Computers" (2604.06425) the scaffolder downloaded, but Percepta's
**`transformer-vm`** — a transformer with analytically-computed (untrained)
weights that simulates a WebAssembly VM. It has no arXiv (GitHub + blog +
Medium only). Researched all four source links (data_lake was empty), recorded
the target, architecture, claims, and recipe in `notes/sources.md`. Rewrote
`queue.md` as a recipe-first plan, updated `README.md` and `paper.json`. The
arXiv paper is kept under `replication_target/source/` as related work only.

## 2026-06-05 — Went live + submodule added

- User gave explicit consent to run the third-party code locally and chose the
  remote name `replicating-transformer-vm`.
- Created the PUBLIC repo and pushed:
  https://github.com/EmmaLeonhart/replicating-transformer-vm
- Added `Percepta-Core/transformer-vm` as a git submodule at
  `replication_target/transformer-vm`, pinned at `6cfee30`.
- Toolchain decision: Windows lacks uv/clang/MSVC and the repo only documents
  macOS/Ubuntu builds, so we run inside the existing **WSL Ubuntu 24.04** distro
  (Python 3.12, 16 CPU / 15Gi RAM, internet OK). On Linux the C++ engine builds
  with plain `g++ -std=c++17 -O3` — no BLAS. Setup scripted in
  `scripts/wsl_setup.sh`; only the `apt install build-essential clang lld cmake`
  step needs sudo (handed to the user).

## 2026-06-05 — Toolchain up; first reproduced evidence

- `uv sync` installed all 51 deps (torch 2.10.0, highspy, ninja, pybind11…) in
  WSL Ubuntu. User installed `build-essential clang lld cmake`; verified
  `clang --print-targets` has the **wasm32** target and `g++ 13.3.0` is present.
- **Light path ran:** `uv run wasm-eval` compiled all 6 example C programs to
  WASM and generated correct **reference traces** (the WASM VM ground truth):
  hello→`Hello World!`, addition→`19134`, fibonacci→`55`,
  collatz(7)→`7 22 11 … 1`, min_cost_matching→Hungarian `optimal cost: 9`,
  **sudoku solved** (`534678912…`, ~1.0M tokens — matches the README's ~900K
  headline order-of-magnitude). Graph evaluator: `addition: PASS`.
- **Gap found:** the `hull_ext` Python extension needs `Python.h`
  (`python3-dev`), which isn't installed, so `wasm-eval` fell back to brute-force
  O(n) attention (~30 tok/s) — too slow for the big programs. The C++ engine
  (`wasm-run`) embeds the hull cache as a header and doesn't need it, so it's the
  path used for the throughput/scale claims. Recorded in `notes/claims.md`.
- Kicked off `uv run wasm-run` (builds analytic weights via MILP + torch, then
  the C++ engine, then runs all programs) — the headline ~30K tok/s path.

## 2026-06-05 — REPLICATED: 6/6 programs PASS through analytic weights

`uv run wasm-run` built the analytic transformer (MILP solved to optimality in
5.5s: `d_model=38, 7 layers, 19 heads, vocab=915`), compiled the C++ engine, and
ran all six programs through it. **Every program PASSed** — the transformer's
output matches the reference WASM trace token-for-token:

| Program | Tokens | tok/s | Output |
|---|--:|--:|---|
| hello | 1,034 | 22,090 | `Hello World!` |
| addition | 4,362 | 23,384 | `19134` |
| fibonacci | 9,104 | 23,626 | `55` |
| collatz | 44,589 | 22,002 | `7 22 11 … 1` |
| min_cost_matching | 178,226 | 19,178 | Hungarian, `optimal cost: 9` |
| **sudoku** | **1,055,417** | 17,684 | **solved** `534678912…345286179` |

Total 1,292,732 tokens, 18,049 tok/s mean. This confirms the core claim: a
transformer with **analytically-computed, untrained weights** correctly simulates
a WASM VM on real programs. Throughput is ~18–24K tok/s vs the authors' ~30K
(same order; lower on a WSL CPU box, no Accelerate BLAS on Linux).

- Wrote `scripts/run.py` (CI entry point) → `results/metrics.json`
  (`all_pass: true`, 6/6, mean 21,355 tok/s on the cached re-run).
- Set `paper.json` status → **`replicated`** (turns the Pages badge green).
- Wrote `FINDINGS.md` (reproduced-vs-reported table, recipe-covered vs filled,
  gaps) and filled `notes/claims.md`.
- Added `.github/workflows/ci.yml` to run the replication end-to-end on push.
- Milestone: **replication reproduced**. Remaining: confirm Pages/CI green; the
  Futamura projection + Python hull path are optional extras.
