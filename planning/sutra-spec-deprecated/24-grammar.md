# Surface Grammar

> **Status: describes v0.0.0, which is what actually compiles today.** Unlike the solution-structure and workspace docs (which are planning for v0.0.1), this grammar is a snapshot of the surface the reference compiler in `sdk/sutra-compiler/` currently accepts. The intent is to document what exists, not to design something that doesn't.

## The grammar itself lives in [`24-grammar.ebnf`](24-grammar.ebnf)

The formal grammar is a proper grammar file in ISO 14977 EBNF at [`24-grammar.ebnf`](24-grammar.ebnf). That file is the canonical reference. This markdown document is context around it — prose explanation, rationale, version policy, diagnostic-code index — but **when this document and `24-grammar.ebnf` disagree, the `.ebnf` file wins**, and when `24-grammar.ebnf` and the reference parser at `sdk/sutra-compiler/sutra_compiler/parser.py` disagree, one of them is wrong and the disagreement has to be resolved explicitly (per `CLAUDE.md`).

Syntactic decisions discussed in prose live in [`sutra-syntax-decisions.md`](../../sutra-syntax-decisions.md) at the repo root. The `.ebnf` file is the mechanical distillation of those decisions; this markdown is the connective tissue.

## Status and versioning

**`24-grammar.ebnf` is the v0.0.0 grammar.** Everything in this repo is v0.0.0 source, the reference compiler in `sdk/sutra-compiler/` is the v0.0.0 toolchain, and the grammar file is what that toolchain accepts. Nothing in this policy is meant to break existing code — v0.0.0 must keep compiling under the current toolchain, because it is the only toolchain that exists.

The grammar is **versioned with the language**. Starting at v0.0.1, the version a given source tree is written against will be pinned by the `sutra_version` field of its workspace or project `atman.toml`. See [`22-workspaces.md`](22-workspaces.md) for the workspace schema and [`25-solution-structure.md`](25-solution-structure.md) for how version pinning propagates through a solution — including what "no `atman.toml` ⇒ implicit v0.0.0" means, and what happens to v0.0.0 trees once a v0.0.1 toolchain exists.

**v0.0.1 does not exist yet.** It is the next planned cut, on the order of two weeks out as of this writing. Until then, v0.0.0 is the only version, and v0.0.0 is extremely permissive for a specific structural reason: the current reference compiler was spaghetti-coded to the architecture of the FlyWire connectome, so the surface and semantics bend around that one substrate. The solution-structure model in [`25-solution-structure.md`](25-solution-structure.md) exists precisely so that v0.0.1 can target other substrates without breaking the v0.0.0 FlyWire-shaped codepath — per-project `substrate` fields in `atman.toml` are how a v0.0.1 solution says "this project targets silicon" or "this project targets logit-space" instead of assuming fly-brain.

Treat [`24-grammar.ebnf`](24-grammar.ebnf) as a snapshot of v0.0.0, not a forward-compatibility commitment. Breaking changes between v0.0.0 and v0.0.1 are explicitly allowed, because the whole point of calling the current state v0.0.0 rather than v0.0.1 is to keep those breaking changes on the table.

## What the grammar covers

At a glance — see [`24-grammar.ebnf`](24-grammar.ebnf) for the full productions:

- **Syntactic grammar**: modules, function/method declarations with modifiers and operator overloads, typed and inferred variable declarations, block statements, all C#-style control flow forms (`if` / `while` / `for` / `foreach` / `do...while` / `try`/`catch`), the Sutra-specific `loop` with bounded-unroll and eigenrotation forms, and a cascaded-precedence expression grammar.
- **Primary expressions**: literals, identifiers, `this`, grouped expressions, casts, array literals, map literals, and the four "special-call" contextual keywords (`unsafeCast`, `unsafeOverride`, `defuzzy`, `embed`).
- **Lexical grammar**: identifiers, keywords, contextual keywords, numeric / string / boolean / interpolated-string literals, operators, punctuation, and all four comment forms (`//`, `/* */`, `///`, `#`).
- **Documented ambiguities**: cast-vs-group, generic-call-vs-less-than, and bounded-vs-eigenrotation `loop` — all resolved with lookahead in the reference parser.

The `|>` pipe-forward operator is **lexed** so the validator can reject it with a clear diagnostic, but it is never legal syntax in a compiling v0.0.0 program. See `sutra-syntax-decisions.md` §"No pipe operator; nested function calls only".

## Diagnostics

The lexer and parser emit diagnostics with stable `SUT####` codes. v0.0.0 codes in the grammar space:

| Code | Meaning |
|---|---|
| `SUT0001` | Unterminated block comment |
| `SUT0002` | Unterminated string literal |
| `SUT0003` | Unexpected character in source |
| `SUT0100` | Parser expected a specific token |
| `SUT0101` | `public`/`private`/`static` used outside `function`/`method` |
| `SUT0102` | Non-overloadable operator in `operator` declaration |
| `SUT0103` | `var` combined with an explicit type |
| `SUT0104` | Expected expression |
| `SUT0105` | `unsafeCast` missing type argument |
| `SUT0110` | `\|>` used (spec forbids pipe forward) |

Codes `SUT2000-SUT2099` are reserved for workspace-model errors; see [`22-workspaces.md`](22-workspaces.md).

## Out of scope for v0.0.0

The following have reserved tokens or partial parser support in [`24-grammar.ebnf`](24-grammar.ebnf) but no defined semantics in v0.0.0, and are expected to land in a later version:

- `new` keyword — reserved, not used by any production.
- `implicit` keyword — reserved for implicit-conversion declarations (see `sutra-syntax-decisions.md` §"Implicit casts are allowed but must be explicitly defined").
- `foreach` with non-iterable arguments — parsed, but semantics depend on the collection model, which is not fixed in v0.0.0.
- `try`/`catch` failure-pattern matching — parsed; semantics live in the runtime spec.
- Lambda / anonymous function literals — not yet in the grammar (candidate decision per `sutra-syntax-decisions.md`).

None of these should be expected to survive the v0.0.1 cut unchanged.
