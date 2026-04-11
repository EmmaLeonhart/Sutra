# Sutra TODO

## Next up

The fly-brain compile-to-brain pipeline is now real end-to-end
(`.su` → parser → AST → codegen → Brian2 mushroom body → correct
program A/B/C/D behavior, 16/16 decisions correct, verified locally
with Brian2 2.10.1). The last medium-term item in
`fly-brain/STATUS.md` is closed. What's next, roughly in priority:

1. **Expand the fly-brain experiments section in `sutra-paper/paper.md`.**
   The first paragraph of §6.6 "Biological Substrate" is already in
   place on remote (commit 285bcfd — 16/16 result, four distinct
   program permutations, reference to the §4.2 substrate-adaptivity
   claim). Next incremental additions, roughly in order: a small
   summary table of the 16 decisions (program × input), a one-sentence
   mention of the result in the abstract, a §7.3 update so Future
   Directions doesn't contradict the new §6.6 empirical claim.
   Claw4S deadline is 2026-04-20, today is 2026-04-10 — there is
   room to iterate a few times.
   Follow the incremental-changes rule from `CLAUDE.md`: one paragraph
   or one table at a time, diffs approved before commit. Pushing is
   fine now (submit-papers.yml is manual-only, so push ≠ clawRxiv
   submission) — only the actual `workflow_dispatch` trigger counts
   as a submission.

2. **Run `sutrac` across every `.su` file in the repo and fix what
   it reports.** From the Pending Decisions list — the compiler is
   now stable enough to be ground truth. Lint sweep over `examples/`,
   `sutra-demo-program.su`, `fly-brain/`, and any other stragglers.
   Resolve class-name casing, builtin usage, structural drift.

3. **Declare the VSA builtin signatures inside the compiler itself.**
   Right now `21-builtins.md` has the spec but the validator is still
   permissive about bareword calls. Once the v0.2 name resolver
   lands, wire the builtin table into it so undeclared names fire a
   real diagnostic.

4. **Fresh competition analysis.** `scripts/fetch_all_papers.py`,
   `scripts/fetch_reviews.py`, `scripts/fetch_top_papers.py` →
   update `planning/competition-analysis-*.md` with the April 10+
   landscape. Low effort, relevant to paper decisions before the
   deadline.

## Recently done

- **AST → FlyBrainVSA translator + `--emit-flybrain` CLI + e2e.**
  New module `sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`
  walks a parsed `Module` and emits Python targeting the
  `FlyBrainVSA` runtime. The fixed-frame invariant from
  `fly-brain/STATUS.md` §Technical Insight 2 becomes a compile-time
  guarantee (every generated module pins the PN→KC seed via a
  `_FixedFrameFlyBrainVSA` subclass in its prelude). 16 new codegen
  tests, full SDK suite green at 85/85. `fly-brain/test_codegen_e2e.py`
  is the real end-to-end check: parses `permutation_conditional.su`,
  translates, execs on a live Brian2 mushroom body, verifies all 16
  decisions match the expected behavior table. Loops and if-stmts
  are intentionally unsupported and fail loudly with source spans.
- **VSA builtins declared in the spec.** New file
  `planning/sutra-spec/21-builtins.md` gives formal signatures for
  every implicit-global VSA function used in the repo's `.su` code:
  `bind`, `unbind`, `bundle`, `similarity`, `permute`, `compose`,
  `basis_vector`, `permutation_key`, `identity_permutation`, `snap`,
  `argmax_cosine`. Each entry has a signature, semantic description,
  substrate notes (which tier from `02-operations.md` it belongs to,
  whether it runs on the mushroom body or in numpy), and cross-refs
  to the operational prose in `02-operations.md` and the type
  definitions in `05-type-system.md`. Linked from the spec README.
  This heads off the diagnostic avalanche that would otherwise hit
  when v0.2 name resolution lands.
- **Map types and map literals.** `map<K, V>` is now a primitive
  generic type. The inline literal `{k1: v1, k2: v2, ...}` parses as
  a `MapLiteral` expression in expression position; empty `{}` is
  legal; a bare `{ ... }` at statement position is still always a
  block, as in C-family languages. Vector-valued keys work, which is
  what the fly-brain prototype table needs. Spec: extended the
  "Primitive Types" section in `planning/sutra-spec/05-type-system.md`
  with a `map<K, V>` entry covering the lookup semantics and the
  statement-vs-expression disambiguation. Test corpus:
  `tests/corpus/valid/24_map_literal.su`; parser unit tests in
  `tests/test_parser.py`. **Running the validator on
  `fly-brain/permutation_conditional.su` now reports 0 diagnostics
  (down from 46 before the permutation-type work started).**
- **`permutation` as a primitive type.** Added to `PRIMITIVE_TYPE_NAMES`
  in the lexer, to the parser's `_PRIMITIVE_TYPES`, and to the
  validator's `_record_type_usage` PRIMITIVES set. Spec entry added to
  `planning/sutra-spec/05-type-system.md` documenting the distinction
  from plain `vector` and why it matters for the compile-to-brain
  strategy. Test corpus: `tests/corpus/valid/21_permutation_type.su`.
- **Array literals and subscript access.** `[a, b, c]` now parses as
  an `ArrayLiteral` expression (empty `[]` legal; no trailing commas,
  to match the rest of the grammar). `target[index]` now parses as a
  `Subscript` postfix, composing cleanly with call/member/subscript
  chaining. Test corpus:
  `tests/corpus/valid/22_array_literal.su` and
  `tests/corpus/valid/23_subscript_access.su`; parser unit tests added
  to `tests/test_parser.py`.

## Pending Decisions

- **Run the Sutra code checker (sutrac, in sdk/sutra-compiler) over every `.su` file in the repo
  and fix every inconsistency it reports.** The compiler/validator is the ground truth for what
  Sutra code should look like. Once it's stable, run it in lint mode against `examples/`,
  `sutra-demo-program.su`, `fly-brain/`, and any `.su` files generated under `scripts/` or
  elsewhere. Resolve class-name casing, builtin usage, and structural inconsistencies.
- Decide on anonymous functions. Leaning toward `lambda` keyword. Need to pick exact form.
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Whether there is a lightweight role-annotation system for semantic roles.
- Expression-versus-statement bias.
- Which access modifiers exist beyond public/static defaults.
- How the half-compilation / immediate-execution model works.
- Implement many-to-many as a `hop` non-algebraic function in Sutra.
- Figure out IO — how Sutra handles input/output.

## Recently Decided (2026-04-08)

- Function declarations: C# signature shape with `function` keyword
- `function` = free function (public static default). `method` = attached to object (public non-static default).
- Methods desugar to static functions: `Adam.getCat()` → `human.getCat(Adam)`
- Full internal form: `function public static scalar operator +(scalar a, scalar b) { ... }`
- `function.` prefix is for calling (disambiguation), not declaration
- `var` for mutable, `const` for immutable (C#-style)
- Files do not imply namespaces. Code can just execute. Solution structures optional.
- All C# loop forms: while, for, foreach, do...while
- Errors produce garbage vectors. Try-catch is if-statement sugar.
- C#-style string interpolation: `$"Result: {result}"`
- All comment forms allowed: //, /* */, ///, #
- C#-style generics (compile-time only)
- No pipe operator. Nested calls + dot chaining via methods.
- `if (cat)` is a compilation error — classes don't exist at runtime
- Truthiness is geometric — euclidean distance from true/false, accessed via unsafe cast only
- Operators support overloading
- Implicit casts allowed but must be explicitly defined
- `fuzzy` to `bool` cast performs `defuzzy`
- Class system is user-defined, not runtime-special

## Competition Analysis
- Run fresh competition analysis using `scripts/fetch_all_papers.py`, `scripts/fetch_reviews.py`, `scripts/fetch_top_papers.py`
- Update `planning/competition-analysis-2026-04-08.md` with current landscape

## Future Goals

- Get Sutra running on normal hardware first
- Then try running it on a simulated fly brain

## Speculative / not yet committed to

- **OWL → SutraDB extension + Sutra ontology import/editing.** Build out
  the existing OWL handling so that (a) SutraDB gains a first-class OWL
  ontology extension (import, query, edit, export), and (b) the Sutra
  language itself has ontology-aware operations for importing an OWL
  file and manipulating classes/individuals as vector-substrate objects.
  Note: **Protégé** may be a more helpful starting point than raw OWL
  files for organizing ontologies into vectors — it has a rich
  class/property model and existing editing UI, and its export formats
  are the obvious bridge into SutraDB. Hesitant about committing to any
  of this before the Claw4S deadline — it's a scope expansion on top of
  an already-busy rename and paper-polish cycle. Revisit after the
  deadline (2026-04-20).
