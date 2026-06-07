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
(measured; see the replication report in the repository): the analytic model
reproduces the reference WASM
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
role), and its *memory is the append-only token sequence*.

## 2. Related work

**Neural memory architectures.** The Neural Turing Machine (Graves, Wayne &
Danihelka 2014) couples a neural controller to an external memory whose read/write
heads are addressed by attention (content- and location-based). The Differentiable
Neural Computer (Graves et al. 2016) extends it with dynamic memory allocation and a
temporal link matrix. Both are **trained end-to-end, differentiable, and recurrent** —
they *learn* to use attention as a memory-addressing mechanism. The artifact we study,
Percepta's `transformer-vm`, sits at the same design point — attention as memory
addressing — but reached from the opposite direction: its weights are **constructed,
not trained**; its addressing is **exact hardmax**, never soft or approximate; and the
recurrent controller is replaced by the **autoregressive token loop**. We therefore
read it as a *constructed, deterministic NTM*, and our reduction question (how small
can its attention be made) is in service of building a differentiable computer on the
Sutra substrate — i.e. moving from the constructed/exact end of this lineage toward the
trained/differentiable end. Relative to learned memory networks, our §5 substrate
machine is closer to a hand-written virtual machine realized in tensor algebra; the
contribution is the empirical bridge between the constructed-NTM weight structure and
a runnable tensor-substrate machine.

**Compiled and program-synthesized transformers.** The closest prior line is the
work that *compiles* symbolic programs into transformer weights. RASP (Weiss,
Goldberg & Yahav 2021) is a sequence-processing language whose primitives map onto
attention and feed-forward layers, and Tracr (Lindner, Kramár et al. 2023) compiles
RASP programs into concrete decoder weights, explicitly to produce
known-ground-truth models for interpretability research. `transformer-vm` belongs to
this compiled-transformer paradigm — it is a hand-constructed (rather than
RASP-compiled) instance that targets a full WebAssembly interpreter rather than the
histogram/sort/Dyck demonstrations Tracr ships. The distinction relevant to this
paper is the analysis lens: RASP and Tracr study what *programs* a transformer can
represent and provide ground-truth circuits for interpretability; we instead measure
the **weight spectrum and head-utilization of a compiled artifact** to ask whether it
is *reducible*. The two findings here — that magnitude-PCA is defeated by the
hard-coded saturating constants such a compilation introduces (§4), and that the
genuine reduction lever is the computation schedule, not the spectrum (§4) — are, to
our knowledge, not reported for Tracr-style compiled models, whose magnitude regime
is the same by construction. Our §5 substrate machine is then the converse move:
rather than compiling a program *into* attention, we run the symbolic VM directly as
a tensor-op graph on the Sutra substrate.

## 3. Question and method

To build a DNC on Sutra we need a *small, runnable* attention core. The natural first
attempt is to take the constructed transformer's weights and reduce their
dimensionality by PCA/SVD. We (i) built the analytic transformer (the MILP schedule,
cached), (ii) ran a full singular-value decomposition of every weight matrix, and
(iii) measured how many attention heads genuinely attend per layer. All of this is
analysis on the constructed weights, off any runtime path.

## 4. PCA result: magnitude is the wrong lens; the schedule is the lever

The analytic model has **144,286 parameters** — `d_model` is already 38, so this is
not an over-provisioned embedding to shrink. SVD of the weight matrices shows an
**extreme dynamic range**: the largest singular values reach **~1.7e30**, produced by
the hardmax temperature (`HARD_K = 1e10`) and the 2^k address/position scales, down to
~1 for the byte logic. Several matrices are additionally *ill-conditioned* — their
σ_max/σ_min ratio runs to 1e89–1e119 (e.g. `ff_in.2.weight` at 6.5e119). That ratio is
a **condition number, not a singular-value magnitude**: the small end falls to the
float64 noise floor, so those tiny singular values are numerically indistinguishable
from zero relative to the 1e30 scale, and the relative-threshold rank used below
discards them by construction. (Earlier drafts of this paper reported the condition
numbers as if they were singular values; no singular value approaches 1e119, and the
analysis does not overflow.) Consequently the energy-fraction "effective rank" is
dominated by a few giant directions and reports a misleadingly low rank: the
small-magnitude singular directions, which carry the actual computation, contribute
almost nothing to the Frobenius norm. **Magnitude-PCA cannot truncate this machine** —
dropping the small directions deletes the logic, not redundancy. The right way to read
this regime is that the high-magnitude, high-condition-number weights are a
**digital logic circuit simulated at high gain inside attention**: the 1e30 constants
push hardmax into a hard switch, so the "neural" computation here is an exact gate
array, not a smooth learned representation. That is a property of *constructed/compiled*
transformers (this artifact, and Tracr-style models §2), and it is precisely why
spectral pruning fails on them — and why a *trainable* differentiable computer, the
goal these measurements serve, is a different and more robust object. These magnitudes are
by construction, not numerical error: the analytic weights literally encode the
hardmax temperature and 2^k address constants, so a largest singular value near 1e30 is
the expected scale of those encoded constants, not instability. Such values are well
within float64 (max ≈ 1.8e308), and even their squares (≈ 1e60) are; it is *float32*
whose square overflows (max ≈ 3.4e38), which is the only reason the analysis is run in
float64. One clarification this invites: `HARD_K = 1e10` is **not** a softmax exponent.
It scales the *query-projection weights* (`query_expr · HARD_K · √d_h` in the
construction), so the attention *scores* become large and the softmax saturates to a
hard argmax; the softmax itself is the standard max-subtracted (numerically stable)
form (the reference computes `F.softmax` over max-shifted scores), so no `exp(1e10)` is
ever evaluated and nothing overflows. The 1e30 figures are static weight-matrix entries
(`HARD_K` composed with the 2^k address constants), not intermediate activations. This
caution
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

## 5. A RAM-state NTM-style machine that runs on the Sutra substrate

Independent of the reduction question, we tested whether an NTM-style machine can run
on the Sutra substrate at all. **Sutra** is a typed, purely functional language whose
compiler lowers an entire program — primitives, control flow, I/O — to a single fused
tensor-operation graph over a fixed high-dimensional embedding space (the "frozen
substrate"); a value is a vector in that space, an integer is encoded on dedicated
synthetic axes, `if/else` compiles to a three-valued-Kleene polynomial and a loop to a
bounded soft-halt recurrence, so the compiled graph *is* the program's semantics (as a
neural network's weights are its computation). Storage is an external **RAM device** —
a host-attached array of value-vectors addressed by an integer pointer — read and
written by two operations, `ramRead(addr)` and `ramWrite(addr, value)`.

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
about the model, not the size of the opcode menu. The current opcode set is 17
(`HALT`/`CONST`/`ADD`/`SUB`/`MUL`/`AND`/`BR_IF`/`LOAD`/`STORE`/`EQ`/`LT`/`OUTPUT`/`OR`/
`XOR`/`DUP`/`SWAP`/`DROP`), enough to exercise every class. Measured on the substrate:
arithmetic (e.g. `3+4 = 7`, `100+23 = 123`, chained `5×6−2 = 28`), bitwise
(`12 AND 10 = 8`, `12 OR 10 = 14`, `12 XOR 10 = 6`, via a substrate bit-plane
decomposition), comparison (`3<5 = 1`, `7==7 = 1`), stack manipulation (`DUP`, `SWAP`
— verified by `7,2 SWAP SUB = −5` — and `DROP`), a conditional branch taking or not
taking by data, a `STORE`/`LOAD` round-trip, byte `OUTPUT` to a buffer (emitting
72,73,74), and — the load-bearing cases for the Turing-completeness claim — a
**backward-branch memory loop** (a counter at one address, an accumulator at another;
each iteration increments the accumulator and decrements the counter, branching back
while non-zero) that yields `acc = N` for `N = 1, 3, 5`, and a full
**multiply-accumulate algorithm computing `factorial(3) = 6`** (the same loop with a
multiplying accumulator) running end-to-end on the substrate. All cases are guarded by
a regression test that compiles the machine and runs it on the substrate (20/20). The
evaluation establishes the mechanism, not coverage of a full instruction set.

The OCaml realization of the reference machine is being transpiled to Sutra by an
OCaml→Sutra frontend; the substrate primitives the machine needs (RAM-backed arrays,
a substrate bitwise stdlib) are in place and individually verified.

## 6. What we are not claiming

- We do **not** claim a working DNC. We measured the reduction target for its
  attention and built a Turing-complete NTM-style machine on the substrate; we have
  not trained or assembled a differentiable neural computer.
- We do **not** claim the full 35-opcode `transformer-vm` runs on the Sutra
  substrate. The substrate machine implements 17 opcodes and demonstrates the
  mechanism (memory, dispatch, loops, output, stack, bitwise); the remaining opcodes
  are breadth, and the reference's multi-megabyte linear memory exceeds the current
  host RAM device.
- We do **not** claim PCA reduces the transformer. The measured result is the
  opposite: magnitude-PCA is misleading here; the reducible structure is the two zero
  attention layers, the ~3-dimensional vocabulary embedding, and the 42/133 genuinely
  used heads — the last obtainable only from the schedule.
- Throughput and replication figures are quoted from the replication measurements,
  not from the original authors; where they differ (≈18K vs ~30K tok/s) we report the
  measured value.
- The artifact under study is Percepta's `transformer-vm`. Its repository was
  originally scaffolded against a separate neural-computers e-print before
  `transformer-vm` was identified as the actual target; that source was fetched and
  then removed, and we do **not** reproduce it here.

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
- G. Weiss, Y. Goldberg, E. Yahav. *Thinking Like Transformers.* arXiv:2106.06981,
  ICML 2021 (the RASP language).
- D. Lindner, J. Kramár, S. Farquhar, et al. *Tracr: Compiled Transformers as a
  Laboratory for Interpretability.* arXiv:2301.05062, 2023.
- Percepta-Core. *transformer-vm* / "Can LLMs Be Computers?" (code + blog; no arXiv).
  https://github.com/Percepta-Core/transformer-vm
