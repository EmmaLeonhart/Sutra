# Sutra — Architectural Overview

This document is the "under the hood" tour of the Sutra programming language: what it is, what the source looks like, what the compiler does with it, what the resulting code actually runs on, and why the design choices are the way they are. The formal specification is split across `planning/sutra-spec/` (twenty-plus files, one topic each); this page is the readable single-file summary that ties them together.

## What Sutra Is

Sutra is a programming language whose primitive values are **hypervectors** — high-dimensional vectors in a pre-trained embedding space — and whose primitive operations are the algebraic operations that have meaning on those vectors (addition, sign-flip binding, rotation, similarity, projection, thresholding). Conventional languages compile to integer and pointer operations that execute on silicon arithmetic units. Sutra compiles to vector operations that execute on a **Vector Symbolic Architecture (VSA)** runtime, and the runtime is in turn hosted on a substrate: numpy on silicon, a spiking neural network in Brian2, a real connectome-derived circuit, or (in principle) biological neurons.

The design thesis is that embedding spaces are not just representations — they are a computational medium with algebraic structure, and once you take that structure seriously you can program in the medium directly instead of using it as a side-channel to a conventional runtime. Silicon arithmetic has no inherent meaning: `0x2A + 0x10` is not "about" anything. The addition of two hypervectors in an LLM embedding space is about the semantic content of the two concepts those hypervectors encode. Sutra is the first language designed around making that the native abstraction rather than an incidental property.

Two other commitments follow from this:

- **Fuzzy-by-default.** Everything returns a confidence-valued answer; crispness is the special case obtained by defuzzification (`is_true`, threshold matching, argmax readout). This matches the ground truth of embedding spaces — nothing is ever fully true or false inside one — and inverts the usual "crisp logic plus probabilistic bolt-on" model of most languages.
- **Substrate-agnostic.** The language surface and operation model are defined without assuming any particular execution target. The same `.su` program compiles to a numpy runtime for development and to a spiking neural network for a biological substrate, without surface changes. This is the same relationship C has with x86 vs. ARM — one source, many backends — except the backends include living tissue.

## The Three-Tier Operation Model

Every operation in Sutra belongs to exactly one of three tiers. The tier determines where the operation can legitimately run, and the compiler refuses to lower higher-tier operations onto lower-tier-only substrates. The canonical spec is `planning/sutra-spec/02-operations.md`.

**Tier 1 — Primitive.** Scalars, small integers, tuples, bounded integer iteration with a literal bound, and compile-time string manipulation. Tier-1 is ordinary host code. It is not vector computation, and `loop (N)` with a literal `N` unrolls at compile time into a flat algebraic expression at this tier. There is no runtime loop counter.

**Tier 2 — Algebraic / VSA.** The pure-math operations on hypervectors: `bundle(a, b) = a + b`, `bind(a, role) = a * sign(role)`, `unbind(bound, role) = bound * sign(role)` (self-inverse for sign-flip binding), `similarity(a, b) = cos(a, b)`, `scalar_multiply`, `project`, `rotate(v, R) = R · v` (where `R` is a rotation operator constructed at compile time as a composition of Givens rotations or derived from a real connectome via polar decomposition). These are O(1), pure math, and can run on numpy, on a spiking neural network with the same arithmetic realized as synaptic summation, or on any substrate that supports linear combination of rate-coded vectors. The spec is explicit that running them in numpy is correct and spec-compliant — the tier says nothing about where they must run, only that they are algebraic.

**Tier 3 — Non-algebraic / Vector-Graph.** The operations that are *not* linear maps and cannot be implemented in pure algebra on the vector: `snap(v)` — cleanup to the nearest codebook entry — and cone / prototype queries. These are approximate-nearest-neighbor operations, and they *are* the substrate-level operations. A codebook lookup has no non-substrate implementation — the substrate (a mushroom body, an HNSW index, a codebook) *is* the lookup. Every termination decision in a `loop (condition)` is a tier-3 pattern match.

The three-tier split is load-bearing for the fly-brain paper: the reviewer critique "your rotation runs on the host, not the neurons" is answered by pointing at tier 2 — rotation is algebraic, running it on numpy is spec-compliant, and the *termination signal* that actually gates control flow is tier-3 Jaccard-on-KC which runs on the spiking substrate. The paper's novelty is that tier-3 runs on a real connectome.

## What a `.su` File Looks Like

Sutra source files have extension `.su`. A file is one of: an **object declaration** (a named hypervector or prototype), a **module** (a group of related declarations and functions), or a **standalone executable** (a program with a top-level body). The workspace / project manifest is `atman.toml` (fixed filename, one per project or workspace root — spec: `planning/sutra-spec/22-workspaces.md`).

Representative surface features:

- **Hypervector literals and named objects**: atoms in the embedding space.
- **VSA operations**: `bundle`, `bind`, `unbind`, `snap`, `similarity`, `rotate`, `project`.
- **Fuzzy conditionals**: `if ... then ... else ...` compiles to weighted superposition, not a host-side test. The branch that "fires" is selected by KC-space similarity against compiled prototypes, per `planning/sutra-spec/03-control-flow.md`.
- **Loops**: `loop (N)` with a literal `N` unrolls at compile time; `loop (condition)` compiles to eigenrotation with a tier-3 termination signal — the "counter" is the angular position `R^i · v₀` on the helix in substrate state space, not an integer on the host.
- **Defuzzification**: `is_true(expr, threshold)` is a first-class operation. Recursive thresholding is the way Sutra turns fuzzy confidence into crisp control flow where it's needed.
- **`embed` / `defuzzy`**: surface constructors that lower to tier-2 / tier-3 operations during codegen.

See `examples/` for hand-written programs that exercise each surface feature, and `fly-brain/fuzzy_conditional.su` for the paper-cited four-way conditional program.

## The Compiler Pipeline

The reference compiler lives at `sdk/sutra-compiler/sutra_compiler/`. It is a hand-written Python implementation structured as a classical compiler frontend plus a connectome-aware codegen backend. No external parser-generator, no LLVM — the surface is small enough that hand-writing is clearer than pulling in infrastructure, and the backend is unusual enough that no off-the-shelf target fits.

**1. Lexer (`lexer.py`).** Turns source text into a token stream. Handles identifiers, numeric literals, string literals, VSA operator keywords, punctuation, and comments. Produces `Token` records with kind + lexeme + source span.

**2. Parser (`parser.py`).** Recursive-descent parser over the token stream. Produces an AST of typed nodes defined in `ast_nodes.py`: `ModuleDecl`, `ObjectDecl`, `FunctionDecl`, `IfExpr`, `LoopExpr`, `BindExpr`, `BundleExpr`, `SnapExpr`, `EmbedExpr`, `DefuzzyExpr`, and so on. Parse errors are collected in a diagnostics stream and the parser tries to keep going rather than bailing on the first error.

**3. Validator (`validator.py`).** Semantic checks over the AST: scope resolution, tier compatibility (you can't use a tier-3 result where a tier-1 primitive is required without explicit defuzzification), arity checks on VSA operations, type checks where they apply. This is also where the three-tier invariant is enforced — a program that would require running a tier-3 op on a tier-2-only substrate is rejected with a diagnostic.

**4. Codegen (`codegen_flybrain.py`).** The current reference backend lowers the validated AST into **Python source** that calls the `fly-brain/vsa_operations.py` runtime. Each AST node has a corresponding emission rule: `BindExpr` becomes `_VSA.bind(...)`, `IfExpr` lowers to a sequence of prototype compilations + a `snap` call + a weighted-superposition combine + an argmax readout, `LoopExpr` lowers to either a compile-time unroll (if the bound is literal) or to a tier-2 rotation setup plus a tier-3 Jaccard-on-KC termination loop. The emitted Python is then `exec`'d against a `FlyBrainVSA` instance, which supplies the runtime.

The CLI entry point is `python -m sutra_compiler` (packaged as `sutrac` for the IDE plugin). `sutrac --json` emits machine-readable diagnostics for the IntelliJ plugin's external annotator.

**What the compiler does not do.** There is no optimizer, no type-erasure pass, no monomorphization. Tier-2 operations are already O(1) on hypervectors, and the scale of a Sutra program is small by compiler-infrastructure standards — programs are measured in hundreds of lines, not millions. The interesting complexity is all in the substrate, not the code path that gets it there.

## What the Code Compiles To

After codegen, a `.su` program becomes **Python source that is a sequence of calls into the runtime** — `_VSA.bundle(...)`, `_VSA.bind(...)`, `_VSA.snap(...)`, `_VSA.similarity(...)`, and so on. The `_VSA` object is a `FlyBrainVSA` instance (see `fly-brain/vsa_operations.py`). The emitted Python is the compile artifact; the runtime object determines the substrate.

Here is the key design point that confuses people on first read: **the compile target is the API of the runtime object, not a particular substrate.** The same emitted Python runs against:

- A **numpy-backed** `FlyBrainVSA` (tier-2 ops in numpy, tier-3 snap against a numpy codebook) — this is the development-time substrate, fast and reproducible.
- A **Brian2 spiking-neural-network-backed** `FlyBrainVSA` — tier-2 ops as Brian2 LIF populations with Poisson rate coding, tier-3 snap as a mushroom-body circuit (140 PN → 1,882 KC, APL feedback inhibition for ~7.8% sparsity). This is the biologically-faithful substrate.
- A **real-connectome-backed** `FlyBrainVSA(use_hemibrain=True)` — identical interface, but the PN→KC projection is loaded from the Janelia hemibrain v1.2.1 connectome (real synaptic weights of a real fly brain). Rotation operators can be derived from real FlyWire v783 wiring via polar decomposition.

Switching substrates is a constructor argument. The compiled program is unchanged. This is the reason the three-tier operation model is designed around substrate-agnostic interfaces: the compiler can produce one artifact, and the runtime can dispatch it to silicon, spikes, or biological neurons without the language having to know.

## Runtime Targets (Substrates)

Every operation can be realized on multiple substrates, and the substrate rules are the contract the compiler and the runtime honor. The canonical file is `planning/sutra-spec/19-substrate-candidates.md`.

- **Numpy / CPU.** The reference runtime. Every tier-2 op is a linear-algebra call. Tier-3 snap is a brute-force cosine search against a codebook. No biological claim attached.
- **Brian2 spiking neural network.** Tier-2 ops as LIF populations; tier-3 snap as a mushroom-body circuit. Used for the fly-brain paper's validation that algebraic ops survive the Poisson noise of spiking realization (`fly-brain/neural_vsa.py`).
- **Real connectome (hemibrain + FlyWire).** The tier-3 PN→KC projection comes from real synaptic wiring. The tier-2 rotation operator can come from real recurrent wiring via polar decomposition of the synapse-count matrix (EPG → EPG, hDelta subset, etc.). This is the strongest form of the claim: both the rotation operator and the sparse-expander readout are real biology.
- **LLM embedding space (Sutra's original target).** Tier-2 arithmetic is arithmetic in the embedding space; tier-3 snap is ANN against the embedding index. This is what motivated the language; see `planning/sutra-pivot.md` for the original design document and `VSA-paper/` for the empirical foundation (86 predicates discovered as FOL operations in the mxbai-embed-large space).
- **SutraDB.** The bundled vector database at `sutraDB/` acts as a persistent codebook for the tier-3 snap operation when programs need storage beyond a single process.

The fly-brain paper's central empirical result is that a Sutra program compiles once and runs correctly on all of {numpy, Brian2 spiking, real hemibrain}, with termination decisions on the spiking/real substrate driven by KC-Jaccard pattern matching (not a host-side test). That is the "programming language that compiles to a connectome" claim, made literal.

## Control Flow

Two pieces of Sutra control flow are non-obvious and are the most common source of confusion. Both have dedicated spec files.

**Fuzzy conditionals (`planning/sutra-spec/03-control-flow.md`).** `if q then A else B` does not compile to a host-side boolean test. It compiles to a weighted superposition: `result = w_true · A + w_false · B`, where `w_true = relu(cos(snap(q), prototype_true))` and similarly for `w_false`, normalized to sum to one. The four-way conditional in the fly-brain paper generalizes this to `result = Σ_i w_i · branch_i` over four joint prototypes (smell × hunger). The branch that "fires" is the one with the highest KC-pattern overlap, and the decision is made *by the circuit* — the argmax at the end is readout, not branching.

**Eigenrotation loops (`03-control-flow.md` §18–46).** `loop (condition)` with data-dependent termination compiles to: a tier-2 rotation operator `R` is constructed at compile time; the host issues a sequence of presentations `R^i · v₀` (accumulated on the original `v₀`, not on decoded output) to the substrate; at each iteration the substrate computes `P(state)` — the KC-pattern projection — and checks Jaccard overlap against a compiled prototype table; the loop terminates when the overlap exceeds threshold. There is no integer counter at runtime. The "counter" is the angular position on the helix `R^i · v₀` in the substrate's state space — a geometric, corkscrew-shaped quantity, not a scalar on the host.

Why the helix is a counter: each application of `R` rotates the state by a fixed angle; the set of positions `{R^i · v₀ : i = 0, 1, 2, …}` is discrete and geometrically ordered along the spiral. Target prototypes placed at specific angles act as stopping conditions. The loop "counts" by accumulating rotation; the substrate decides when to stop by detecting a prototype match.

The theoretical reason this works — why KC-Jaccard pattern matching dominates cosine similarity as a termination readout, and why the discrimination is independent of substrate dimensionality — is in `planning/sutra-spec/23-loop-readout-theory.md`.

## Fuzzy Logic and Defuzzification

Sutra values are fuzzy by default. A `similarity(a, b)` call returns a continuous confidence, not a boolean. Every logical operation is defined on that continuous space: fuzzy conjunction is minimum, fuzzy disjunction is maximum, fuzzy negation is `1 - x`. Crisp control flow is obtained via defuzzification, and the canonical defuzzification is `is_true(expr, threshold)` — recursive because `is_true(is_true(x, t₁), t₂)` is itself a valid Sutra expression and lowers to a second thresholding step.

The canonical spec is `planning/sutra-spec/04-defuzzification.md`. The design principle is that confidence is the ground truth and threshold-based crispness is a conscious choice a programmer makes at specific points in a program — not a silent coercion the compiler inserts. Where conventional languages treat booleans as primitive and fuzzy logic as a library, Sutra treats fuzzy logic as primitive and booleans as a defuzzified special case.

## VSA Math Foundations

The full axiomatic treatment of the VSA operations is in `planning/sutra-spec/11-vsa-math.md` — eight vector-space axioms that the operations must satisfy for the language's algebraic guarantees to hold.

The key operations:

- `bundle(a, b) = a + b` — superposition. Commutative, associative, identity element is the zero vector.
- `bind(a, role) = a * sign(role)` — sign-flip binding. Self-inverse: `unbind(bind(a, r), r) = a`. Commutative with bundle.
- `similarity(a, b) = cos(a, b)` — normalized inner product. Ranges over `[-1, 1]`.
- `rotate(v, R) = R · v` — linear transformation by an orthogonal matrix. Preserves norms and pairwise angles.
- `snap(v)` — cleanup to the nearest codebook entry. Tier-3. The substrate-level operation.

These together give Sutra enough algebraic structure to encode addressable read/write memory (via bind + bundle + snap for cleanup), conditional branching (via fuzzy weighted superposition over joint prototypes), and iteration (via eigenrotation with tier-3 termination). The fly-brain paper argues that this primitive set is Turing-equivalent at the language level, with the patient's connectome serving as the bounded finite-state machine in the same sense any physical computer's memory is a bounded finite-state machine.

A historical note: what Sutra calls `bind` is the sign-flip operation `a * sign(role)`, not dimension permutation. An earlier version called this `permute` — that was a misnomer and was renamed. The spec operation `permute` (which shuffles dimensions) exists but is separate; the class alias is preserved for back-compat only.

## Workspaces and Projects

A Sutra workspace is a directory containing an `atman.toml` file. A single-project workspace has a `[project]` table; a multi-project workspace has a `[workspace]` table listing member projects. The file is fixed-filename — not an extension — and there is exactly one per project or workspace root. Spec: `planning/sutra-spec/22-workspaces.md`.

The manifest names dependencies, substrate targets, and compiler options. Historically, workspaces used `.aksln` and projects used `.akproj` (from the language's pre-rename "Ākaśa" identity); both were collapsed into the single `atman.toml` when the language was renamed to Sutra on 2026-04-11.

## IDE and Tooling

The IDE layer is not an afterthought. Sutra's semantics are rich enough — long-range dependencies through the embedding space, fuzzy logic, substrate tier invariants — that static analysis in the editor is load-bearing for productive use, not optional polish. The IntelliJ plugin at `sdk/intellij-sutra/` is the reference IDE and talks to the compiler via `sutrac --json`; the VS Code extension at `sdk/vscode-sutra/` is the lighter convenience option with TextMate grammar and snippets.

An MCP (Model Context Protocol) server is planned as part of the language runtime — the tooling is a first-class layer that tells an AI assistant (or a human reading the code) where things actually live and how operations relate, resolving the long-range semantic dependencies that would otherwise require guesswork. The architecture spec is in `planning/sutra-spec/20-ide-architecture.md`.

## Related Papers

Three papers ground the language empirically:

- **Latent Space Cartography** (`VSA-paper/`, primary repo at [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography)) — the FOL-discovery work that validated the "embedding spaces encode consistent vector arithmetic" premise. Currently at Strong Accept on clawRxiv as post 1127.
- **Sutra language paper** (`sutra-paper/`) — the language design: three-tier model, sign-flip binding, fuzzy weighted superposition, defuzzification, substrate-agnostic compilation.
- **Fly-brain paper** (`fly-brain-paper/`) — the compile-to-connectome demonstration: a Sutra program running end-to-end on real hemibrain wiring with tier-3 termination decisions made by the circuit's KC-space pattern matching.

## Further Reading in the Spec

The `planning/sutra-spec/` directory is the canonical specification. The files most relevant to the architecture overview above:

- `01-design-principles.md` — why fuzzy-by-default, why vectors as primitives, why substrate-agnostic.
- `02-operations.md` — the three-tier operation model (the load-bearing file for this whole document).
- `03-control-flow.md` — conditionals and loops, including the precise eigenrotation semantics.
- `04-defuzzification.md` — `is_true` and threshold-based crisp control.
- `06-runtime.md` — the runtime object and how it dispatches to substrates.
- `09-lambda-calculus.md` — encoding of lambda terms in VSA, basis for the language-level Turing-equivalence argument.
- `10-turing-completeness.md` — the formal Turing-equivalence argument and the language-vs-substrate distinction.
- `11-vsa-math.md` — the eight VSA axioms.
- `19-substrate-candidates.md` — which substrates support which tier and why.
- `20-ide-architecture.md` — the IDE / MCP layer as part of the language runtime.
- `22-workspaces.md` — `atman.toml` and multi-project workspaces.
- `23-loop-readout-theory.md` — why KC-Jaccard dominates cosine as a termination readout, and the dimension-independence theorem behind it.

If a choice in this overview document seems under-justified, the answer is almost always in one of those files.
