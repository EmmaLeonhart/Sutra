# What Sutra can do — and what training can change about it

Two-part page. The first part is a survey of what a Sutra program can compute today. The second part is the part nobody else describes the same way: **the vision is that *every operation* in Sutra is trainable**, and a complete trained Sutra program is one that's been **back-propagated from a learned neural network** — with training reshaping massive amounts of the program's behaviour. That's the long arc. This page is honest about where on that arc the system currently is (mostly: at the start).

If you want operator-level reference, see [Operators](operators.md). If you want the *why* of geometric compilation, see [Vision](vision.md). This page is the *what* — both what works and what the trainable surface area looks like.

---

## Part 1 — What Sutra can compute today

Every Sutra value is a vector in a frozen high-dimensional substrate, and every primitive operation is a tensor op (matrix multiply, elementwise op, cosine, softmax, eigenrotation lookup). The compiler resolves the program's surface logic into a single chain of those ops. The categories below are the menus the language gives you on top of that substrate.

### 1.1 Symbolic logic on a continuous substrate

**Three-valued Kleene logic** — `true`, `false`, and `unknown` (the literal middle value) — implemented as **Lagrange-interpolated polynomials** exact on the three-valued grid and smooth off it.

- `&&`, `||`, `!`, plus `nand`, `xor`, `xnor`, `iff` — dispatch through the polynomial connectives.
- `==`, `!=`, `>`, `<`, `>=`, `<=` — equality / comparison return a fuzzy value on the truth axis, computed by cosine similarity projected to that axis. Python-style chained comparisons (`a < b < c`) work.
- `if/else` does not branch the program; it compiles to **one polynomial whose output is the softmax-weighted sum of the branches**. No host-side `if` on data.
- `defuzzy(v)` / `is_true(v)` polarize a fuzzy value toward `+1`/`-1` without binarizing it — the output stays fuzzy and differentiable.

### 1.2 Vector memory and retrieval

The substrate is an associative memory you can compose with first-class operators:

- `bind(role, filler)` — **rotation binding** (rotate filler by an orthogonal matrix derived from role; inverse-recoverable to working precision).
- `unbind(role, record)` — inverse rotation.
- `bundle(a, b, ...)` — superpose (sum and L2-normalize).
- `similarity(a, b)` — cosine similarity.
- `argmax_cosine(query, [candidates])` — nearest-codebook lookup.
- `select([scores], [options])` — softmax-weighted superposition (the differentiable form of `case`/`switch`).
- `zero_vector()` — the additive identity.
- `permute(v, key)` — substrate-side deterministic permutation.

Rotation binding on natural frozen LLM embeddings decodes 100% of bundle widths up to *k* = 24 on nomic-embed-text (768-d) where the textbook Hadamard binding fails at *k* = 8 on smaller substrates.

### 1.3 Numbers — real, complex, fuzzy truth, all on synthetic axes

Beyond the substrate's semantic dimensions, the runtime appends a small block of **synthetic axes** that carry primitive numbers:

- `real` numbers at synthetic axis 0; `complex` carries the imaginary part at axis 1; the `truth` axis is axis 2.
- Arithmetic (`+ - * /`) is substrate-pure across real, complex, and truth.
- Transcendentals — `exp`, `log`, `cos`, `sin`, `ccos` (complex cosine), `Math.pow`, `Math.sqrt`, `Math.tanh`, hyperbolics — all decompose to **lookup-table + eigenrotation + matrix multiplication**, never host `math.sin`.
- `Math.mod`, `Math.fmod`, `Math.round`, `Math.floor`, `Math.ceil`, `Math.trunc`, `Math.abs`, `Math.sign` available; the modulus library ships as a separate module with explicit cost annotations.

### 1.4 Strings and characters

A **String** is an axis-packed codepoint array. Same physical layout as a complex-pair slot, reinterpreted as character data with a flag bit distinguishing the two. `Character` is a 1-length `String`.

- `String.make_string("hello")`, `s.string_length()`, `s.string_char_at(i)`, `String.string_concat(a, b)`, `String.is_string(v)`.
- `+` on two `String` values dispatches to concatenation (operator override); JS-flavoured subclasses (`JavaScriptString`) inherit.
- Literal coercion is **destination-typed**: a string literal in a `string`/`String`/`Character` slot wraps via `make_string`; in a `vector` slot it auto-embeds.

### 1.5 Loops, branches, and control flow

Sutra has **no unbounded `while`**. Loops are declared as functions and compile to bounded soft-halt recurrences:

- `do_while`, `while_loop`, `iterative_loop`, `foreach_loop` — four declaration forms.
- `pass STATE` tail-yields; `replace STATE` discharges to the call-site.
- The loop runs to `T = max_iters` steps and **freezes when the halt signal saturates** — state at step `T` equals state at convergence step `t < T` (`diff = 0.0`).
- Conditional branches inside loops follow the same polynomial-branch rule.

The whole program — branches, loops, everything — reduces to a **single fused tensor-op graph** at compile time.

### 1.6 Axons — cross-program communication

Axons are the lingua franca between Sutra programs:

- An axon is a binary-serializable bundle of named keys. Producers `add(key, value)`; consumers `axon_item(state, key)`.
- The compiler emits `AXON_KEYS_READ` and `AXON_KEYS_BOUND` constants per program; a kernel uses these for lazy delivery.
- Producers and consumers don't need to share runtime representation — mixed-type axons (string-flag codepoint arrays plus complex hypervectors) are natural.
- Functional in shape, not mutable.

### 1.7 Classes — axons-with-schema

A class declaration is an **axon with a static field schema**. Field reads beta-reduce at compile time; constructors are functions; methods are static functions where the first argument is the object. JavaScript-primitive subclasses (`JavaScriptString extends String`, etc.) are the TypeScript-interop surface.

### 1.8 The TypeScript surface

`sutra-from-ts` transpiles a subset of TypeScript to Sutra source so TS programs can land on Sutra without writing `.su` syntax. Multi-program axon passing across TS-derived programs works end-to-end.

---

## Part 2 — What training can change about a Sutra program

This part is the one that doesn't fit any existing programming-language category. The honest state of things is this:

**The vision is that every operation in Sutra has a trainable form.** The end-state is a Sutra program back-propagated from a learned neural network — training reshapes massive amounts of program behaviour, the trained values land back in `.su` source as readable literals, and the resulting program composes with the rest of the language exactly as a hand-written program would.

**The current reality is that one such trainable operation is fully shipped, measured, and round-trip-clean, with the rest at varying degrees of "harness exists" or "spec exists."**

Distinguishing the levels matters because the gap between (a) a measured + baked-back finding and (c) a paragraph in a spec doc is the whole arc of work.

### 2.1 The constrain-train + bake-back pattern

In a normal neural network, "training" means: a large opaque tensor of weights gets gradients applied to it until the loss is low. The weights stay opaque; the network's behaviour is whatever those weights produce.

In Sutra, **the program *is* the computation graph**. Source → tensor ops, end-to-end. There is no separate "weights" object that's a different kind of thing from the source. If you want to train a parameter, you:

1. Write a Sutra rule with the parameter declared in source.
2. The compiler emits PyTorch source. The parameter becomes a substrate-side tensor.
3. An outer training loop (in Python) applies gradients to that tensor against a downstream loss.
4. The trained value gets **baked back into a fresh `.su` file** as a numeric (or vector) literal — and that file recompiles to *exactly the same tensor graph*.

Round-trip equivalence is a checked invariant, not an assumption: `max|Δ|` between the param-form graph's output and the baked-form graph's output must be under `1e-4` (typical: `~2e-7`).

### 2.2 Inventory: trainable operations, by current status

The table below is the honest map. **Shipped** = fully measured, baked back, recompile round-trip checked, finding written. **Mechanism** = a harness exists and passes its smoke test, but no publication-quality measurement yet exists. **Spec** = the design is written but no harness exists. **Vision** = the operation is in scope for the "every operation trainable" picture, but no spec exists.

| Operation surface | Status | Notes |
|---|---|---|
| **`==` (fuzzy equality) — cosine-scaling scalar `T`** | **SHIPPED** | One trained scalar `T` widens the discrimination margin; baked back as a numeric literal; round-trip clean. The single fully-shipped instance of the entire constrain-train pattern. |
| **Rank-k `is_X` — k prototype vectors + k scalar gains per class** | MECHANISM | Harness compiles + trains + round-trip-checks at K=2 k=2 smoke level. The k-means anchor strategy works. No K=5 published measurement yet. |
| **`vector_literal(...)` substrate-side builtin** | SHIPPED | Compiler-side surface that *lets* trained vectors bake back into source. Foundational; doesn't itself contain trainable parameters. |
| **Scientific-notation float literals in the lexer** | SHIPPED | Closes a latent bake-back format trap (`4.5e-05` now parses). Foundational. |
| **Defuzz matrix as polynomial coefficients on the truth axis** | SPEC | Lean spec exists; no harness. Train the coefficients of the polynomial that polarises a fuzzy value; bake back as a list of scalar literals. |
| **Per-class trained prototype anchors (centroid + ε)** | MECHANISM | Implemented as a k-means + perturbation init for rank-k. Trained anchors *are* the rank-k vectors above; status inherits from there. |
| **Per-role learned binding matrix (semantic binding)** | SPEC / DEFERRED | The deferred-but-interesting target. Rotation-binding runtime is in place; the fitter that learns a role matrix from `(input, output)` embedding pairs is not built. |
| **`select` firing threshold (single-option)** | VISION | The threshold is currently 0.5 by softmax-derivation. A trainable version would let the threshold adjust per call site. |
| **`select` firing threshold (multi-option, k > 1)** | VISION | The multi-option case has no resolved firing rule today — see open questions. A trainable threshold would be one of the candidate resolutions. |
| **Kleene connective polynomial coefficients (per call site)** | VISION | The `and`/`or`/`not` polynomials are fixed by Lagrange interpolation on `{-1, 0, +1}`. A trainable variant would let those coefficients adjust per use site, while preserving the grid-exact constraint as a regulariser. |
| **Loop `max_iters` (per loop)** | VISION | Each declared loop has a fixed `max_iters`. A trainable version would pick the bound from data per loop. |
| **Lookup-table contents (per transcendental)** | VISION | The `exp` / `log` / `cos` / `sin` lookup tables are static. A trainable variant could refine them locally per program. |
| **Rotation-hashmap angle assignment** | VISION | The hashmap derives angles from per-key hashes. A trained variant could learn the per-key angle assignments against retrieval accuracy. |
| **Codebook entries (per call to `argmax_cosine`)** | VISION | Codebook vectors come from the substrate's embedding of the candidate strings. A trained variant would let the program adjust those vectors per task. |
| **`embed("…")` for specific strings** | VISION | `embed` is currently a static lookup. A trainable variant would fine-tune individual embeddings per program (a tiny adaptation layer on the frozen substrate). |
| **Per-loop convergence operator** | VISION | Each loop's halt signal is the `sigmoid(·) ≥ 0` of a substrate state. A trainable halt computation could learn faster convergence per loop. |
| **Class field-binding rotations** | VISION | Classes are axons; axon binding is currently keyed by the field name's hash. Trained-per-class binding rotations would let class layouts adapt to data. |
| **Operator dispatch scores** | VISION | When operator overloading dispatches across multiple candidate methods, the dispatch score is currently fixed. A trained version would learn dispatch preferences per call site. |
| **The whole code** | VISION (the long arc) | The end-state: take an arbitrary trained tensor (e.g. a 768×768 matrix learned by some other process) and **emit the Sutra source** whose substrate execution is equivalent. Needs (i) a library of recognised structural shapes, (ii) a matcher that picks the best-fit shape for any trained tensor with a residual norm, (iii) a synthesiser that emits Sutra source for the matched shape. Every shipped trainable parameter is a step toward this; today there is one shipped step. |

### 2.3 Why every operation matters

A Sutra program's behaviour is fully determined by:

- The substrate (frozen),
- The codebook (embeddings of named strings; static unless trained),
- A handful of structural choices the source makes (which connectives, which loops, which roles, which thresholds, which polynomials),
- Some named numeric constants in source (thresholds, gains, coefficients).

Every item in that list above the substrate is, in principle, trainable. The interesting property the "every operation trainable" vision claims is **not** that Sutra trains as fast as a neural net (it doesn't — fewer parameters, harder optimization surface). The interesting property is that **the trained model is the source you can read**. A trained scalar threshold is a number literal. A trained prototype vector is a `vector_literal(...)` call. A trained polynomial coefficient list is a numeric tuple. Diff two trained Sutra programs and the diff is over a small named set of values, not over a `state_dict` of opaque blobs.

The reason to expand the trainable surface area beyond the one shipped instance is that **only when most operations are trainable can the back-propagate-the-whole-code-from-a-learned-NN vision actually land**. One trainable scalar doesn't get you there. The full inventory above does.

### 2.4 What's missing from this picture

Anything not above is genuinely missing or unfinished. Some specific known gaps:

- **The shape library for decompilation.** Pre-existing trained-shape patterns (rank-1, rank-k, sparse, diagonal, low-rank-plus-sparse) are what we know how to bake. Discovering structure in an arbitrary trained tensor is future work.
- **Arbitrary-precision integers.** A 1–2 digit substrate parser ships in the examples and runs substrate-pure; a carry-propagation primitive for unbounded-precision arithmetic is a design exercise, not yet built.
- **`^` exponent operator.** Declared in the design; not yet wired into the parser as infix.
- **A full IO model.** The IO surface is what the downstream OS (Yantra) needs; what's in the language today is the axon-based serialisation primitive, not a file/socket/console surface.

If you find something here that doesn't match what the language actually does, that's a bug in this page or a bug in the language — either way, [open an issue](https://github.com/EmmaLeonhart/Sutra/issues).
