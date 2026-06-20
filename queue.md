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

### Shared codegen — int-local in expression position (unblocks Rust + Haskell)

Open item from `planning/wasm-fallback-edge-cases.md` § "Shared codegen limitation". A VARIANT
`match`/`case` nested in an EXPRESSION slot (not the function tail) needs to bind int-locals (the
variant tag `_vtag`, payload `_valN`) as STATEMENTS, which an expression slot can't emit. Affects
Rust (variant inner `match` / nested `if let`) and Haskell (VARIANT `case` in expression position).
The doc's suggested general fix: hoist the inner match to a prelude temp.

Steps:
1. Inspect the compiler codegen for how expression-slot lowering handles statements/temps, and the
   Rust + Haskell frontends' VARIANT case handling.
2. Add a fixture exercising a VARIANT case in expression position; lower + substrate-run; measure.
3. If the prelude-temp hoist is clean in budget, ship it (fixture RUN == ground truth).
4. If NOT clean in a few cycles (the doc flags it non-trivial), record the assessment and move on —
   leave it on the WASM fallback.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
