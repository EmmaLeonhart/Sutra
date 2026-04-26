# Program structure

## Files and entry point

A Sutra program lives in one or more `.su` files. The conventional
entry point is a top-level function named `main`:

```
function string main() {
    ...
}
```

`examples/hello_world.su` is the canonical minimal program. Some
demos use different `main` return types (`function vector main`)
or define `main` trivially and expose the actual work as separate
functions. **The compiler does not enforce a `main` signature** —
`function string main()` is a convention that the test harness
and example conventions rely on, not a language rule.

## Module-level items

The following are accepted at module scope (outside any function
body):

- **Function declarations** (`function <return-type> name(args) { … }`).
- **Typed variable declarations** (`vector X = …;`,
  `map<K, V> X = {…};`, `var X : vector;`, etc.). These act as
  module-level constants computed at module-load time — when the
  generated Python module is imported, the initializer runs and
  the name is bound.
- **`role` declarations** (`role X = …;`) — contextual keyword,
  see `types.md` and `binding.md`.

The following **are not accepted** at module scope (parser accepts
them but codegen rejects):

- **Method declarations** (`method X.foo(…) { … }`) — rejected
  with "method declarations are not supported by the V1 codegen."
- **Operator declarations** (`operator + (…) { … }`) — rejected.
- **Generic functions** (`function <T> name(…)`) — rejected.
- **Statements other than declarations** at module scope —
  generally parsed but rejected at codegen.

The same form of `var` / `role` / `TYPE X = …` works in both
module and function scope; the codegen path is the same.

## Modifiers (parser-only)

The parser recognizes `public`, `private`, and `static` modifiers
on function and method declarations. **The codegen ignores them.**
All emitted Python code is plain module-level definitions with no
visibility enforcement. If you write `public function foo(…)` or
`private function foo(…)`, the compiler parses it and silently
drops the modifier at codegen time.

This is a parser-reservation of the syntax, not a language
feature. Whether Sutra should grow real visibility semantics, and
whether `static` means something beyond "doesn't close over
state" in a functional language, are open questions.

## No imports, no module system

The language has no `import` statement and no module system.
Every `.su` file is a standalone compilation unit — it sees only
what it declares itself, plus the builtins provided by the
codegen runtime (`_VSA`, `_argmax_cosine`, `_select_softmax`,
etc., injected as the emitted-Python prelude).

This means demos that want to share codebooks or role declarations
have to either (a) duplicate them across files, or (b) be
concatenated into a single `.su` file. The test harness's smoke
test currently handles the multi-file case by compiling each demo
independently.

A future import system is an obvious feature to want but hasn't
been designed. Open question: does Sutra want Python-style
`import` / `from X import Y`, Rust-style `mod X; use X::Y`,
something flatter, or something more novel (e.g.
substrate-aware imports where a module declares what it needs
from the substrate)?

## `atman.toml` — project manifest

Each Sutra project carries an `atman.toml` manifest at the project
root. The file describes runtime configuration the project needs.
The schema in use (see `examples/atman.toml` for the canonical
example) has the following sections:

```
[project]
name        = "sutra-examples"
entry       = "hello_world.su"
substrate   = "silicon"
description = "…"

[project.sources]
include = ["**/*.su"]

[project.embedding]
provider    = "ollama"
model       = "nomic-embed-text"
dim         = 768
mean_center = true
```

**Who reads it today:** the test harness
(`examples/_su_harness.py`) reads `[project.embedding]` and passes
`model` + `dim` to `NumpyCodegen` when compiling a `.su` file.
The compiler itself does not read atman.toml.

**Substrate precedence (highest wins)** when compiling a `.su`
file, as of 2026-04-22:

1. Explicit kwarg to `compile_to_module` (Python-level override,
   used by cross-substrate sweeps).
2. `// @embedding: <model>` directive in the first 10 lines of
   the `.su` file.
3. `[project.embedding]` in the nearest walked-up `atman.toml`.
4. NumpyCodegen's hardcoded defaults (nomic-embed-text, 768).

The `atman.toml` schema is stable enough to be relied upon by the
harness. Adding new fields for substrate-specific configuration
(e.g. the still-deferred `main(embedding_space: string)` runtime-
override form) is a natural extension path.

## Architecture-independence is a spectrum

Sutra programs are *somewhat* architecture-independent. A program
that uses only the core vector operations
(`bind`/`unbind`/`bundle`/`similarity`/`argmax_cosine`) runs on
the PyTorch backend with no source change between CPU and CUDA
targets. A program that uses
`snap`/`make_rotation`/`compile_prototypes`/`geometric_loop`
requires a substrate with a cleanup-circuit primitive (none is
currently wired; the retired fly-brain backend was the previous
example). A program that uses `basis_vector` with nomic-specific
assumptions (specific clusters, specific distances) may not
transfer meaningfully to a different embedding model.

The user's position: architecture-independence is a spectrum, not
a binary property. The design doesn't force either extreme; the
same `.su` source may or may not run unchanged on a different
substrate depending on how substrate-specific it is. `atman.toml`
declares the project's substrate commitments so that a
compatibility check is possible.

## Open questions

- **Exact schema of `atman.toml`.** The fields in the canonical
  example are accepted, but what's required vs. optional isn't
  documented. No validator exists today.
- **Substrate-incompatibility detection.** When a `.su` program
  uses an op the declared substrate doesn't support (e.g. `snap`
  on numpy), the numpy codegen rejects it — that's compile-time
  detection via the backend. Should the atman.toml-declared
  substrate also check at compile time, or only at backend-
  selection time?
- **Per-file vs. whole-project compilation.** Today each `.su`
  file is its own compilation unit. Whether multi-file projects
  should exist, and how they'd share declarations, is the
  imports-system open question above.
- **Directory layout.** `atman.toml` sits at the project root by
  convention. Whether sub-projects can nest, what happens when
  walking up finds multiple atman.toml files, etc. — all
  undecided.
- **Multiple entry points.** Libraries and tools with subcommands
  would want more than one callable from outside. The test
  harness currently calls arbitrary functions on the compiled
  module (not just `main`); formalizing that as a Sutra language
  feature is open.
- **Fate of parsed-but-ignored modifiers.** `public` / `private` /
  `static` currently do nothing. Keep-and-implement, remove, or
  leave as a syntactic reservation?
- **Fate of parsed-but-rejected module-level items.** Methods,
  operators, generic functions are parsed; codegen rejects them.
  Implement or remove from the parser?
