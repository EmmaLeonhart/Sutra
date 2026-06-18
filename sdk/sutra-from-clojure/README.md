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
base); `(case E c1 r1 … [default])` → a nested *equality* defuzz blend (the
`cond` shape with an implicit `(= E ci)` test per clause; a trailing lone arg is
the default, literal number/bool constants). A clause test may also be a
**multi-constant list** `(c1 c2 …)`, which matches when `E` equals any member —
lowered to an OR of `(E == ci)` tests (Clojure's list-test semantics). Members
must be number/bool literals. Dynamically-typed values lower as `number`.
Substrate-verified: `add_main` = 16, `if_classify` = 100, `nary_sum` = 16,
`let_block` = 17, `cond_grade` = 150, `case_dispatch` = 119 (`(case x 1 10 2 20 3
30 99)`; matched-clause + default), `case_multilist` = 300 (`(case x (1 3 5) 100
(2 4) 200 999)`; `(classify 3)` + `(classify 4)` = 100 + 200, list-test OR), `tail_rec` = 15 (`(defn f [p…] (if COND BASE (recur a…)))`
→ a declared `while_loop`; both `recur` and a named self-call are accepted, the
OCaml/Scala/F#/Rust/Haskell shape), `nontail_fact` = 120 (foldable non-tail
recursion `(OP LEAF (f REC))` → an accumulator `while_loop` trampoline, the OCaml
CPS port; param-dependent bases rejected).

As of 2026-06-13: **`(loop [v0 i0 v1 i1 …] (if COND (recur a…) BASE))` → a
substrate `while_loop`.** The loop bindings become the recurrent state
(initialised from their init exprs, not 0), `recur` updates them simultaneously
via temps (the tail-recursion shape), and any defn param the cond/recur-args/base
reference is threaded read-only (the Rust `while`-loop param shape, since the
hoisted loop is top-level); the base is returned after write-back. Substrate-
verified: `loop_recur` = 15 (`(loop [acc 0 i 0] (if (< i n) (recur (+ acc i)
(+ i 1)) acc))`, `sumLoop 6`). As with all loop bounds, use strict `<`/`>` — `<=`
drops the boundary iteration on the substrate (finding `2026-06-13-while-loop-le-
boundary-equality-defuzz`). Destructuring binds, `(loop …)` with a non-`if` body,
and other non-tail recursion surface as `UNSUPPORTED-*` (never a silent self-call).

As of 2026-06-15: **maps → axons** (the Rust-struct / OCaml-record / Elixir-map
pattern). A map literal `{:x a :y b}` (keyword keys) cannot lower inline — axon
construction is statement-shaped — so it is hoisted to a prelude temp `Axon _ahN;
_ahN.add("x", a); …` and the temp name fills the position where the map appeared
(the `_ARG_HOIST` node-id mechanism). Keyword access `(:x p)` (a keyword in head
position) lowers to `realvec(p.item("x"))`, and a param read via `(:k p)` or
`(get p :k)` types as `Axon` rather than the default `number`. Map keys may be
keywords (`:x`) or **strings** (`"x"`), both yielding the field name `x`; the
function-call accessor **`(get m :k)` / `(get m "k")`** lowers the same as `(:k m)`.
Substrate-verified: `map_axon` = 13 (`(+ (:x p) (:y p))`; `(sum2 {:x 5 :y 8})`),
`map_get` = 13 (`(+ (get p :x) (get p :y))`; `(sum2 {"x" 6 "y" 7})`). Numeric/symbol
map keys and maps in recursive bodies are later items.

## Next

Symbol map keys; multi-arity `defn` (needs call-site arity rewriting); `case`
symbol/keyword test members (currently number/bool literals only); maps in
recursive bodies. (Multi-constant test lists, keyword/string-key maps → axons, and
`(get m :k)` access shipped 2026-06-15. NESTED vector destructuring `(let [[[a b] c] t] …)`
shipped 2026-06-17 — an `Axon` temp per non-leaf prefix in a function-level destructure
prelude [Clojure's `let` is substitution-only], since chaining `.item()` on a raw tensor fails.)
