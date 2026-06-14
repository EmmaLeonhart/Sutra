# Sutra → thrml: hardware-alignment notes (Extropic TSU) — host vs sampled

**Date:** 2026-06-14
**Status:** the last thrml-track item (queue.md H follow-on). Grounds the A–H
approaches against what the Extropic **Thermodynamic Sampling Unit (TSU)**
actually is, per the architecture paper vendored at
`external/thrml/docs_site/static/paper.html` ("An efficient probabilistic hardware
architecture for diffusion-like models", arXiv 2510.23972). thrml is the
GPU/CPU **prototyping** layer; this doc is about what carries to the *chip*.
Facts below are quoted/paraphrased from that paper; the synthesis is ours.

## What the TSU is (from the paper)

- A **grid of probabilistic bits (p-bits)**, "two-colored for parallel block Gibbs
  updates." The chip's one job is **rapid sampling** of an energy model.
- **The host/chip boundary is explicit:** "The host programs weights, the chip
  performs rapid sampling, and the host reads back the result."
- **Connectivity is sparse + local.** "arrays of probabilistic computing elements
  connected in a **sparse, locally-connected graph**." All-to-all "is
  **incompatible** with the sparse connectivity of a TSU" (it also blows up the
  graph's chromatic number, killing the two-color parallelism).
- **Native energy terms are local/pairwise.** The paper works with "local or
  pairwise energy terms"; higher-order / global constraints are **gadgetized**
  into local pairwise couplings + auxiliary structure (e.g. ferromagnetic
  nearest-neighbor couplings along a per-variable spin chain, plus constraint
  edges) — not expressed directly.

## Host vs sampled — mapping our A–G work

| Piece of our pipeline | Where it runs |
|---|---|
| spin registers (`SpinNode`s) ↔ **p-bits** | **chip** (the sampled variables) |
| block-Gibbs `sample_states` over two-color free blocks | **chip** (the TSU's core op; our demos already two-color the free blocks) |
| factor / coupling **weights** | **host** programs them onto the chip |
| codebook construction (assigning registers to atoms) | **host** (compile-time, like `codegen_thrml` does) |
| **sample-and-verify** verifier (A) | **host** reads samples + checks the relations |
| ground-state decode (B) / modal / argmax | **host** reads back the result |
| compositor / staged hand-off (#5) | **host** |

So: **the substrate op that the TSU accelerates is exactly the sampling.**
Everything else in approaches A–G (weight setup, codebook, verifier, decode,
composition) is host-side — and the Extropic paper says the same ("host programs
weights … host reads back the result"). This is consistent with our integrity
framing all along (we flagged the host-side verifier/compositor as such).

## Per-approach TSU alignment (the non-obvious finding)

The TSU's sparse-local-pairwise constraint sorts our approaches by how much
gadgetizing they need:

- **NATIVELY ALIGNED (already pairwise + biases):**
  - the **AND gadget (A2)** — derived as 1-body biases + 2-body couplings, **no
    higher-order term**. Maps straight onto a TSU.
  - the **carry factor** of the adder — three 2-body terms `−J σ_cout(σ_a+σ_b+σ_c)`.
- **NEEDS A LOCAL-PAIRWISE REDUCTION (auxiliary p-bits):**
  - **bind/unbind** and **XOR/parity** — these are 3-body (and the adder sum bit is
    4-body) product factors. thrml takes arbitrary arity in *software*, but on a
    TSU each must be reduced to 2-body via an auxiliary spin (standard gadget;
    costs extra p-bits + local edges). Bounded and well-understood.
- **LEAST ALIGNED (all-to-all):**
  - **Hopfield associative memory** (#1/#2) and the **cleanup** in the kv-query (E)
    — fully-connected Hebbian `W`. All-to-all is exactly what the paper says is
    *incompatible* with TSU connectivity. These are a strength of the **prototyping
    layer** (GPU thrml), not the chip; for the TSU they'd need a sparse/locally-
    connected embedding (or the structured-codes route, F, with a sparse code).

## Refinement of the H recommendation, for actual TSU deployment

The H comparison (`2026-06-14-thrml-approaches-comparison.md`) picked
bit-registers + sample-and-verify (A) / ground-state (B) as the default. The
hardware lens sharpens it:

1. **Keep the factor graph sparse + local-pairwise.** Reduce every 3-/4-body
   factor (bind, XOR, parity) to 2-body with auxiliary p-bits at codegen time;
   never emit all-to-all couplings for the chip.
2. **The gate-circuit path is the most TSU-aligned compute path** — AND and carry
   are already pairwise; the rest gadgetizes locally. Arithmetic/logic via
   sample-and-verify maps well.
3. **Dense associative memory stays on the prototyping layer** unless given a
   sparse code; it is the least chip-aligned of the approaches.
4. **The host/chip split is fixed by the hardware**, and matches ours: chip
   samples; host programs weights, verifies, decodes, composes.

## Deferred / open (honest)

- A concrete **3-/4-body → 2-body auxiliary-spin reduction pass** in
  `codegen_thrml` (so emitted graphs are TSU-shaped) — not built; the current
  codegen emits the higher-order factors thrml accepts in software.
- Exact TSU primitive set, p-bit count, and on-chip precision are from one public
  paper; real numbers need Extropic's hardware spec. Claims here are about
  *graph shape* (sparse/local/pairwise), which the paper states plainly — not
  about throughput.
