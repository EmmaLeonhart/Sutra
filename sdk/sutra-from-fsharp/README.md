# sutra-from-fsharp

F# → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend — F# is its close cousin and the ionide grammar mirrors the
ML shapes). `lower(source)` turns F# source into Sutra source; fixtures are
verified **compile-AND-run on the substrate** (the OCaml harness bar).

## Grammar (no PyPI wheel)

tree-sitter-fsharp has no PyPI package and `pip install git+…` fails on the
repo's SSH-only example submodules (and the repo ships no Python binding
anyway). `build_grammar.py` does the minimal real thing instead: clone the
ionide grammar (Emma-authorized source, 2026-06-12), compile `parser.c` +
`scanner.c` into `_grammar/fsharp.dll` with MSVC, and `lower.py` loads it via
ctypes. The DLL is machine-local (`_grammar/` is gitignored); tests skip with
a loud reason when it is missing.

```bash
py sdk/sutra-from-fsharp/build_grammar.py   # needs MSVC (VS Build Tools)
```

## Status

First cut (2026-06-12): top-level `let f a b = expr` functions (and
`let main () = expr`); integer/float consts; infix arithmetic/comparison/
boolean operators (`<>` → `!=`, expression-position `=` → `==`); application
spines flatten to Sutra calls (`add 7 9` → `add(7, 9)`); `if/then/else` → the
defuzz blend; `match` (`| 1 -> … | _ -> …`, and **name-binding** `| x -> …`) →
a nested defuzz blend over `scrut == k` tests (the OCaml/Scala shape; last rule
the base — a `_` wildcard, the final literal, or an identifier pattern that
binds the scrutinee to the name via the `_MATCH_SUBST` substitution shared with
the Elixir/Rust/Haskell frontends). **Type-annotated parameters** (`(x: int)`,
`(k: float)`, `(b: bool)`, `string`, `unit`) lower to the mapped Sutra type (the
OCaml `_map_type` set; `double` → `float`); untyped params still default to int.
**Return-type annotations** (`let f (…) : R = …`) are also supported: the
return-annotated form parses as a `value_declaration_left` whose curried-type
nesting is walked structurally (every `paren_pattern` is one param; the
`simple_type` inside a param-and-return `typed_pattern` is `R`), and `R` is
threaded into the emitted signature. Substrate-verified: `add_main` = 16,
`if_classify` =
100, `paren_sum` = 26, `match_literal` = 200, `match_bind` = 160
(`| 0 -> 100 | x -> x * 10`; `(classify 0) + (classify 6)` = 100 + 60, literal
dispatch + the bound catch-all), `tail_rec` = 15 (tail-recursive
accumulator `let rec f p… = if COND then BASE else f a…` → a declared
`while_loop`, the OCaml/Scala shape; non-tail recursion stays
`UNSUPPORTED-RECURSION`), `nontail_fact` = 120 (foldable non-tail recursion
`LEAF +|* (f REC)` → an accumulator `while_loop` trampoline, the OCaml CPS port;
the self-call must be parenthesised per the grammar quirk; param-dependent bases
rejected). **Measured grammar quirk:**
unparenthesized application mixed with infix (`add 7 9 + classify 5`)
mis-associates in the ionide grammar — parenthesize call operands. Recursion
surfaces as `UNSUPPORTED-RECURSION` until the tail/CPS transforms are ported.

## Next

Variant/record `match` patterns; records/DUs → axons (the OCaml record/variant
pattern); modules. (Parameter + return type annotations shipped 2026-06-15;
literal + name-binding `match` patterns shipped 2026-06-13; NESTED tuple AND
record destructure (`let (a,(b,c)) = t`, `let { inner = { v = vv } } = r`) shipped
2026-06-17 — nested-axon construction + an `Axon` temp per non-leaf prefix (shared
`_emit_nested_reads`) so reads dispatch as `axon_item`, since chaining `.item()` on
a raw tensor fails. Mixed tuple-in-record / record-in-tuple nesting still a later item.)
