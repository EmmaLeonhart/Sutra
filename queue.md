# Sutra — Work Queue (branch: wasm-fallback-edge-cases-native)

**This branch is OFF the main big-leg queue.** Emma 2026-06-19: separate exploratory
branch. Mission: walk `planning/wasm-fallback-edge-cases.md` ONE edge case at a time —
pull it into this queue, attempt a NATIVE lowering within a few-cycles budget, and:

- If it lowers natively (new fixture lands, RUN == ground truth): delete it from the
  edge-case doc, add a fixture/regression test, append to `DEVLOG.md`, commit+push.
- If it is NOT clean in a few cycles: leave it on the WASM fallback, record the
  assessment in the edge-case doc (dated), commit+push, move to the next one.

**NEVER fake / never loosen a test** to make one "pass" (edge-case doc policy).

---

## Status: discrete edge cases worked through

The discrete, actionable items in `planning/wasm-fallback-edge-cases.md` have been cleared or
assessed this session (see `DEVLOG.md` 2026-06-19 entries). What REMAINS in the doc is non-discrete /
deliberately-deprioritized, NOT a next concrete fixture:

- **F# / Scala general breadth** (closures, generics, traits/instance classes, "more String ops") —
  open-ended "as needs arise"; no concrete current gap (string ops are at OCaml parity). Not a
  discrete edge case to clear in a few cycles.
- **OCaml non-zero `Array.make` fill** — already **assessed STAYS** (pre-session); needs a concrete
  consumer reading an unwritten slot.
- **Erlang list comprehensions** — **assessed STAYS** this session (no array-builder primitive / no
  wired `lists:*` reducer; finding `2026-06-19-erlang-list-comprehension-stays-on-fallback.md`).
- **Haskell mutual-recursion cycle / laziness** — out of scope (needs fixpoint/laziness).

Cleared natively this session: Haskell forward `where`/`let`, Elixir+Erlang multi-arg non-tail
multibase, F# no-parens app-as-infix-operand, Haskell >2-guard non-tail multibase, Haskell variant
`case` in expr position, Rust variant-inner-`match` + nested `if let` (shared int-local limit fully
closed across Haskell+Rust).

## Active edge case (ONE at a time — Emma: add things to the queue one by one)

### Scala — multibase NON-tail recursion (nested if/else-if)

Port the multibase non-tail fold (OCaml DONE; recipe in finding
`2026-06-19-multibase-nontail-gap-ocaml-scala-fsharp-rust.md` and DEVLOG 2026-06-19). Scala writes
multibase as `if (c0) b0 else if (c1) b1 else step`.

Transform: flatten the nested-if chain into bases `[(cond_i, base_i), …]` + the recursive step
`LEAF <OP> f(REC…)`; emit a `while_loop` carrying every recursion arg + a synthetic `_acc` seeded to
the OP identity; fold the leaf each step; post-combine `_acc OP base_blend(final state)`. Add fixture
`multiarg_nontail_multibase` (`f(3, 10) = 115`), substrate-verify RUN == 115, run the suite, commit+push.

Then (pull in one at a time as each lands): F#, Rust (same recipe).

---

## Backlog (do AFTER the multibase work — Emma 2026-06-19)

- **Host the web-page-optimization sample at `https://sutra.topazcomputing.com/example`.** Emma wants
  the web-page optimization thing hosted as a sample page on the Sutra site (`/example`). Site is the
  static multi-page build (`scripts/build_site.py` over `docs/`); figure out the source of the
  "web-page optimization" demo and wire a page for it. Pull into the active queue only after the
  multibase frontends are done.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
