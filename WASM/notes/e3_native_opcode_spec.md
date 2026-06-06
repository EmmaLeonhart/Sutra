# E3 spec — integrate a native saturating-add opcode end-to-end

Goal: add `i32.sat_add_u` (unsigned saturating add, `min(a+b, 0xFFFFFFFF)`) as a
**native opcode** the analytic transformer executes directly — not lowered — and run
a program using it end-to-end vs a reference trace (G2). Spec-first per the hard
rails (don't blind-hack the analytic construction).

## Feasibility (corrected)

A first worry: the machine emits one result byte per token (byte 0 → 3) with a
forward carry, so saturation that depends on the *final* (high-byte) overflow seemed
impossible to apply to the already-emitted low bytes. **That worry is wrong.** The
construction has the **full 32-bit operand values** available as single quantities —
`stack_top_value`, `stack_second_value` (built via the `store_value` lookup;
`wasm/interpreter.py:397-405`), already used by the comparison ops
(`a_gt_b_u = stepglu(one, stack_second_value - stack_top_value - 1)`, line 449). So
the overflow flag can be computed **up-front, before any byte is emitted**, and each
output byte saturated by it. A native single-pass saturating-add opcode is therefore
feasible.

(General rule this clarifies: an op can be native/single-pass if each output byte is a
function of the input bytes at position ≤ k plus a forward carry, OR of the full
operand values which the machine already exposes. Ops needing the *full result's*
high bits to alter low bits are fine **iff** that dependency is computable from the
full operand values up-front — which saturating add is.)

## The byte semantics

Let `a = stack_second_value`, `b = stack_top_value` (full u32). Define
`overflow = stepglu(one, a + b - (1 << 32))` (1 iff `a + b ≥ 2³²`). Then, per byte:

```
sat_add_byte = (1 - overflow) * add_byte + overflow * 255
             = add_byte + reglu(255 - add_byte, overflow)        # DSL form
result_carry = (1 - overflow) * add_carry                        # no carry once saturated
```

`add_byte`/`add_carry` already exist (`interpreter.py:440-442`) — reuse them.

## Integration points (files to change — all in the submodule, local only)

1. **`wasm/reference.py`** (the spec + Rust/OCaml isomorphs): add an `i32.sat_add_u`
   handler — `bv=pop; av=pop; result = min(av+bv, 0xFFFFFFFF); push`; token_count += 5;
   trace bytes like i32.add. *Also add to `iso/rust` + `iso/ocaml`* to keep the
   isomorphs in lockstep (and re-run `scripts/iso_equiv.sh`).
2. **`wasm/interpreter.py`** — the analytic construction:
   - Register the opcode in the opcode table / `op_dot` vocabulary (so `op_dot(
     "i32.sat_add_u")` resolves) and give it `stack_delta = -1`, `is_write`/
     `store_to_stack` like i32.add (it pops 2, pushes 1, 4-byte result).
   - Add `overflow` (from full values, above).
   - Add `+ reglu(sat_add_byte, op_dot("i32.sat_add_u"))` to `result_byte`
     (line 510) and `+ reglu(add_carry, op_dot("i32.sat_add_u") - overflow…)` style
     term to `result_carry` (line 540). Mirror i32.add's structure exactly, scaled by
     overflow.
3. **`compilation/compile_wasm.py` / opcode decoding** — map a chosen WASM byte (or a
   custom intrinsic, e.g. a recognised call to `__sat_add_u`) to the new opcode so a C
   program can emit it. (Simplest: a tiny C test that uses an inline intrinsic the
   compiler lowers to this opcode, or hand-write a `.txt` program.)
4. **A test program** (`examples/sat_add.c` or a hand-built `.txt`) exercising
   saturating add at and around the overflow boundary (e.g. `0xFFFFFFF0 + 0x20`,
   `1 + 2`).

## Verification (G2)

- `uv run wasm-reference` on the test program → reference trace.
- `uv run wasm-build` (MILP + weights with the new opcode) → `uv run wasm-run` the
  test program through the C++ engine; assert PASS (token-for-token vs reference).
- Re-run the existing 6 programs to confirm **no regression** (the new opcode term is
  gated by `op_dot("i32.sat_add_u")`, zero for all existing ops, so it must not
  perturb them — verify, don't assume).
- Re-run `scripts/iso_equiv.sh` (Rust/OCaml updated) → still ISO_EQUIV_OK.

## op_dot vocabulary — RESOLVED (E3a, verified)

The dispatch vocabulary is **fully extensible** (checked numerically,
`scripts/wsl_check_opdot.sh`):
- `interpreter.py` defines **64** dispatch points (all on `x²+y²=32045`); `OPCODES`
  uses **36** of them (`OPCODE_POINT = {op: points[i] for i,op in enumerate(OPCODES)}`),
  so **28 are spare**.
- `op_dot(op)` detects op P iff every distinct used pair has `P·Q ≤ 32043` (so the
  `stepglu` indicator is strictly 0 off-match; match gives `P·P − 32044 = 1`).
- **Max pairwise dot across ALL 64 points is 32037 ≤ 32043** — so separation holds for
  *any* subset, including 37, 38, … opcodes. Adding `i32.sat_add_u` as opcode #37
  (next spare point `points[36]`) is clean.

To add the opcode: append to `OPCODES` (fresh WASM byte + auto-assigned next point),
add its `STACK_DELTA`/`STS_OPS` membership, and the `result_byte`/`result_carry`
terms above. No collision risk on dispatch.

## Remaining risks / open questions

- **MILP/scheduling.** A new gate adds dims; the MILP should absorb it, but d_model /
  layer budget may shift. Verify the build still solves and runs.
- **MILP/scheduling.** A new gate adds dims; the MILP should absorb it, but d_model /
  layer budget may shift. Verify the build still solves.
- **Relationship to the learned op.** This native op is *constructed* (exact, by
  hand). The learned/crystallized `sat_add_u` (E1/E2) is the *gradient-discovered*
  version of the same function; E3 is the integration of the construction. A nice
  follow-up: show the learned op, once crystallized, drops into this same slot.

## Recommendation

Feasible but it is real surgery in the analytic construction; the gating
(`op_dot`) vocabulary is the part to understand first. Do it on a branch of the
submodule (local only — we don't push to Percepta). If the `op_dot` assignment turns
out to be fixed/closed, fall back to **compile-time lowering** (`sat_add` → `add` +
overflow-compare + `select`), which needs no construction change — but that is not a
"native opcode," so prefer the native path if the vocabulary is extensible.
