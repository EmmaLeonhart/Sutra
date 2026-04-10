# Akasha TODO

## Next up — AST → FlyBrainVSA compilation path

`fly-brain/permutation_conditional.ak` parses and validates with zero
diagnostics, and the VSA builtins are now formally declared in
`planning/akasha-spec/21-builtins.md`. The SDK validator is no longer
the blocker on the fly-brain work. The next piece that would
meaningfully move things forward is the compilation path from parsed
`.ak` source to fly-brain runtime calls:

1. **Compilation path: translator from AST to `FlyBrainVSA` calls.**
   See the medium-term plan in `fly-brain/STATUS.md`. Walk the AST of
   an `.ak` file and emit Python that constructs vectors, builds the
   prototype table, and runs the decide function. This replaces the
   hand-written `permutation_conditional.py` with compiler output.
   Staging split: `vector proto_PH = snap(bind(...));` lines run at
   compile time; the `decide()` function body is runtime. Fixed-frame
   enforcement should become a compile-time guarantee as part of this.

## Recently done

- **VSA builtins declared in the spec.** New file
  `planning/akasha-spec/21-builtins.md` gives formal signatures for
  every implicit-global VSA function used in the repo's `.ak` code:
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
  "Primitive Types" section in `planning/akasha-spec/05-type-system.md`
  with a `map<K, V>` entry covering the lookup semantics and the
  statement-vs-expression disambiguation. Test corpus:
  `tests/corpus/valid/24_map_literal.ak`; parser unit tests in
  `tests/test_parser.py`. **Running the validator on
  `fly-brain/permutation_conditional.ak` now reports 0 diagnostics
  (down from 46 before the permutation-type work started).**
- **`permutation` as a primitive type.** Added to `PRIMITIVE_TYPE_NAMES`
  in the lexer, to the parser's `_PRIMITIVE_TYPES`, and to the
  validator's `_record_type_usage` PRIMITIVES set. Spec entry added to
  `planning/akasha-spec/05-type-system.md` documenting the distinction
  from plain `vector` and why it matters for the compile-to-brain
  strategy. Test corpus: `tests/corpus/valid/21_permutation_type.ak`.
- **Array literals and subscript access.** `[a, b, c]` now parses as
  an `ArrayLiteral` expression (empty `[]` legal; no trailing commas,
  to match the rest of the grammar). `target[index]` now parses as a
  `Subscript` postfix, composing cleanly with call/member/subscript
  chaining. Test corpus:
  `tests/corpus/valid/22_array_literal.ak` and
  `tests/corpus/valid/23_subscript_access.ak`; parser unit tests added
  to `tests/test_parser.py`.

## Pending Decisions

- **Run the Akasha code checker (akashac, in sdk/akasha-compiler) over every `.ak` file in the repo
  and fix every inconsistency it reports.** The compiler/validator is the ground truth for what
  Akasha code should look like. Once it's stable, run it in lint mode against `examples/`,
  `akasha-demo-program.ak`, `fly-brain/`, and any `.ak` files generated under `scripts/` or
  elsewhere. Resolve class-name casing, builtin usage, and structural inconsistencies.
- Decide on anonymous functions. Leaning toward `lambda` keyword. Need to pick exact form.
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Whether there is a lightweight role-annotation system for semantic roles.
- Expression-versus-statement bias.
- Which access modifiers exist beyond public/static defaults.
- How the half-compilation / immediate-execution model works.
- Implement many-to-many as a `hop` non-algebraic function in Akasha.
- Figure out IO — how Akasha handles input/output.

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

- Get Akasha running on normal hardware first
- Then try running it on a simulated fly brain
