# sutra-from-clojure

Clojure → Sutra transpiler frontend (MVP). Models on `sutra-from-ocaml` (the
reference frontend). `lower(source)` turns Clojure source into Sutra source;
fixtures are verified **compile-AND-run on the substrate** (the OCaml harness
bar).

## Grammar (no PyPI wheel)

tree-sitter-clojure has no PyPI package. `build_grammar.py` clones the sogaiu
grammar (Emma-authorized source, 2026-06-12) and compiles `parser.c` into
`_grammar/clojure.dll` with MSVC; `lower.py` loads it via ctypes. The DLL is
machine-local (`_grammar/` is gitignored); tests skip with a loud reason when
it is missing.

```bash
py sdk/sutra-from-clojure/build_grammar.py   # needs MSVC (VS Build Tools)
```

## Status

First cut (2026-06-12): `(defn name [params] body)` lowers to a Sutra
function; the s-expression surface makes the lowering a single dispatch on the
list head — arithmetic/comparison/boolean heads lower as left-folded n-ary
infix (`(+ a b c d)` works), `(if c t e)` → the defuzz blend, any other symbol
head is a call. Dynamically-typed values lower as `number`. Substrate-verified:
`add_main` = 16, `if_classify` = 100, `nary_sum` = 16. `let`, `cond`,
destructuring, and recursion surface as `UNSUPPORTED-*` (recursion until the
tail/CPS transforms are ported — never a silent self-call).

## Next

`let` bindings; `cond` → nested blends; the recursion transforms (`recur` is
Clojure's own loop form — it maps naturally onto the Sutra `while_loop`);
maps → axons.
