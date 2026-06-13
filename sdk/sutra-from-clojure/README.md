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
head is a call; `(let [n1 v1 n2 v2 …] body)` lowers via sequential substitution
(each value lowered with the earlier binds active, the OCaml `let..in` shape —
numbers only, so re-evaluating a substituted value is side-effect-free); `(cond
t1 r1 … :else d)` → a nested defuzz blend (`:else` or the final clause is the
base). Dynamically-typed values lower as `number`. Substrate-verified:
`add_main` = 16, `if_classify` = 100, `nary_sum` = 16, `let_block` = 17,
`cond_grade` = 150, `tail_rec` = 15 (`(defn f [p…] (if COND BASE (recur a…)))`
→ a declared `while_loop`; both `recur` and a named self-call are accepted, the
OCaml/Scala/F#/Rust/Haskell shape). Destructuring and non-tail recursion surface
as `UNSUPPORTED-*` (never a silent self-call).

## Next

`loop`/`recur` with an explicit accumulator; the foldable non-tail CPS
transform; maps → axons; destructuring binds.
