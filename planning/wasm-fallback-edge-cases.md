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
- **OCaml** (`sutra-from-ocaml/`, reference): aggregate payload in an `option`/variant **MATCH** arm
  (`match s with Some { x; y } -> …`) — the match binds the payload as a SCALAR `_oval` and the
  record fields stay unbound, AND `Some { record }` construction is UNSUPPORTED; needs the match
  path to descend an aggregate payload like the variant-`let` path does (a 2-sided rework).
  Scalable RAM device for the 10MB linear memory; non-zero `Array.make` fill (slots start at 0).
- **Elixir / Erlang** (`sutra-from-{elixir,erlang}/`): >2-clause NON-tail multibase (same seed-
  selection problem as Haskell); GUARDED >2-clause multibase (a mix of integer-literal and `when`
  bases — the literal-only multibase + the guarded-recursive-clause are done); Erlang list
  comprehensions.
- **Clojure** (`sutra-from-clojure/`): maps/vectors literals inside a recursive body (the fold
  transform lowers the leaf/base without running the map-hoist pass, so a map/vector literal there
  reads UNSUPPORTED; needs the hoist prelude threaded into the loop body).
- **F#** (`sutra-from-fsharp/`): no-parens curried application as an infix operand
  (`classify "foo" + classify "bar"` → application-precedence error; parenthesise as
  `(classify "foo") + (classify "bar")` to work today).
- **TS** (`sutra-from-ts/`): per-variable interface typing so a field-type lookup is exact when two
  interfaces share a field name with different types (low priority).

## Not on this list (genuinely done or out of scope)

- The recursion families that DO lower natively (tail, single non-tail CPS fold, literal/guard
  multibase TAIL recursion, explicit/guarded recursive guard) — shipped, not here.
- String literals + `==`/`<>` dispatch — now native in OCaml/TS/Clojure/Scala/F# (2026-06-18).
