# sutra-from-erlang

Erlang → Sutra transpiler frontend (MVP). Erlang is on the BEAM like Elixir, but
its own syntax/grammar is separate — this is its own frontend (Emma 2026-06-14).
Models on `sutra-from-ocaml` / `sutra-from-elixir`.

## Grammar (machine-local DLL)

No PyPI wheel exists for tree-sitter-erlang, so `build_grammar.py` clones the
WhatsApp grammar and compiles `parser.c` + `scanner.c` into `_grammar/erlang.dll`
(MSVC); `lower.py` loads it via ctypes. `_grammar/` is gitignored; the test suite
skips with a loud reason if the DLL is missing.

```
py sdk/sutra-from-erlang/build_grammar.py   # needs Visual Studio Build Tools
```

## What lowers

The WhatsApp grammar emits **one `fun_decl` per clause**, so the driver groups
clauses by (name, arity) — first-seen order — into one function.

- **Functions / calls / binary ops.** `add(A, B) -> A + B.` → a Sutra `function`;
  `+ - *`, comparisons (`==`/`=:=`→`==`, `/=`/`=/=`→`!=`, `<`, `>`, `=<`→`<=`, `>=`),
  `andalso`/`orelse` → `&&`/`||`. (`div`/`rem` omitted — `rem` would need the
  forbidden `Math.mod`; a later item via complex rotation.)
- **`if` / `case` → defuzz blend.** `if G1 -> R1; ...; true -> D end` → a nested
  guard blend (`true` clause = base); `case E of 1 -> R1; ...; _ -> D end` → a
  nested equality blend on `E` (integer pattern → `(E == k)` test, `_`/var = base).
- **Multi-clause heads + `when` guards → dispatch blend.** `grade(N) when N > 90 ->
  100; grade(N) when N > 50 -> 50; grade(_N) -> 0.` → one dispatching function; an
  integer pattern is an `(_ai == k)` test, a var pattern binds `_ai`, a `when` guard
  is ANDed in, the last clause is the base.
- **`if`-based recursion → substrate loops.** Single-clause tail recursion
  (`sum_to(Acc, N) -> if N == 0 -> Acc; true -> sum_to(Acc+N, N-1) end.`) → a declared
  `while_loop`; foldable non-tail recursion (`fac(N) -> if N == 0 -> 1; true ->
  N * fac(N-1) end.`) → a CPS accumulator trampoline (the OCaml/Scala/Elixir shape).

Substrate-verified (compile AND run vs ground truth; suite 12/12): `add_main` = 16,
`if_classify` = 100, `tail_rec` = 15, `nontail_fact` = 120, `guard_dispatch` = 150,
`case_dispatch` = 119.

## Next

Multi-clause recursion (Erlang's other idiom — `f(0) -> …; f(N) -> … f(N-1).`, a
base-case-pattern clause + a recursive clause; currently `UNSUPPORTED-RECURSION`);
maps/records/tuples → axons; list comprehensions; `div`/`rem` via complex rotation.
(Map-PATTERN params `getx(#{x := X, y := Y}) -> X + Y` — each field binds its `var`
to `realvec(M.item("key"))` — shipped 2026-06-17.)
