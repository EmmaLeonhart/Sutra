# Multibase non-tail recursion: undocumented gap in OCaml / Scala / F# / Rust (2026-06-19)

**Status:** RESOLVED 2026-06-20. Found by a parity check, surfaced to Emma, who chose to port the
fold recipe to all four frontends — done one at a time (OCaml → Scala → F# → Rust), each with a
`multiarg_nontail_multibase` fixture RUN == 115 on the substrate. See DEVLOG 2026-06-19/20.
**Branch:** `wasm-fallback-edge-cases-native`.

## How it was found

After clearing the documented multi-arg / >2-base non-tail multibase edge cases for **Elixir,
Erlang, and Haskell** this session (those three were the only ones the edge-case doc listed as open),
a parity check on the same recursion family across the OTHER frontends showed they share the gap —
but it was never documented for them.

## Measured

A multibase non-tail recursion (≥2 bases, recursive step is `LEAF <OP> f(REC)` not a tail call),
e.g. `f a b = if a==0 then b else if a==1 then b+100 else a + f (a-1) b; f 3 10` (ground truth 115),
emits `UNSUPPORTED-(LET-)RECURSION` in all four:

- **OCaml** (`sutra-from-ocaml`, the REFERENCE frontend): `_try_lower_foldable_nontail_recursive`
  only handles `len(params) == 1` and a single `if_expression` (one base + one fold-else). The
  nested `else if` chain and the multi-arg shape both fall out.
- **Scala** (`sutra-from-scala`): `UNSUPPORTED-RECURSION: not the tail-accumulator shape`.
- **F#** (`sutra-from-fsharp`): `UNSUPPORTED-RECURSION: not the tail-accumulator or foldable non-tail shape`.
- **Rust** (`sutra-from-rust`): same marker.

(Single-base non-tail CPS fold works in all four — `nontail_factorial` etc. The gap is specifically
>1 base and/or >1 arg.)

## The fix (the proven recipe, ported)

The same transform shipped this session for Elixir/Erlang/Haskell: a `while_loop` trampoline carrying
every recursion arg plus a synthetic `_acc` seeded to the OP identity, folding the leaf at each step's
current state, then post-combining `_acc OP base_blend(final state)` — the base the recursion bottoms
out at is the seed (the seed-selection). The wrinkle for these four: their multibase is written as a
NESTED `if/else if/else` (OCaml/F#/Rust) rather than guards/clauses, so the else-if chain must be
flattened into the base list first (Scala uses `if/else if` too). That flattening + the multi-arg
carry is **more than a few-cycles change per frontend** (× 4 frontends) — hence surfaced rather than
silently launched.

## Recommendation / open decision

This is genuine, high-value work (the reference frontend lacks a recursion family), but it is (a) not
in the edge-case document, (b) a 4-frontend feature beyond the doc's "few cycles each" policy, and
(c) this session was explicitly deprioritized by Emma. Awaiting Emma's call on whether to take it on
now, defer to `todo.md`, or leave the four on the WASM fallback (which covers correctness).
