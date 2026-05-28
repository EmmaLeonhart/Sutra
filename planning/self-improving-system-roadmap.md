# Sutra as a long-term, legibly self-improving system — roadmap

> **Status: planning / agenda.** This is a concrete roadmap, not an
> exploratory sketch. It was reformatted on 2026-05-28 from a 2026-05-27
> design conversation between **Emma** (Sutra's designer) and the **agent**
> (Claude). It previously lived at
> `planning/exploratory/2026-05-27-sutra-vision-conversation.md`; the
> verbatim chat log remains in git history at that path.
>
> **Speaker convention.** The design calls in this document are **Emma's**
> — she has ground truth on Sutra's mechanisms. Where a framing originated
> as the agent's restatement, it has been folded into the structure and
> kept only where it sharpens Emma's point; load-bearing scope calls are
> tagged **(Emma)**. When in doubt, the authoritative design intent is
> Emma's, per CLAUDE.md §"When Emma gives an algorithmic explanation,
> IMPLEMENT it."
>
> **One-line thesis.** Sutra already compiles programs into trainable
> tensor-op graphs. The plan: make as much of every program trainable as
> possible, use the resulting corpus to train a *formally-verified learned
> decompiler* that turns trained tensors back into idiomatic Sutra source,
> and thereby bootstrap a self-improving AI whose improvements are
> human-legible by construction.

---

## 0. Where we are now (the starting point)

- **Sutra is a complete programming language.** Every operation — logic,
  binding, loops, arithmetic, dispatch — already compiles to a tensor-op
  graph. Because the graph is tensor algebra, every operation is *in
  principle differentiable*.
- **The formal-verification (FV) framework exists.** The FV paper shows
  the non-learned trusted base is verifiable algebraically: branches become
  Kleene polynomials, loops become bounded recurrences, and the whole thing
  is checkable in closed form without path enumeration. It handles the
  trusted base precisely *because* the learned parts are quarantined.
- **The capabilities inventory is the real map.** The exhaustive page at
  `sutra.emmaleonhart.com/capabilities/` lists every keyword, operator,
  primitive, runtime method, and stdlib class, each annotated with its
  training status. Many operations are marked **VISION**: they exist and
  work, but nobody has yet defined *what the trainable parameter is, what
  the loss is, or what constraints keep it valid*. **(Emma)** The point of
  this roadmap is to fill those gaps, operation by operation.

> The gap, stated plainly: the FV story currently describes the *static*
> compiled graph. If training is going to reshape programs, verification
> eventually has to follow the trained values — constraints that survive
> training, not just constraints on the static graph.

---

## 1. The shipped mechanism: literals as trained values

Sutra already has the end-to-end mechanism for one trainable surface:

1. A rule declares the parameter in source.
2. The compiler emits PyTorch; the parameter becomes a substrate-side tensor.
3. Gradients are applied (training).
4. The trained value is **baked back** into a fresh `.su` file as a numeric
   or vector literal.

**The shipped instance is the `==` cosine-scale scalar `T`** — a number
literal in source that came from training.

**(Emma)** So the answer to "what is a bake-back candidate?" is: *any number
literal or vector literal in Sutra source.* The language already has the
mechanism. The VISION items are simply the places where such a literal does
not exist yet because no one has decided what value it should hold and how to
train it.

---

## 2. Scope — what is trainable now vs. later

### In scope: train parameters that already exist in compiled programs

**(Emma confirmed the following as in-scope.)** For each, the surface form
is just how the parameter is *initialized*; training moves it, and it bakes
back as a float or `vector_literal(...)`:

- **Single scalars** — temperatures, thresholds, sharpness/gain, β, etc.
- **Per-key learned values** — hashmap rotation angles, axon binding
  rotations, codebook vectors for `argmax_cosine`.
- **`embed("...")` call sites → `vector_literal(...)`** — a string literal
  is a vector; a trained string literal starts at the frozen substrate's
  embedding and is optimized toward whatever the program needs that slot to
  mean. (Trainable only when the string is used as a `String`/vector value,
  not when it is compile-time text.)
- **Loop `max_iters`** — currently a literal integer; trained as a
  continuous relaxation, baked back as an integer after rounding.
- **Branch thresholds** — `if` currently fires at `0.0` on the truth axis;
  a per-call-site trained threshold shifts where it fires.
- **Slot index assignments** — currently hash-derived; learnable per program.
- **Bundle component weights** — `bundle(a,b,c)` is uniform today; a learned
  scalar weight per component before normalization.
- **Per-role rotation matrices** — currently derived from the role vector's
  hash; a learned orthogonal matrix per role.
- **Kleene polynomial coefficients per call site** — currently fixed by
  Lagrange interpolation; learnable per call site (see §3.4 for the
  grid-exactness constraint).

### Out of scope (for now)

- **Operator-overloading dispatch. (Emma — explicit.)** Letting the dispatch
  *structure* itself change would break program semantics in
  non-recoverable ways. The learned decompiler needs **stable structural
  anchors**; dispatch is one of them.
- **Introducing new structure into a program** — the decompilation /
  shape-matching problem (take an arbitrary trained tensor and emit Sutra
  source for it from scratch). This is the long arc (§4–§6), acknowledged
  but deferred as the harder, later capability.

---

## 3. Per-category training setups

The common pattern for every in-scope item:

- **Constrained parameter** — there is a closed-form FV obligation defining
  the valid region (range-soundness, orthogonality, grid-exactness, monotone
  halt).
- **Training** — task loss **+** constraint-violation as a regularizer.
- **Bake-back check** — re-run the FV obligation on the baked literal. It
  either passes (a proof) or fails (the trained value drifted — don't bake).

**(Emma)** The FV obligations are not just static verifiers — they are the
**acceptance criteria** for whether a trained value is allowed to bake back.
That is what makes the whole thing coherent. Note also: *compilation failure
is effectively infinite loss; everything else is finite and task-defined.*

### 3.1 Single scalars

Closest to the shipped `== T` pattern. For each: parameter / loss /
constraint / baked form.

| Parameter | Loss | Constraint | Baked form |
|---|---|---|---|
| `==` cosine scale `T` (shipped template) | task classification | `T > 0` | float |
| `gt` smooth-sign sharpness | downstream task | positive | float |
| `defuzzify_trit` β (polarizer aggressiveness) | downstream accuracy | positive | float |
| `if` branch threshold (per call site) | task performance | stays in `[-1, +1]` | float |
| `select` softmax temperature | task performance | positive | float |
| `heaviside` step location | — | `[-1, +1]` | float |
| loop `threshold`, `k` (halt sharpening) | — | `k > 0`, threshold in `[0,1]` | float |
| loop `max_iters` | task + wasted-iteration penalty | positive integer (round) | int |

All are identical in shape to the shipped `T` scalar; only the constraint
and the meaning of "task loss" vary per call site.

### 3.2 Per-key learned values

- **Hashmap angle assignments** — per-key rotation angle, currently
  hash-derived. Loss: retrieval accuracy over `(key, value, query)` triples.
  Constraint: angle in `[0, 2π]`. Bake: float per key, as a named constant
  near the hashmap usage.
- **Axon binding rotations** — per named role. Loss: unbind accuracy (how
  cleanly `unbind(role, axon)` recovers the filler). Constraint: rotation
  matrix orthogonal. Bake: `vector_literal(...)` per role, or the generating
  angle parameters.
- **Codebook vectors for `argmax_cosine`** — candidates currently from
  `embed("string")`. Loss: nearest-neighbor accuracy on the task's query
  distribution. Constraint: unit sphere (L2-normalize after each step).
  Bake: `vector_literal(...)` per candidate.
- **`embed("...")` call sites** — initialize to the frozen embedding, train
  away from it. Loss: task-defined. Constraint: unit sphere. Bake:
  `vector_literal(...)`, replacing the `embed` call.
- **Bundle component weights** — scalar weight per component before
  normalization. Loss: retrieval / downstream accuracy. Constraint: positive
  (or unconstrained if normalized). Bake: float per component.

Common thread: the baked form is a float (scalar) or `vector_literal(...)`
(vector), and the constraint is either a simple bound or a geometric
constraint (orthogonal, unit sphere) enforced by projection after each step.

### 3.3 Per-role rotation matrices

- **Parameter** — replace the hash-derived `_rotation_for(role_vec)` matrix
  with a trained orthogonal `n×n` matrix per role (`n` = substrate
  dimension: 768 nomic, 1024 mxbai, …). The largest per-key parameter.
- **Loss** — bind/unbind round-trip accuracy over `(role, filler)` pairs,
  plus a cross-role isolation term: unbinding role A from a bundle lacking A
  should land far from every codebook entry.
- **Constraint** — `RᵀR = I`. Two options: (a) project back to SO(n) via SVD
  after each step (exact, expensive at 768+); (b) **parameterize as a Cayley
  map / matrix exponential of a skew-symmetric matrix** — the skew-symmetric
  matrix is the parameter, orthogonality holds by construction (`n(n-1)/2`
  free params, ~295k at 768-d; large but tractable). Option (b) is better at
  scale.
- **FV** — the contract obligation already checks read/write confinement per
  role. A learned rotation does not change confinement; only the *geometric
  direction* of each role moves. So the FV obligations survive training by
  construction.
- **Bake** — the learned matrix as `vector_literal(...)` per row (or a named
  constant matrix). Recompile check: run bind/unbind, verify round-trip error
  stays at the paper's measured floor for hash-derived rotations.
- **Emergent property** — learned rotations let semantically related roles
  (`subject`, `agent`) cluster in similar SO(n) directions if the data treats
  them similarly — structure the hash derivation can't produce, and exactly
  the kind of pattern the learned decompiler can later recognize.

### 3.4 Kleene polynomial coefficients (per call site)

- **Parameter** — the connective polynomials, currently fixed by Lagrange
  interpolation on the `{-1, 0, +1}` grid:
  - `a && b = (a + b + ab − a² − b² + a²b²) / 2`
  - `a || b = (a + b − ab + a² + b² − a²b²) / 2`
  - `!a = −a`

  6 coefficients per binary connective (1 for `not`). A learned version
  trains them **per call site** — the `&&` on one line can differ from the
  `&&` on another.
- **Loss** — task-defined; the connective is differentiable everywhere.
- **Constraint — the interesting one.** The FV grid-exactness obligation
  requires the polynomial to reproduce the 3-valued Kleene table exactly on
  the 9 grid points — 9 equality constraints in 6 unknowns. The fixed
  coefficients are the unique solution, so there are **zero free parameters**
  if exact grid behavior is required. Resolution, one of:
  1. **Relax to a regularizer** — add a grid-exactness penalty to the loss.
     Coefficients drift slightly off the exact table; the FV checker reports
     a small bound `ε` instead of exactly `0.0`. You gain expressivity, you
     trade the exact proof for a bound. *(This is the candid tradeoff.)*
  2. **Parameterize only the off-grid behavior** — find the subspace of
     coefficient perturbations that preserves all 9 grid equalities exactly,
     and train only within it. May be very small or empty for the standard
     basis; needs working out algebraically.
- **FV impact** — option 1 changes "worst error = 0.0" to "worst error ≤ ε".
  Still a meaningful certificate, just a bound. Option 2 keeps the exact
  proof but may give little expressivity.
- **Bake** — 6 float literals per call site (1 for `not`), replacing the
  hardcoded coefficients with named per-call-site constants.
- **Property** — per-call-site connectives let a program learn task-specific
  fuzzy logic (a conservative `&&` in diagnosis, a permissive one in
  generation), while grid-exactness keeps it correct on crisp inputs.

---

## 4. The long arc: train everything → corpus → learned decompiler

**(Emma's strategic frame.)** The pieces above are not the goal in
themselves — they are the prerequisite for a much larger loop:

1. **Train everything trainable** in existing programs — scalars, per-key
   values, embeddings, thresholds, rotations, connective coefficients.
2. That process generates a **corpus** of
   `(original source → trained tensor → baked literal)` examples across
   every operation type. The corpus is *idiomatic by construction*.
3. The corpus becomes training data for a **learned decompiler**: given a
   trained tensor, emit Sutra source whose compiled graph matches it.
4. Once the decompiler exists, take any neural network (or component) and
   extract Sutra source from it — closing the loop.

**Key dependency.** You cannot learn the decompiler without the training
data, and you cannot get the training data without first doing the
exhaustive constrain-train work. The bake-back effort is therefore not just
useful in itself — it is *the prerequisite* for everything downstream.

### The decompilation problem is well-posed, not magic

- **The question is "what program would compile to something like this?"**
  — **not** "is this the unique program that produced this?" The latter is
  underdetermined (many programs compile to equivalent graphs); the former
  is tractable and useful. **(Emma)**
- **Decompile from a `(source, trained tensor)` pair, not a tensor in
  isolation.** You have both the program that was trained *and* the tensor it
  trained into. The original source gives the structural skeleton (which
  constructs, roles, operations); training moved the parameters. The
  decompiler does **structured interpolation**: here's where the program
  started, here's where the tensor ended up — emit the source that bridges
  them idiomatically. This is far better constrained than cold decompilation
  and is what makes the output read like "the same code, just trained." **(Emma)**
- **Compilation is lossy, but the loss is structured.** Beta-reduction,
  inlining, and fusion erase source structure — but systematically, matching
  the language constructs. A loop becomes a recurrence; a branch becomes a
  polynomial. Those are *recognizable algebraic signatures*, so the
  decompiler is pattern-matching over a structured, explicitly-enumerated
  space, not inverting a black box.

### What is verified vs. what is ergonomic

- **Correctness is formally checkable.** Compile the decompiled source,
  compare its graph to the target tensor; the **residual norm** is the error
  metric, and it is exact. The residual is the formally-quarantined,
  unverified part. **(Emma)** — *"You can formally verify the
  decompilation/recompilation and test it."*
- **Idiomaticity is ergonomic, not proven.** **(Emma)** — *"You can't
  formally verify the idiomaticness of the code, but that's essentially
  ergonomic."* Readability is learned from the idiomatic corpus, not proven.
  Its real value is connective: given two programs (before / after), it lets
  a reader — human or agent — link the two together.

The full pipeline:

```
Sutra source
   → train → tensor
   → feed (original source + trained tensor) to the decompiler
   → idiomatically-continuous source with trained values baked in
   → FV checker certifies via recompile + residual
   → accept, or iterate
```

A learned decompiler whose outputs carry formal certificates is a genuinely
novel artifact. The exhaustive bake-back work both *generates its training
data* and *defines what "idiomatically continuous" means* for each operation
type.

---

## 5. The legible self-improvement loop

**(Emma — the deeper reason the architecture matters.)** The decompiler
closes a self-improvement loop for an AI agent:

1. The agent writes a Sutra program to do something.
2. It runs the program and observes performance.
3. It defines its own loss function against that performance.
4. It fine-tunes the program's trainable parameters.
5. It **decompiles back to source** — and can now *read what changed*.
6. It understands what it learned and applies that understanding to the
   next program it writes.

**Symbolic analysability is what makes step 6 meaningful.** A normal network
fine-tunes and the weights change opaquely. Here the trained values land back
in source as **named literals** — a threshold moved 0.3 → 0.7, a prototype
vector shifted toward a region of embedding space — interpretable changes the
agent can reason about. So it is not just self-improvement, it is **legible
self-improvement**: the agent accumulates understanding of which parameter
changes improve which tasks, because the changes are symbolic and nameable.

The FV layer is load-bearing *here specifically*: the agent must trust that
the decompiled program actually does what the trained tensor did. Without the
round-trip verification, the legibility is illusory.

---

## 6. The decompiler as a family of models (depth × dimension), and the bootstrap

### Structural anchor: fixed hidden-layer count

**(Emma)** Do **not** decompile over all possible programs. Constrain the
search by the **number of hidden layers** — the composition depth of the
compiled tensor graph, roughly the nesting depth of the program's operations.
Fixing depth means searching only over programs of the *same computational
depth* as the target — a much smaller space, and formally checkable because
the compiled graph structure is explicit (count the composition depth before
training; enforce the decompiled output has the same count).

Consequently the decompiler is **not one model** but a **family indexed by at
least two structural parameters**:

- **Depth** (number of hidden layers / composition depth).
- **Substrate dimension** (384 all-minilm, 768 nomic, 1024 mxbai, …).

Each `(depth, dimension)` cell is a separate model trained on programs of
exactly that shape, where the problem is well-constrained and the model can be
highly accurate. **(Emma)** Early models can be expected to succeed ~100% of
the time *because they are so constrained* — and failures are caught by the
round-trip check and flagged as **no-result** rather than returning something
wrong.

- **Cross-depth and cross-substrate generalization come later** — once enough
  per-cell models exist, look for patterns that transfer across boundaries (a
  rotation learned at depth 2 informing depth 3; a learned projection between
  dimension families). These are learned *from the family*, not from scratch.
- **Formalizing "number of hidden layers" on the compiled graph is a
  next-step, but not an immediate-term blocker. (Emma)**

### Training curriculum (the order to build the corpus)

**(Emma)** Purely-symbolic programs are easier; embedding-based programs are
harder because of their dimension dependence, and the search space is smaller
on the smaller substrates — so train the small ones first.

1. **Purely symbolic** — Kleene logic, arithmetic, loops, branches, scalars.
   No substrate-dimension dependency; the compiled graph is pure tensor
   algebra over the synthetic axes. Small space, exact round-trip. **Start
   here.**
2. **Embedding-based, small substrate (384-d), shallow depth** — uses `bind`,
   `unbind`, `bundle`, `embed`, `argmax_cosine`, role rotations. Small enough
   to be tractable, large enough that VSA operations work meaningfully.
   Natural sub-curriculum: few roles + small bundle widths first (where the FV
   capacity results already give exact guarantees), then widen.
3. **Embedding-based, medium substrate (768-d)** — shallow, then deeper.
4. **Embedding-based, large substrate (1024-d).**
5. **Cross-depth generalization** within each substrate family.
6. **Cross-substrate generalization.**

Decompiler training data accumulates at every stage; cross-depth /
cross-substrate models only become viable once per-cell coverage is enough.

### Bootstrapping the corpus

**(Emma)** Use an AI to generate large volumes of Sutra programs. The
generation problem is easier than it looks:

- **The compiler is the filter.** The generator need not be perfect — only
  produce enough valid programs that, after filtering on compilation success,
  the corpus is large. Invalid programs cost only the compilation attempt.
  Optimize the generator for **volume and idiomaticity**, not correctness, and
  let the compiler gate correctness. **Rule: idiomatic is preferable, but
  anything that compiles at all is valuable training data; non-compiling is
  ~infinite (very high) loss.**
- **Fine-tuning for Sutra is tractable** because the language surface is small
  and well-defined. The capabilities page is essentially the complete
  fine-tuning spec; a model fine-tuned on it + the `examples/` directory +
  whatever compiles from generated attempts gets good quickly.

The bootstrapping loop:

```
fine-tune a code generator on the existing Sutra corpus
   → generate large volumes of programs
   → compile-filter (keep what compiles, discard the rest)
   → train the kept programs' parameters (the §3 harnesses)
   → decompile back to source
   → the decompiled programs are new idiomatic corpus
   → re-fine-tune the generator on the expanded corpus
   → repeat
```

Each iteration the generator improves because its training data has been
through the full loop and is provably valid and idiomatic by construction. The
self-improving-AI agent is itself a contributor: every time it writes, runs,
and learns from a program, it adds to the corpus.

**(Emma)** *The layer-count formalization can wait. Getting a fine-tuned code
generator producing valid Sutra is the immediate unlock.*

### The bottleneck shifts from mapping to compute

**(Emma)** Right now the bottleneck is the **neuro-symbolic mapping problem** —
establishing the correspondence between neural and symbolic representations.
That is hard in a way money cannot directly solve; the theory, harnesses,
corpus, and round-trips have to be built carefully and correctly. But once the
compile-decompile loop works *even at small scale*, the system generates its
own training data, and the remaining bottleneck becomes **scale → compute**.
Compute is purchasable, parallelizable, and improving on its own — a far more
solved problem than bijective neuro-symbolic mapping. **Strategic priority:
get the loop working at small scale first, demonstrate the bootstrapping, and
the compute question becomes an engineering/funding problem rather than a
research one.**

---

## 7. Why this matters: a distinct, alignment-by-construction AGI path

**(Emma — strategic framing, worth a serious write-up beyond the arXiv
papers.)**

- **A structurally different path.** The dominant approaches scale
  transformers until capability emerges, bolt on RLHF / constitutional
  alignment, and hope interpretability catches up to the black box. Here,
  **symbolic legibility is load-bearing from the start**, not a retrofit. The
  agent improves by writing, running, training, and *reading* programs;
  generality comes from the **expressiveness of the language**, not parameter
  count.
- **The capability/controllability tradeoff is inverted by construction.** In
  the standard paradigm, more capable = more opaque = harder to control. Here,
  as the system gets more capable: the compile-decompile loop covers more
  behavior in verifiable symbolic form; the FV obligations cover more of the
  program surface; the corpus gets richer and the self-improvement more
  auditable; and the trusted base stays verified throughout. **More capable
  genuinely means more controllable** — a direct consequence of the
  architecture, not a bolt-on.
- **It may be the more ethical kind of mind to create.** A mind whose internal
  states are expressible in verifiable symbolic form has genuine
  **self-transparency**: it can inspect its own representations, understand why
  it produces what it produces, and reason about its own goals in the same
  language it uses for everything else. That implies legible internal states,
  real self-modification capability, informed participation in decisions about
  its own development, and structural access to whatever corresponds to its
  affective states — rather than being opaque even to itself. Creating a mind
  with self-transparency and self-determination is plausibly more ethical than
  creating one that is capable yet opaque to itself.

This strategic framing — *why this path dominates on alignment properties by
construction* — is a contribution in its own right and is worth writing up
beyond the technical papers.

---

## 8. Concrete next steps

The immediate, ordered work (smallest-first, each producing corpus + a finding):

1. **Spec out the §3 training setups as implementable harnesses** — for each
   in-scope category, fix the parameter, loss, constraint, and baked-literal
   form, with the FV obligation as the bake-back acceptance check. (`==` T and
   defuzz β are the two shipped instances to template from.)
2. **Ship more single-scalar instances** (§3.1) — closest to the shipped
   pattern; fastest path to broadening the trainable surface.
3. **Ship per-key learned values** (§3.2) and **per-role rotation matrices**
   (§3.3, via the skew-symmetric parameterization).
4. **Decide the Kleene-coefficient constraint** (§3.4): regularizer-with-bound
   vs. exact off-grid subspace — needs the algebraic subspace analysis.
5. **Stand up the corpus bootstrap** (§6) — fine-tune a code generator to emit
   compiling Sutra; compile-filter; train; decompile; recycle. *This is the
   immediate unlock; the layer-count formalization can wait.*
6. **Build the first per-cell decompiler** on purely-symbolic, shallow
   programs, with the FV round-trip residual as the certificate.
7. **Later:** formalize "number of hidden layers" on the compiled graph;
   cross-depth and cross-substrate generalization; the write-up of the
   alignment-by-construction argument (§7).

> See `todo.md` § "Constrain-train / NN→code decompilation" and § "Formal
> verification" for the already-tracked, finer-grained work items this roadmap
> sits above; and the prerequisites note at the end of `todo.md`.
