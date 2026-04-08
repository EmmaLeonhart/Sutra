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

- Choose the function declaration keyword and block form.
- Decide whether files imply namespaces.
- Decide how primitive operations are written inside function bodies.

## Candidate Decisions

- function declaration keyword
- block delimiters
- namespace or module syntax
- expression-versus-statement bias
- annotation system for semantic roles
