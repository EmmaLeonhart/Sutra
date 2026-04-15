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
fly-brain cleanup builtin. The numpy backend rejects `snap()` calls at
codegen time (`_UNSUPPORTED_BUILTINS`). Programs in this directory
therefore *cannot use `snap` directly* — they use `argmax_cosine`
against a candidate list, which is the same shape but a different
name. Worth either (a) routing `snap` through `argmax_cosine` on
numpy, or (b) being explicit in the paper that `snap` is a fly-brain-
specific name and the demo path uses `argmax_cosine`.

## Items that should move to `STATUS.md` when prioritized

- Document the hardwired embedding-model assumption in the paper's
  Limitations section.
- Resolve the output-semantics framing (issue 1 above) before the next
  paper push.
- Decide whether to expose `snap` on the numpy substrate or to
  formally split the builtin set by backend.
