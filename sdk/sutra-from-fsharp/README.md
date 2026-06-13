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
defuzz blend; literal `match` (`| 1 -> … | _ -> …`) → a nested defuzz blend
over `scrut == k` tests (the OCaml/Scala shape; last rule the base). Untyped
params default to int. Substrate-verified: `add_main` = 16, `if_classify` =
100, `paren_sum` = 26, `match_literal` = 200, `tail_rec` = 15 (tail-recursive
accumulator `let rec f p… = if COND then BASE else f a…` → a declared
`while_loop`, the OCaml/Scala shape; non-tail recursion stays
`UNSUPPORTED-RECURSION`). **Measured grammar quirk:**
unparenthesized application mixed with infix (`add 7 9 + classify 5`)
mis-associates in the ionide grammar — parenthesize call operands. Recursion
surfaces as `UNSUPPORTED-RECURSION` until the tail/CPS transforms are ported.

## Next

Type annotations; the foldable non-tail CPS transform; variant/record `match`
patterns; records/DUs → axons (the OCaml record/variant pattern); modules.
