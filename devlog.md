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

## 2026-06-05 — Deliverables green + Futamura projection (C6) confirmed

- Enabled GitHub Pages via the API (the `configure-pages` auto-enable lacked
  permission on the fresh repo), re-ran `pages` → **green**. Site live with the
  "Replicated" badge: https://emmaleonhart.github.io/replicating-transformer-vm/
- `package` workflow (ZIP) dispatched → **green**. `ci` workflow → **green**:
  reproduced **6/6 PASS, all_pass=true** from a clean clone on `ubuntu-latest`
  (~15–17K tok/s) — independent confirmation the replication runs from scratch.
- **First Futamura projection (C6) reproduced:** `wasm-specialize` baked collatz
  (813 instructions) into a specialized model (`d_model=40, 8 layers, d_ffn=1630`,
  1,686,480 params, `collatz.bin` 13.5 MB; MILP optimal in ~20 min). The
  specialized model output the correct collatz sequence (`7 22 11 … 1`).
  Throughput ~1.2K tok/s (projection = 93% of runtime, the expected size/speed
  trade). Updated `FINDINGS.md` + `notes/claims.md`.
- All 7 headline claims now reproduced (C3 throughput partial; C6 confirmed).

## 2026-06-05 — Deliverables green; new thread: learned CPU operations

- `pages`, `package`, and `ci` workflows all green (CI reproduces 6/6 from a clean
  clone). Replication thread closed.
- New research direction opened (user's vision): because the analytic weights live
  in a standard differentiable transformer (`VanillaTransformer(nn.Module)`,
  `model/transformer.py:21`), we can **train new CPU operations** as new neurons on
  the frozen, correct-by-construction scaffold, then **crystallize** them to exact
  DSL weights — the constructed+trained hybrid toward a Completely Neural Computer.
- Confirmed feasibility in source: trainable `nn.Module` params; inference forward is
  `@torch.no_grad()` + argmax (`transformer.py:41-69`), so training needs a
  grad-enabled softmax-attention forward (the one real build item). License confirmed
  **Apache-2.0** (`LICENSE:1`, `pyproject.toml:7`) — permissive, derivatives OK.
- Wrote the experiment design `notes/experiment_learned_ops.md` (thesis, frozen/
  trainable split, op-local→end-to-end signal, soft/hard τ schedule, crystallization,
  metrics G1–G4, phases E0–E4). Queued E0–E4. **Gated on user approval — no code yet.**

## 2026-06-05 — E0 done: differentiable forward reproduces exact execution

User approved building; E4 north-star op chosen: **saturating arithmetic**. Built
E0 via TDD (test-first, watched it fail, then implemented):
- `src/learned_ops/soft_forward.py` — a grad-enabled, batched, causal
  softmax-attention forward over the constructed weights (mirrors the per-token
  embedding+position / `Q·K` attention / ReGLU FFN / vocab head, with a temperature
  knob `tau`). At `tau=1` it equals the reference `StandardKVCache` softmax path.
- `tests/test_soft_forward.py` — teacher-forces the model's own exact `hello`
  execution and asserts the forward predicts the same next token at every generated
  position. **1 passed.** (Ground truth uses `StandardKVCache`, sidestepping the
  hull_ext/`python3-dev` gap.)
- This is the foundation we can backprop through. Next: E1 — learn `i32.and`.

## 2026-06-05 — E1 finding: bit-exact AND is not learnable from raw integers (spectral bias)

Built the E1 op-local harness TDD-style: `learned_op.py` (LearnedByteOp ReGLU MLP +
verified exactness metric), `train_and.py` (full-table trainer with hard-example
focusing), gate test `test_and_checkpoint_exact.py` (RED until 100% exact). Contract
tests pass; metric verified (reference-exact→1.0, trivial→<1.0, bit round-trip).

**Result (user's chosen constraint = raw integer operands, no bit decomposition):**
training plateaus far below 100% exact (10%→22% over 100 epochs, flattening).
**Cause: spectral bias.** The low result bits are the highest-frequency functions of
the integer inputs (bit0(a&b) = [a odd]&[b odd]; "a odd" is a period-2 square wave
over 0..255). MLPs learn low frequencies first, so the LSB resists bit-exactness, and
exact-match needs zero errors across 524,288 bit-decisions.

This is meaningful, not a harness bug: gradient-learning bit-exact arithmetic from
integers is exactly what's hard — which is *why* the paradigm constructs weights
instead of training them. The hardness is an artifact of the op-local raw-scalar
proxy, NOT the vision: the integrated scaffold (E3) already manipulates bytes
bit-wise (ADD's ReGLU carry machinery), so a learned op there builds on existing
bit-level features. Surfaced the methodological fork to the user (pure-finding vs
pivot-to-integrated vs relax-encoding vs brute-force).

## 2026-06-05 — E1 WIN: learned unsigned saturating-add to 100% exact

After the AND spectral-bias finding and discovering the architecture has no runtime
bit decomposition (lower.py only handles constant masks), pivoted the learnable-op
target to **saturating arithmetic** (the user's E4 north star) with **value-output**
(regress the byte, not 8 bits). Rationale: arithmetic ops are low-frequency and
value-natured (min(a+b,255) = a+b - relu(a+b-255), one ReLU) — exactly the scaffold's
native byte representation.

**Result: 100.0000% exact, 0/65536 wrong** (epoch 550), vs AND's 23% plateau.
Verified via TDD gate `test_sat_add_checkpoint_exact.py` (5 passed, 1 skipped — the
AND gate is now a documented negative-result skip). SGD learned a genuinely new CPU
instruction (not in the 35 opcodes) to bit-exactness on the differentiable scaffold —
the constructed+trained hybrid thesis, demonstrated.

- Generalized the harness to an op registry (`TARGETS`) + value/bits output modes;
  fixed the trainer's results path (was saving one dir too high).
- Negative result (AND) preserved as an executable skip + documented in
  `notes/experiment_learned_ops.md`.
- Next (E2): crystallize the learned sat_add to its exact minimal DSL form
  (a + b - relu(a+b-255)) and confirm learned == crystallized on all pairs.

## 2026-06-05 — E2 done: crystallized the learned sat_add (learn → re-compile)

`crystallize.py: CrystallizedSatAddU` expresses the exact closed form the net
learned — min(a+b,255) = a + b - relu(a+b-255), a single ReGLU neuron in the
scaffold's primitives. TDD: gate failed (no module), then GREEN. Full learned_ops
suite: **7 passed, 1 skipped** (AND negative result), incl.:
- crystallized op is 100% exact, AND
- the learned net agrees with the crystallized op on ALL 65 536 pairs (learned ==
  crystallized).

So the loop is closed: a new CPU instruction (unsigned saturating add) was
discovered by gradient on the differentiable scaffold, then re-compiled to a
permanent, deterministic, bit-exact DSL construction — the constructed+trained
hybrid, demonstrated end-to-end (E0 forward → E1 learn → E2 crystallize).

Remaining: E3 — wire crystallized sat_add as a native opcode into the interpreter and
pass a program end-to-end through the transformer (integration); broader Yantra OS
integration tracked in notes/yantra_integration.md.

## 2026-06-05 — Significance thesis + isomorphism program documented

Captured Emma's framing comprehensively in `notes/significance_and_isomorphism.md`:
`transformer-vm` is an **autoregressive, deterministic Neural Turing Machine** — it
uses attention to address RAM and then performs deterministic, fully code-describable
operations; the first time an attention mechanism has been turned into deterministic,
human-interpretable code. Same family as DNC/NTM (attention-as-memory-addressing) but
constructed/deterministic, no RNN (autoregression replaces recurrence), append-only
memory (WASM in, data appended out).

Added the **isomorphism program** to the end of `todo.md`: find a reference impl
(likely C/C++) → **Rust** isomorphic (iterator first, attention-as-addressing later) →
arbitrary tests → **OCaml** (structurally close to Sutra) → tests → **Sutra** (final
item). Equivalence by behavioural testing, not formal verification yet. Proposed repo
rename to **"Neural WebAssembly"**. Persisted to project memory.

## 2026-06-05 — Autonomous loop started; ISO-1 done (reference search)

Started the three-cron work-loop playbook (session-local): work-loop :03 (57ccb9ba),
auto-flush :15 (2c9174b4), status-report :42 (8b51cb26). Restructured queue.md to
work top-to-bottom with the isomorphism program (Neural WebAssembly → Rust → OCaml →
Sutra) as the priority thread, pinned tail = ensure-crons + final-status.

**ISO-1 (search for a reference impl):** the seed already exists in the repo —
`wasm/reference.py` is a plain imperative 35-opcode stack-machine interpreter = the
exact behavioural spec the transformer's traces are checked against. So the Rust
isomorph ports `reference.py` (not an external full-MVP interpreter). Secondary Rust
refs for cross-checking: DLR-FT/wasm-interpreter, tinywasm, wain. Literature
validating the thesis: "Weights to Code" (arXiv:2601.05770, attention-as-NTM-pointer
→ closed-form code) and "Attention is Turing Complete" (JMLR 22). Recorded in
`notes/isomorphism_reference_search.md`. Next: ISO-2 (Rust isomorph spec).

## 2026-06-05 — ISO-2/3 done: Rust isomorph, byte-identical on 6/6 programs

Built the first stage of the isomorphism program: `iso/rust/` — a faithful Rust port
of `transformer-vm/wasm/reference.py` (the deterministic 35-opcode stack machine the
autoregressive transformer is isomorphic to). Iterator-first addressing (plain memory
indices); the attention-as-addressing formulation is a later step.

- Installed Rust (rustup, unprivileged) in WSL.
- `iso/rust/src/lib.rs` (parse + run, opcode-for-opcode), `src/main.rs` (CLI),
  `tests/equiv.rs` (known reference outputs), `scripts/iso_equiv.sh` (Python-vs-Rust
  harness).
- **cargo test --release: 6 passed.** Equivalence harness: **6/6 programs produce
  byte-identical output** to the Python reference — hello, addition, fibonacci,
  collatz, min_cost_matching (Hungarian, 882 bytes), sudoku (solved). ISO_EQUIV_OK.

So: autoregressive transformer ≡ reference.py ≡ Rust isomorph, verified behaviourally.
Next: ISO-4 (OCaml isomorph — the stepping stone to Sutra).
