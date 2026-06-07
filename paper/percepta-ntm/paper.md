# Toward a Differentiable Neural Computer on a Frozen-Embedding Substrate: PCA of a Constructed Neural Turing Machine, and a RAM-State Machine that Runs on the Substrate

---

## Abstract

A transformer with **analytically computed (untrained) weights** can execute
arbitrary WebAssembly programs — Percepta's `transformer-vm`. We read this artifact
as an **autoregressive, deterministic Neural Turing Machine (NTM)**: attention is
used as exact, content/location-addressed memory access, the feed-forward layers are
the per-step compute, and the append-only token sequence is the machine's state. We
ask a concrete engineering question for building a *Differentiable* Neural Computer
(DNC) on Sutra — a typed functional language whose compiled program is a fused
tensor-op graph over a frozen embedding substrate: **can the constructed
transformer's attention be reduced to a smaller, runnable core, and can an NTM-style
machine run on the Sutra substrate at all?**

We report two measured results. First, **principal-component / singular-value
analysis of the constructed weights shows that magnitude-PCA is the wrong reduction
lens for this machine**: the weights span ~30 orders of magnitude (the hardmax
temperature and address arithmetic produce singular values to ~1e30), so
energy-fraction rank is dominated by a few giant "switch" directions while the small
directions carry the actual byte logic. The honest reduction lever is the
*computation schedule*, not the weight spectrum: of the nominal 19 heads × 7 layers =
133 attention head-slots, only **42 (31.6%) genuinely attend**, concentrated in 5
layers (two attention layers are entirely zero), and the 915-symbol vocabulary
embeds into a ~3-dimensional subspace. Second, we **build a RAM-state stack machine
that runs on the Sutra substrate** and is Turing-complete (memory, arithmetic,
bitwise, comparison, conditional branch, and backward-branch loops), with all machine
state held in a RAM device and opcode dispatch performed by reading the opcode fresh
from memory each step. The hard substrate questions (memory model, dispatch, state,
side effects) are answered with measurements; the remaining work is breadth.

## 1. The artifact: a constructed, deterministic Neural Turing Machine

Percepta's `transformer-vm` is a standard softmax-ReGLU transformer whose weights are
**constructed analytically from a computation-graph DSL**, not trained. A C program
is compiled to WebAssembly; the supported WASM opcodes are encoded as byte-level
arithmetic over a residual stream that acts as machine memory (stack, locals, linear
memory, instruction cursor, call depth); a MILP solver schedules the graph nodes onto
transformer layers; the resulting tensors are written out. Replication results
(measured; `WASM/FINDINGS.md`): the analytic model reproduces the reference WASM
execution trace **token-for-token on all 6/6 test programs**, including a Sudoku
solver run of **1,055,417 tokens**, at a mean of **18,049 tokens/s over 1,292,732
tokens** (the authors report ~30K tok/s; the same order of magnitude). The analytic
model is small: `d_model = 38, n_layers = 7, n_heads = 19, d_ffn = 44, vocab = 915`;
the MILP solves to optimality in 5.5 s.

Read in the lineage of neural-memory architectures, this is an **autoregressive,
deterministic NTM**. A Neural Turing Machine (Graves, Wayne & Danihelka 2014) is a
neural controller with external memory whose read/write heads address memory via
attention; a Differentiable Neural Computer (Graves et al. 2016) adds dynamic
allocation and temporal links. Both are *trained, differentiable, recurrent*.
`transformer-vm` uses the same core mechanism — attention as content/location-
addressed memory access — but is *constructed and exact* (the addressing is hardmax,
never approximate), has *no recurrent controller* (the autoregressive loop plays that
role), and its *memory is the append-only token sequence*. The full framing is in
`WASM/notes/significance_and_isomorphism.md`.

## 2. Question and method

To build a DNC on Sutra we need a *small, runnable* attention core. The natural first
attempt is to take the constructed transformer's weights and reduce their
dimensionality by PCA/SVD. We (i) built the analytic transformer (the MILP schedule,
cached), (ii) ran a full singular-value decomposition of every weight matrix, and
(iii) measured how many attention heads genuinely attend per layer. All of this is
analysis on the constructed weights, off any runtime path.

## 3. PCA result: magnitude is the wrong lens; the schedule is the lever

The analytic model has **144,286 parameters** — `d_model` is already 38, so this is
not an over-provisioned embedding to shrink. SVD of the weight matrices shows an
**extreme dynamic range**: singular values reach ~1e30 (some matrices to 1e89–1e119),
produced by the hardmax temperature (`HARD_K = 1e10`) and the 2^k address/position
scales, down to ~1 for the byte logic. Consequently the energy-fraction "effective
rank" is dominated by a few giant directions and reports a misleadingly low rank: the
small-magnitude singular directions, which carry the actual computation, contribute
almost nothing to the Frobenius norm. **Magnitude-PCA cannot truncate this machine** —
dropping the small directions deletes the logic, not redundancy. (The squared
singular values overflow float32; the analysis runs in float64.) This caution
generalizes beyond this artifact: any model whose weights are *constructed* or
*distilled* with saturating (hardmax / high-temperature-softmax) routing develops the
same magnitude/importance decoupling, so spectral-energy pruning is unsafe for that
whole class — the specific numbers below are this artifact's, but the failure mode is
not.

What *is* reducible, measured honestly:

- **Two of seven attention layers are entirely zero** (`attn.5`, `attn.6`: their
  input and output projections sum to exactly 0). The schedule places all attention
  in the first five layers; the last two are FFN-only. These attention blocks are
  directly removable.
- **The 915-symbol vocabulary embedding is genuinely low-rank**: the token and head
  embedding matrices (915×38) carry **99% of their energy in 3 of 38 dimensions** (90%
  in 1–2). No giant switches live there, so this is a magnitude-honest reduction.
- **The attention core's reduction lever is the schedule, not the spectrum.** Counting
  heads that genuinely attend (Q *and* K projection rows non-zero), only **42 of the
  nominal 133 head-slots (31.6%)** are used — per layer 7, 5, 11, 11, 8, 0, 0. The
  reduced-attention target for a DNC realization is therefore ~⅓ of the nominal
  provisioning, concentrated in five layers, and must be obtained by scheduling fewer
  heads/dims in the computation graph rather than by SVD-truncating the constructed
  weights. This is not the tautology "a scheduled model is set by its schedule": the
  measured content is that *the schedule under-provisions* — it allocates 19 heads per
  layer and 7 layers but leaves 68% of those head-slots unused — so the operative
  reduction number (42) is an empirical property of the produced weights, recoverable
  only by inspecting them, not a restatement of the construction method.

## 4. A RAM-state NTM-style machine that runs on the Sutra substrate

Independent of the reduction question, we tested whether an NTM-style machine can run
on the Sutra substrate at all. Sutra compiles to tensor operations over a frozen
embedding space; numbers live on synthetic axes; storage is the substrate RAM device,
read and written by `ramRead`/`ramWrite` (`planning/sutra-spec/ram-pointers.md`).

We hand-wrote a stack machine whose **entire state — program counter, stack pointer,
halt flag, the program, and the value stack — lives in RAM**, and whose host driver
issues one execution step per instruction (the same autoregressive shape as the
transformer). Each step reads the opcode **fresh from RAM** and dispatches by
comparing it against the opcode tags; this matters because a value read fresh from
memory recovers a sharp truth value against a literal (its equality test defuzzes to
±1 — the {−1,0,+1} Kleene truth axis Sutra computes), whereas a value carried across
substrate loop iterations does not — so dispatch is driven from memory, not from
loop-carried state. (By "frozen-embedding substrate" we mean Sutra's fixed
high-dimensional vector space in which numbers and storage are encoded; a Sutra
program compiles to a fused tensor-op graph over it.) Per-opcode side effects are
realized as single blended writes to fixed cells (each cell receives its new value if
its opcode matched, otherwise a no-op rewrite of its existing value), which avoids
address blending on the fuzzy substrate.

The machine is a genuine interpreter — the program is data in RAM. Its **computational
class is Turing-complete**: it has unbounded addressable memory (`LOAD`/`STORE` against
the RAM device), a data-dependent conditional branch (`BR_IF`), and unbounded
iteration (backward branch), which is the standard sufficient criterion — the claim is
about the model, not the size of the opcode menu. The current opcode set is 12
(`HALT`/`CONST`/`ADD`/`SUB`/`MUL`/`AND`/`BR_IF`/`LOAD`/`STORE`/`EQ`/`LT`/`OUTPUT`),
enough to exercise every class. Measured on the substrate: arithmetic (e.g. `3+4 = 7`,
`100+23 = 123`, chained `5×6−2 = 28`), bitwise (`12 AND 10 = 8`, via a substrate
bit-plane decomposition), comparison (`3<5 = 1`, `7==7 = 1`), a conditional branch
taking or not taking by data, a `STORE`/`LOAD` round-trip, byte `OUTPUT` to a buffer
(emitting 72,73,74), and — the load-bearing case for the Turing-completeness claim — a
**backward-branch memory loop** (a counter at one address, an accumulator at another;
each iteration increments the accumulator and decrements the counter, branching back
while non-zero) that yields `acc = N` for `N = 1, 3, 5`. All cases are guarded by a
regression test that compiles the machine and runs it on the substrate (14/14). The
evaluation establishes the mechanism, not coverage of a full instruction set.

The OCaml realization of the reference machine is being transpiled to Sutra by an
OCaml→Sutra frontend; the substrate primitives the machine needs (RAM-backed arrays,
a substrate bitwise stdlib) are in place and individually verified.

## 5. What we are not claiming

- We do **not** claim a working DNC. We measured the reduction target for its
  attention and built a Turing-complete NTM-style machine on the substrate; we have
  not trained or assembled a differentiable neural computer.
- We do **not** claim the full 35-opcode `transformer-vm` runs on the Sutra
  substrate. The substrate machine implements 12 opcodes and demonstrates the
  mechanism (memory, dispatch, loops, output); the remaining opcodes are breadth, and
  the reference's multi-megabyte linear memory exceeds the current host RAM device.
- We do **not** claim PCA reduces the transformer. The measured result is the
  opposite: magnitude-PCA is misleading here; the reducible structure is the two zero
  attention layers, the ~3-dimensional vocabulary embedding, and the 42/133 genuinely
  used heads — the last obtainable only from the schedule.
- Throughput and replication figures are quoted from the replication measurements,
  not from the original authors; where they differ (≈18K vs ~30K tok/s) we report the
  measured value.
- We did **not** reproduce the arXiv "Neural Computers" e-print (2604.06425, April
  2026); it is cited as related work only. It is the paper the artifact's repository
  was originally scaffolded against before `transformer-vm` was identified as the
  actual target, so its source was fetched and then removed from that repository; we
  retain the citation for provenance, not as a reproduced result. The artifact under
  study is Percepta's `transformer-vm`.

## Reproducibility

The analysis and the substrate machine are reproducible from the project repository:
the PCA/SVD and head-usage scripts (`experiments/wasm_transformer_pca/`), the
substrate machine and its regression test (`experiments/iso5_substrate_dispatch/`,
`sdk/sutra-compiler/tests/test_mini_wasm_machine.py`), and the replication of
`transformer-vm` (the `WASM/` subtree, with the authors' code as a submodule).
Repository: https://github.com/EmmaLeonhart/Sutra

## References

- A. Graves, G. Wayne, I. Danihelka. *Neural Turing Machines.* arXiv:1410.5401, 2014.
- A. Graves, G. Wayne, M. Reynolds, et al. *Hybrid computing using a neural network
  with dynamic external memory.* Nature 538, 2016 (the Differentiable Neural
  Computer).
- M. Zhuge, C. Zhao, H. Liu, et al. *Neural Computers.* arXiv:2604.06425 (April 2026)
  — the e-print the artifact's repository was scaffolded against; related work only,
  not the artifact studied here and not reproduced (see §5).
- Percepta-Core. *transformer-vm* / "Can LLMs Be Computers?" (code + blog; no arXiv).
  https://github.com/Percepta-Core/transformer-vm
