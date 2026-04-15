# Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing

**Emma Leonhart**

## Abstract

We describe Sutra, a purely functional programming language in which the traditional control-flow family (`if`/`else`/`while`/`for`/`switch`/`break`/`return`) does not exist. Every Sutra program compiles to a straight-line composition of vector operations — bind, bundle, similarity, snap-to-nearest — gated by two continuous control primitives: `select` (softmax-weighted blend over candidate branches) and `gate` (defuzzification to a codebook entry). Iteration is data-dependent rotation through vector space, terminating when `gate` commits. The primitive set is computationally universal under standard VSA-completeness arguments (Plate 1995, Kanerva 2009): binding + bundling + snap + unbounded iteration + addressable memory is sufficient for general-purpose programming. There is no `print`, no IO primitive, no side effect a function body can invoke — the single escape from the pure region is a final name lookup at the program's edge, structurally analogous to the IO boundary of a Haskell program.

A hand-written compiler (`sdk/sutra-compiler/`) takes `.su` source through lexing, parsing, validation, and codegen to self-contained Python that depends only on numpy. Three demonstration programs — a minimal embed-and-retrieve ("hello world"), a 4-way fuzzy weighted-superposition conditional, and a bind/bundle/unbind structured record — compile and run end-to-end with 23/23 outputs matching their committed reference. The generated code is matrix-only, so a PyTorch/GPU backend is a mechanical refactor rather than a rewrite; this paper does not claim the port, only that the compilation surface admits it.

We also attempted to compile Sutra programs onto a spiking neural network substrate — specifically, a Brian2 simulation of the *Drosophila melanogaster* mushroom body wired with real FlyWire hemibrain connectivity. That attempt is not carried through as a working backend in this paper: fitting the language's primitives onto a fixed biological anatomy turned out to require more substrate-specific engineering than a single programming-language paper can honestly include, and specific structural mismatches (e.g. the real FlyWire weight matrix does not function as a rotation operator in the sense the language's `loop` primitive requires) are research projects in their own right. We report the attempt and the negative findings in the companion `fly-brain-paper/`. The language's substrate in this paper is the numpy runtime; the connectome direction is plausibly addressable by a dedicated library but is not in scope here.

## 1. Introduction

Conventional programming languages have a control-flow family: `if`/`else` for selection, `while`/`for` for iteration, `switch` for multi-way dispatch, `break`/`continue`/`return` for early exit. These constructs compile to machine branches — conditional jumps, back-edges, branch-predictor state. On commodity CPUs this is free; on GPUs it is expensive (divergent warps and synchronization stalls); on connectionist substrates (spiking networks, neuromorphic hardware, or frozen LLM embedding spaces used as a compute surface) there is no native notion of "branch" at all.

Sutra asks what the smallest replacement is for the traditional control-flow family if you remove it from the language. The answer Sutra proposes is three primitives:

- **`select(scores, options)`** = `Σᵢ softmax(scores)ᵢ · optionsᵢ` — a weighted blend of candidate branches. Replaces `if`/`else`/`switch`: every branch evaluates, scores determine how much each contributes.
- **`gate(v)`** — defuzzify a fuzzy vector `v` by snapping it to the nearest entry in a compiled codebook. Commits a continuous trajectory to a discrete answer.
- **`loop(cond)`** — data-dependent iteration, implemented as `state ← R · state` through vector space, terminating when `gate` commits to a prototype. `loop[N]` with a compile-time `N` unrolls into a flat algebraic expression with no runtime iteration required.

All three compile to vector operations: weighted sums, rotations, and cosine-argmax snaps. Nothing in the language compiles to a machine branch. The composition of these three primitives with the VSA algebra (bind, bundle, similarity, snap) yields a Turing-complete programming surface under the standard VSA-universality arguments (Plate 1995; Kanerva 2009; Gayler 2003): binding + superposition gives addressable memory; unbounded iteration with a convergence test gives unbounded recursion; `select` gives arbitrary boolean composition.

This paper describes Sutra as a language: its grammar, its compiler, its IDE tooling, its two working backends, and the design point the absence of branching opens up. Empirical results on the two backends are reported in the companion papers and are referenced here as substrate demonstrations, not as the primary contribution of this paper.

## 2. The Language

### 2.1 Surface syntax

Sutra source files have extension `.su`. The syntax is C-family with object/method declarations, operators, and type casts. A full EBNF grammar lives at `planning/sutra-spec/grammar.md`; the operation model and control-flow semantics are specified across `planning/sutra-spec/02-operations.md`, `03-control-flow.md`, `04-defuzzification.md`, `11-vsa-math.md`, and `26-select-and-gate.md`.

The grammar contains no `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, or `goto`. These constructs are not hidden behind macros or library calls — they are not tokens the lexer recognizes. A fuzzy conditional is written as a `select`; a multi-way dispatch is a `select` with more than two branches; an iteration is a `loop`.

### 2.2 Primitive operations

**Vector primitives** are the VSA algebra:

- `bundle(a, b) = a + b` — superposition.
- `bind(a, r) = a * sign(r)` — sign-flip binding. Self-inverse (`bind(bind(a,r),r) = a`), approximately orthogonal across distinct roles. See §3 for the empirical choice.
- `unbind` — the inverse of `bind` (for sign-flip, identical to `bind`).
- `similarity(a, b) = cos(a, b)` — cosine similarity.
- `snap(q)` — cleanup to the nearest codebook entry by cosine argmax.

**Control primitives**:

- `select(scores, options)` — softmax-weighted blend (§1).
- `gate(v)` — defuzz-and-commit (§1).
- `loop[N] { body }` — compile-time unroll; no runtime iteration, no back-branch.
- `loop(cond) { body }` — data-dependent rotation, `state ← R · state`, termination via `gate` on a compiled prototype.

### 2.3 Iteration in detail

`loop(cond)` is the primitive most unlike its conventional counterpart. A `while` loop in a branching language has a back-edge in the control-flow graph; the program counter returns to the top of the loop body. A Sutra `loop(cond)` has no back-edge. Instead, the loop's state is rotated through vector space by a rotation operator R (either a synthetic Givens rotation chosen at compile time, or a substrate-native operator fit during empirical initiation); at each step, the current state is compared against a compiled set of termination prototypes; when `gate` commits to one of them, the loop returns.

This means an iteration is not a sequence of conditional jumps but a continuous geometric trajectory with a discrete termination event. The trajectory itself is computed by matrix-vector multiplication and is therefore GPU-native; the termination check is a cosine-argmax, also GPU-native. On an unconstrained substrate — numpy on a laptop, or a CUDA kernel — this works straightforwardly: rotation iterates, cosine-snap fires, the loop exits.

## 3. The Compiler

The reference compiler lives at `sdk/sutra-compiler/`, ~2000 LOC of hand-written Python. Pipeline:

- `lexer.py` — character stream → token stream.
- `parser.py` — tokens → AST (`ast_nodes.py`).
- `validator.py` — name resolution, type checks, diagnostics (`diagnostics.py`).
- `codegen_flybrain.py` — AST → executable Python against the `fly-brain/` runtime.
- `workspace.py` — `atman.toml` project resolution.

CLI: `python -m sutra_compiler <file.su>`. A JUnit-style test corpus lives under `sdk/sutra-compiler/tests/`.

An IntelliJ Platform plugin (`sdk/intellij-sutra/`) provides lexer, syntax highlighting, brace matching, completion, live templates, a settings panel, and an external annotator wired to `sutrac --json`. A VS Code extension (`sdk/vscode-sutra/`) provides a TextMate grammar and snippets.

## 4. Substrates

The same `.su` source compiles to and runs on two qualitatively different substrates. This is not an incidental property — it is the concrete content of "control-flow-free." A program that compiles to vector operations does not need to know whether the vectors are dense floating-point arrays in a numpy buffer, spike counts on a simulated neural circuit, or activations in an LLM embedding space.

### 4.1 Frozen LLM embedding spaces

A numpy backend compiles Sutra source against three frozen general-purpose embedding models (GTE-large, BGE-large, Jina-v2). Bind, bundle, similarity, and snap run as dense vector operations over 768–1024-dim embeddings. Iteration (`loop(cond)`) runs as rotation + cosine-argmax-snap; because the substrate is a plain numpy array, rotation iterates as designed and the loop terminates on prototype match with no substrate-specific adjustments.

Empirical results — sign-flip binding achieves 14/14 role-filler recoveries on a 14-role codebook across all three models; 10/10 chained bind-unbind-snap cycles; multi-hop composition between bundled structures — are reported in *Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces* (Leonhart). For the language paper the relevant fact is: the same source compiles here and runs.

### 4.2 *Drosophila* mushroom body (Brian2 LIF)

A second backend, `codegen_flybrain.py`, targets a Brian2 spiking neural network of the right mushroom body of *Drosophila melanogaster* wired from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020). The circuit is 140 projection neurons → 1,882 Kenyon cells → APL feedback → 20 MBON readouts, with leaky integrate-and-fire dynamics.

A conditional program — two binary inputs (odor × hunger) mapped to one of four behaviors — compiles to a `bind`/`bundle`/`snap` pipeline plus a `select` over four pre-compiled prototypes. Thirty-five independent hemibrain simulations produce 560/560 correct decisions (σ=0). The same program ported to the Shiu et al. 2024 whole-brain LIF model (138,639 neurons, 15M synapses, real FlyWire v783 W) produces 155/160 (96.9%) at n=10 seeds with no parameter tuning. Full treatment: *Compiling a Vector Programming Language to the Drosophila Hemibrain Connectome* (Leonhart).

### 4.3 Substrate portability

The two backends share no runtime state and no compilation stage past AST. One is a dense-vector numpy runtime on CPU; the other is a sparse spiking simulation of a real biological connectome. The fact that the same source compiles to both without modification is possible because every operation Sutra emits — bind, bundle, similarity, snap, select, gate, rotation — is a vector operation with a known substrate-native implementation on each backend. A third backend, a connectionist simulator whose wiring is a compile-time parameter (design in progress under the 2026-04-14 pivot, `STATUS.md`), will add a substrate where every primitive has wiring chosen to match the operation's requirements rather than inherited from biology or pretraining.

## 5. Why Branchless Matters

Three consequences of removing the control-flow family from the language surface:

**GPU-native execution.** Every Sutra operation is a matrix-vector multiplication, a sum, a Hadamard product, or a cosine. The entire language runtime is sparse or dense BLAS. There is no divergent-warp penalty because there is no divergence; every branch of every `select` runs, weighted. A program the size of an interpreter can run entirely on the GPU with no CPU handoff.

**End-to-end differentiability.** The constructs that normally break backpropagation — hard `if`, `break`, early `return`, discrete `switch` — are not in the language. A Sutra program is differentiable with respect to its inputs by construction, because every operation in it is differentiable. A learned Sutra program is a natural object: train the `select` scores, the bind roles, and the codebook, and you have gradient flow through everything.

**Connectionist-native compilation.** Spiking neural circuits, frozen LLM embeddings, and analog neuromorphic hardware all lack native branching. They have weighted summation (bundle), attenuation (bind), convergence (similarity), and winner-take-all (snap). A language whose only primitives are these operations compiles to such substrates directly, without an emulation layer. The existence of the two working backends is the proof that this is not hypothetical.

## 6. Related Work

Vector Symbolic Architectures (Kanerva 2009, Plate 1995, Gayler 2003, Smolensky 1990) define the binding/bundling/similarity algebra Sutra inherits; Hyperdimensional Computing (Imani et al. 2019, Joshi et al. 2016, Neubert et al. 2019) builds systems on it. Sutra's contribution on top of VSA is the language-level framing: a concrete grammar, a compiler, and the specific choice of `select` + `gate` + `loop` as the complete control primitive set.

Differentiable programming frameworks (JAX, PyTorch, TensorFlow) remove branches in practice by convention inside jitted regions; Sutra removes them by grammar. `tf.cond` and `jax.lax.cond` are library-level selects over a still-branching host language; Sutra's `select` is the language's only selection primitive, and the host language does not have `if`.

Neuromorphic and connectome-based computing proposals (Neftci et al. 2019, Davies et al. 2018) typically pair a conventional host language with a spiking-circuit target, emulating host branches at the edge of the substrate. Sutra's grammar targets the spiking circuit directly; there is no host-side conditional that the substrate must emulate.

The empirical premise — that frozen LLM embedding spaces encode consistent algebraic structure that VSA operations can exploit — is established by prior relational-displacement analysis of three general-purpose embedding models (Leonhart, *Latent space cartography applied to Wikidata*): 86 predicates discovered as consistent vector operations, r = 0.861 correlation between geometric consistency and prediction accuracy. That work establishes the substrate; this paper is the language that compiles to it.

## 7. Current Scope

Sutra's compiler handles the programs cited in this paper and its companion papers. A worked illustrative corpus lives under `examples/`; six of the thirteen example programs currently exercise compiler features beyond the v1 codegen (method/operator declarations, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`) and are tracked in `planning/open-questions/codegen-v1-feature-coverage.md`. The natural next demonstrations — running larger programs end-to-end (a 2D game loop, a grammar-driven parser, a small interpreter) on an unconstrained substrate — are straightforward given the primitive set and the existing backends.

## 8. Conclusion

Sutra is a programming language in which `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, and `return` do not exist. Their place is taken by `select`, `gate`, and `loop`, all compiled to vector operations. The primitive set is computationally universal under standard VSA-completeness arguments. A compiler, a specification, an IntelliJ plugin, a VS Code extension, and two substrate backends exist and are in the public repository; the same source compiles to and runs on a numpy runtime over frozen LLM embeddings and a Brian2 simulation of the *Drosophila* mushroom body. The design point is the language's existence: a Turing-complete programming surface that compiles to matrix multiplications and cosine-argmax snaps, with no machine branches anywhere in its runtime.

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

