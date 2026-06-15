# Transpiler frontends — source languages that lower to Sutra

**Status: grounded in implemented, substrate-verified code, not aspirational design.**
Everything in this file describes lowering passes that exist under `sdk/sutra-from-*/`,
each of which compiles **and runs** its fixtures on the real substrate against ground
truth (the compile-AND-run bar, not compile-only). Per-frontend detail lives in each
`sdk/sutra-from-<lang>/README.md`; this file is the cross-frontend contract — what it
*means* for a language to transpile to Sutra.

## What a frontend is

A frontend is a pure source-to-source pass: `<lang>` source text → Sutra (`.su`) source
text. It does **not** touch the substrate itself. It parses the source language (every
frontend uses a tree-sitter grammar), walks the AST, and emits Sutra surface syntax. The
emitted `.su` then goes through the one canonical compiler (`sdk/sutra-compiler/`,
`codegen_pytorch.py`) like any hand-written Sutra program. So a frontend inherits the
substrate-purity guarantee for free: if it emits valid Sutra, the result is a
substrate-pure tensor-op graph, because the compiler is the only thing that ever lowers
to tensors.

This is why "transpiles to Sutra" is a meaningful claim and not just "has a parser": the
frontend's output is run on the substrate and checked against the source language's own
semantics. A fixture that lowers but produces the wrong number is a failure, not a pass.

## The shared lowering shapes

All frontends agree on a small set of lowering shapes. The shapes are the contract; a new
frontend is mostly the work of recognizing the source language's spelling of each shape
and emitting the shared target. OCaml (`sdk/sutra-from-ocaml/`) is the reference
implementation — when a shape is ambiguous, OCaml's is canonical.

| Source-language construct | Sutra target | Notes |
|---|---|---|
| Function / `let` / `def` / `fn` | `function` | Untyped params default to `int`; annotated params map to the Sutra type (`int`/`float`/`bool`/`String`/`void`). |
| `if`/`then`/`else`, `match`, `case`, guards | **defuzz blend** (strong-defuzz two-way soft-mux) | No host control flow. A conditional is `((1+w)·then + (1−w)·else)/2` with `w = truth_axis(defuzzy(cond))`; multi-arm match nests the blend over `scrut == k` tests, last arm = base. |
| Tail-recursive accumulator (`f … = if C then BASE else f a…`) | declared **`while_loop`** | Bounded substrate iteration — a self-calling function would not terminate through the fuzzy-if blend, so tail recursion is reified as a loop with simultaneous-update temporaries. |
| Foldable non-tail recursion (`LEAF +\|* f(REC)`) | **CPS accumulator `while_loop` trampoline** | The pending call-stack work is reified as an accumulator carried by the loop; combine op must be associative+commutative (`+`/`*`). |
| Imperative `while` / unbounded `loop { … break }` | substrate **`while_loop`** | State = the in-scope names the cond/body touch; only mutable locals are written back. A `loop { if C { break; } … }` lowers to `while !C { … }`. |
| Enums / variants / ADTs / tuples / records / structs | **tagged or structural axon** | A constructor becomes a `{_tag, _val…}` axon; a record/struct becomes a positional/field axon (the structural-typing carrier). Field access is an `unbind`. |
| Pipe operator (`\|>`), `where`/`let` local binds | inlined application / local bindings | Sugar that beta-reduces; no new substrate mechanism. |

The recurring boundary caveat across every loop shape: **loop bounds must use strict
`<`/`>`, not `<=`/`>=`** — at exact equality the substrate comparison defuzzes false, so a
`<=` bound drops the boundary iteration (finding
`2026-06-13-while-loop-le-boundary-equality-defuzz`). For Rust's `loop { … break }` this
applies to the negated *break* condition (`if i >= n { break; }` negates to strict `i < n`).

## Maturity (2026-06-15)

Nine frontends are active plus C (parked). Fixture counts are the substrate-verified
compile-AND-run fixtures; they track breadth of covered shapes, not lines of code.

| Frontend | Fixtures | Furthest-along shapes beyond the core |
|---|---|---|
| OCaml (`sutra-from-ocaml`) | 45 | The reference frontend — records/variants→axons, options, tuples, modules. |
| TypeScript (`sutra-from-ts`) | 19 | Yantra's downstream GUI gate; the most-exercised in practice. |
| Rust (`sutra-from-rust`) | 10 | Enums→axons, structs→axons, imperative `while` + compound assignment, unbounded `loop { … break }`. |
| Scala (`sutra-from-scala`) | 9 | Named roadmap complete (val bindings, if/else + literal `match` blends). |
| Clojure (`sutra-from-clojure`) | 9 | `case` → nested equality blend. |
| Elixir (`sutra-from-elixir`) | 9 | `when` guards (incl. `and`/`or` chains), pipe `\|>`, multi-clause dispatch. |
| F# (`sutra-from-fsharp`) | 8 | Name-binding `match` patterns, parameter type annotations. |
| Haskell (`sutra-from-haskell`) | 8 | `where`/`let` bindings (laziness out of scope). |
| Erlang (`sutra-from-erlang`) | 6 | Multi-clause function heads grouped by (name, arity); guards. |
| C (`sutra-from-c`) | 2 | **Parked** (2026-05-08) — earliest, behind TS as the Yantra gate. |

## What is deliberately out of scope per frontend

Recursion outside the tail-accumulator and foldable-non-tail shapes surfaces as
`UNSUPPORTED-RECURSION` rather than emitting a self-calling function that would not
terminate through the fuzzy-if blend — this is a correctness guard, not a gap to paper
over. Likewise, a source construct with no clean substrate meaning (e.g. an Elixir
`is_integer/1` type-test guard, where the substrate has no runtime type tag) is left
unsupported rather than faked with an always-true blend. Each frontend's README lists its
own next-increment backlog.

## Relationship to the rest of the spec

- The **target** surface syntax these frontends emit is the same Sutra described in
  `program-structure.md`, `control-flow.md`, `operations.md`, and `axons.md`.
- The **defuzz blend** they all emit for conditionals is specified in
  `equality-and-defuzzification.md` and `control-flow.md`.
- The **axon** carrier for variants/records/tuples is specified in `axons.md` and
  `axon-io.md`.

A frontend never introduces a substrate operation the hand-written-Sutra spec does not
already define; if a source language needs something the spec lacks, that is a gap in the
spec to resolve in `open-questions.md`, not a license for the frontend to invent a lowering.
