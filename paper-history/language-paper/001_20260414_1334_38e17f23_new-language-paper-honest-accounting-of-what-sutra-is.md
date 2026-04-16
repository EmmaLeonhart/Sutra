<!--
commit:  38e17f2359af4d8af935dc693537710cb6e8255a
date:    2026-04-14 13:34:14 -0700
subject: new language-paper: honest accounting of what Sutra is
path:    language-paper/paper.md
-->

# A Programming Language Whose Only Control Primitives Are `select` and `gate`

**Emma Leonhart**

## Abstract

We describe Sutra, a small programming language in which traditional control flow (`if`/`else`/`while`/`for`/`switch`) does not exist. Its place is taken by two substrate-resident primitives: `select(scores, options)`, a softmax-weighted blend over candidate values, and `gate(condition, value)`, a defuzzification that commits a fuzzy vector to a discrete codebook entry. Every Sutra program compiles to a straight-line composition of vector operations — bind, bundle, similarity, snap, select, gate — with no host-side branching, no jumps, and no back-edges. We report what exists: a hand-written compiler (lexer → parser → validator → codegen) that takes `.su` source to runnable Python against two different substrate backends; a formal grammar and operation specification (`planning/sutra-spec/`); an IntelliJ Platform plugin and a VS Code extension; and two empirical demonstrations that the same language surface compiles to two qualitatively different substrates — frozen LLM embedding spaces (sign-flip binding, 14/14 role-filler recovery) and a spiking neural model of the *Drosophila* mushroom body (560/560 conditional decisions). We do not claim Turing-completeness, general-purpose programming, or that Sutra is ready to replace existing languages. The contribution is the existence of the design point: a language in which the traditional control-flow family is replaced by two continuous primitives, compiled and demonstrated end-to-end on multiple substrates.

## 1. Introduction

Conventional programming languages have a control-flow family — `if`/`else` for selection, `while`/`for` for iteration, `switch` for multi-way dispatch, `break`/`continue`/`return` for early exit. These constructs compile to machine branches: conditional jumps, back-edges, branch-predictor state. On commodity CPUs this is natural; on GPUs it is expensive (divergent warps); on connectionist substrates (spiking networks, analog neuromorphic hardware, or frozen LLM embeddings used as a compute surface) it is unclear what a "branch" would even mean.

Sutra asks a narrow question: if you delete the control-flow family from the language, what is the smallest replacement that keeps the language useful? The answer Sutra proposes is two primitives:

- `select(scores, options)` = `Σᵢ softmax(scores)ᵢ · optionsᵢ` — a weighted blend of candidate values. This replaces `if`/`else`/`switch`: every branch runs, the scores determine how much each branch contributes to the result.
- `gate(v)` — defuzzify a fuzzy vector `v` by snapping it to the nearest entry in a compiled codebook. This replaces `break`/`return`/termination: a loop terminates when `gate` commits to a prototype.

Both primitives are continuous, differentiable, and executable as vector operations — a weighted sum and a cosine-argmax-snap, respectively. Nothing in the language compiles to a branch.

This paper is not the case for doing this at scale. It is the existence claim: a compiler exists, the language is specified, two backends exist, and the same source compiles to and runs on both. The rest of this paper is what we have built and what it does not yet do.

## 2. What Exists

### 2.1 The language

Sutra source files have extension `.su`. The surface syntax is C-family with object/method declarations, operators, and type casts. A full EBNF grammar lives at `planning/sutra-spec/grammar.md`; the operation model and control-flow semantics are specified across `planning/sutra-spec/02-operations.md`, `03-control-flow.md`, `04-defuzzification.md`, `11-vsa-math.md`, and `26-select-and-gate.md`.

The primitive vector operations are `bundle(a, b) = a + b`, `bind(a, r) = a * sign(r)` (sign-flip binding; see §3.1), `unbind`, `similarity`, and `snap`. Control flow is exactly `select` and `gate` as defined above; loops are written as `loop[N]` (compile-time unroll, no runtime iteration) or `loop(condition)` (data-dependent termination via `gate`). There is no `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, or `goto` in the grammar.

### 2.2 The compiler

The reference compiler is `sdk/sutra-compiler/`, ~2000 LOC of hand-written Python. The pipeline is:

- `lexer.py` — character stream → token stream.
- `parser.py` — token stream → AST (`ast_nodes.py`).
- `validator.py` — name resolution, type checks, diagnostic collection (`diagnostics.py`).
- `codegen_flybrain.py` — AST → executable Python against the `fly-brain/` runtime.
- `workspace.py` — `atman.toml` project resolution.

The CLI is `python -m sutra_compiler <file.su>`. A JUnit-style test corpus lives under `sdk/sutra-compiler/tests/`. Six of the thirteen illustrative programs in `examples/` currently hit `CodegenNotSupported` on method/operator declarations, `EmbedExpr`, `DefuzzyExpr`, and `UnsafeCastExpr`; the paper-cited programs compile. Feature-coverage breakdown: `planning/open-questions/codegen-v1-feature-coverage.md`.

### 2.3 The IDE surface

An IntelliJ Platform plugin (`sdk/intellij-sutra/`) ships a lexer, syntax highlighting, brace matching, completion, live templates, a settings panel, and an external annotator wired to `sutrac --json`. A lighter VS Code extension (`sdk/vscode-sutra/`) provides a TextMate grammar and snippets.

### 2.4 The specification

`planning/sutra-spec/` is thirty-odd markdown files covering grammar, operations, control flow, defuzzification, types, VSA math axioms, substrate compatibility, and IDE architecture. It is the language's contract; implementations that diverge from it are bugs (on whichever side the drift landed — see `CLAUDE.md` §"The spec is load-bearing").

## 3. What Compiles and Runs

### 3.1 Backend 1: frozen LLM embedding spaces

On a numpy backend over frozen general-purpose embedding models (GTE-large, BGE-large, Jina-v2), Sutra programs compile to sequences of sign-flip bindings, bundles, and snap-to-nearest over a codebook. The choice of binding operation is empirical, not design-by-fiat: six binding candidates were tested on bundled role-filler structures, and the textbook VSA choice (Hadamard product) fails on natural embeddings because they are anisotropic and correlated. Sign-flip (`a * sign(r)`) is self-inverse at ~7μs per call and achieves 14/14 correct role-filler recoveries at the 14-role limit of the test codebook, across all three models. Sustains 10/10 chained bind-unbind-snap cycles; supports multi-hop composition between bundled structures. Reported separately in the companion empirical-operations paper (*Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces*, Leonhart).

For the language paper the relevant fact is: the same source program compiles to this backend and runs.

### 3.2 Backend 2: Drosophila mushroom body (Brian2 LIF)

The `codegen_flybrain.py` backend targets `fly-brain/`, a Brian2 spiking neural network of the right mushroom body of *Drosophila melanogaster* wired with synaptic connectivity loaded directly from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020). The circuit is 140 projection neurons → 1,882 Kenyon cells → 1 APL feedback neuron → 20 MBON readouts, with leaky integrate-and-fire dynamics.

A Sutra program that encodes a four-way conditional — two binary inputs (odor × hunger) mapped to one of four behaviors — compiles to a sequence of bind/bundle/snap operations plus a `select` over four pre-compiled joint prototypes. Across thirty-five independent hemibrain simulations with different Brian2 seeds, the four-way conditional produces **560/560 correct decisions (σ=0)** across 16 scenarios × 35 runs. The same algorithm ported to the Shiu et al. 2024 whole-brain LIF model (138,639 neurons, 15M synapses, real FlyWire v783 connectivity) produces **155/160 (96.9%) at n=10 seeds** with no parameter tuning. Full treatment: the companion paper (*Compiling a Vector Programming Language to the Drosophila Hemibrain Connectome*, Leonhart).

### 3.3 What substrate-portability buys

The same `.su` source — a conditional program written once — compiles against two backends with no source changes. The first backend is a numpy runtime over 1024-dim frozen LLM embeddings. The second is a sparse-matrix spiking simulation of a real fly connectome. Neither substrate has branching, loops, or jumps as primitives; both implement `select`, `gate`, `bundle`, `bind`, and `snap` as their native operations. The compiler emits vector-op sequences that run natively on either.

This is the concrete content of "control-flow-free language": the same source does not need to know which substrate it targets because the compilation target has no branches on either side.

## 4. What Does Not Yet Work

Honest limits, not framed as future work:

**Iteration on real connectome substrate.** `loop(condition)` is specified as eigenrotation through vector space, `state ← R · state`, terminating via `gate` on a prototype match. On a synthetic Givens-rotation backend this executes as intended. On the real FlyWire v783 substrate, the EPG-only ring attractor under direct drive produces essentially no recurrent dynamics (47/47 single-drive probes at 200 Hz/100 ms, 0 recurrent spikes; 5× escalation crosses only noise floor). The polar-decomposition orthogonal matrix previously reported was a mathematical approximation of a subset of W (98% of Frobenius content discarded), not the connectome's own operator. Retracted in the fly-brain paper Result 3. Iteration on real connectome W is open work; `loop[N]` (compile-time unroll) and `loop(condition)` over synthetic Givens both work.

**Addressable memory via bind/unbind has a documented failure mode.** On the Shiu spike-count readout (138,639-D), bind is self-inverse at cos=1.000 but cross-unbind with the wrong role recovers the original at cos=0.999 (should be near zero). Cause: role-driven spike-count vectors are sparse (~40 of 138,639 dims nonzero), so median-split produces a ±1 mask dominated by -1, and any wrong-role unbind ≈ -(-v) = v. This is an encoding mismatch between spec (balanced ±1 role) and the substrate's sparse response, not a dynamics failure; captured at `planning/findings/2026-04-13-shiu-bind-unbind.md`.

**Turing-completeness is not claimed.** Earlier drafts reached for this; it is not defended here. The primitive set is control-flow-free and compiles to real substrates, which is what this paper claims. Whether the language is computationally universal is a separate question requiring a separate proof we have not written.

**Benchmarks against existing languages do not exist.** This paper contains no performance comparison, no compilation-speed number relative to any other compiler, and no claim about relative productivity. The contribution is the existence of the design point, not its superiority.

**Compiler feature coverage is partial.** 6 of 13 illustrative `.su` examples hit `CodegenNotSupported` on method/operator declarations, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`. The paper-cited programs compile; the example corpus as a whole is ahead of the compiler.

**The substrate the language was designed around is still being built.** The 2026-04-14 project pivot moved the fly-brain to a downstream compatibility target; the primary substrate going forward is a spiking population whose connectivity is a compile-time parameter, matched to what each operation needs. That substrate is in design; this paper reports what exists against the two substrates that do work today.

## 5. Related Work

Vector Symbolic Architectures (Kanerva 2009, Plate 1995, Gayler 2003, Smolensky 1990) define the binding/bundling/similarity algebra Sutra inherits; Hyperdimensional Computing (Imani et al. 2019, Joshi et al. 2016, Neubert et al. 2019) builds systems on it. Sutra's contribution on top of VSA is the language-level framing — a concrete grammar, a compiler, and the specific choice of `select` + `gate` as the full control primitive set — not the VSA algebra itself.

Differentiable programming languages (e.g. JAX, PyTorch) remove branches *in practice* by convention (avoid data-dependent Python control flow inside jitted regions); Sutra removes them *by grammar*. TensorFlow's `tf.cond` and similar are library-level selects over a still-branching host language; Sutra's `select` is the language's only selection primitive.

Neuromorphic and connectome-based computing proposals (Neftci et al. 2019, Davies et al. 2018) typically pair a conventional host language with a spiking-circuit target. Sutra's grammar targets the spiking circuit directly — no host-side conditional controls the run.

Prior work grounding the algebraic structure exists: relational displacement analysis of frozen embedding spaces discovered 86 predicates as consistent vector operations across three models with r = 0.861 consistency-prediction correlation (Leonhart, *Latent space cartography applied to Wikidata*). That work establishes the empirical premise — frozen embedding spaces *have* the algebraic structure Sutra exploits — without itself proposing a language.

## 6. Conclusion

Sutra is a small programming language in which `if`/`else`/`while`/`for`/`switch`/`break`/`return` do not exist; their place is taken by `select` (softmax-weighted blend) and `gate` (defuzz-and-commit), both compiled to vector operations. A compiler, a specification, an IntelliJ plugin, a VS Code extension, and two substrate backends exist and are in the public repository. The same source compiles to and runs on both a numpy runtime over frozen LLM embeddings and a Brian2 simulation of the *Drosophila* mushroom body wired with real connectome connectivity. We do not claim the language is ready for general-purpose programming, Turing-complete, or faster than existing tools. We claim its existence as a working design point and report honestly which pieces do and do not yet function.

## References

Davies, M., et al. (2018). Loihi: A neuromorphic manycore processor with on-chip learning. IEEE Micro.

Gayler, R. W. (2003). Vector symbolic architectures answer Jackendoff's challenges for cognitive neuroscience. ICCS.

Imani, M., et al. (2019). A framework for HD computing. ReConFig.

Joshi, A., et al. (2016). Language recognition using random indexing. arXiv.

Kanerva, P. (2009). Hyperdimensional computing: An introduction to computing in distributed representation. Cognitive Computation.

Leonhart, E. Latent space cartography applied to Wikidata: Relational displacement analysis reveals a silent tokenizer defect in mxbai-embed-large.

Leonhart, E. Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces.

Leonhart, E. Compiling a Vector Programming Language to the Drosophila Hemibrain Connectome.

Neftci, E. O., Mostafa, H., & Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine.

Neubert, P., et al. (2019). An introduction to hyperdimensional computing for robotics. KI.

Plate, T. A. (1995). Holographic reduced representations. IEEE Transactions on Neural Networks.

Scheffer, L. K., et al. (2020). A connectome and analysis of the adult Drosophila central brain. eLife.

Shiu, P. K., et al. (2024). A Drosophila computational brain model reveals sensorimotor processing. Nature.

Smolensky, P. (1990). Tensor product variable binding and the representation of symbolic structures in connectionist systems. Artificial Intelligence.
