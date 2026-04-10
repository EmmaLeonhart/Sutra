# Akasha TODO

## Next up — the next biggest win for the fly-brain branch

The previous top two wins (permutation primitive type + array literals
and subscript access) are done. See the "Recently done" section below.
The one remaining blocker for `fly-brain/permutation_conditional.ak` to
parse cleanly is map literals:

1. **Map types and map literals.** `map<K, V>` as a type expression,
   `{k: v, ...}` as an inline literal in expression position, with a
   disambiguation from block statements (expression position vs.
   statement position). Needed for the `map<vector, string> BEHAVIOR_OF
   = { proto_PH: "approach", ... };` table in
   `fly-brain/permutation_conditional.ak`, which is currently the only
   remaining source of diagnostics in that file (25 errors, all on
   lines 60–65). Touch points: parser primary expression (detect `{` in
   an expression-start context), a new `MapLiteral` AST node, the
   generic-type parser to accept `map<K, V>`, plus test-corpus entries
   under `tests/corpus/valid/` showing the new form.

When it lands, re-run
`python -m akasha_compiler ../../fly-brain/permutation_conditional.ak`
and confirm the diagnostic count drops to near-zero (there will still
be undeclared-builtin mentions until the spec declares `snap`,
`similarity`, `bind`, `permute`, etc. — that's a separate short-term
task documented in `fly-brain/STATUS.md`).

## Recently done

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
  to `tests/test_parser.py`. Rerunning the validator on
  `fly-brain/permutation_conditional.ak` cut the error count from 46
  to 25; every remaining error is a map-literal issue on lines 60–65,
  which is the separate follow-up task above.

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
