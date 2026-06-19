# Transpiler edge cases that fall to the WASM fallback (low-value, few-cycles-each)

**Policy (Emma 2026-06-18).** These are per-frontend source constructs that do NOT yet lower
*natively* to Sutra, but **run via the tier-5 WASM fallback** (the `wasm_core` VM — see
`planning/sutra-spec/recursion-execution-model.md` and queue §2/§6). They are worth *attempting*
to lower natively, but they are **NOT high value added** — so:

- **Spend at most a few cycles on each.** If a native lowering isn't clean in that budget, leave
  it on the WASM fallback and move on. Do not sink a long session into one edge case.
- **Never fake / never loosen a test** to make one "pass" — if it doesn't lower natively, it
  stays here (WASM covers correctness).
- These live at the **end of `todo.md`** as the lowest-priority frontend work, and in the queue's
  LAST section. The hourly work-loop reaches them only after everything above is cleared.

When one IS cleared natively (a fixture lands, RUN == ground truth), delete it from this list and
record it in `DEVLOG.md`.

## Shared codegen limitation (blocks several of the below)

- **Int-local in expression position.** A VARIANT `match`/`case` nested in an *expression* (not the
  function tail) needs to bind int-locals (the variant tag `_vtag`, payload `_valN`) as
  *statements*, which an expression slot can't emit. Affects Rust (variant inner `match` / nested
  `if let`) and Haskell (VARIANT `case` in expression position). A general fix (hoist the inner
  match to a prelude temp) would unblock both; non-trivial, low priority.

## Per-frontend catalogue

- **Haskell** (`sutra-from-haskell/`): >2-guard NON-tail multibase (the CPS fold must pick its
  seed from *which* base the recursion bottoms out at — a real compile-time analysis); mutually-
  recursive / forward `where`/`let`; VARIANT `case` in expression position (the int-local limit
  above). Laziness is out of scope entirely (not a WASM-fallback item — just unsupported).
- **Rust** (`sutra-from-rust/`): a VARIANT inner `match` / NESTED `if let` (the int-local limit).
  Dropped from active §4 per Emma — Rust is low priority. (Loop bounds: use strict `<`/`>`; `<=`
  drops the boundary iteration — finding `2026-06-13-while-loop-le-boundary-equality-defuzz`.)
- **OCaml** (`sutra-from-ocaml/`, reference): `option`/variant payload support is **DONE 2026-06-19**
  — all five gaps from finding `2026-06-19-ocaml-option-payload-five-gaps.md` fixed + substrate-
  verified (scalar AND aggregate payload, annotated or not); the finding is RESOLVED. Still open and
  unrelated to payloads: scalable RAM device for the 10MB linear memory; non-zero `Array.make` fill
  (slots start at 0).
- **Elixir / Erlang** (`sutra-from-{elixir,erlang}/`): >2-clause NON-tail multibase (CPS fold) and
  GUARDED >2-clause multibase (mixed integer-literal + `when` bases) are **DONE 2026-06-19** for BOTH
  (fixtures `multibase_nontail_fact` RUN == 600, `guarded_multibase` RUN == 9114 each). Still open:
  Erlang list comprehensions (needs a list abstraction the substrate lacks); multi-arg non-tail
  multibase.
- **Clojure** (`sutra-from-clojure/`): map/vector literal in a TAIL-recursive base — **DONE
  2026-06-18** (`_try_lower_tail_recursive` now runs `_hoist_maps` on the base and types the fn
  return `Axon`; fixtures `map_in_recursion` RUN == 3, `vec_in_recursion` RUN == 60). The residual
  `.item()`-on-call-result limit that blocked inline `(:k (f …))` reads is **DONE 2026-06-19** by the
  COMPILER fix (`_translate_call` routes `.item(key)` on a non-identifier receiver to `axon_item`;
  finding `2026-06-18-axon-item-on-call-result-not-supported.md` RESOLVED).
- **F#** (`sutra-from-fsharp/`): no-parens curried application as an infix operand
  (`classify "foo" + classify "bar"` → application-precedence error; parenthesise as
  `(classify "foo") + (classify "bar")` to work today).

## Not on this list (genuinely done or out of scope)

- The recursion families that DO lower natively (tail, single non-tail CPS fold, literal/guard
  multibase TAIL recursion, explicit/guarded recursive guard) — shipped, not here.
- String literals + `==`/`<>`/`++` dispatch — now native in OCaml/TS/Clojure/Scala/F#/Elixir/Erlang
  (2026-06-18; Elixir `<>` and Erlang `++` concat via String-param inference).
