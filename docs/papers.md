# Papers

Sutra is grounded in two papers, both submitted to the [Claw4S 2026 conference](https://clawrxiv.io). Both are open source. Both live in this repository — paper sources, reproduction scripts, and supporting data are all in-tree.

A third paper — [*Latent Space Cartography Applied to Wikidata*](https://clawrxiv.io/posts/1127) — is the empirical foundation for the existence of stable algebraic structure in frozen LLM embeddings, and provides the citation that grounds Sutra's "computation in embedding space is real, not metaphor" claim. It is **not** maintained from this repo; its primary source of truth is [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography), and it is currently at **Strong Accept** on clawRxiv (post 1127).

## 1. Sutra: A Vector Programming Language for Computation in Embedding Spaces

**Author:** Emma Leonhart
**Read it on clawRxiv:** [post 1542 — sutra-paper v2](https://clawrxiv.io/posts/1542)
**Source (GitHub):** [`sutra-paper/paper.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/sutra-paper/paper.md)
**Reproduction skill:** [`sutra-paper/SKILL.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/sutra-paper/SKILL.md)
**Reviews:** [`sutra-paper/reviews/`](https://github.com/EmmaLeonhart/Sutra/tree/master/sutra-paper/reviews)

The white paper that introduces Sutra as a programming language. It frames frozen LLM embedding spaces as the substrate for computation, not just the search index for it, and reports the empirical results that ground the framing:

1. **Bundled role-filler structures decode reliably under the right binding operation.** The textbook VSA binding (elementwise multiplication, "Hadamard") fails on frozen general-purpose text embeddings — bundled structures lose all signal at 2+ role-filler pairs. The paper characterizes which alternative bindings recover correctly across GTE-large (1024-d), BGE-large-en-v1.5 (1024-d), and Jina-v2-base-en (768-d), and quantifies the per-operation cost of each.

2. **Sustained computation across chained bind-unbind cycles.** Repeatedly building bundled structures, unbinding a target, cleaning up, and feeding the result into the next iteration. The paper reports the cosine trajectory across cycles and the conditions under which it stays in a recoverable basin.

3. **Multi-hop composition across structures.** Pull a filler out of structure A, insert it into a different role in structure B, pull it out of B. The cross-structure extractions return the correct filler when binding and cleanup are operating in their valid range.

4. **Cross-substrate calibration gates.** A formal calibration phase tests an embedding model's algebraic fitness, fits correction matrices, and either approves or rejects it for Sutra use. The paper reports the capacity gains across substrates and documents pathology-specific probes (e.g. the mxbai-embed-large diacritic attention sink) that catch silent corruption modes the algebraic gates miss.

5. **Compile-to-connectome as a substrate stress test.** §6.6 reports that an earlier compiler targeted a Brian2 spiking simulation of the *Drosophila melanogaster* mushroom body, with the four-way conditional program executing through the spiking circuit. That research line has since been retired (see the note on paper 2 below); the section is preserved as a historical record of the substrate-portability claim.

The paper documents its limitations: VSA algebra alone is not Turing complete, some operations are expensive, noise accumulates and requires cleanup, and embedding substrates can have silent pathologies. The language design addresses each one rather than hides it.

> **Note on framing.** Earlier drafts of this paper headlined sign-flip binding as the contribution. The current Sutra design uses rotation binding as the runtime mechanism for non-semantic structural storage (sign-flip is retired as of 2026-04-22), and the headline contribution is the broader claim that learned matrices fit to corpus data can serve as the binding operators for semantic roles. The published paper version reflects the older framing; the spec under [`planning/sutra-spec/`](https://github.com/EmmaLeonhart/Sutra/tree/master/planning/sutra-spec) is the current source of truth for the language design.

## 2. Running Sutra on the Drosophila Hemibrain Connectome (retired research line)

**Author:** Emma Leonhart
**Read it on clawRxiv:** [post 1541](https://clawrxiv.io/posts/1541)

> **Status (2026-04-26):** The supporting `fly-brain/` directory and `codegen_flybrain.py` backend were retired from the repo on 2026-04-26 — the substrate work outpaced the language's maturity, and the half-finished compile-to-connectome path was clogging the repo without paying for itself. The paper is preserved as a historical research artifact on clawRxiv. The negative findings the work produced (real FlyWire weight matrices do not function as rotation operators; CX ring-attractor circuits did not discriminate direction on real connectivity) are preserved as `planning/findings/2026-04-1*-*` documents.

The compile-to-brain paper. The empirical-initiation framework in the language paper claims *substrate-adaptivity*: the same source code compiles for different embedding spaces given a calibration pass. This paper tested that claim against a substrate deliberately far outside the training distribution of any silicon embedding model — a Brian2 spiking simulation of the mushroom body of the fruit fly.

**Architecture:**

| Layer | Count | Role |
|---|---:|---|
| Projection neurons (PNs) | 50 | Input layer; receives encoded queries |
| Kenyon cells (KCs) | 2,000 | Sparse high-dimensional projection layer (~5% activation, APL-enforced) |
| Anterior paired lateral (APL) | 1 | Feedback inhibition; enforces sparsity |
| Mushroom body output neurons (MBONs) | 20 | Readout layer; competing prototype detectors |

**The result:** a Sutra source file describing a four-state conditional was parsed and validated by the same compiler used for the silicon experiments (paper 1), translated by a substrate-specific backend (the now-retired `codegen_flybrain.py`) into Python calls against the spiking circuit, and executed. Across four program variants × four input conditions (sixteen decisions total), the compiled output produced the expected behavior mapping on every trial. The four variants yielded four distinct permutations of the underlying behavior table.

To our knowledge, this is **the first demonstration of a programming language whose conditional semantics compile mechanically onto a connectome-derived spiking substrate**. It serves as a non-silicon stress test for the substrate-agnostic claim that Sutra is supposed to satisfy.

Technical findings reported in the paper:

- **The fixed-frame invariant.** Every `snap` call in one program execution must share the same PN→KC connectivity matrix, or prototype matching fails. Measured fidelity: ~0.53 cosine per-snap under rolling frames vs. 1.0 under fixed frame; 4-way discrimination requires the fixed frame.
- **Negation as permutation compiles `!` away.** Source-level `!X` compiles cleanly into `permute(NOT_X, X)` because sign-flip permutations are involutive and distribute over `bind`. The `if/else` tree is gone — the runtime decision is a single cosine argmax against a precomputed prototype table.
- **Loops are intentionally unsupported.** A `while` compilation path probably needs recurrent KC→KC connections that the circuit didn't have. Framed as a research question, not a codegen oversight.

