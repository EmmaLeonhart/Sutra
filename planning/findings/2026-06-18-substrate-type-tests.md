# What a type test means on a substrate where everything is a vector (Elixir `is_integer` etc.)

**Date:** 2026-06-18 (queue §0.6); **String/number subset SHIPPED 2026-06-19; is_axon REVERTED
as a negative result.** **Outcome: `is_binary`/`is_bitstring`→`is_string_truth` and
`is_number`→`is_number_truth` (= NOT-a-String) lower for Elixir AND Erlang;
`is_list`/`is_map`/`is_tuple` do NOT lower (need an axon tag the substrate can't carry without
corrupting axons); `is_integer`/`is_float` remain unrepresentable.**

## RESOLUTION (2026-06-19) — String/number subset shipped; `is_axon` is a NEGATIVE RESULT

What ships: runtime predicates `is_string_truth` and `is_number_truth` (`codegen_pytorch.py` +
`codegen.py` parity, `codegen_base.BUILTINS`). Elixir lowers `is_binary`/`is_bitstring`→
`is_string_truth`, `is_number`→`is_number_truth`; Erlang lowers `is_number`→`is_number_truth`
(it EXCLUDES `is_binary` — Erlang strings are charlists, not binaries). Both predicates read the
**clean `AXIS_STRING_FLAG`**: `is_string` = `2*sflag − 1`, `is_number` = `1 − 2*sflag` (i.e.
"NOT-a-String"). Fixtures `type_test_guard` RUN == 12 for both (`kind("a")*10 + kind(5)` /
`kind(5)*10 + kind("hello")`, 2-way). Gap table: `is_string_truth` and `is_number_truth` each
separate String-vs-number with **gap 2.0** (`tests/test_type_test_gap.py`).

### Negative result: `is_axon` / `is_list` / `is_map` / `is_tuple` are NOT supported

The 2026-06-19 attempt to support them by having `axon_add` set `AXIS_AXON_POPULATED[7]` (so a
substrate `is_axon_truth` could read it) was **REVERTED** after a cascade of substrate breaches —
an axon tag cannot be carried in the vector without corrupting the axon's own contents:

1. **Flagging the real axis (`tuple_in_ctor`: 13→6).** The axon permutation scrambled the whole
   synthetic block, mapping the flag axis [7] onto the real axis [0] for some keys, so
   `realvec(axon_item(...))` read the flag's ~1.0 into the recovered number. A permutation fix
   (reserve [4,8) as fixed points) addressed *this* case.
2. **Corrupting String values in axons (`echo`: `in='hello' out='hell\x01'`).** The string codepoint
   block packs `char[4]` at `synthetic[7]`, so a String stored as an axon value lost its 5th
   codepoint when the flag overwrote [7]. A string-encoding change (skip the reserved axes)
   addressed *this* case.
3. **Thinning the nested-axon crosstalk margin (`nested_ctor_case`/`nested_ctor_let`: 16→29 on CI).**
   The permutation fix from (1) excludes 4 dims from the axon permutation, thinning the already-thin
   nested-axon bundling margin (finding `2026-06-17-nested-axon-readout-crosstalk-is-dim-dependent`).
   At `runtime_dim=256` this is clean on the dev GPU (float64-ish) but **structurally fails on CI's
   float32 CPU** (the inner axon's sum leaks fully into an outer field read), and the failure could
   not be reproduced on the dev machine. Not fixable without removing the flag.

The flag, the permutation fix, and the string-encoding change were all reverted to the pre-attempt
state (which is CI-green and stable). Supporting `is_axon` properly needs a **dedicated axon tag
that does not live in the data-carrying synthetic block** — a core encoding change (a new reserved
axis outside both the codepoint block and the permutation range, or a structured orthogonal role
basis so nested-axon reads don't crosstalk). Until then `is_list`/`is_map`/`is_tuple` emit
`UNSUPPORTED-GUARD` and `is_number` is documented as "NOT-a-String" (it does not reject axons; the
fixtures never pass one to it).

## The question

Elixir guards like `def f(n) when is_integer(n)` are TYPE TESTS. On a substrate where every
value is a vector, what does a type test mean? The queue (§0.6) asked to define this — a
tag/axis check — before building, or defer with the reason recorded.

## Measurement — what the substrate can and cannot tag

Available axis flags on a runtime vector: `AXIS_REAL`, `AXIS_IMAG`, `AXIS_TRUTH`,
`AXIS_STRING_FLAG`, `AXIS_CHAR_FLAG`, `AXIS_AXON_POPULATED`, `AXIS_LOOP_DONE`,
`AXIS_PROMISE_*`. A type test is representable iff the type corresponds to a distinguishable
tag.

**The decisive negative result — `is_integer` vs `is_float` is UNREPRESENTABLE:**

```
make_real(2)  vs  make_real(2.0)   →   ||diff|| = 0.0   (bit-identical)
make_real(2)  vs  make_real(2.5)   →   ||diff|| = 0.5
```

Int `2` and float `2.0` are the **same vector** — int/float/complex share the real/imag
synthetic-axis allocation by design (no int/float tag). So NO axis check can separate
`is_integer(2.0)` (Elixir: false) from `is_integer(2)` (true): they are the identical value
on the substrate. `is_integer` and `is_float` are fundamentally unrepresentable here.

Making them representable would require a new int/float tag in the **core** number encoding —
a language-level change to Sutra's number system (an Emma-level design decision), not a
frontend fix. Until then they cannot be lowered without faking the answer (which the
signal-separation integrity rule forbids).

## Taxonomy of Elixir type-test guards

| guard | substrate status |
|---|---|
| `is_integer`, `is_float` | **unrepresentable** — int N ≡ float N (same vector) |
| `is_number` | tag-checkable: NOT `AXIS_STRING_FLAG`, NOT `AXIS_AXON_POPULATED` |
| `is_binary`, `is_bitstring` | tag-checkable: `AXIS_STRING_FLAG` |
| `is_atom` | tag-checkable (atoms → string-flag codepoint arrays); boolean-as-atom boundary is subtle |
| `is_boolean` | tag-checkable: value lives on `AXIS_TRUTH` only |
| `is_list`, `is_map`, `is_tuple` | tag-checkable: `AXIS_AXON_POPULATED` |
| `is_nil`, `is_function`, `is_pid`, … | no substrate notion yet |

## Decision

1. **Defer `is_integer` / `is_float`** to `todo.md` with the measured reason (unrepresentable;
   needs a core int/float tag). Do NOT fake them as `is_number` — `is_integer(2.5)` would
   wrongly pass.
2. **The tag-checkable subset is real future work** (not done this session): it needs (a) a
   substrate-pure truth-returning predicate per tag — read the axis flag, scatter `2·flag − 1`
   onto `AXIS_TRUTH` (no host `.item()`), so it composes in the `defuzzy` blend; and (b) for
   `is_binary`, Elixir **string-literal-arg lowering**, which is itself currently
   `UNSUPPORTED-EXPR: string` (a separate gap) — without it an `is_binary` guard cannot be
   exercised with a measurable string argument.
3. **Honesty change shipped now:** the Elixir frontend no longer emits a call to a nonexistent
   `is_*` runtime function (which silently looked like it might work). A type-test guard now
   produces a clear `UNSUPPORTED-GUARD: <name> — <reason>` marker (→ the clause becomes
   `UNSUPPORTED-DEF`), grep-able and pointing here. See `_TYPE_TEST_GUARDS` in
   `sdk/sutra-from-elixir/sutra_from_elixir/lower.py`.

## Build recipe for the tag-checkable subset (when it is picked up)

- Add to the runtime (codegen_pytorch + codegen for parity): `is_string_truth(v)`,
  `is_axon_truth(v)`, `is_number_truth(v)` — each reads the relevant axis flag and returns a
  fuzzy vector with `2·flag − 1` on `AXIS_TRUTH` (`is_number` = `1 − 2·max(string_flag, axon)`).
- Land Elixir string-literal lowering first (so `is_binary` is measurable).
- Lower `is_binary`/`is_bitstring` → `is_string_truth`; `is_list`/`is_map`/`is_tuple` →
  `is_axon_truth`; `is_number` → `is_number_truth`. Each composes into the existing guard
  blend unchanged.
- Measurable fixture once string args land: `def kind(x) when is_binary(x), do: 1;
  def kind(x) when is_number(x), do: 2; def kind(_), do: 3` → `kind("a")=1`, `kind(5)=2`.
