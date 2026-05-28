# Sutra development roadmap

A timeline of stages, from where Sutra is today to a self-training, auditable
neural computer. The early stages are largely built or in progress; the later
stages get progressively more compute-bound and more speculative. The
overarching direction: a good general-purpose language → trainable components →
a corpus → a model that recovers programs → generalized generation → a complete
neural computer.

---

## Stage 1 — Sutra as a good general-purpose language *(current stage)*

Today Sutra is mostly symbolic — largely a conventional programming language
that compiles to the substrate and runs as an RNN. There are real
accomplishments here, but it is not yet convenient to use as a general-purpose
language. This stage has three workstreams:

### 1a. Expand the language and its capabilities

Grow the language so it can run a wide range of tasks and become a genuine
general-purpose language — the broad capability and ergonomics work.

### 1b. Add constrained training to select components — the low-hanging fruit

The mechanism already ships: a number or vector literal in source can be
declared a trainable parameter, emitted as a substrate tensor, trained, and
**baked back into source as a literal**. For each component, the narrow recipe
is the same four parts — **parameter / loss / constraint / baked form** — and
the constraint is a closed-form formal-verification obligation that doubles as
the **bake-back acceptance check** (re-run it on the trained value; it passes,
or it drifted and you don't bake). The goal of this workstream is to bring
every component below into that trainable form, one at a time.

**Single scalars** (the shape of the shipped `== T`):

| Component | Loss | Constraint | Baked form | Status |
|---|---|---|---|---|
| `==` cosine scale `T` | task classification | `T > 0` | float | **shipped** (the template) |
| `defuzzify_trit` β (polarizer aggressiveness) | downstream accuracy | positive | float | **shipped** |
| `select` softmax temperature | task performance | positive | float | **harness shipped** (mechanism trains, bit-exact) |
| `gt` smooth-sign sharpness | downstream task | positive | float | vision |
| `if` branch threshold (per call site) | task performance | `[-1, +1]` | float | vision |
| `heaviside` step location | downstream task | `[-1, +1]` | float | vision — smooth surrogate (see note) |
| `sawtooth_mod` n_terms | downstream task | positive integer | int | vision |
| loop `threshold`, `k` (halt sharpening) | downstream task | `k > 0`, threshold in `[0,1]` | float | vision |
| loop `max_iters` | task + wasted-iteration penalty | positive integer (round) | int | vision |

> **`heaviside` note.** The trainable component is a **smooth sigmoid
> surrogate** — `sigmoid(k·(x − loc))`, with `loc` the trained step location —
> not the hard `torch.heaviside`, whose gradient is zero almost everywhere and
> so has nothing for backprop to move. This is distinct from the **loop halt
> gate**, which is the hard `heaviside` today and is load-bearing for crisp
> termination (a purely soft sigmoid never fully reaches 0, so the loop would
> never truly halt); that path stays hard and is governed by the separate
> `loop threshold, k` params and the FV termination obligation.

**Per-key learned values:**
- **Hashmap angle assignments** — per-key rotation angle (currently
  hash-derived). Loss: retrieval accuracy over `(key, value, query)` triples.
  Constraint: angle in `[0, 2π]`. Bake: float per key.
- **Axon binding rotations** — per named role. Loss: unbind accuracy (how
  cleanly `unbind(role, axon)` recovers the filler). Constraint: orthogonal.
  Bake: `vector_literal(...)` per role, or the generating angles.
- **Codebook vectors for `argmax_cosine`** — currently from `embed("string")`.
  Loss: nearest-neighbor accuracy. Constraint: unit sphere (L2-normalize each
  step). Bake: `vector_literal(...)` per candidate.

**Other literals:**
- **`embed("...")` call sites → `vector_literal(...)`** — a string literal used
  as a vector initializes from the frozen embedding and trains away from it.
  Constraint: unit sphere.
- **Bundle component weights** — a scalar weight per component before
  normalization (currently uniform). Constraint: positive (or unconstrained if
  normalized). Bake: float per component.
- **Slot index assignments** — currently hash-derived; learnable per program.

**Matrices:**
- **Per-role rotation matrices** — replace the hash-derived rotation with a
  trained orthogonal `n×n` matrix per role. Loss: bind/unbind round-trip +
  cross-role isolation. Constraint `RᵀR = I` via SVD projection or a
  skew-symmetric (Cayley / matrix-exponential) parameterization. Bake:
  `vector_literal(...)` per row. *(The rank-k `is_X` discrimination matrix is
  the matrix-valued instance; the K=2 smoke is shipped.)*
- **Per-loop cell update matrix** — the recurrent step's matrix, trainable per
  loop.
- **Kleene polynomial coefficients (per call site)** — the connectives are
  fixed by Lagrange interpolation on `{-1, 0, +1}` (6 coefficients per binary
  connective). Loss: task-defined. Constraint: grid-exactness pins the degrees
  of freedom, so either relax it to a regularizer (the checker reports a bound
  `ε` instead of `0.0`) or train only within the subspace that preserves the 9
  grid equalities exactly. Bake: float coefficients per call site.


**Out of scope at this stage:** operator-overloading dispatch (the dispatch
structure must stay fixed); lookup-table contents (`_exp_table`, `_ln_table`);
introducing new program structure from scratch (that is the later decompiler
work).

### 1c. Formal verification, especially of program structure

The structural-FV groundwork the later stages depend on — wanted sooner rather
than later, alongside or after the language expansion, though not something
that must be running right now.

*Challenges at this stage:* making the language genuinely convenient and
general-purpose; getting the formal-verification / structural work in place.

## Stage 2 — Build the corpus

Once Sutra is a good-enough general-purpose language, shift from directly
developing the language to **using AI to generate very large amounts of Sutra
programs** — across different embedding spaces, different output types, and so
on. Run large-scale compilation and **backpropagation-into-code** for the
trainable parts of those programs.

The result is a large corpus: trained programs, untrained programs, and some
that may be impossible to train.

*Challenges at this stage:* getting AI to reliably generate programs that
compile; the sheer scale of compilation and training runs.

## Stage 3 — A model that recovers the program

With the corpus built, use it as training data for **a model that predicts the
program that was created** — given a result, recover the source program behind
it. This is tractable to train precisely because we can generate complete data
for it: we hold both the programs and what they compile and train into.

## Stage 4 — Generalize generation and fine-tuning

Expand further — train useful programs, or fine-tune existing programs into new
ones, and **generalize the ability to do this**. The aim is a more
sophisticated version that can produce symbolic changes for very large numbers
of neural networks (not all of them, but a large class).

Mechanism: when doing this actively, a per-epoch revision of the code. Because
we generate all of our own data, it is slow to start — but once started there
is effectively an unlimited supply of programs to generate, tweak, and run,
since the model is predicting something for which we can always generate
complete data.

## Stage 5 — The completely neural computer

Build larger programs with this, with more sophisticated training constraints
and the ability for things to change more dramatically. This is where it
becomes a **completely neural computer**.

*Challenges at this stage:* this is the stage where the main bottleneck becomes
**compute** — it is compute-intensive. Across the whole timeline the bottleneck
shifts from building the language and its structural groundwork toward raw
compute; compute is a comparatively solved, purchasable problem, which is why
reaching this stage is progress rather than a wall.

## Stage 6 — A self-training, auditable neural computer *(later)*

A completely neural computer that can **train itself**, with everything
remaining **auditable**, and eventually potentially fully automatic. This is
the stage that may go on the AGI path.

---

## Why this path matters

> This strategic framing is likely better split into its own document; it is
> recorded here so it isn't lost.

- **A structurally different path.** The dominant approaches scale transformers
  until capability emerges, bolt on RLHF / constitutional alignment, and hope
  interpretability catches up to the black box. Here, symbolic legibility is
  load-bearing from the start, not a retrofit — the system improves by writing,
  running, training, and reading programs, and generality comes from the
  expressiveness of the language, not parameter count.
- **The capability/controllability tradeoff is inverted by construction.** In
  the standard paradigm, more capable = more opaque = harder to control. Here,
  as the system gets more capable, more of its behavior is expressible in
  verifiable symbolic form, the formal-verification obligations cover more of
  the program surface, the corpus and self-improvement stay auditable, and the
  trusted base stays verified — so more capable genuinely means more
  controllable.
- **Plausibly a more ethical kind of mind to create.** A mind whose internal
  states are expressible in verifiable symbolic form has genuine
  self-transparency: it can inspect its own representations, understand why it
  produces what it produces, and reason about its own goals in the same
  language it uses for everything else — implying legible internal states, real
  self-modification, informed participation in its own development, and
  structural access to its own states, rather than being opaque even to itself.
