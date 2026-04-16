<!--
commit:  53023b3371078427ad82078a6f1cbe7e969f1271
date:    2026-04-14 18:41:11 -0700
subject: language-paper: aggressive rewrite; queue concurrency design note
path:    language-paper/paper.md
-->

# Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing

**Emma Leonhart**

## Abstract

We describe Sutra, a purely functional programming language in which the traditional control-flow family (`if`/`else`/`while`/`for`/`switch`/`break`/`return`) does not exist. Every Sutra program compiles to a straight-line composition of vector operations — bind, bundle, similarity, snap-to-nearest — gated by two continuous control primitives: `select` (softmax-weighted blend over candidate branches) and `gate` (defuzzification to a codebook entry). Iteration is data-dependent rotation through vector space, terminating when `gate` commits. The primitive set is computationally universal under standard VSA-completeness arguments (Plate 1995, Kanerva 2009): binding + bundling + snap + unbounded iteration + addressable memory is sufficient for general-purpose programming. There is no `print`, no IO primitive, no side effect a function body can invoke — the single escape from the pure region is a final name lookup at the program's edge, structurally analogous to the IO boundary of a Haskell program.

A hand-written compiler (`sdk/sutra-compiler/`, ~2000 LOC of Python) takes `.su` source through lexing, parsing, validation, and codegen to self-contained Python that depends only on numpy. Three demonstration programs — a minimal embed-and-retrieve ("hello world"), a 4-way fuzzy weighted-superposition conditional, and a bind/bundle/unbind structured record — compile and run end-to-end, producing 23/23 outputs matching their committed reference. The generated code is matrix-only (matmuls, sums, cosines), so a PyTorch/GPU backend is a mechanical refactor of the code-emission layer rather than a rewrite; this paper does not claim the port, only that the compilation surface admits it.

We also attempted to compile Sutra programs onto a spiking neural network substrate — specifically, a Brian2 simulation of the *Drosophila melanogaster* mushroom body wired with real FlyWire hemibrain connectivity. That attempt is not carried through as a working backend in this paper. Fitting the language's primitives onto a fixed biological anatomy turned out to require more substrate-specific engineering than a language paper can honestly include, and specific structural mismatches surfaced — most concretely, the real FlyWire weight matrix does not function as a rotation operator in the sense the language's `loop` primitive requires, so data-dependent iteration does not lift onto the connectome without additional machinery we have not built. We report the attempt and the negative findings separately in the companion `fly-brain-paper/`. The language's substrate in this paper is the numpy runtime; compiling Sutra to a biological connectome would need a dedicated library and is not in scope here.

## 1. Introduction

Conventional programming languages have a control-flow family: `if`/`else` for selection, `while`/`for` for iteration, `switch` for multi-way dispatch, `break`/`continue`/`return` for early exit. These constructs compile to machine branches — conditional jumps, back-edges, branch-predictor state. On commodity CPUs this is nearly free; on GPUs it is expensive (divergent warps and synchronization stalls); on connectionist substrates (spiking networks, neuromorphic hardware, or frozen LLM embedding spaces used as a compute surface) there is no native notion of "branch" at all.

Sutra asks what the smallest replacement is for the traditional control-flow family if you remove it entirely. The answer it proposes is three primitives:

- **`select(scores, options)`** = `Σᵢ softmax(scores)ᵢ · optionsᵢ` — a weighted blend of candidate branches. Replaces `if`/`else`/`switch`: every branch evaluates; scores determine how much each contributes.
- **`gate(v)`** — defuzzify a fuzzy vector `v` by snapping it to the nearest entry in a compiled codebook. Commits a continuous trajectory to a discrete answer.
- **`loop(cond)`** — data-dependent iteration, implemented as `state ← R · state` through vector space, terminating when `gate` commits to a prototype. `loop[N]` with a compile-time `N` unrolls into a flat algebraic expression with no runtime iteration required.

All three compile to vector operations: weighted sums, rotations, and cosine-argmax snaps. Nothing in the language compiles to a machine branch. The composition of these three primitives with the VSA algebra (bind, bundle, similarity, snap) yields a Turing-complete programming surface under the standard VSA-universality arguments (Plate 1995; Kanerva 2009; Gayler 2003): binding + superposition gives addressable memory; unbounded iteration with a convergence test gives unbounded recursion; `select` gives arbitrary boolean composition.

The contribution of this paper is the language itself plus a compiler and runtime that executes it. Two explicit non-goals: we do not claim Sutra runs on a biological brain (§5 reports that attempt as an open problem), and we do not claim GPU speedups (the runtime is currently numpy-on-CPU; GPU is future work).

## 2. The Language

### 2.1 Surface syntax

Sutra source files have extension `.su`. The syntax is C-family: type-annotated declarations, function definitions, method calls, arithmetic operators. A full EBNF grammar lives at `planning/sutra-spec/grammar.md`; the operation model and control-flow semantics are specified across `planning/sutra-spec/02-operations.md`, `03-control-flow.md`, `04-defuzzification.md`, `11-vsa-math.md`, and `26-select-and-gate.md`.

The grammar contains no `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, or `goto`. These constructs are not hidden behind macros or library calls — they are not tokens the lexer recognizes. A fuzzy conditional is written as a `select` (§4.2 shows one); a multi-way dispatch is a `select` with more than two branches; an iteration is a `loop`.

Programs are composed of top-level `vector` declarations (basis vectors and derived ones), `map<vector, string>` tables (for the name-lookup edge), and `function` definitions whose bodies are sequences of `vector` bindings and a `return`. There are no statements in the imperative sense. No assignment-to-mutable-variable. No exceptions. No side effects inside the pure region.

### 2.2 Primitive operations

**Vector primitives** are the VSA algebra:

- `bundle(a, b, …)` — superposition. Concretely `sum(a, b, …)` followed by L2 normalization.
- `bind(a, r) = a * sign(r)` — sign-flip binding. Self-inverse (`bind(bind(a,r),r) = a`), approximately orthogonal across distinct roles. The choice of sign-flip rather than Hadamard product is empirical: the companion paper *Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces* (Leonhart) shows that on three frozen LLM embedding models Hadamard fails at modest codebook sizes while sign-flip sustains 14/14 role-filler recoveries. On fresh random vectors (the default demo substrate) both work; we use sign-flip everywhere for consistency.
- `unbind(role, bound)` — the inverse of `bind`. For sign-flip, identical to `bind`.
- `similarity(a, b)` — cosine similarity.
- `argmax_cosine(q, codebook)` — cleanup to the nearest codebook entry by cosine-argmax.

**Control primitives**:

- `select(scores, options)` — softmax-weighted blend (§1). In the demo programs this is expressed as an explicit weighted sum `Σᵢ wᵢ · optionsᵢ` with `wᵢ = similarity(query, prototypeᵢ)`, which compiles to the same expression the primitive names.
- `gate(v)` — defuzz-and-commit (§1). Expressed in the demos as `argmax_cosine` against a committed codebook.
- `loop[N] { body }` — compile-time unroll; no runtime iteration, no back-branch.
- `loop(cond) { body }` — data-dependent rotation, `state ← R · state`, termination via `gate` on a compiled prototype.

### 2.3 Iteration in detail

`loop(cond)` is the primitive most unlike its conventional counterpart. A `while` loop in a branching language has a back-edge in the control-flow graph; the program counter returns to the top of the loop body. A Sutra `loop(cond)` has no back-edge. Instead, the loop's state is rotated through vector space by a rotation operator R (either a synthetic Givens rotation chosen at compile time, or — on a substrate where R is not a free parameter — the substrate's native linear operator); at each step, the current state is compared against a compiled set of termination prototypes; when `gate` commits to one of them, the loop returns.

This means an iteration is not a sequence of conditional jumps but a continuous geometric trajectory with a discrete termination event. The trajectory itself is computed by matrix-vector multiplication and is therefore GPU-native; the termination check is a cosine-argmax, also GPU-native. On an unconstrained substrate — numpy on a laptop, or a CUDA kernel — this works straightforwardly: rotation iterates, cosine-snap fires, the loop exits. The demonstrations in §4 do not exercise `loop(cond)`; they cover straight-line programs plus `loop[N]`-shaped unrolling. We flag `loop(cond)` as implemented in the compiler but not stressed in the demonstration corpus.

### 2.4 Purity and the edge

Sutra is purely functional. There is no `print`, no `read`, no exception, no mutable global, no side-effecting primitive a function body can invoke. Every function is a deterministic vector-to-vector (or vector-to-scalar) map. The single way values leave the pure region is a final `map<vector, string>` lookup at the program's edge, which converts a gated codebook entry to the string the host sees. Structurally this is the same shape as Haskell's IO boundary: the pure body computes a description of a result; the edge commits it.

The consequence is that a Sutra "Hello World" does not print "Hello, world." It embeds a greeting vector, retrieves it from a codebook by similarity, and returns the matching name. §4.1 gives the full program (10 non-comment lines) and its captured output.

## 3. The Compiler

The reference compiler is ~2000 LOC of hand-written Python at `sdk/sutra-compiler/`:

- `lexer.py` — character stream → token stream.
- `parser.py` — tokens → AST (`ast_nodes.py`).
- `validator.py` — name resolution, type checks, diagnostics (`diagnostics.py`).
- `codegen_numpy.py` — AST → self-contained Python with a small inline `_NumpyVSA` class. **The demo path. No external runtime dependencies beyond numpy.**
- `codegen_flybrain.py` — AST → Python against the `fly-brain/` Brian2 runtime. Kept for the fly-brain paper's experiments; not used by the language demonstrations.
- `workspace.py` — `atman.toml` project resolution.

CLI, from the repository root:

```bash
python -m sutra_compiler --emit-numpy examples/hello_world.su     # print generated Python
python examples/_smoke_test.py                                    # compile + run all three demos
```

A JUnit-style test corpus lives at `sdk/sutra-compiler/tests/`. An IntelliJ Platform plugin (`sdk/intellij-sutra/`) provides lexer, syntax highlighting, brace matching, completion, live templates, and an external annotator wired to `sutrac --json`. A VS Code extension (`sdk/vscode-sutra/`) provides a TextMate grammar and snippets.

The numpy backend's emitted module is ~70 lines for a typical demo. It instantiates a `_NumpyVSA(dim=256, seed=42)` object with five methods (`embed`, `bind`, `unbind`, `bundle`, `similarity`), then emits the user's top-level `vector` and `map` declarations as Python assignments and the user's `function` declarations as Python `def`s. There is no control flow in the emitted module that was not in the source; there are no runtime branches the user did not write as a `select`-style weighted sum.

## 4. Demonstrations

Three programs compile and run through the numpy backend end-to-end. All three live in `examples/`; the test harness `examples/_smoke_test.py` compiles each from source, executes the generated Python, and verifies outputs against committed reference tables. On a clean run it reports `PASS` with 23/23 outputs matching.

### 4.1 Hello world — the minimum shape

```sutra
vector greeting = basis_vector("hello_world");

vector v_hello    = basis_vector("hello_world");
vector v_goodbye  = basis_vector("goodbye");
vector v_question = basis_vector("are_you_there");

map<vector, string> PHRASE_NAME = {
    v_hello:    "hello world",
    v_goodbye:  "goodbye",
    v_question: "are you there"
};

function string say() {
    vector winner = argmax_cosine(greeting, [v_hello, v_goodbye, v_question]);
    return PHRASE_NAME[winner];
}
```

Expected output: `say() → "hello world"`. Traditional Hello World is IO-heavy: a `print` statement against a standard output stream. Sutra has no `print`. The equivalent minimal shape is to embed the greeting in the vector space, retrieve it from a codebook by cosine-argmax, and look the result up in the `map` at the edge. This is the smallest program in which every Sutra feature that distinguishes the language (basis vectors, argmax-cosine as `gate`, map-lookup as edge) appears.

### 4.2 Fuzzy branching — `select` as the only conditional

The full program is `examples/fuzzy_branching.su`. Four state prototypes are pre-computed by binding pairs of basis vectors (`proto_PH = bind(smell_present, hunger_hungry)`, etc.). Each of four program variants (A, B, C, D) defines a different prototype→behavior map. The shared decision pipeline is a 4-way weighted superposition:

```sutra
vector result =
    w_PH * beh_PH +
    w_PF * beh_PF +
    w_AH * beh_AH +
    w_AF * beh_AF;
vector winner = argmax_cosine(result, [b_approach, b_ignore, b_search, b_idle]);
return BEHAVIOR_NAME[winner];
```

where `w_*` are cosine similarities between the input query and each prototype. All four branches contribute to `result`; the `argmax_cosine` at the edge commits to one. No `if`. No `switch`. 4 program variants × 4 input conditions = 16 decisions; all 16 match the reference table on a clean run.

### 4.3 Role-filler records — structured memory as a flat vector

The full program is `examples/role_filler_record.su`. A record is bundled from role-filler bindings:

```sutra
function vector make_record(vector name, vector color, vector shape) {
    return bundle(
        bind(r_name,  name),
        bind(r_color, color),
        bind(r_shape, shape)
    );
}

function string decode_field(vector record, vector role) {
    vector recovered = unbind(record, role);
    vector winner = argmax_cosine(
        recovered,
        [f_alice, f_bob, f_red, f_blue, f_circle, f_square]
    );
    return FILLER_NAME[winner];
}
```

Encoding: `record = Σᵢ bind(roleᵢ, fillerᵢ)`. Decoding one field: `unbind(record, role_i); argmax_cosine`. No branches, no loops, no dispatch. The smoke test runs two records (alice/red/circle; bob/blue/square) × three roles each = 6 decodes; all 6 match.

### 4.4 Summary of results

| Program | Inputs × Programs | Outputs | Correct |
|---|---|---|---|
| `hello_world.su` | 1 | 1 | 1/1 |
| `fuzzy_branching.su` | 4 × 4 | 16 | 16/16 |
| `role_filler_record.su` | 2 × 3 | 6 | 6/6 |

Total: 23/23. The outputs are not stochastic — the seed is fixed (`seed=42`, `dim=256`) and the reference table is committed under `examples/`. A reader running `python examples/_smoke_test.py` on a fresh clone reproduces exactly these numbers.

## 5. Attempted substrate: the *Drosophila* mushroom body

We attempted to compile Sutra programs onto a biological spiking substrate. The target was a Brian2 leaky integrate-and-fire simulation of the right mushroom body of *Drosophila melanogaster*, wired from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020): 140 projection neurons → 1,882 Kenyon cells → APL feedback → 20 MBON readouts. A second target was the Shiu et al. 2024 whole-brain LIF model (138,639 neurons, 15 million synapses, real FlyWire v783 connectivity).

Parts of the attempt succeeded. A 4-way fuzzy conditional written as a `select` over four pre-compiled Kenyon-cell prototypes produces decisions on the hemibrain simulator that match a reference table for a specific compilation of one program (results in `fly-brain-paper/`). Bundle and snap operate on spiking substrates with accuracy reported in the same companion.

Parts did not. Most concretely: `loop(cond)` as specified in §2.3 requires a rotation operator R such that iterated application `state ← R · state` traces a trajectory through vector space. On a synthetic Givens rotation matrix this works. On the actual FlyWire weight matrix — used as `R` as the fly-brain codegen would need — iterated application produces a compressive projection, not a rotation: states collapse rather than traverse, and the gate never fires on the intended prototype. A central-complex EPG ring-attractor slice, which anatomically should implement directional rotation, fails to discriminate direction on the real connectivity (see `planning/findings/` under the dated negative-result entries). The conclusion we carry is that the connectome-as-substrate direction is a research program — one that needs dedicated substrate-compilation infrastructure (prototype fitting, anatomy-aware rotation discovery, alternative iteration primitives) which is outside the scope of a language paper.

We report this explicitly rather than eliding it. Prior summaries of this project have variously described the fly-brain backend as "working" and as a core contribution of the language; neither framing is honest given the structural mismatches we found. The honest framing is: Sutra as a language exists and runs on the numpy substrate, the connectome substrate is a separate open research question, and the companion `fly-brain-paper/` exists to catalog what does and does not transfer.

## 6. Why Branchless Matters

Three consequences of removing the control-flow family from the language surface, independent of which substrate runs underneath:

**GPU-native execution, in principle.** Every Sutra operation is a matrix-vector multiplication, a sum, a Hadamard product, or a cosine. The entire language runtime is sparse or dense BLAS. There is no divergent-warp penalty because there is no divergence; every branch of every `select` runs, weighted. The current numpy backend does not demonstrate GPU speedup — that requires the PyTorch/JAX port that is future work — but the emitted code is GPU-ready in the sense that every operation has a trivially corresponding GPU kernel.

**End-to-end differentiability.** The constructs that normally break backpropagation — hard `if`, `break`, early `return`, discrete `switch` — are not in the language. A Sutra program is differentiable with respect to its inputs by construction, because every operation in it is differentiable. A learned Sutra program — where the `select` weights, the bind roles, and the codebook are trained by gradient descent rather than hand-coded — is a natural object; we have not yet demonstrated a trained program, but the path is straightforward.

**Connectionist-native compilation, in theory.** Spiking circuits, frozen LLM embeddings, and analog neuromorphic hardware all lack native branching. They have weighted summation, attenuation, convergence, and winner-take-all. A language whose only primitives are these operations maps onto such substrates *in principle*. §5 reports what we actually learned when we tried: the mapping is not free — specific substrates fail to implement specific primitives — and the gap is real work, not a formality.

## 7. Related Work

Vector Symbolic Architectures (Smolensky 1990, Plate 1995, Gayler 2003, Kanerva 2009) define the binding/bundling/similarity algebra Sutra inherits; Hyperdimensional Computing (Imani et al. 2019, Neubert et al. 2019) builds systems on it. Sutra's contribution on top of VSA is the language-level framing: a concrete grammar, a compiler, and the specific choice of `select` + `gate` + `loop` as the complete control primitive set.

Differentiable programming frameworks (JAX, PyTorch, TensorFlow) remove branches in practice by convention inside jitted regions; Sutra removes them by grammar. `tf.cond` and `jax.lax.cond` are library-level selects over a still-branching host language; Sutra's `select` is the language's only selection primitive, and the host language does not have `if`.

Neuromorphic and connectome-based computing proposals (Davies et al. 2018, Neftci et al. 2019) typically pair a conventional host language with a spiking-circuit target, emulating host branches at the edge of the substrate. Sutra's grammar targets the spiking-circuit style of computation directly; §5 reports the realities of the mapping when the substrate is a real connectome.

The empirical premise — that frozen LLM embedding spaces encode consistent algebraic structure that VSA operations can exploit — is established by prior relational-displacement analysis of three general-purpose embedding models (Leonhart, *Latent space cartography applied to Wikidata*): 86 predicates discovered as consistent vector operations, r = 0.861 correlation between geometric consistency and prediction accuracy.

## 8. Limitations

- **The runtime is numpy-on-CPU.** We claim the compilation surface admits GPU execution. We do not demonstrate GPU execution.
- **The demonstration corpus is small.** Three programs, 23 decisions. We have not run a 2D game loop, a parser, or an interpreter — each is a natural next demonstration given the primitive set. The companion empirical papers stress-test the underlying VSA operations more extensively (14/14 role-filler recoveries on a 14-role codebook, etc., Leonhart) but those are substrate-characterization results, not language-level demonstrations.
- **`loop(cond)` is implemented but not exercised in the demonstrations.** The three demo programs are straight-line plus `loop[N]`-shaped unrolls. A data-dependent `loop(cond)` demo is future work.
- **The connectome substrate is an open research question.** §5 reports the attempt and the specific structural failures (FlyWire-as-rotation, EPG direction-discrimination). A dedicated library for compiling to biological connectivity is plausible but unbuilt.
- **We do not claim peer review.** This paper is a preprint; the citations to companion work are also preprints on the same preprint service.

## 9. Conclusion

Sutra is a programming language in which `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, and `return` do not exist. Their place is taken by `select`, `gate`, and `loop`, all compiled to vector operations. The primitive set is computationally universal under standard VSA-completeness arguments. A compiler, a specification, an IntelliJ plugin, a VS Code extension, and a numpy runtime exist and are in the public repository; three demonstration programs run end-to-end, producing 23/23 outputs matching their committed reference. The design point is the language's existence: a purely functional, Turing-complete programming surface that compiles to matmuls, sums, and cosines, with no machine branches anywhere in its runtime.

## Appendix: Reproducibility

Repository: `https://github.com/EmmaLeonhart/Sutra`.

```bash
git clone https://github.com/EmmaLeonhart/Sutra
cd Sutra
python examples/_smoke_test.py
```

Expected output: three per-example sections followed by `PASS` and 23 individual `OK` lines. The seed (42) and dimension (256) are hardcoded in the numpy codegen; the reference tables are committed in `examples/_smoke_test.py` and `examples/role_filler_record.expected`. To inspect the generated Python for any example:

```bash
PYTHONIOENCODING=utf-8 python -m sutra_compiler --emit-numpy examples/hello_world.su
```

Dependencies: Python 3.10+, numpy. No GPU required. No Brian2, no fly-brain runtime — those dependencies belong to `fly-brain-paper/`'s reproducibility path, not this paper's.

## References

Davies, M., et al. (2018). Loihi: A neuromorphic manycore processor with on-chip learning. IEEE Micro.

Gayler, R. W. (2003). Vector symbolic architectures answer Jackendoff's challenges for cognitive neuroscience. ICCS.

Imani, M., et al. (2019). A framework for HD computing. ReConFig.

Kanerva, P. (2009). Hyperdimensional computing: An introduction to computing in distributed representation. Cognitive Computation.

Leonhart, E. *Latent space cartography applied to Wikidata: Relational displacement analysis reveals a silent tokenizer defect in mxbai-embed-large.*

Leonhart, E. *Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces.*

Leonhart, E. *Compiling a Vector Programming Language to the Drosophila Hemibrain Connectome.*

Neftci, E. O., Mostafa, H., & Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine.

Neubert, P., et al. (2019). An introduction to hyperdimensional computing for robotics. KI.

Plate, T. A. (1995). Holographic reduced representations. IEEE Transactions on Neural Networks.

Scheffer, L. K., et al. (2020). A connectome and analysis of the adult Drosophila central brain. eLife.

Shiu, P. K., et al. (2024). A Drosophila computational brain model reveals sensorimotor processing. Nature.

Smolensky, P. (1990). Tensor product variable binding and the representation of symbolic structures in connectionist systems. Artificial Intelligence.
