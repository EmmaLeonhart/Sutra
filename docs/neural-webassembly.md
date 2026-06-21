# Neural WebAssembly

Sutra now carries a sibling research artifact in-tree, under `WASM/`: a full
**replication and isomorphism study of a transformer that *is* a WebAssembly
virtual machine.** This page explains what that artifact is, why it matters to
Sutra specifically, and how it connects to Sutra's own memory and
Neural-Turing-Machine direction.

In one sentence: a standard transformer, with **analytically computed (untrained)
weights**, correctly executes arbitrary WebAssembly programs — and that execution
turns out to be **deterministic, fully describable code**. It is, as far as we
know, the first time an attention mechanism has been rendered as exact,
human-interpretable code rather than a learned statistical approximation.

---

## What the system is

The target of the replication is Percepta's `transformer-vm` (published as code +
a blog post, ["Can LLMs Be Computers?"](https://www.percepta.ai/blog/can-llms-be-computers),
not as a paper). The replication lives at
[`EmmaLeonhart/neural-webassembly`](https://github.com/EmmaLeonhart/neural-webassembly)
and is mirrored into this repository's `WASM/` subtree with its full history.

The machine is **not trained.** Its weights are *constructed* from a
computation-graph DSL:

1. A C program is compiled to WebAssembly.
2. The 35 supported WASM opcodes are encoded as byte-level arithmetic over a
   **residual stream that acts as machine memory** — stack, locals, linear
   memory, instruction cursor, call depth all live in the residual stream.
3. A MILP solver schedules the computation-graph nodes onto transformer layers.
4. The resulting tensors are written out as the model's weights.

A standard softmax-ReGLU transformer then runs that bytecode **autoregressively**,
emitting **one byte of machine state per token**. An `O(log n)` "hull" KV-cache
(an incremental 2-D convex hull plus hardmax) replaces `O(n)` softmax attention,
which is what keeps long programs tractable.

Two operating modes exist:

- a **universal interpreter** — the program is supplied as input tokens, one
  shared model runs anything; and
- the **First Futamura projection** — a specific program is baked into the
  weights, producing a specialized model for that one program.

### Replication result

A transformer with analytically computed, untrained weights reproduced the
reference WASM execution trace **token-for-token on all 6/6 test programs**,
including a Sudoku solver that runs for **1,055,417 tokens and solves correctly**,
at ~18K tokens/sec on a CPU box (the authors report ~30K — the same order of
magnitude). The analytic model is tiny: `d_model=38, 7 layers, 19 heads,
vocab=915`, with the MILP schedule solved to optimality in a few seconds.

| Program | Result | Tokens | Output |
|---------|--------|-------:|--------|
| hello | pass | 1,034 | `Hello World!` |
| addition | pass | 4,362 | `19134` |
| fibonacci | pass | 9,104 | `55` |
| collatz | pass | 44,589 | `7 22 11 34 … 2 1` |
| min_cost_matching | pass | 178,226 | Hungarian algorithm, `optimal cost: 9` |
| sudoku | pass | 1,055,417 | solved |

---

## Why this is a Neural Turing Machine

The natural first reaction is that this is the *opposite* of a Neural Turing
Machine (NTM) or Differentiable Neural Computer (DNC): those are trained and
fuzzy, this is constructed and exact. That reaction is wrong, and the correction
is the interesting part.

An **NTM** (Graves et al., 2014) is a neural controller with external memory whose
read/write heads **address memory via attention**. A **DNC** (Graves et al., 2016)
adds dynamic allocation and temporal links. Both are trained, differentiable, and
driven by a recurrent controller. They *learn* to use attention as a memory
addressing mechanism.

`transformer-vm` uses the **same core mechanism** — attention as
content/location-addressed memory access — but:

- it is **deterministic and constructed**, so the addressing is exact, never
  approximate;
- it has **no recurrent controller** — the **autoregressive loop** over the token
  sequence plays the role recurrence plays in an NTM;
- its **memory is the token sequence itself** (append-only), addressed by hardmax
  attention rather than a separately rewritable matrix.

So the precise classification is an **autoregressive, deterministic Neural Turing
Machine**: attention is used to reach out and grab a specific memory cell, and a
deterministic operation is then performed on it — the whole behavior expressible
as ordinary imperative code. Grounded in the verified mechanism:

- **registers** (program counter, stack pointer, call depth) are *cumulative
  sums* of per-step deltas (attention averaging);
- **memory reads** (stack top, locals, linear memory, instruction fetch) are
  *argmax attention lookups* keyed by address/depth;
- **per-step arithmetic and opcode dispatch** are *ReGLU FFN* gates.

Memory access is attention; computation is the FFN; state is the append-only
sequence.

---

## The isomorphism program: transformer → Rust → OCaml → Sutra

Because the machine is deterministic, append-only, and every step is a describable
operation on an addressed piece of data, it maps cleanly onto imperative code.
That observation drives the artifact's central research program: build code that
is **isomorphic** to the transformer — behaving identically, step for step — and
carry that isomorphism across languages until it reaches Sutra. Equivalence is
established by behavioral testing (identical traces on every example program), not
yet by formal proof.

The chain, with status:

1. **Reference executor** (Python) — the readable specification of the machine.
2. **Rust** — a deterministic, imperative port, byte-identical to the reference.
   *Done.*
3. **OCaml** — a port into an ML-family language structurally close to Sutra,
   byte-identical to both the reference and the Rust port on all 6 programs.
   *Done.*
4. **Sutra** — port the OCaml realization into Sutra and measure how far Sutra can
   express this same machine. *This is the end of the road.*

So today: **transformer ≡ reference ≡ Rust ≡ OCaml**, verified byte-for-byte. The
final Sutra stage is the natural reason this artifact now lives inside the Sutra
repository: the chain was always pointing here.

This isomorphism — from an attention-addressed neural machine down to plain,
testable code — is the same bridge Sutra approaches from the other side. Sutra's
[memory model](memory.md) already stores and retrieves data as pure algebraic
operations over a single high-dimensional vector, with no branches and no pointer
dereference; and Sutra's runtime reaches Turing-completeness through the recurrence
of its substrate loops. The Neural WebAssembly work supplies a concrete,
fully-worked example of attention-as-addressing rendered as code — exactly the
shape Sutra's memory and loop primitives are built to express.

---

## Where this is heading: a neural executor for Sutra for Windows

The longer-term motivation is **Sutra for Windows**, Sutra's desktop I/O layer.
The design adopted there treats this transformer as a **real neural executor** —
the actual way the I/O layer runs WebAssembly — using one shared
universal-interpreter model per process sandbox.

The hard part of "run full WebAssembly as a neural executor" collapses through a
single **trap-and-resume** primitive: the neural core natively handles only
integer compute, control flow, and trap signaling; everything expensive or impure
— floating point, large linear memory, syscalls — is offloaded to conventional
host code through one uniform trap channel (emit a structured request, host
services it and writes the response into a memory slot, execution resumes by
loading that slot). Floats trap to the host FPU; LOAD/STORE trap to real
per-process RAM; syscalls trap to the kernel. Both mechanisms the trap relies on —
byte emission and runtime input via a memory region — already exist in the
replicated engine. This turns "full WASM MVP" from a moonshot into a bounded,
phased roadmap.

---

## Layout of the `WASM/` subtree

- `src/`, `scripts/run.py` — the replication and its CI entry point.
- `iso/rust/`, `iso/ocaml/` — the isomorphic ports; `scripts/iso_equiv.sh` checks
  byte-identical equivalence across all four implementations.
- `src/learned_ops/` — a separate thread showing new CPU operations can be
  *learned by gradient* on the analytic scaffold and then *crystallized* to exact
  weights (saturating add/sub/min/max all reach 100% exact; a logical-AND attempt
  is kept as a documented negative result).
- `notes/` — the research notes, including the full architectural classification
  and the Sutra-for-Windows integration design.
- `FINDINGS.md` — the replication report.

> **A note on provenance.** This work was originally scaffolded against an
> unrelated arXiv paper ("Neural Computers", 2604.06425) only because the
> scaffolding flow required an arXiv identifier. That paper is **not** what is
> replicated here; its extracted source was removed from the repository and its
> history. The real, replicated target is Percepta's `transformer-vm`, as
> described above.
