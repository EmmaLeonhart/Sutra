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

### Haskell — mutually-recursive / forward `where`/`let` bindings

Open item from `planning/wasm-fallback-edge-cases.md` § Haskell. A `where`/`let` block whose
bindings reference each other (mutual / forward order) does not yet lower natively.

Steps:
1. Add a fixture `sdk/sutra-from-haskell/tests/fixtures/forward_where/input.hs` exercising a
   forward reference in a `where` block (binding used before its definition line).
2. Run the existing lower + substrate run; observe whether it already works or emits UNSUPPORTED.
3. If close, fix the binding-ordering analysis in `lower.py` (topo-sort the bindings).
4. If not clean in budget, record assessment in the edge-case doc and move on.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
