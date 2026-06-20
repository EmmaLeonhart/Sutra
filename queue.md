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

Next: pick up a genuine new construct only if one surfaces (a real consumer, a new frontend feature),
or hand back. Do NOT manufacture vague breadth tasks.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
