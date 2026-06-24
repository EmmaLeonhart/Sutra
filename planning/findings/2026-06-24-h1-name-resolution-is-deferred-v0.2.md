# H1 unknown-type/function diagnostics = the deferred v0.2 symbol table (2026-06-24)

## What the audit asked for

The newcomer-usability audit's top finding (H1): the validator silently accepts unknown TYPE names
(`vec`, removed `scalar`) and unknown FUNCTION calls (typos like `argmaxcosine`), so they fail cryptically
at runtime instead of at compile time. Proposed fix: add unknown-type + unknown-function diagnostics.

## Why it's NOT a quick usability fix

It is the **v0.2 name-resolution milestone the project deliberately deferred.** `validator.py:21-29`
explicitly documents: *"v0.1 deliberately does NOT do: Type checking across declarations / Name
resolution (unknown identifiers) / Arity checking on calls … Those land in v0.2+ once we have a symbol
table and cross-module resolution."*

A measured false-positive scan (`scratchpad/h1_recon.py`, over all `examples/*.su` +
`tests/corpus/valid/*.su` with a comprehensive allowlist = `PRIMITIVE_TYPE_NAMES` ∪ `list/dict/set/array`
∪ `stdlib_class_parents()` ∪ user classes ∪ type params; and functions = `BUILTINS` ∪ `intrinsic_names`
∪ `stdlib_function_names` ∪ class methods ∪ file-scope decls) confirms a naive diagnostic fires on
EXISTING VALID code:

- **TYPE misses:** `float` + `function` are missing from `PRIMITIVE_TYPE_NAMES` (real allowlist gaps,
  easily added); numeric type-args (`BigInt<512>` → "512") get mis-flagged (skip all-digit names);
  **and — the blocker — `03_methods.su` (a *valid* corpus file) declares top-level methods referencing
  `Animal`/`Cat` types that are NEVER declared in the file.** It validates today only because of the
  documented leniency. An unknown-type warning would fire on it (and on the `examples/uncertain/*`
  pedagogical fragments). Warnings don't break the corpus test (errors-only), but warning on
  intentionally-valid code is the symptom that this needs a real symbol table + cross-file resolution,
  not an allowlist.
- **FUNCTION misses (huge surface):** ~25 names — user functions called by bare name, **first-class
  function-valued LOCALS** (`f`, `scale` in the arrow-function examples — a local var holding a function,
  legitimately callable), and the `function.Foo()` prefix form. Resolving these correctly requires
  local-scope tracking + the first-class-function model — i.e. the symbol table.

## Resolution

H1 is reclassified as the **v0.2 symbol-table / name-resolution milestone** (Emma's call on when to build
it — it's a language-direction step that tightens the deliberately-lenient v0.1 validator and will warn on
existing lenient code). It is NOT part of the quick usability batch.

The newcomer-facing gap (confusing cryptic runtime failures on typos) is **mitigated at the doc level
already** (shipped Batch 5.1): `docs/tutorials/01-hello-sutra.md` now states the v0.1 validator checks
"syntax and structure, not yet name resolution — a mistyped *type* or *function name* isn't flagged at
compile time today; that diagnostic pass is on the roadmap." That's the honest interim mitigation until
the v0.2 symbol table lands.
