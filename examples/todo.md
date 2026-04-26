# `examples/` — open questions and hardwired assumptions

This file lists context the compiler quietly assumes about example
programs that should be made explicit in the spec / paper rather than
left implicit in code.

## Hardwired substrate assumptions

The `.su` files in this directory don't pick a substrate themselves —
the substrate is fixed by which codegen backend the smoke test invokes.
Today that is **always** the numpy backend (`codegen_numpy.py`), which
hardwires:

- **Vectors are fresh random unit vectors per name**, deterministic by
  `(seed=42, hash(name))`. There is no real embedding model in this
  path — `embed("hunger")` is just a seeded RNG draw, not a lookup
  into a frozen LLM. Programs whose meaning depends on
  semantically-grounded embeddings (e.g. analogical reasoning over
  natural-language tokens) cannot be honestly demonstrated on this
  substrate.
- **Dimension = 256**, seed = 42. Both are constants in the
  `NumpyCodegen.__init__` signature.
- **Sign-flip binding** (`a * sign(b)`), normalized bundle, cosine
  similarity. Per the spec rename (permute → sign_flip).

The other backends fix different things:

- **Fly-brain backend** (`codegen_flybrain.py`): KC-space
  prototypes via the mushroom body simulator; `snap` runs against
  Kenyon-cell sparse codes. Embedding model is whatever was used to
  initialize the KC codebook (currently fresh random vectors of
  dim 50, not a frozen LLM).
- **Embedding-paper substrate** (`sutra-paper/`): one specific frozen
  LLM (the one used in `sutra-paper/scripts/`). This is the substrate
  the sign-flip binding paper characterizes; it is *not* exposed as a
  Sutra codegen target today.

**Implication for examples:** every `.su` file in this directory runs
on fresh random vectors. Anything that *looks* like it relies on
semantic structure (e.g. "color is closer to red than to truck") is in
fact relying on the hash collision properties of seed=42 — not on a
real embedding. The paper should either say so explicitly or only
demonstrate programs that don't depend on semantic geometry.

## Open semantic questions

### 1. What does a Sutra program output?

Current paper framing (§1, §2.2): "the program's edge commits a
continuous trajectory to a discrete answer" via `snap` /
argmax-cosine. This is too narrow. A Sutra program can output:

- A discrete codebook entry (the snap-to-nearest framing).
- A raw vector / fuzzy answer that downstream consumers interpret.
- A logit-shaped score over candidates.
- A polarized fuzzy state (post-`is_true`) that is "near-true" but not
  binary.
- A tuple / record whose fields are any of the above.

The terminal commit is a choice the *program* makes, not a property of
the language. The paper currently writes as if every program ends in
`snap`. Open: rewrite §1 / §2.2 / §4 to make output choice explicit;
restructure the demos so at least one outputs raw logits rather than a
snapped codebook entry.

### 2. Is the language monadic?

The pattern is: pure vector-algebra body with a final commit at the
edge. This rhymes with Haskell's IO monad (pure description + edge
commit), and with monadic effect systems generally (low-level logic
encapsulated, output configured at the boundary). Open question: is
this *literally* a monad in the formal sense — does the edge commit
have unit + bind + associativity? Or is it just monad-shaped?

Worth a planning doc in `planning/exploratory/` if anyone gets pulled
into the question. Not load-bearing for Apr 26.

### 3. Spec coverage for `snap`

`snap` is defined in `02-operations.md` and `21-builtins.md` as a
substrate-level cleanup builtin (it required a real attractor
circuit; the retired fly-brain backend was the prior example). The
current PyTorch backend rejects `snap()` calls at codegen time
(`_UNSUPPORTED_BUILTINS`). Programs in this directory therefore
*cannot use `snap` directly* — they use `argmax_cosine` against a
candidate list, which is the same shape but a different name. Worth
either (a) routing `snap` through `argmax_cosine` on the current
backend as the no-cleanup-circuit fallback, or (b) being explicit
in the spec that `snap` requires a substrate-level attractor and
the demo path uses `argmax_cosine`.

### 4. "Every class is a vector (or matrix)" — clarify

The user has stated as a working position that essentially every class
in Sutra is a vector, and matrices are "really more like functions."
This is a strong claim that the spec does not yet carry. Concretely:

- `scalar`, `vector`, `tuple`, `string`, `fuzzy`, `bool`,
  `permutation`, `void` are all listed in `05-type-system.md` as
  primitive types. Most are vector-shaped under the hood (a fuzzy is
  a polarized vector, a bool is a polarized vector with a counter, a
  permutation is a ±1 vector). `string` and `void` are the obvious
  exceptions.
- Matrices in this framing are functions on the vector substrate, not
  data containers. That matches the way `is_true` is specified
  (`M(v) * v = t`) and the way rotations are specified (R is a
  matrix, but its job is to act on state).
- **Open:** is the spec's primitive-type list correct as-is, or does
  it need a refactor that says "everything is a vector, with
  type-level labels carrying additional structure"? The labels
  (fuzzy / bool / permutation) are doing the work of enabling
  multiple-dispatch / method-overloading; the underlying data is
  always a vector.

### 5. Vector classes carry compile-time memory

Vectors aren't just their value — they also carry a record of which
operations have been applied to them. The `bool` defuzzification
counter (issue above) is one example; the same mechanism applies to
other vector subclasses. This is **compile-time metadata**, not
runtime side effects. It gives the *illusion* of side effects without
actually being effects:

- You CANNOT write `if defuzzification_counter == 10 { ... }` —
  that's a runtime branch on metadata, which Sutra doesn't allow.
- You CAN write a function that "normalizes" the defuzzification
  counter to 10 — that is a compile-time, fully-differentiable
  transformation that exists only in the compiler's view of the
  program.

This is important enough that it should probably get a dedicated spec
section (a candidate `27-compile-time-vector-memory.md`) once the
user has thought more about it. For now, recording it here so we
don't lose the framing.

### 6. Switch the numpy backend to a real frozen LLM

The current numpy backend hardwires fresh random vectors per name
(seed=42, hash-based). The user has flagged this as iffy and noted
that a real frozen LLM is what we should be using — most likely the
same model the embedding paper characterizes. This would:

- Make the demo programs actually rely on semantic geometry
  (analogies, similarity-by-meaning) rather than seeded RNG
  collisions.
- Unify the demo substrate with the embedding paper's substrate, so
  the language paper and the embedding paper are pointing at the
  same compute surface.
- Cost: one frozen-LLM forward pass per `embed("...")`, cached. Not
  free, but cheap on a laptop.

Open: which model. The embedding paper uses one specific frozen LLM;
the user has flagged that picking *any* embedding model is a
constraint we should declare in the spec rather than leave implicit.

### 7. `role(name)` as a separate primitive from `embed(name)`

When the substrate is a frozen LLM, `embed("pos_0")` and
`embed("pos_1")` return near-identical vectors (lexically similar
inputs → similar outputs). That's fatal for structural roles: VSA
binding requires roles to be near-orthogonal. See
`planning/findings/2026-04-15-llm-substrate-role-name-collision.md` —
`sequence.su` drops from 11/11 to 3/11 under the LLM for exactly this
reason.

The split that works is: content from the LLM (semantic), roles from a
seeded RNG (structural, near-orthogonal). `sutra-paper/scripts/sutra_runtime.py`
already does this via `EmbeddingSubstrate.random_roles()`. Sutra needs
a `role("name")` primitive distinct from `embed("name")` so programs
can say explicitly which they want, substrate-independent.

**Open:** spec the primitive, add to the compiler, rewrite `sequence.su`
to use it, re-run smoke test expecting 11/11.

## Items that should move to `STATUS.md` when prioritized

- Document the hardwired embedding-model assumption in the paper's
  Limitations section.
- Switch the numpy backend from random vectors to the embedding
  paper's frozen LLM (issue 6).
- Resolve the output-semantics framing (issue 1) before the next
  paper push.
- Decide whether to expose `snap` on the numpy substrate or to
  formally split the builtin set by backend.
- Pick a spec home for the compile-time-vector-memory model
  (issue 5) and the "everything is a vector" framing (issue 4).
