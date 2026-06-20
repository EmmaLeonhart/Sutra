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

## Active edge case

### F# — no-parens curried application as an infix operand

Open item from `planning/wasm-fallback-edge-cases.md` § F#. `classify "foo" + classify "bar"`
parses as application-precedence error; today it needs explicit parens
`(classify "foo") + (classify "bar")`. See whether the lowering can insert the implied
grouping (curried application binds tighter than infix `+`).

Steps:
1. Add a fixture exercising no-parens curried application as an infix operand; lower; measure.
   (F# grammar DLL may not build on this clone — MSVC; if so, route through CI and assess on the
   lowering logic / Scala-shaped analog.)
2. If a clean native fix is in budget, ship it (fixture RUN == ground truth, regression test).
3. If not clean in budget, record the assessment in the edge-case doc and move on.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
