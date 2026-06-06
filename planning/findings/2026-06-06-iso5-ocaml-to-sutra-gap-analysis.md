# ISO-5 (Neural WebAssembly OCaml → Sutra): transpiler gap analysis

**Date:** 2026-06-06
**Context:** The `WASM/` subtree's isomorphism program is transformer ≡ reference
≡ Rust ≡ OCaml (byte-identical on all 6 programs). ISO-5 is the final stage —
express the same autoregressive-deterministic-NTM stack machine in **Sutra**. It
was blocked in the WASM repo only on lack of access to Sutra; that blocker is gone
(Sutra is this repo). The natural on-ramp is the `sdk/sutra-from-ocaml/` frontend.
This finding measures how far that on-ramp currently reaches and decomposes the rest
into bounded transpiler items.

## What the reference is

`WASM/iso/ocaml/bin/main.ml` — 189 lines, a deterministic 35-opcode WASM stack
machine. It is **imperative OCaml**: mutable `ref` cells (`stack`, `pc`, `instr`,
`tok`, `locals`, `call_stack`), a `Bytes.make` memory buffer, a `Buffer` for
output, `while`/`for` loops, `Array.make`/`arr.(i)` arrays, exceptions
(`raise Exit`/`failwith`), `String`/`Char` ops, lists (`::`, `List.rev`), tuples
(`fst`/`snd`), and option types (`Some`/`None`). This matters: the
significance notes already flagged the Sutra stage as the hardest *because* the
Rust/OCaml realisations are imperative/deterministic while Sutra is functional —
a faithful port is not a mechanical transpile.

## Measured transpiler reach (this tick)

Running the full reference through `sutra-from-ocaml` does not crash — it degrades
to `// UNSUPPORTED-*` markers, so the gap is fully visible.

**Closed this tick:** OCaml top-level value bindings (`let mask32 = 0xFFFFFFFF`,
`let mem_size = 10 * 1024 * 1024`) now lower to Sutra top-level constants
(`int mask32 = 4294967295;`), verified visible inside functions on the substrate.
Required normalizing OCaml hex/octal/binary/`_`-separated/width-suffixed number
literals to decimal, since Sutra's lexer rejects `0xFF`. Guarded by the
`toplevel_const` runnable fixture (`main () = (300 - 0xFF) + 5 = 50.0` on the
substrate).

**Remaining gaps (counts in the reference), in dependency order:**

| Gap | Count | Note |
|-----|------:|------|
| `sequence_expression` (`e1; e2`) | 4 | The keystone — refs/`while`/mutation all live inside sequences. |
| `string` literals | 3 | Sutra has a `String` class; the frontend just doesn't emit it yet. |
| `array_get_expression` (`arr.(i)`) | 3 | Needs an array representation + bounds model. |
| option `constructor` (`Some`/`None`) | 2 | Parameterised constructors; only nullary variants lower today. |
| nested function (`let f … in` fn) | 1 | Sutra has no nested fn decls — hoist or inline. |
| `list_expression` (`[]`, `::`) | 1 | Needs a list representation. |
| `character` (`'\000'`) | 1 | Char literal → codepoint int / Sutra `Character`. |
| value binding `let () = …` | 1 | The entry point; correctly stays UNSUPPORTED (`()` is not a binder). |

## Decomposition of ISO-5 into bounded transpiler items

These are queued (see `queue.md` Transpiler track / merged-WASM-queue). Order is
by how much each unblocks, easiest-meaningful-first:

1. **Sequence expressions + local mutation.** `e1; e2; …; eN` in a function body
   → Sutra statements then a final return. Pairs with OCaml `ref`/`:=`/`!` →
   Sutra mutable locals (`let r = ref 0 … r := !r + 1` → `int r = 0; r = r + 1;`).
   This is the keystone: most of the reference's body is sequenced mutation.
2. **`while`/`for` loops → substrate loop.** The reference's `while !pc < n do …`
   is the machine's fetch-execute loop. Per CLAUDE.md this must lower to a Sutra
   `loop`/`while_loop` carrying state as substrate vectors (the tail-rec path
   already proves the shape) — NOT a host loop. This is the substrate-fidelity
   crux of ISO-5.
3. **Char + string literals.** `'\000'` → codepoint; `"0x"` → Sutra `String`.
4. **Arrays.** `Array.make` / `arr.(i)` / `arr.(i) <- v` → a Sutra array
   representation (rotation-binding hashmap or the array primitive).
5. **Tuples + option types.** `fst`/`snd`, `Some`/`None` (parameterised
   constructors) — needed for `parse_program`'s return and `input_base`.
6. **Nested functions** — hoist `is_ws` to a top-level helper or inline it.
7. **Stdlib shims** — `String.length`, `Bytes.*`, `Buffer.*`, `List.rev`,
   `int_of_string`, file IO. Many are out of scope for the substrate port; the
   machine core (stack/locals/memory/pc as state, opcode dispatch as a match,
   the fetch-execute loop) is the part that must run on Sutra.

## The real ISO-5 question (not just transpiler coverage)

Even with every gap above closed mechanically, the faithful port is the
**fetch-execute loop as a substrate recurrence**: machine state (pc, stack,
locals, memory cursor) carried as vectors across loop iterations, opcode dispatch
as a defuzz-blend/match on the substrate, one byte of state per iteration —
mirroring the transformer's own autoregressive step. That is the isomorphism worth
having (it maps back onto the NTM/RAM-pointer track), and it is bigger than
transpiler coverage. The transpiler gaps above are the on-ramp; the loop-as-
substrate-recurrence is the destination. Closing items 1–2 is the point where a
real (if small) WASM-machine fragment first runs on Sutra.
