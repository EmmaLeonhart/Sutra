# ISO-5 unblocked: the WASM machine's memory is RAM, and RAM-based opcode dispatch works

**Date:** 2026-06-06 (12:xx, following the 11:30 milestone)
**Emma's design call:** "if the array is the wasm then this isn't even a sutra array
it's ram." The WASM machine's program/stack/locals/linear-memory are **RAM**, read
via `ramRead()` and written via `ramWrite()` (the host-attached `_VSA.ram` device,
`planning/sutra-spec/ram-pointers.md`) — NOT a Sutra `dict<int,int>` array. This
moots the array blocker (the broken `dict<int,int>`) for the machine entirely.

## What this fixes — measured

The 11:30 milestone found that opcode dispatch failed because a **loop-carried**
state var compared to a literal (`pc == 2`) misfired. The RAM model sidesteps it:
the dispatched value is read **fresh from RAM each step** (`ramRead(cur).real()`),
and a fresh read compares cleanly against a literal.

RAM device attached (`v.ram = [make_real(10), make_real(20), make_real(99), …]`),
runtime_dim=2, llm_model="none":

| Form | Test | Expected | Measured |
|---|---|---|---|
| straight-line | `ramRead(addr).real()` for addr 0/1/2 | 10 / 20 / 99 | **10 / 20 / 99** ✓ |
| straight-line | `truth(ramRead(addr).real() == 99)` | −1 / −1 / +1 | **−1 / −1 / +1** ✓ |
| recurring-cursor step | per-step `truth(ramRead(cur).real() == 99)`, cur advances | −1, −1, +1 | **−1, −1, +1** ✓ |

So **opcode dispatch works** when the opcode is a fresh `ramRead`, both straight-line
and in the recurring-cursor (autoregressive one-step-per-call) loop.

## The required loop form

`ramRead` inside a `while_loop` + `slot int` cursor FAILS (`IndexError: ... size 0` —
the slot-carried int is not handed to `ram_read` as a proper vector). The WORKING
idiom (also `test_synchronous_ram_read_in_recur`) is a **`recurring vector` cursor +
`recur`**:

```
function vector step(scalar dummy) {
    recurring vector cur = make_real(0.0);
    int op = ramRead(cur).real();          // fresh read -> dispatches cleanly
    recur(cur + make_real(1.0));
    return make_real(truth_axis(defuzzy(op == 99)));
}
```

Called once per step (host-driven autoregressive loop), with the cursor/stack-pointer
as `recurring` substrate state and the stack/memory in RAM. **This matches the
transformer-vm's own autoregressive model** (one byte/step per token) — see
`WASM/notes/significance_and_isomorphism.md` §3. Artifact:
`experiments/iso5_substrate_dispatch/ram_dispatch.py` (the three measurements above).

## The ISO-5 RAM-based machine design (now unblocked)

- **Program + stack + locals + linear memory:** RAM cells (`ramRead`/`ramWrite`).
  The WASM input program is loaded into RAM host-side; output is appended via
  `ramWrite`. Stack pointer / pc are `recurring` substrate vectors.
- **Fetch-execute:** one `recur` step per instruction — `ramRead(pc)` the opcode,
  dispatch via fresh-read `== opcode_tag` defuzz blends, `ramRead`/`ramWrite` the
  stack, advance pc (and sp) as recurring state.
- **Still needed (real substrate work, not yet done):**
  1. **Bitwise stdlib** — `land 0xFF`, `lsl 8`, `lsr`, `lor` (byte arithmetic). Sutra
     has no bitwise operator; needs a substrate decomposition (bit vectors). The
     transpiler currently emits `UNSUPPORTED-OP` for these.
  2. **Exceptions** — `raise Exit` (halt / loop break) → a recurring `halted` flag
     that stops the recur; `failwith` → error sentinel.
  3. **Transpiler lowering** of OCaml `Array.make`/`arr.(i)`/`arr.(i) <- v` and
     `Bytes.get`/`set` → `ramRead`/`ramWrite`, and the `while`+`try` fetch-execute
     loop → the `recurring`+`recur` step form.
  4. **Submodule** `WASM/replication_target/transformer-vm` — its URL is missing from
     the parent `.gitmodules` after the subtree merge (`git submodule update --init`
     → "No url found"); the test-program `.txt` data needs the submodule re-wired
     before byte-exact ground-truth comparison.

## Bottom line

The array blocker is gone (memory = RAM), and the dispatch blocker is gone (fresh
`ramRead` dispatches cleanly). The RAM-based fetch-execute machine is a viable,
verified path. Remaining work is the bitwise stdlib, exception lowering, the
array→RAM transpiler lowering, and the submodule re-wire — each tracked above.
