# Akasha TODO

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
