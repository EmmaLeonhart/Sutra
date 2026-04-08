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

## Candidate Decisions

- block delimiters
- namespace or module syntax
- expression-versus-statement bias
- annotation system for semantic roles
- return annotation syntax
