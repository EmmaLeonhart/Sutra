# Neural WebAssembly — significance, classification, and the isomorphism program

> Research notes capturing the thesis articulated by Emma (2026-06-05). The point of
> these notes is that **the significance here is not obvious** and must be stated
> explicitly. This document records *why* this artifact matters, *what it actually
> is* in the lineage of neural-memory architectures, and the concrete program for
> turning it into human-interpretable code (Rust → OCaml → Sutra).

Proposed name for this work / repository: **Neural WebAssembly**.

---

## 1. The core significance (stated plainly)

Percepta's `transformer-vm` is, as far as we know, **the first time a transformer's
attention mechanism has been turned into deterministic, human-interpretable code.**

That sentence is the whole point. Everything else is elaboration.

What makes it remarkable is *not* "a transformer can compute" in the abstract. It is
that **the model systematically uses the attention mechanism to reach out and grab an
individual piece of data — a specific RAM address / memory cell / stack slot — and
then performs a deterministic operation on it**, and the entire behaviour is exactly
describable as ordinary imperative code. The attention mechanism, normally a soft,
learned, statistical thing, is here being used as a precise, deterministic
*addressing* primitive: *go fetch the byte at this location, now operate on it.*

This is the actual significance: **an attention mechanism rendered as deterministic,
human-interpretable code.** We have not seen this before.

## 2. What it actually is: an autoregressive, deterministic Neural Turing Machine

A natural first reaction is that this is the *opposite* of a Differentiable Neural
Computer (DNC) or a Neural Turing Machine (NTM) — one is trained and fuzzy, this is
constructed and exact. **That first reaction is wrong, and the correction is the
important insight:** they are not opposites. They are the *same architectural idea*,
approached from opposite directions.

- A **Neural Turing Machine** (Graves et al., 2014) is a neural controller with an
  external memory, where read/write **heads address memory via attention**
  (content- and location-based). A **Differentiable Neural Computer** (Graves et al.,
  2016) extends this with dynamic memory allocation and temporal links. Both are
  **trained** end-to-end, **differentiable**, and use a **recurrent (RNN)**
  controller. They *learn* to use attention as a memory-addressing mechanism.

- `transformer-vm` uses the **exact same core mechanism** — attention as
  content/location-addressed memory access — but:
  - it is **deterministic and constructed**, not trained (the weights are computed
    analytically so the addressing is exact, never approximate);
  - it has **no recurrent network component** — there is no RNN controller. The
    **autoregressive loop** over the token sequence plays the role recurrence plays
    in an NTM: each step appends one token, and the "controller" is the same
    feed-forward transformer applied at each position;
  - its **memory is the token sequence itself** (append-only), addressed by hardmax
    (argmax) attention, rather than a separately rewritable memory matrix.

So the precise classification is: **an autoregressive, deterministic Neural Turing
Machine** — a constructed, non-recurrent NTM whose memory is an append-only sequence
and whose addressing is exact. (Whether one calls it "NTM-like" or "DNC-like" is
secondary; the load-bearing facts are: attention-as-memory-addressing + deterministic
+ autoregressive + no RNN + describable as code.)

The deep observation: **Percepta did an extremely *imperative* thing with a
transformer using the attention mechanism — which is precisely what a DNC / NTM does —
and they may not have fully framed it that way.** The NTM/DNC lineage *learned* to do
imperative memory manipulation softly; this *constructs* it exactly. Same family,
inverted method.

## 3. The append-only / autoregressive data model

The machine never mutates its input. It is **append-only**:

- The **input sequence is WebAssembly** — the program bytecode (plus any input data).
- Execution proceeds **autoregressively**: at each step the model appends exactly one
  token (one byte of machine state — a stack byte, a memory byte, an output byte) to
  the end of the sequence.
- The **output is data appended to the input sequence.** Reads happen by attention
  back over the whole grown sequence; writes happen by appending.

Because nothing is overwritten and every step is a deterministic function of the
sequence so far, the whole execution is a clean, inspectable trace — which is exactly
what makes it expressible as ordinary code (see §4). (This matches the codebase's own
internal name for the abstraction: an **Append-Only Lookup Machine**.)

Grounding in the mechanism (verified earlier, see `notes/sources.md` and the
walkthrough in `devlog.md`): "registers" (program counter, stack pointer, call depth)
are **cumulative sums** of per-step deltas (attention averaging); "memory reads"
(stack top, locals, linear memory, instruction fetch) are **argmax attention
lookups** keyed by address/depth; the per-step arithmetic and opcode dispatch are
**ReGLU FFN** gates. Memory access = attention; computation = FFN; state = the
append-only sequence.

## 4. Why this maps cleanly onto imperative code

Because the machine is deterministic, append-only, and every step is a describable
operation on an addressed piece of data, **it maps most naturally onto imperative
code** — C, C++, or Rust. Each attention lookup is "read the value at this index";
each ReGLU step is "compute this arithmetic"; each append is "push/store this byte";
the autoregressive loop is "while not halted: step".

We choose **Rust** as the first target (deterministic, imperative, good fit). The one
representational subtlety:

- **How to represent "where to write next" / "where to read from".** Two options:
  1. **An iterator** over the memory location being written to / read from — the
     simple, explicit imperative representation. *We do this first.*
  2. **Use the attention mechanism itself** to find where to write/read — i.e. keep
     the addressing as an argmax-over-keys operation rather than a plain index. *We
     explore this second.*

  Starting with an iterator makes the Rust isomorphic and obviously correct; later we
  can reintroduce the attention-as-addressing formulation to stay faithful to the
  neural structure.

## 5. Why this matters *here*: the road to Sutra

A program like this is only *interesting* in the context of **Sutra**. The reason to
care about an interpretable, code-shaped neural Turing machine is that we want to
build the analogous thing in Sutra. So the significance is instrumental as well as
scientific: this is the first concrete, runnable bridge from "attention mechanism" to
"deterministic interpretable code," and that bridge is what makes a Sutra realisation
conceivable.

## 6. The isomorphism program (the plan)

**Goal:** establish code that is *isomorphic* with this autoregressive transformer —
code that behaves in *exactly the same way*, step for step — and then carry that
isomorphism across languages until it reaches Sutra.

Pipeline (each stage validated by arbitrary behavioural tests — **not** formal
verification yet; that comes later):

1. **Find a reference implementation.** Search for existing code — almost certainly
   **C or C++**, possibly **Rust** — that does exactly this (a WASM interpreter of
   this shape / an append-only attention-addressed machine), or something simple
   enough to serve as the seed. Percepta's own repo is the primary candidate; look
   wider too.
2. **Rust (isomorphic).** Represent / rewrite that reference in **Rust** so we have a
   deterministic, imperative program that is isomorphic to the transformer's
   behaviour. Memory addressing via an **iterator** first; the attention-as-addressing
   formulation second.
3. **Test Rust.** Run a battery of arbitrary behavioural tests confirming the Rust
   program produces identical traces/outputs to the transformer on the example
   programs (and beyond). Equivalence by testing, not proof — for now.
4. **OCaml (isomorphic).** Build a comparable **OCaml** program that does the same
   thing and establish the same isomorphism. OCaml is harder to express this in than
   Rust, which is exactly why it is the right stepping stone — **OCaml is structurally
   close to Sutra.**
5. **Test OCaml.** Same battery of arbitrary tests; confirm equivalence.
6. **Sutra.** Because OCaml ≈ Sutra structurally, port the OCaml realisation into
   **Sutra**, and test the extent to which Sutra can express this same machine. Sutra
   is the end of the road (and the end of `todo.md`). The Sutra stage is harder
   because the Rust/OCaml versions are deterministic/imperative while Sutra sits in a
   different position — hence doing it last, after the imperative isomorphisms are
   nailed down.

**Why this order:** Rust makes the imperative structure trivial to express and
obviously correct; OCaml forces the structure into a shape close to Sutra's; Sutra
inherits a fully-tested, isomorphic blueprint instead of starting from the raw
transformer. Find → Rust → test → OCaml → test → Sutra → test.

---

### One-line statement of the thesis

> `transformer-vm` is an **autoregressive, deterministic Neural Turing Machine**: it
> uses the attention mechanism to address RAM and then performs deterministic, fully
> code-describable operations — the first time an attention mechanism has been turned
> into deterministic, human-interpretable code. Our program is to make that code
> explicit and isomorphic, in Rust, then OCaml, then **Sutra**.
