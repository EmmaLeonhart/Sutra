# S2 Language Comparisons

This document is a working reference for designing S2 syntax. It does not lock decisions by itself. It exists to compare language shapes, syntax tradeoffs, and semantic defaults before we commit to S2 forms.

## Current S2 Direction

- S2 is not aiming to look like a general-purpose scripting language.
- S2 functions exist independently rather than living inside classes or modules by default.
- S2 should probably sit above assembly and below C# in abstraction level.
- S2 has to stay compatible with fuzzy, vector-native semantics rather than pretending values are conventional datatypes.
- Syntax should help with reasoning, not hide the substrate.

## Quick Comparison Matrix

| Language | General Feel | Function Model | Typical Syntax Pressure | Likely S2 Takeaway |
| --- | --- | --- | --- | --- |
| C# | structured, explicit, industrial | functions usually live in classes or types | verbosity, declarations, braces, type surface area | good for readability and names, bad fit for class-centric defaults |
| TypeScript | JavaScript shape with added structure | free functions exist but module patterns dominate | type annotations, object literals, arrow functions | good reference for tooling-heavy design without full OOP commitment |
| JavaScript | lightweight, flexible, multi-style | functions are first-class and can stand alone | too many forms for the same thing, weak semantic discipline | useful for independent functions, weak as a model for language rigor |
| Python | readable, indentation-driven | top-level functions are normal | whitespace significance, dynamic ambiguity, runtime-centric feel | good reference for approachable definitions, maybe too soft for substrate-oriented code |
| Rust | explicit, expression-oriented, systems-minded | free functions are normal; methods are secondary | ownership, types, punctuation density | good model for standalone functions and disciplined syntax |
| Scheme | tiny core, prefix notation, functional | functions are primary and independent | uniform syntax can hide intent for non-Lisp readers | strong reference for small-core language design |
| Lisp | homoiconic, macro-friendly, symbolic | functions are independent and central | parentheses dominate surface readability | useful if S2 needs code-as-structure, risky if readability matters more |

## By Language

## C#

### Useful traits

- Strong naming conventions for declarations.
- Clear block structure.
- Good separation between declarations and statements.
- Reads like a serious compiled language.

### Weak fit for S2

- Too class-centered for the direction currently on the table.
- Type declarations communicate things S2 may not want to pretend it has.
- Property and access-modifier culture adds weight without helping vector semantics.

### S2 lesson

Take seriousness and declaration clarity from C#, but not its class-first worldview.

## TypeScript

### Useful traits

- Tooling can be load-bearing without turning the source into total ceremony.
- Free functions and modules are normal enough.
- Good balance between readable syntax and modern expression forms.
- Interfaces show how "soft structure" can still be documented explicitly.

### Weak fit for S2

- Structural typing assumes conventional data shapes.
- JavaScript inheritance from the host language brings legacy weirdness.
- Too many equivalent function styles if copied directly.

### S2 lesson

TypeScript is a good reference for a language where tooling matters, but S2 should avoid inheriting JavaScript's excess surface area.

## JavaScript

### Useful traits

- Functions truly exist independently.
- First-class function semantics are natural.
- Modules can stay lightweight.

### Weak fit for S2

- Surface syntax is too permissive.
- Multiple declaration forms weaken stylistic consistency.
- Prototype/object idioms are mostly noise for S2.

### S2 lesson

Keep function independence, reject permissiveness.

## Python

### Useful traits

- Top-level functions read cleanly.
- Syntax is approachable.
- Minimal punctuation can help core ideas stand out.

### Weak fit for S2

- Indentation significance may be too fragile for a substrate-oriented language.
- Dynamic "just run it" culture may work against explicit semantic control.
- Conventional literals and containers imply datatypes S2 may not want.

### S2 lesson

Python is a strong readability reference, but S2 may need more visible structure than indentation alone.

## Rust

### Useful traits

- Free functions are fully respectable.
- Item-oriented layout works well in source files.
- Expression orientation could map well to vector transformations.
- Feels compiled and disciplined without needing classes.

### Weak fit for S2

- Rust's type and ownership machinery is specific to its memory model.
- Syntax can become visually dense quickly.

### S2 lesson

Rust is one of the better mainstream references for "serious language with independent functions."

## Scheme

### Useful traits

- Small number of primitives.
- Functions and composition are central.
- Very good precedent for building a powerful language from a compact semantic core.

### Weak fit for S2

- Uniform prefix notation can make different semantic categories look too similar.
- Readability cost is real for larger codebases if the audience is not already Lisp-native.

### S2 lesson

Scheme is a strong conceptual reference for minimalism and function-first design, even if S2 does not use prefix syntax.

## Lisp

### Useful traits

- Code-as-data is powerful if S2 ever needs self-transforming programs.
- Independent functions are completely natural.
- Symbolic structure is explicit.

### Weak fit for S2

- Surface syntax is polarizing.
- Homoiconicity may be more power than we need at the start.
- Parenthesis-heavy syntax may obscure vector-semantic intent for readers.

### S2 lesson

Lisp is useful as a reminder that a language can center functions and symbolic composition without classes, but its concrete notation should not be adopted casually.

## Cross-Cutting Syntax Questions For S2

## 1. Function Declarations

Because independent functions are already a likely decision, the main question is not whether S2 has free functions. The main question is what a function definition should look like.

Reference shapes:

```text
C#         result Blend(a, b) { ... }
TypeScript function blend(a, b) { ... }
JavaScript function blend(a, b) { ... }
Python     def blend(a, b):
Rust       fn blend(a, b) -> Result { ... }
Scheme     (define (blend a b) ...)
Lisp       (defun blend (a b) ...)
```

Early S2 implication:

- `fn` or `function` style is likely easier to scan than a Lisp form.
- A declaration keyword is probably better than relying on punctuation alone.
- Return-type syntax should stay optional until S2 has stronger commitments about its type surface.

## 2. Blocks Versus Indentation

Reference split:

- Braces: C#, TypeScript, JavaScript, Rust
- Indentation: Python
- Parenthesized forms: Scheme, Lisp

Early S2 implication:

- Braces are the safest default if S2 needs explicit, unambiguous structure.
- Indentation-only syntax is elegant but easier to make fragile.
- Lisp-style grouping should only be chosen if code-as-structure becomes a core goal.

## 3. Statement Versus Expression Orientation

Reference split:

- More statement-heavy: C#, JavaScript
- Mixed: TypeScript, Python
- More expression-heavy: Rust, Scheme, Lisp

Early S2 implication:

- Expression-oriented design may fit vector transformations better than a purely statement-driven model.
- S2 probably still needs explicit declaration forms even if most computation is expression-shaped.

## 4. Typing Surface

Reference split:

- Heavy visible types: C#, Rust, TypeScript
- Light or dynamic surface: JavaScript, Python
- Semantic minimalism: Scheme, Lisp

Early S2 implication:

- S2 should be careful not to fake conventional datatypes if the substrate is fundamentally vector-native.
- It may still need lightweight annotation forms for roles such as atomic, predicate, truth-space, transform, or compiled artifact classes.

## 5. Calling Style

Reference split:

- Infix-friendly mainstream syntax: C#, TypeScript, JavaScript, Python, Rust
- Prefix-only functional syntax: Scheme, Lisp

Early S2 implication:

- Infix syntax is probably better for readability when representing algebraic operations.
- Prefix forms might still be useful for primitive substrate operations if they need to be unmistakable.

## Initial S2 Lean

If we stay aligned with the current direction, the strongest influences are probably:

- Rust for serious free-function structure
- TypeScript for tooling-aware ergonomics
- Python for readability pressure
- Scheme for compact semantic core

The weakest direct influences are probably:

- C# class-centric structure
- JavaScript permissiveness
- Lisp concrete notation, unless homoiconicity becomes a central goal

## Provisional Non-Decisions

These are intentionally not locked yet:

- exact function declaration keyword
- whether blocks use braces
- whether return annotations exist
- whether modules/namespaces are mandatory, optional, or absent
- whether primitive operations are infix, prefix, or mixed
- whether S2 source is expression-first or statement-first

## Next Decisions To Make

- exact syntax for top-level function declarations
- whether S2 has explicit namespaces or just files plus symbols
- whether primitive operations look mathematical, keyword-based, or both
- how truth-testing and fuzzy conditionals should read in source
- whether there is any lightweight role-annotation system even without conventional datatypes
