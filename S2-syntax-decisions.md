# S2 Syntax Decisions

This is the rolling document for syntax and surface-language decisions. Comparisons and speculation live elsewhere. Decisions recorded here should be treated as the current direction until replaced.

## Established Decisions

### 2026-04-08

#### Functions exist independently

Status: active

Decision:

- Functions are first-class top-level language constructs.
- S2 does not assume functions live inside classes by default.
- If later grouping constructs exist, they should organize functions rather than own them.

Reasoning:

- This fits the current understanding of S2 as a serious, compiled, substrate-oriented language rather than an object-model-first language.
- It keeps the language closer to Rust, Scheme, Lisp, Python, and plain functions in TypeScript than to C#'s traditional class-centered shape.
- It avoids forcing an OOP structure onto a language whose semantics are driven by vector operations and fuzzy reasoning.

Implications:

- Top-level function declaration syntax is now a priority decision.
- Any future module or namespace design should preserve standalone functions.
- Method syntax, if it exists later, should be secondary sugar rather than the core model.

Open follow-up:

- Choose the block form.
- Decide whether files imply namespaces.
- Decide how primitive operations are written inside function bodies.

#### Function declarations use `function`

Status: active

Decision:

- S2 uses the keyword `function` to introduce a function declaration.
- This is intentionally aligned with TypeScript's top-level function form.
- Shorter alternatives such as `fn` are not the current direction.

Reasoning:

- `function` is explicit and easy to scan.
- It preserves the independent-function model without bringing in C#'s class-centered structure.
- It borrows a familiar declaration shape from TypeScript without inheriting the rest of JavaScript's loose surface design.

Implications:

- Comparison examples should treat `function` as the current S2 baseline.
- Future syntax sketches should prefer `function name(...) { ... }` unless a later decision explicitly changes block form.
- The remaining open question is not the declaration keyword anymore, but the rest of the function signature and body syntax.

Open follow-up:

- Decide block delimiters.
- Decide whether return annotations exist.
- Decide whether files imply namespaces.
- Decide how primitive operations are written inside function bodies.

#### Conditionals use TypeScript-style `if (...) { ... } else { ... }`

Status: active

Decision:

- S2 uses TypeScript-style conditional syntax.
- The baseline shape is `if (condition) { ... } else { ... }`.
- This is a surface-syntax decision, not a final semantic decision about truthiness.

Reasoning:

- This gives S2 a familiar and readable conditional form.
- It preserves explicit braces and keeps branching visually close to C# and TypeScript.
- It avoids prefix-only conditionals while remaining compatible with fuzzy truth semantics underneath.

Implications:

- Comparison examples should treat the TypeScript conditional form as the default S2 branch syntax.
- The open issue is how truthiness works, not how the branch keywords and punctuation work.

Open follow-up:

- Define truthiness versus explicit boolean checks.
- Decide whether `if (cat)` is legal.
- Decide how `isTrue(...)` interacts with conditional syntax.

#### Use `return`

Status: active

Decision:

- S2 uses the keyword `return`.

Reasoning:

- `return` is conventional, explicit, and readable.
- It keeps function bodies easy to scan and aligns with the rest of the current mainstream surface direction.

Implications:

- Function examples should use `return` when they need explicit early exits or explicit return points.
- The open design space is expression orientation, not the exit keyword.

Open follow-up:

- Decide whether final expressions can be implicitly returned in some contexts.

#### Looping uses TypeScript-style `while (...) { ... }`

Status: active

Decision:

- S2 uses TypeScript-style loop syntax for conventional loops.
- The baseline loop shape is `while (condition) { ... }`.

Reasoning:

- This keeps looping syntax readable and familiar.
- It aligns with the same branch-and-block surface style as S2 conditionals.
- It gives a stable surface form even while loop semantics remain open.

Implications:

- Comparison examples should treat TypeScript-style `while` loops as the current S2 baseline.
- Semantic questions about convergence, fuzziness, and termination remain open.

Open follow-up:

- Decide whether `for` loops exist.
- Decide whether loop conditions use ordinary truthiness, explicit truth tests, or both.

#### `fuzzy` and `bool` are distinct data types, and `defuzzy(...)` converts `fuzzy` to `bool`

Status: active

Decision:

- S2 has a data type `fuzzy`.
- S2 has a data type `bool`.
- `defuzzy(...)` converts a `fuzzy` value into a `bool`.
- Both `fuzzy` and `bool` are still represented as vectors at the substrate level.

Reasoning:

- This preserves the vector-native model without pretending booleans are a separate low-level substrate.
- It gives the language an explicit place where fuzzy truth becomes forced into a two-way decision.
- It avoids overloading ordinary branch syntax with all of the burden of semantic collapse.

Implications:

- Truthiness questions now have to distinguish among raw values, `fuzzy`, and `bool`.
- `defuzzy(...)` is a first-class operation in the language surface, not just a runtime detail.
- Comparisons should show both direct truth-testing pressure and explicit `defuzzy(...)` pressure.

Mechanism note:

- `defuzzy(...)` applies an `isTrue` multiplication loop to a `fuzzy` until it reaches true or false.

Open follow-up:

- Decide whether `if (...)` accepts only `bool`, or also accepts `fuzzy`.
- Decide whether `defuzzy(...)` is required in branching.
- Decide whether there are implicit conversions involving `fuzzy` and `bool`.

#### `if (cat)` is a compilation error

Status: active

Decision:

- `if (cat)` where `cat` is a class instance is a compilation error.
- Classes do not exist at runtime. The runtime operates on vectors, scalars, matrices, tuples, and strings.
- There is no implicit truthiness coercion for arbitrary values.

Reasoning:

- S2 does not have conventional runtime class instances. A "class" is a compile-time organizing concept, not a runtime entity.
- Allowing `if (cat)` would imply that arbitrary values have truthiness, but in S2, truth is a geometric property (euclidean distance from true/false vectors), not a type-level coercion.
- If you want to treat an arbitrary vector as a truth value, you must explicitly use an unsafe cast or unsafeOverride to force it into fuzzy/bool space.

Implications:

- `if (condition)` requires `condition` to be `bool` or `fuzzy`.
- To branch on something that isn't already bool/fuzzy, you must explicitly convert it.
- Truthiness is a runtime geometric property, not a compile-time type coercion. It emerges from treating a vector as a fuzzy value via unsafe operations.

#### Operators support overloading

Status: active

Decision:

- S2 supports operator overloading.
- The syntax follows the `function operator` pattern.

Reasoning:

- Vector operations like bind and bundle map naturally to `*` and `+`.
- Overloading is a real language feature in C#, Python, and Rust, not a hack.
- It lets primitive operations read as algebra when that improves clarity.

Implications:

- The declaration form is `function operator +(vector a, vector b) { ... }`.
- This applies to user-defined and primitive types.
- Built-in meanings for `+`, `*`, etc. on primitive types may exist alongside user overloads.

#### Truthiness is geometric, not type-level

Status: active

Decision:

- Truthiness and falsiness are determined by euclidean distance from the true and false vectors in embedding space.
- This is a runtime property, not a compile-time type coercion.
- Truthiness only manifests when a value is forced into fuzzy/bool space via unsafe cast or unsafeOverride.

Reasoning:

- S2's substrate is embedding space. True and false are specific vectors in that space.
- Any vector has some geometric relationship to true/false, but accessing that relationship is an explicit, unsafe operation.
- This inverts conventional truthiness: instead of the language defining which values are "truthy," the geometry defines it, and the programmer must opt in.

Implications:

- There is no automatic truthiness for arbitrary values.
- `if (x)` requires `x` to already be `bool` or `fuzzy`.
- To get truthiness from a non-bool/non-fuzzy value, use `unsafeCast<fuzzy>(x)` or `unsafeOverride(x)`.
- `defuzzy(...)` then collapses a `fuzzy` into a `bool` for branching.

#### Implicit casts are allowed but must be explicitly defined

Status: active

Decision:

- Implicit casts can happen at call sites and assignments.
- The conversion itself must be explicitly declared in source code.
- There are no silent coercions without a visible definition somewhere.

Reasoning:

- This balances ergonomics with explicitness.
- C# is the direct precedent: `public static implicit operator Vector(Cat c) { ... }` lets `Vector v = cat;` compile, but someone had to write the conversion.
- S2 avoids surprise coercions while still allowing convenient call-site syntax.

Implications:

- The declaration form for implicit conversions needs to be designed (candidate: similar to C#'s `implicit operator` pattern).
- Call sites can look clean (`getVector(cat)`) as long as the implicit conversion is defined.
- This is distinct from unsafe casts, which bypass the type system rather than defining a conversion.

#### Special cast: `fuzzy` to `bool` performs `defuzzy`

Status: active

Decision:

- Casting a `fuzzy` to `bool` performs the `defuzzy(...)` operation.
- This is a special built-in cast, not a user-defined implicit conversion.

Reasoning:

- `defuzzy(...)` is already the established bridge from fuzzy to bool.
- Making the cast invoke `defuzzy` keeps the language consistent: there is one way to collapse fuzzy truth.

Implications:

- `bool b = (bool) signal;` where `signal` is `fuzzy` is equivalent to `bool b = defuzzy(signal);`.
- This is a safe, well-defined cast, not an unsafe operation.

## Candidate Decisions

- block delimiters
- namespace or module syntax
- expression-versus-statement bias
- annotation system for semantic roles
- return annotation syntax
- primitive operation call surface
- primitive cast syntax
