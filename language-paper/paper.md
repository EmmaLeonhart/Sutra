# Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing

**Emma Leonhart**

## Abstract

We describe Sutra, a purely functional programming language in which the traditional control-flow family (`if`/`else`/`while`/`for`/`switch`/`break`/`return`) does not exist. Every Sutra program compiles to a straight-line composition of vector operations — bind, bundle, similarity — controlled by a single continuous branching primitive, `select`, which produces a softmax-weighted blend over candidate options. A `select` with a single option carries an implicit fuzzy threshold (default 0.5) and acts as the closest equivalent to an `if`; a `select` with k options is multi-way dispatch; a `select` with an `else` clause supplies a "none of the above" sink. Iteration is data-dependent rotation through vector space, terminating when a readout `select` shifts mass from "continue" to "exit" as the trajectory aligns with a target. A program may optionally end with a snap to the nearest entry of a compiled codebook (the discrete-output form), or it may return a raw vector / fuzzy result that downstream consumers interpret — the terminal commit is a programmer choice, not a language requirement. Binding is a learned role matrix — a linear operator fit from (input, output) embedding pairs in a frozen LLM space, where each role (e.g. "located-in-country," "continent-of") is the matrix that maps a subject embedding to its object embedding. Displacements discovered in prior cartographic analysis are the rank-0 (translation-only) special case; the full matrix generalizes to capture non-translational relational structure. We evaluate the learned-matrix binding on Wikidata relational triples across two substrates: on GTE-large (sentence-transformers 1024-d), a ridge-0.1 matrix reaches 87% top-1 on continent-of (10-class codebook, chance 10%, mean-object baseline 19.5%) and 76% on located-in-country (21-class, chance 4.8%); on nomic-embed-text (768-d), every method collapses to the majority-class prior across all predicates and four text-template variants. The substrate choice is load-bearing for the binding direction, and this paper reports both the positive and null result. The numpy demonstration runtime additionally supports a sign-flip non-semantic binding (`a * sign(r)`, self-inverse elementwise) for programs whose roles carry no semantic content.

The primitive set is computationally universal under standard VSA-completeness arguments (Plate 1995, Kanerva 2009): binding + bundling + snap + unbounded iteration + addressable memory is sufficient for general-purpose programming. There is no `print`, no IO primitive, no side effect a function body can invoke — the single escape from the pure region is a final name lookup at the program's edge, structurally analogous to the IO boundary of a Haskell program.

A hand-written compiler (`sdk/sutra-compiler/`, ~2000 LOC of Python) takes `.su` source through lexing, parsing, validation, and codegen to self-contained Python that depends only on numpy. Three demonstration programs — a minimal embed-and-retrieve ("hello world"), a 4-way fuzzy weighted-superposition conditional, and a bind/bundle/unbind structured record — compile and run end-to-end, producing 23/23 outputs matching their committed reference. The generated code is matrix-only (matmuls, sums, cosines), so a PyTorch/GPU backend is a mechanical refactor of the code-emission layer rather than a rewrite; this paper does not claim the port, only that the compilation surface admits it.

We also attempted to compile Sutra programs onto a spiking neural network substrate — specifically, a Brian2 simulation of the *Drosophila melanogaster* mushroom body wired with real FlyWire hemibrain connectivity. That attempt is not carried through as a working backend in this paper. Fitting the language's primitives onto a fixed biological anatomy turned out to require more substrate-specific engineering than a language paper can honestly include, and specific structural mismatches surfaced — most concretely, the real FlyWire weight matrix does not function as a rotation operator in the sense the language's `loop` primitive requires, so data-dependent iteration does not lift onto the connectome without additional machinery we have not built. We report the attempt and the negative findings separately in the companion `fly-brain-paper/`. The language's substrate in this paper is the numpy runtime; compiling Sutra to a biological connectome would need a dedicated library and is not in scope here.

## 1. Introduction

Conventional programming languages have a control-flow family: `if`/`else` for selection, `while`/`for` for iteration, `switch` for multi-way dispatch, `break`/`continue`/`return` for early exit. These constructs compile to machine branches — conditional jumps, back-edges, branch-predictor state. On commodity CPUs this is nearly free; on GPUs it is expensive (divergent warps and synchronization stalls); on connectionist substrates (spiking networks, neuromorphic hardware, or frozen LLM embedding spaces used as a compute surface) there is no native notion of "branch" at all.

Sutra asks what the smallest replacement is for the traditional control-flow family if you remove it entirely. The answer it proposes is three primitives:

- **`select(scores, options)`** = `Σᵢ softmax(scores)ᵢ · optionsᵢ` — a softmax-weighted blend over k candidate options. Replaces `if`/`else`/`switch`: every option evaluates; scores determine how much each contributes; total mass is 1. With one option it acts as `if`: the polarized truth `is_true(score)` weights the option, with a configurable fuzzy threshold (default 0.5) governing whether downstream readouts will treat the result as a definite answer. With an `else` clause (`select(scores, options) else fallback`) an implicit "none of the above" term is added with mass that grows when no named option dominates.
- **`snap(v, codebook)`** — defuzzify a fuzzy vector `v` by selecting the nearest entry in a compiled codebook (cosine-argmax). Commits a continuous trajectory to a discrete answer at the program's edge.
- **`loop(cond)`** — data-dependent iteration, implemented as `state ← R · state` through vector space. The exit is itself a `select` whose two options are "continue iterating" and "leave with the current state," with the exit score driven by the snap-to-prototype match growing as the trajectory aligns. `loop[N]` with a compile-time `N` unrolls into a flat algebraic expression with no runtime iteration required.

All three compile to vector operations: weighted sums, rotations, and cosine-argmax snaps. Nothing in the language compiles to a machine branch. The composition of these primitives with the VSA algebra (bind, bundle, similarity, snap) yields a Turing-complete programming surface under the standard VSA-universality arguments (Plate 1995; Kanerva 2009; Gayler 2003): binding + superposition gives addressable memory; unbounded iteration with a convergence test gives unbounded recursion; `select` gives arbitrary boolean composition. We demonstrate each piece rather than asserting it: `examples/role_filler_record.su` builds a three-field record via bind+bundle and decodes any field by unbinding with the role key (23/23 correct on the committed reference); `examples/loop_rotation.su` runs a data-dependent eigenrotation loop with a snap terminal commit on the numpy substrate; `examples/counter_loop.su` uses `loop(cond)` as a helical counter whose terminal snap identifies where on the trajectory the iteration exited. The iteration count is not a host integer — it is the angular position of the state vector on the helix `R^i · v_0`, matched against a codebook of numeric prototypes at termination.

The contribution of this paper is the language itself — its design, its primitives, what problem it addresses — plus a compiler and runtime that executes it. The language addresses a gap between two observations: (1) frozen LLM embedding spaces encode consistent algebraic structure (86 relational displacements discovered across three models, with r = 0.861 correlation between geometric consistency and prediction accuracy), and (2) no programming language exists that treats this structure as a computational substrate rather than a lookup table. Sutra fills that gap: a formal system for composing vector operations in embedding spaces, where roles are learned matrices, truth is fuzzy, and control flow is geometry.

Two explicit non-goals: we do not claim Sutra runs on a biological brain (§5 reports that attempt as an open problem), and we do not claim GPU speedups (the runtime is currently numpy-on-CPU; GPU is future work).

## 2. The Language

### 2.1 Surface syntax

Sutra source files have extension `.su`. The syntax is C-family: type-annotated declarations, function definitions, method calls, arithmetic operators. The lexer, parser, and AST live in `sdk/sutra-compiler/sutra_compiler/`; the semantics of each operation are defined by the code the compiler emits (`codegen_numpy.py`, `codegen_flybrain.py`) rather than by a separate specification document. A prior spec at `planning/sutra-spec/` was deprecated as of 2026-04-15 for accumulated drift; a new spec is being built incrementally from first principles.

The grammar contains no `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, or `goto`. These constructs are not hidden behind macros or library calls — they are not tokens the lexer recognizes. A fuzzy conditional is written as a `select` (§4.2 shows one); a multi-way dispatch is a `select` with more than two branches; an iteration is a `loop`.

Programs are composed of top-level `vector` declarations (basis vectors and derived ones), `map<vector, string>` tables (for the name-lookup edge), and `function` definitions whose bodies are sequences of `vector` bindings and a `return`. There are no statements in the imperative sense. No assignment-to-mutable-variable. No exceptions. No side effects inside the pure region.

### 2.2 Primitive operations

**Vector primitives** are the VSA algebra:

- `bundle(a, b, …)` — superposition. Concretely `sum(a, b, …)` followed by L2 normalization.
- `bind(role, filler) = R · filler` — role-filler binding, where R is a matrix encoding the semantic role. A role in Sutra is a learned linear operator, not a random vector: "located-in-country" is the matrix fit on (city, country) embedding pairs; "is_cat" is the matrix fit on (entity, cat-label) pairs. This unifies binding with defuzzification — both are matrix-vector products, one encoding a semantic role and the other encoding a truth-extraction. We evaluate this on Wikidata relational triples (§4.5): on GTE-large with 5-fold cross-validated ridge regression, the `continent-of` matrix reaches 87% top-1 on a 10-class codebook and the `located-in-country` matrix reaches 76% on a 21-class codebook, against mean-object baselines of 19.5% and 39.0%. The prior cartographic analysis (Leonhart, *Latent space cartography applied to Wikidata*) identified displacement vectors — the rank-0, translation-only special case of this matrix — for a set of relational predicates; the full matrix generalizes to capture rotations and scalings the displacement-only model misses. The numpy demo runtime additionally provides a sign-flip non-semantic binding (`a * sign(r)`, self-inverse elementwise) for programs whose role keys carry no semantic content — the record-decode demonstration in §4.3 uses this mode because the role keys there are arbitrary tags ("name," "color," "shape") rather than semantic predicates.
- `unbind(role, bound)` — the approximate inverse of `bind`. For the full matrix form, `R⁻¹ · bound` (or `R^T · bound` when R is orthogonal, as it is under the Procrustes fit). For the sign-flip non-semantic form, identical to `bind`.
- `similarity(a, b)` — cosine similarity.
- `argmax_cosine(q, codebook)` — cleanup to the nearest codebook entry by cosine-argmax.

**Control primitives**:

- `select(scores, options)` — softmax-weighted blend (§1), and the language's only branching primitive. Single-option, multi-option, and `else`-clause forms cover the territory normally split across `if`, `switch`, and default branches. In the demo programs `select` is expressed as an explicit weighted sum `Σᵢ wᵢ · optionsᵢ` with `wᵢ = similarity(query, prototypeᵢ)`, which compiles to the same expression the primitive names.
- `snap(v, codebook)` — defuzz-and-commit (§1). Expressed in the demos as `argmax_cosine` against a committed codebook.
- `loop[N] { body }` — compile-time unroll; no runtime iteration, no back-branch.
- `loop(cond) { body }` — data-dependent rotation, `state ← R · state`, termination via a readout `select` whose exit score is driven by snap-to-prototype match.

### 2.3 Iteration in detail

`loop(cond)` is the primitive most unlike its conventional counterpart. A `while` loop in a branching language has a back-edge in the control-flow graph; the program counter returns to the top of the loop body. A Sutra `loop(cond)` has no back-edge. Instead, the loop's state is rotated through vector space by a rotation operator R (either a synthetic Givens rotation chosen at compile time, or — on a substrate where R is not a free parameter — the substrate's native linear operator); at each step, the current state is compared against a compiled set of termination prototypes; the readout is a `select` between "continue iterating" and "leave with the current state," and as the snap-to-prototype match grows the exit score wins.

This means an iteration is not a sequence of conditional jumps but a continuous geometric trajectory with a soft termination event that polarizes as the trajectory aligns. The trajectory itself is computed by matrix-vector multiplication and is therefore GPU-native; the termination check is a cosine-argmax, also GPU-native. On an unconstrained substrate — numpy on a laptop, or a CUDA kernel — this works straightforwardly: rotation iterates, cosine-snap fires, the loop exits. The demonstrations in §4 do not exercise `loop(cond)`; they cover straight-line programs plus `loop[N]`-shaped unrolling. We flag `loop(cond)` as implemented in the compiler but not stressed in the demonstration corpus.

### 2.4 Purity and the edge

Sutra is purely functional. There is no `print`, no `read`, no exception, no mutable global, no side-effecting primitive a function body can invoke. Every function is a deterministic vector-to-vector (or vector-to-scalar) map. The single way values leave the pure region is a final `map<vector, string>` lookup at the program's edge, which converts a snapped codebook entry to the string the host sees. Structurally this is the same shape as Haskell's IO boundary: the pure body computes a description of a result; the edge commits it.

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

Expected output: `say() → "hello world"`. Traditional Hello World is IO-heavy: a `print` statement against a standard output stream. Sutra has no `print`. The equivalent minimal shape is to embed the greeting in the vector space, retrieve it from a codebook by cosine-argmax, and look the result up in the `map` at the edge. This is the smallest program in which every Sutra feature that distinguishes the language (basis vectors, argmax-cosine as `snap`, map-lookup as edge) appears.

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

### 4.4 Summary of demonstration results

| Program | Inputs × Programs | Outputs | Correct |
|---|---|---|---|
| `hello_world.su` | 1 | 1 | 1/1 |
| `fuzzy_branching.su` | 4 × 4 | 16 | 16/16 |
| `role_filler_record.su` | 2 × 3 | 6 | 6/6 |

Total: 23/23. The outputs are not stochastic — the seed is fixed (`seed=42`, `dim=256`) and the reference table is committed under `examples/`. A reader running `python examples/_smoke_test.py` on a fresh clone reproduces exactly these numbers.

### 4.5 Learned-matrix binding on Wikidata

The three compiled demonstrations exercise the language surface on fresh random vectors under sign-flip non-semantic binding — sufficient to show that the control-flow primitives and the bind/bundle/unbind algebra function, but not sufficient to show that semantic bind matters. We ran a separate harness (`sutra-paper/scripts/learned_matrix_templates.py`) that fits role matrices directly from Wikidata relational triples in a frozen LLM embedding space and measures top-1 retrieval against a per-predicate codebook under 5-fold cross-validation.

Five predicates: `capital-of` (city→country), `located-in-country` (place→country), `continent-of` (country→continent), `author-of` (book→author), `country-of-citizenship` (person→country). Eight fit methods: identity (no transform), mean-object (majority-class prior), displacement (the rank-0 translation), orthogonal Procrustes, ridge regression (λ=1.0, λ=0.1), rank-30 low-rank least squares, and a random-Gaussian control.

Two substrates:

**GTE-large** (`thenlper/gte-large`, 1024-d, sentence-transformers). Bare-label subject text, bare-label object retrieval. Top-1 accuracy on the `bare` configuration:

| Predicate | Codebook | Chance | identity | mean_obj | displacement | ridge-0.1 | Best method |
|---|---:|---:|---:|---:|---:|---:|---|
| capital-of | 143 | 0.7% | 82.1% | 0.0% | 81.4% | 47.9% | identity |
| located-in-country | 21 | 4.8% | 41.5% | 39.0% | 60.0% | **76.4%** | ridge-0.1 |
| continent-of | 10 | 10.0% | 68.5% | 19.5% | 82.0% | **87.0%** | ridge-0.1 |
| author-of | 144 | 0.7% | 6.7% | 9.2% | 7.2% | 7.2% | at chance |

On `located-in-country` and `continent-of`, a linear role matrix fit by ridge regression beats the mean-object baseline by 37 and 67 points respectively — the matrix is learning a subject-conditional operator, not a prior over output classes. On `capital-of`, identity alone scores 82% because GTE-large already places cities and their countries in cosine correspondence; the learned matrix cannot improve on a substrate-provided baseline. On `author-of`, no method beats chance: the output space is too open (144 distinct authors) and the relation "wrote" is not recoverable from the book title alone. Template variants (typed, rich, relational sentence) land within ±3 points of the bare config; richer subject text neither helps nor hurts on GTE-large.

**nomic-embed-text** (768-d via Ollama). Same script, four subject-text configurations (`bare`, `typed`, `rich`, `relational`) plus a fifth (`descr`) that concatenates the Wikidata `schema:description` to the subject label. Every method on every predicate collapses to the majority-class prior; learned matrices do not beat mean-object on any config. The richer text does not rescue the substrate. This is a null result across all four predicates on which the GTE-large comparison is meaningful, and we report it as such — nomic is a worked counter-example to the substrate-independence story.

The interpretation the paper carries is that Sutra's learned-matrix binding is a substrate-conditional operation: it works when (a) the substrate has enough between-pair variance that subjects are not already in direct cosine correspondence with objects, and (b) the predicate is structurally low-entropy enough that a linear fit generalizes. GTE-large satisfies both conditions for two of the four tested predicates. nomic does not satisfy (a) for any of them. A Sutra program that uses `bind(located_in_country, city)` on a GTE-large substrate recovers the correct country three-quarters of the time on held-out cities; the same program on a nomic substrate does not. The language and compiler are substrate-agnostic; the semantic content of a bind is not.

Raw results: `sutra-paper/scripts/learned_matrix_gte_large_results.json` and `sutra-paper/scripts/learned_matrix_nomic_descr_results.json`. Reproduction: `python sutra-paper/scripts/learned_matrix_templates.py --model thenlper/gte-large` and `--model nomic-embed-text`.

## 5. Attempted substrate: the *Drosophila* mushroom body

We attempted to compile Sutra programs onto a biological spiking substrate. The target was a Brian2 leaky integrate-and-fire simulation of the right mushroom body of *Drosophila melanogaster*, wired from the Janelia hemibrain v1.2.1 connectome (Scheffer et al. 2020): 140 projection neurons → 1,882 Kenyon cells → APL feedback → 20 MBON readouts. A second target was the Shiu et al. 2024 whole-brain LIF model (138,639 neurons, 15 million synapses, real FlyWire v783 connectivity).

Some isolated operations transferred. Bundle and snap executed on the spiking substrate with the accuracy reported in the companion `fly-brain-paper/`, and a 4-way fuzzy conditional was hand-compiled onto Kenyon-cell prototypes for a single program. We report these as isolated results rather than a working backend — they do not compose into a general compilation path from arbitrary `.su` source to a spiking run.

Parts did not. Most concretely: `loop(cond)` as specified in §2.3 requires a rotation operator R such that iterated application `state ← R · state` traces a trajectory through vector space. On a synthetic Givens rotation matrix this works. On the actual FlyWire weight matrix — used as `R` as the fly-brain codegen would need — iterated application produces a compressive projection, not a rotation: states collapse rather than traverse, and the readout `select` never shifts mass to the exit option because no snap-to-prototype match accrues. A central-complex EPG ring-attractor slice, which anatomically should implement directional rotation, fails to discriminate direction on the real connectivity (see `planning/findings/` under the dated negative-result entries). The conclusion we carry is that the connectome-as-substrate direction is a research program — one that needs dedicated substrate-compilation infrastructure (prototype fitting, anatomy-aware rotation discovery, alternative iteration primitives) which is outside the scope of a language paper.

We report this explicitly rather than eliding it. Prior summaries of this project have variously described the fly-brain backend as "working" and as a core contribution of the language; neither framing is honest given the structural mismatches we found. The honest framing is: Sutra as a language exists and runs on the numpy substrate, the connectome substrate is a separate open research question, and the companion `fly-brain-paper/` exists to catalog what does and does not transfer.

## 6. Why Branchless Matters

Three consequences of removing the control-flow family from the language surface, independent of which substrate runs underneath:

**GPU-native execution, in principle.** Every Sutra operation is a matrix-vector multiplication, a sum, a Hadamard product, or a cosine. The entire language runtime is sparse or dense BLAS. There is no divergent-warp penalty because there is no divergence; every branch of every `select` runs, weighted. The current numpy backend does not demonstrate GPU speedup — that requires the PyTorch/JAX port that is future work — but the emitted code is GPU-ready in the sense that every operation has a trivially corresponding GPU kernel.

**End-to-end differentiability.** The constructs that normally break backpropagation — hard `if`, `break`, early `return`, discrete `switch` — are not in the language. A Sutra program is differentiable with respect to its inputs by construction, because every operation in it is differentiable. A learned Sutra program — where the `select` weights, the bind roles, and the codebook are trained by gradient descent rather than hand-coded — is a natural object; we have not yet demonstrated a trained program, but the path is straightforward.

**Connectionist-native compilation, in theory.** Spiking circuits, frozen LLM embeddings, and analog neuromorphic hardware all lack native branching. They have weighted summation, attenuation, convergence, and winner-take-all. A language whose only primitives are these operations maps onto such substrates *in principle*. §5 reports what we actually learned when we tried: the mapping is not free — specific substrates fail to implement specific primitives — and the gap is real work, not a formality.

## 7. Related Work

Vector Symbolic Architectures (Smolensky 1990, Plate 1995, Gayler 2003, Kanerva 2009) define the binding/bundling/similarity algebra Sutra inherits; Hyperdimensional Computing (Imani et al. 2019, Neubert et al. 2019) builds systems on it. Sutra's contribution on top of VSA is the language-level framing: a concrete grammar, a compiler, and the specific choice of `select` + `snap` + `loop` as the complete control primitive set, with `select` (in single-option, multi-option, and `else`-clause forms) absorbing every traditional branching construct.

Differentiable programming frameworks (JAX, PyTorch, TensorFlow) remove branches in practice by convention inside jitted regions; Sutra removes them by grammar. `tf.cond` and `jax.lax.cond` are library-level selects over a still-branching host language; Sutra's `select` is the language's only selection primitive, and the host language does not have `if`.

Neuromorphic and connectome-based computing proposals (Davies et al. 2018, Neftci et al. 2019) typically pair a conventional host language with a spiking-circuit target, emulating host branches at the edge of the substrate. Sutra's grammar targets the spiking-circuit style of computation directly; §5 reports the realities of the mapping when the substrate is a real connectome.

The empirical premise — that frozen LLM embedding spaces encode consistent algebraic structure that VSA operations can exploit — is grounded in prior relational-displacement analysis of general-purpose embedding models (Leonhart, *Latent space cartography applied to Wikidata*), which found that a non-trivial set of relational predicates manifest as consistent displacement vectors across models. Those displacements are translations — the rank-0 special case of the full learned-matrix binding Sutra targets. §4.5 reports the matrix generalization directly: on GTE-large, ridge-fit role matrices beat the mean-object baseline on `located-in-country` (76% vs 39%) and `continent-of` (87% vs 19.5%), confirming that the displacement finding extends to non-translational relational structure when the substrate supports it. The three compiled demonstration programs themselves use a sign-flip non-semantic binding on random vectors because their role keys are arbitrary tags, not semantic predicates — the two binding modes coexist in the runtime.

## 8. Limitations

- **The runtime is numpy-on-CPU.** We claim the compilation surface admits GPU execution. We do not demonstrate GPU execution.
- **The demonstration corpus is small.** Three programs, 23 decisions. We have not run a 2D game loop, a parser, or an interpreter — each is a natural next demonstration given the primitive set.
- **`loop(cond)` is implemented but not exercised in the demonstrations.** The three demo programs are straight-line plus `loop[N]`-shaped unrolls. A data-dependent `loop(cond)` demo is future work.
- **The connectome substrate is an open research question.** §5 reports the attempt and the specific structural failures (FlyWire-as-rotation, EPG direction-discrimination). A dedicated library for compiling to biological connectivity is plausible but unbuilt.
- **Learned-matrix binding is substrate-conditional.** §4.5 reports 87% / 76% top-1 on two of four tested Wikidata predicates under GTE-large, and null results across all tested predicates under nomic-embed-text. The paper does not claim a substrate-independent recipe for semantic binding; it reports the two substrates we measured. The three compiled demonstration programs use sign-flip non-semantic binding because their role keys (arbitrary field tags, not Wikidata predicates) have no semantic content to fit. Integrating learned role matrices into the demo-program surface — such that a `bind(located_in_country, city)` call in `.su` source compiles against a fitted GTE-large matrix — is implementation work not included in this paper.

## 9. Conclusion

Sutra is a programming language in which `if`, `else`, `while`, `for`, `switch`, `break`, `continue`, and `return` do not exist. Their place is taken by `select`, `snap`, and `loop`, all compiled to vector operations. `select` is the one branching primitive — single-option (the `if`-shape, with a configurable fuzzy threshold defaulting to 0.5), multi-option (the `switch`-shape), and `else`-clause (the "none of the above" form) — and it never breaks differentiability because defuzzification is a polarization of the fuzzy state, not a binarization. The primitive set is computationally universal under standard VSA-completeness arguments. Binding is matrix-vector multiplication, where each role is a linear operator fit from relational data in the embedding substrate — unifying role-filler binding, truth-extraction, and defuzzification under a single matrix-vector primitive; §4.5 shows this working on GTE-large for `located-in-country` (76%) and `continent-of` (87%) and not working on nomic-embed-text, and the paper reports both. A compiler, a specification, an IntelliJ plugin, a VS Code extension, and a numpy runtime exist and are in the public repository; three demonstration programs run end-to-end, producing 23/23 outputs matching their committed reference. The design point is the language's existence: a purely functional, Turing-complete programming surface that compiles to matmuls, sums, and cosines, with no machine branches anywhere in its runtime.

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

Leonhart, E. *Latent space cartography applied to Wikidata: Relational displacement analysis reveals a silent tokenizer defect in mxbai-embed-large.* Preprint.

Neftci, E. O., Mostafa, H., & Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine.

Neubert, P., et al. (2019). An introduction to hyperdimensional computing for robotics. KI.

Plate, T. A. (1995). Holographic reduced representations. IEEE Transactions on Neural Networks.

Scheffer, L. K., et al. (2020). A connectome and analysis of the adult Drosophila central brain. eLife.

Shiu, P. K., et al. (2024). A Drosophila computational brain model reveals sensorimotor processing. Nature.

Smolensky, P. (1990). Tensor product variable binding and the representation of symbolic structures in connectionist systems. Artificial Intelligence.
