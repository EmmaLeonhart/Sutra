# `(atom) <binop>` — cast vs. parenthesized-group grammar ambiguity

## The question

Sutra's primary-expression grammar (`sdk/sutra-compiler/sutra_compiler/parser.py:57-69`)
has one production for both a C-style cast and a parenthesized group:

```
paren_or_cast = "(" ( type ")" unary  |  expr ")" )
```

The parser disambiguates by trying the cast arm first: it parses what is inside
the parens as a *type*, and if a `)` follows *and the next token can start a unary
expression*, it commits to `CastExpr`; otherwise it rewinds and reparses as a
parenthesized expression (`_parse_paren_or_cast`, `_try_parse_type_for_cast`).

The ambiguity: when the parenthesized content is a bare atom that is *also a legal
type name* (an identifier, a `number`/`vector`/… keyword) and it is immediately
followed by an operator token that can begin a **unary** expression — `-`, `+`,
`*` (and other prefix-capable operators) — the cast arm wins. So

```
(x) - y
```

parses as a cast of the unary expression `-y` to type `x` — `CastExpr(x, (-y))` —
**not** the subtraction `(x) - y` the author meant. The grammar cannot tell the
two apart without type information the parser does not have at that point.

## What we currently do

We do **not** resolve the ambiguity in the grammar. Both source-language frontends
side-step it by **never emitting a bare `(atom) <binop>` at expression top level** —
they fully parenthesise every operand so the cast arm can never be entered:

- `sutra-from-ocaml` — `_blend` (lower.py:332-339) wraps each product term:
  `(((1 + w) * (then)) + ((1 - w) * (else))) / 2`, with the comment at line 336-337
  noting the `* (atom)` → CastExpr hazard explicitly. The `let`-binding and match
  paths (lower.py:604, 958) carry the same workaround.
- `sutra-from-ts` — same full-grouping discipline (lower.py:803, 905); fixtures
  `if_else_max`, `if_implicit_else` document the `* (atom)` → CastExpr case
  (worked around 2026-06-05).

So generated `.su` is correct, but only because the emitters are careful. A
hand-written `.su` with `(x) - y` at top level still mis-parses silently.

## Why this is the current state

The cast feature is real (`CastExpr` / `UnsafeCastExpr` are in the AST and codegen)
and the try-cast-then-rewind heuristic is the cheapest disambiguation that keeps
both casts and grouping. Fully-grouped emission was the unblocking move for the
transpilers and cost nothing there, so the grammar ambiguity itself was never
forced to a decision.

## What we don't know / options to weigh

1. **Require a different cast syntax** (e.g. `expr as Type`, or `cast<Type>(expr)`)
   so `(…)` is unambiguously a group. Removes the ambiguity entirely; changes the
   cast surface (migration + any cited examples).
2. **Restrict the type position** — only treat `(IDENT)` as a cast when `IDENT`
   resolves to a declared type, deferring the cast/group choice past parsing. Needs
   type info at parse time (or a post-parse reinterpretation pass).
3. **Disambiguate by the following token** — treat `(atom) -|+|* x` as the binary
   operator (grouping) and reserve casts for non-binary-operator continuations.
   Narrows casts; would need a rule for genuinely-unary-after-cast cases.
4. **Leave it** — keep the heuristic; document the hazard; rely on emitters and a
   lint for hand-written code.

Resolving this means picking one and updating `planning/sutra-spec/` (the grammar /
types spec) plus the parser, then deleting this doc. Until then it is latent: it
does not block the transpilers (they group around it), but it is a real
spec-self-consistency gap for the surface language.

## Cross-refs

- `sdk/sutra-compiler/sutra_compiler/parser.py:57-69, 2235-2305` (the production +
  disambiguation).
- `sdk/sutra-from-ocaml/sutra_from_ocaml/lower.py:332-339, 604, 958` (workaround).
- `sdk/sutra-from-ts/sutra_from_ts/lower.py:803, 905` + fixtures `if_else_max`,
  `if_implicit_else` (workaround + documented cases).
