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

## Shared codegen limitation

- **Int-local in expression position.** A VARIANT `match`/`case` nested in an *expression* (not the
  function tail) needs to bind int-locals (the variant tag `_vtag`, payload `_valN`) as
  *statements*, which an expression slot can't emit. The fix is to hoist those int-local
  declarations to a PRELUDE temp (NOT to inline the raw `realvec(scrut.item(…))` reads — measured:
  the `int`-typed local performs a type-snap the raw read skips, so an inlined tag/payload compares
  wrong). **DONE 2026-06-19 for Haskell** (`_lower_case_stmts(inline=True)` hoists `int _c{uid}_vtag`
  / `_c{uid}_val{i}` to the equation's `_DESTRUCTURE_PRELUDE`; fixture `variant_case_nontail` RUN ==
  4). **DONE 2026-06-19 for Rust too** — `_hoist_enum_constructions` now hoists a VARIANT inner
  `match` (`_vtag_h{k}` / `_val_h{k}_i`) AND a nested `if let` (`_vtag_il{k}`) found in a match arm
  body to the function prelude (fixtures `nested_variant_match_arm` RUN == -2, `nested_if_let_arm`
  RUN == 8). The shared int-local limit is fully cleared.

## Per-frontend catalogue

- **Haskell** (`sutra-from-haskell/`): no open WASM-fallback items remain. **VARIANT `case` in
  expression position is DONE 2026-06-19** (the shared int-local limit above — prelude-temp hoist;
  fixture `variant_case_nontail` RUN == 4). **>2-guard NON-tail multibase is DONE 2026-06-19** — the multibase
  path now folds a non-tail recursive guard via a CPS accumulator (seed = OP identity, fold the leaf
  each step, post-combine `_acc OP base_blend` keyed on the FINAL state, so the seed is whichever
  base the recursion bottoms out at — the seed-selection that was the open analysis); both single-arg
  and multi-arg via `_foldable_step_multi` (fixtures `multibase_nontail_fact` RUN == 600,
  `multiarg_nontail_multibase` RUN == 115). **Forward (out-of-order) `where`/`let` references are
  DONE 2026-06-19** — `_order_binds` topo-sorts each `where`/`let` group so a binding is lowered
  after the local binds it references (fixture `forward_where` RUN == 41). Only a true
  mutual-recursion CYCLE (binding A ↔ B) stays on the fallback — that needs laziness/fixpoint, which
  is out of scope entirely (not a WASM-fallback item — just unsupported).
- **Rust** (`sutra-from-rust/`): no open WASM-fallback items remain. **VARIANT inner `match` and
  NESTED `if let` (the int-local limit) are DONE 2026-06-19** — `_hoist_enum_constructions` hoists
  their tag/payload int-locals from a match-arm body to the function prelude (fixtures
  `nested_variant_match_arm` RUN == -2, `nested_if_let_arm` RUN == 8). (Loop bounds: use strict
  `<`/`>`; `<=` drops the boundary iteration — finding `2026-06-13-while-loop-le-boundary-equality-defuzz`.)
- **OCaml** (`sutra-from-ocaml/`, reference): `option`/variant payload support is **DONE 2026-06-19**
  — all five gaps from finding `2026-06-19-ocaml-option-payload-five-gaps.md` fixed + substrate-
  verified (scalar AND aggregate payload, annotated or not); the finding is RESOLVED. The scalable RAM
  device for the 10MB linear memory is also **DONE 2026-06-19** (direct 1D tensor; finding
  `2026-06-19-ram-device-scaling-limit.md` RESOLVED). Still open: non-zero `Array.make` fill (slots
  start at 0 — a documented limit, not a bug). **Assessed 2026-06-19: STAYS on the fallback.** A
  straight-line array lowers to `dict<int, int>` (missing keys read 0); a non-zero fill would need
  either unroll-on-constant-`n` initialization (bloat, and only when `n` is a compile-time literal)
  or a compiler-level change to the dict default — neither is clean in a few cycles, and the
  straight-line "write before read" pattern makes the fill moot in practice. Do not re-attempt
  without a concrete consumer that reads an unwritten slot expecting the fill.
  - **Multibase NON-tail recursion (found 2026-06-19; Emma: port to all 4).** A parity check after
    clearing the Elixir/Erlang/Haskell multibase-non-tail items showed OCaml, Scala, F#, AND Rust all
    `UNSUPPORTED` a ≥2-base non-tail recursion (`f a b = if a==0 then b else if a==1 then b+100 else
    a + f (a-1) b`). The fold recipe ports; the wrinkle is their multibase is a nested `if/else if/else`
    (needs else-if-chain flattening) + multi-arg carry. **OCaml + Scala DONE 2026-06-19**
    (`_try_lower_multibase_nontail*`; fixtures `multiarg_nontail_multibase` RUN == 115 each).
    F# / Rust still pending (same recipe, ported one at a time). Finding:
    `2026-06-19-multibase-nontail-gap-ocaml-scala-fsharp-rust.md`.
- **F# / Scala** (`sutra-from-{fsharp,scala}/`): general breadth (closures, generics, traits /
  instance classes, more String ops), modelled on OCaml as needs arise. F# additionally can't build
  its grammar DLL on the SutraDev clone (MSVC error), so F# work needs a clone where the grammar
  builds (CI exercises it). Low priority.
- **Elixir / Erlang** (`sutra-from-{elixir,erlang}/`): >2-clause NON-tail multibase (CPS fold),
  GUARDED >2-clause multibase (mixed integer-literal + `when` bases), and **MULTI-ARG non-tail
  multibase** are all **DONE 2026-06-19** for BOTH (fixtures `multibase_nontail_fact` RUN == 600,
  `guarded_multibase` RUN == 9114, `multiarg_nontail_multibase` RUN == 115 each — the last via
  `_foldable_step_multi`: the trampoline carries every recursion arg alongside `_acc`, folds the leaf
  at each step's current state, and keys the base blend on the final multi-arg loop state). Still
  open: Erlang list comprehensions. **Assessed 2026-06-19: STAYS on the fallback** — and the prior
  reason ("needs a list abstraction the substrate lacks") is CORRECTED: the substrate *does* have a
  list abstraction (Sutra binding-arrays — `array_from_literal` / `array_get` / `array_length` /
  `foreach_loop`, `docs/loops.md`). The real blockers: (1) only `array_from_literal` builds an array,
  and only from compile-time-known elements — there is no `array_map` / append / set primitive, so a
  RUNTIME-list comprehension can't build its result list (`foreach_loop` can reduce to a scalar but
  not produce a new list); (2) a compile-time-LITERAL-list comprehension could unroll to
  `array_from_literal(...)`, but no Erlang list-consumer (`lists:sum`/`hd`/`nth`) is wired to reduce
  it to a scalar, so there is no RUN==ground-truth path to verify it — shipping an untested
  list-valued lowering would violate the integrity rules. Re-attempt only with (a) an array-builder
  primitive for the runtime case, or (b) a concrete `lists:*` reducer consumer for the literal case.
  See finding `2026-06-19-erlang-list-comprehension-stays-on-fallback.md`.
- **Clojure** (`sutra-from-clojure/`): map/vector literal in a TAIL-recursive base — **DONE
  2026-06-18** (`_try_lower_tail_recursive` now runs `_hoist_maps` on the base and types the fn
  return `Axon`; fixtures `map_in_recursion` RUN == 3, `vec_in_recursion` RUN == 60). The residual
  `.item()`-on-call-result limit that blocked inline `(:k (f …))` reads is **DONE 2026-06-19** by the
  COMPILER fix (`_translate_call` routes `.item(key)` on a non-identifier receiver to `axon_item`;
  finding `2026-06-18-axon-item-on-call-result-not-supported.md` RESOLVED).
- **F#** (`sutra-from-fsharp/`): no-parens curried application as an infix operand
  (`classify "foo" + classify "bar"`) is **DONE 2026-06-19** — the ionide grammar parses it as
  `application(infix(L, op, R), args)` (the trailing args bind to the whole infix); the lowering
  re-associates to `L op (R args)` since application binds tighter than infix (fixture
  `noparen_app_infix` RUN == 30). No source parenthesisation needed anymore.

## Not on this list (genuinely done or out of scope)

- The recursion families that DO lower natively (tail, single non-tail CPS fold, literal/guard
  multibase TAIL recursion, explicit/guarded recursive guard) — shipped, not here.
- String literals + `==`/`<>`/`++` dispatch — now native in OCaml/TS/Clojure/Scala/F#/Elixir/Erlang
  (2026-06-18; Elixir `<>` and Erlang `++` concat via String-param inference).
