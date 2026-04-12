# Papers

Sutra is grounded in two papers, both submitted to the [Claw4S 2026 conference](https://clawrxiv.io). Both are open source. Both live in this repository — paper sources, reproduction scripts, and supporting data are all in-tree.

A third paper — [*Latent Space Cartography Applied to Wikidata*](https://clawrxiv.io/posts/1127) — is the empirical foundation for the existence of stable algebraic structure in frozen LLM embeddings, and provides the citation that grounds Sutra's "computation in embedding space is real, not metaphor" claim. It is **not** maintained from this repo; its primary source of truth is [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography), and it is currently at **Strong Accept** on clawRxiv (post 1127).

## 1. Sutra: A Vector Programming Language for Computation in Embedding Spaces

**Author:** Emma Leonhart
**Read it on clawRxiv:** [post 1542 — sutra-paper v2](https://clawrxiv.io/posts/1542)
**Source (GitHub):** [`sutra-paper/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/sutra-paper/paper.md)
**Reproduction skill:** [`sutra-paper/SKILL.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/sutra-paper/SKILL.md)
**Reviews:** [`sutra-paper/reviews/`](https://github.com/EmmaLeonhart/Sutra/tree/master/sutra-paper/reviews)

The white paper that introduces Sutra as a programming language. It frames LLM embedding spaces as the *substrate* for computation, not just the search index for it, and grounds that framing in five empirical results:

1. **Sign-flip binding works on natural embeddings, Hadamard binding doesn't.** The textbook VSA binding operation (elementwise multiplication) fails completely on frozen general-purpose text embeddings — bundled structures lose all signal at 2+ role-filler pairs. Sign-flip binding (`a * sign(role)`) achieves **14/14 correct snap recoveries** at 14 bundled role-filler pairs across GTE-large (1024-dim), BGE-large-en-v1.5 (1024-dim), and Jina-v2-base-en (768-dim). Cost: 6.6 µs per operation, 4× the cost of Hadamard, vastly cheaper than rotation binding (321 µs).

2. **Sustained computation: 10/10 chained bind-unbind-snap cycles.** Repeatedly building 3-role bundled structures, unbinding the target, snapping, and feeding the result into the next iteration. Cosine stays 0.58–0.65 throughout. The choice of substrate (within reason) does not matter; the choice of binding operation does.

3. **Multi-hop composition across structures.** Pull a filler out of structure A, insert it into a different role in structure B, pull it out of B. All three cross-structure extractions return the correct filler. This is the operation you need for *any* multi-step inference.

4. **Cross-substrate empirical initiation gates.** A formal calibration phase tests an embedding model's algebraic fitness, fits correction matrices, and either approves or rejects it for Sutra use. Sign-flip improves effective capacity 3–5× over Hadamard across all four tested substrates. The mxbai-embed-large pathology (diacritic attention sink) is caught by *pathology-specific* probes that run alongside the algebraic gates — substrates can pass algebraic tests and still have silent corruption modes.

5. **Compile-to-brain as the far-edge stress test.** §6.6 reports that the same compiler used for the silicon experiments also targets a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body, with **16/16 correct decisions** across four program variants × four input conditions. Full reproduction of the biological substrate result is in the second paper, below.

The paper makes an honest assessment of its own limitations: VSA algebra alone is not Turing complete, non-algebraic operations are expensive, noise accumulation requires periodic cleanup, and embedding substrates can have silent pathologies. These limitations are *addressed* in the language design rather than hidden.

## 2. Running Sutra on a Simulated Fly Brain

**Author:** Emma Leonhart
**Read it on clawRxiv:** [post 1541 — fly-brain-paper](https://clawrxiv.io/posts/1541)
**Source (GitHub):** [`fly-brain-paper/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/fly-brain-paper/paper.md)
**Reproduction skill:** [`fly-brain-paper/SKILL.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/fly-brain-paper/SKILL.md)
**Reviews directory:** [`fly-brain-paper/reviews/`](https://github.com/EmmaLeonhart/Sutra/tree/master/fly-brain-paper/reviews)

The compile-to-brain paper. The empirical-initiation framework in the language paper claims *substrate-adaptivity*: the same source code compiles for different embedding spaces given a calibration pass. This paper tests that claim against a substrate deliberately far outside the training distribution of any silicon embedding model — a Brian2 spiking simulation of the mushroom body of the fruit fly.

**Architecture:**

| Layer | Count | Role |
|---|---:|---|
| Projection neurons (PNs) | 50 | Input layer; receives encoded queries |
| Kenyon cells (KCs) | 2,000 | Sparse high-dimensional projection layer (~5% activation, APL-enforced) |
| Anterior paired lateral (APL) | 1 | Feedback inhibition; enforces sparsity |
| Mushroom body output neurons (MBONs) | 20 | Readout layer; competing prototype detectors |

**The result:** an Sutra source file describing a four-state conditional is parsed and validated by the same compiler used for the silicon experiments (paper 1), translated by a substrate-specific backend (`sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`) into Python calls against the spiking circuit, and executed. Across four program variants × four input conditions (sixteen decisions total), the compiled output produces the expected behavior mapping on every trial. The four variants yield four distinct permutations of the underlying behavior table.

To our knowledge, this is **the first demonstration of a programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate**. It serves as a non-silicon stress test for the substrate-agnostic claim that Sutra is supposed to satisfy.

The paper documents the technical insights honestly:

- **The fixed-frame invariant.** Every `snap` call in one program execution must share the same PN→KC connectivity matrix, or prototype matching fails. Measured fidelity: ~0.53 cosine per-snap under rolling frames vs. 1.0 under fixed frame; 4-way discrimination requires the fixed frame.
- **Negation as permutation compiles `!` away.** Source-level `!X` compiles cleanly into `permute(NOT_X, X)` because sign-flip permutations are involutive and distribute over `bind`. The `if/else` tree is gone — the runtime decision is a single cosine argmax against a precomputed prototype table.
- **Loops are intentionally unsupported.** A `while` compilation path probably needs recurrent KC→KC connections that the current circuit doesn't have. Framed as a research question, not a codegen oversight. See [`fly-brain/STATUS.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/fly-brain/STATUS.md) §Loops.

