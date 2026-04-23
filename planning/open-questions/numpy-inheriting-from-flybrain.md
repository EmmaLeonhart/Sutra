# NumpyCodegen inherits from FlyBrainCodegen

**Opened:** 2026-04-23.
**Status:** Structural concern flagged by the user mid-session. Not
broken, but the inheritance chain contradicts the CLAUDE.md framing
of the demo path vs. the fly-brain substrate.

## The concern

Current codegen class hierarchy:

```
FlyBrainCodegen (base — fly-brain Brian2 / hemibrain backend)
    └── NumpyCodegen          (the demo path)
            └── PyTorchCodegen (GPU variant of the demo path)
```

Per CLAUDE.md:

> **Numpy is the demo substrate. Fly-brain is segregated.** Two
> backends: `codegen_numpy.py` (demo path, self-contained, no
> fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific
> work, not the demo).

But the implementation has:

```python
# codegen_numpy.py line 23
from .codegen_flybrain import FlyBrainCodegen, CodegenNotSupported

class NumpyCodegen(FlyBrainCodegen):
    ...
```

So the demo path imports from and inherits the entire translator
from the fly-brain backend. The framing in CLAUDE.md says fly-brain
is the segregated, experimental target; the implementation says
fly-brain is the base that the demo builds on top of.

User framing (2026-04-23):

> Yeah, I'm not sure what's stuck in our code is still from the
> Flybrane. I don't know what stuff in our code is still in the
> Flybrane. Or still influenced by it, because of the fly brain
> stuff. I don't know. It was a red herring.

## Why it got this way

Historical order: the fly-brain backend was written first (when the
plan was "compile Sutra to a Drosophila connectome"). Numpy was
then added as a simpler backend for the paper demos. The fastest
way to get numpy working was to inherit the AST walker from the
fly-brain backend and override the prelude + a few call-translation
sites. PyTorch was then layered on top of numpy the same way.

The result is technically working but semantically inverted: the
thing the spec treats as the experimental substrate is the base
class of the thing the spec treats as the canonical substrate.

## What's actually shared vs. what isn't

Looking at what NumpyCodegen inherits from FlyBrainCodegen:

- `_translate_expr` — shared (literal dispatch, identifier lookup,
  binary/unary ops, member access, paren groups, array / map
  literals, subscripts). **No fly-brain-specific logic.**
- `_translate_stmt`, `_translate_function_decl`,
  `_translate_var_decl`, `_translate_top_level` — shared. Purely
  structural; no fly-brain content.
- `_translate_call` — partially shared. NumpyCodegen overrides it
  to handle vector-accessor methods (which only make sense with
  the extended-state runtime, i.e. not fly-brain). The base has
  generic call translation.
- `_translate_bounded_loop`, `_translate_eigenrotation_loop`,
  `_translate_while_as_geometric_loop`,
  `_translate_for_as_geometric_loop` — shared.

So a good chunk of what's "in" FlyBrainCodegen is actually
backend-agnostic translator scaffolding, not fly-brain logic. The
genuinely fly-brain-specific pieces are things like:
- The prelude (Brian2 imports, LIF neuron setup, hemibrain wiring).
- `CodegenNotSupported` rules that refuse EmbedExpr / DefuzzyExpr /
  UnsafeCastExpr (because fly-brain has no LLM, no defuzzy runtime,
  no unsafe-cast target).
- The `_VSA` class body emission.

Those are what should live in a fly-brain-specific module; the
translator scaffolding belongs in a shared base.

## Candidate refactor

```
BaseCodegen (new — pure AST-to-Python translator, backend-agnostic)
    ├── NumpyCodegen         (demo path)
    │       └── PyTorchCodegen (GPU variant)
    └── FlyBrainCodegen      (segregated experimental target)
```

Mechanical change:

1. Create `codegen_base.py` that holds the backend-agnostic
   `_translate_expr`, `_translate_stmt`, `_translate_call` (for the
   generic-call case), `_translate_function_decl`,
   `_translate_var_decl`, `_translate_top_level`, and the loop
   translators. Keep `CodegenNotSupported` here.
2. `codegen_flybrain.py` keeps only the fly-brain-specific prelude,
   the Brian2 / hemibrain setup, and the backend-specific call
   rejections. Imports from `codegen_base`.
3. `codegen_numpy.py` imports from `codegen_base`, not from
   `codegen_flybrain`. The demo path and the fly-brain path both
   sit at the same level.
4. `codegen_pytorch.py` continues to extend `NumpyCodegen` — that
   inheritance is correct (pytorch *is* a GPU-capable variant of
   the demo path).

The existing tests cover enough ground that the refactor is
bisectable: every corpus file still needs to compile and the three
demo programs still need to produce the same outputs.

## Why not do it right now

Scope. The 2026-04-23 literals work (char / fuzzy / string auto-
embed) already touched every file in `sutra_compiler/`. Landing a
concurrent hierarchy refactor would couple the two in a way that
makes bisecting regressions harder. The inheritance inversion isn't
producing wrong output today; it's producing wrong *framing* — the
file that says "fly-brain" has the demo logic in it.

The refactor should be its own commit (or series of commits) with
the goal:

- Every demo/pytorch test still passes.
- `grep -l fly ./sdk/sutra-compiler/sutra_compiler/codegen_numpy.py`
  returns no matches (no fly-brain references in the demo path).
- `from .codegen_flybrain import ...` disappears from
  `codegen_numpy.py`.

## What to watch for

The things currently imported from `codegen_flybrain` into the numpy
backend: `FlyBrainCodegen` (the class), `CodegenNotSupported` (the
exception). Both need to move to the new base module. No other
cross-module references to worry about in the demo path — the imports
are intentional and small.

## Pointers

- Concerns per CLAUDE.md: §"Numpy: compile and monitor only, never
  runtime"; §"Numpy is the demo substrate. Fly-brain is segregated."
- Current inheritance: `codegen_numpy.py:26`,
  `codegen_pytorch.py:39`.
- Shared translator body: `codegen_flybrain.py:870` (_translate_expr),
  `codegen_flybrain.py:430` (_translate_var_decl).
- Related sprawl hygiene: CLAUDE.md §"Avoiding `fly-brain/` Python
  sprawl" (that section is about the `fly-brain/` experimental dir,
  but the same "keep fly-brain contained" principle generalizes to
  this compiler-level structure).
