# Non-numeric (string) record fields are blocked on axon string round-trip

**Date:** 2026-06-08
**Context:** OCaml frontend completeness — non-numeric record fields (`type person =
{ age : int; name : string }`, read `p.name`). Attempted; hit a deeper blocker; reverted
the speculative code per the integrity rule (don't ship a half-feature that doesn't work
end-to-end). This is the measured negative result + the precise remaining work.

## What was tried

Added a field-type map (field name → numeric/non-numeric, from the `type` declaration)
so `field_get_expression` emits `realvec(p.item("f"))` for numeric fields (recover the
real-axis number) but a plain `p.item("name")` for string fields (a string is a
codepoint array on synthetic axes; `realvec` would zero it). The lowering came out
correct in isolation:

```
function String get_name(Axon p) { return p.item("name"); }
function String main() { return get_name((mk(30, "Alice"))); }
```

(with `mk (a:int) (n:string) : person = { age=a; name=n }`).

## The measured blocker

Run on the substrate, `main()` returns **`65.0`, not `"Alice"`** — even with explicit
`string` annotations on the constructor param and `main`'s return (so it is NOT just a
type-inference gap). `65` is the codepoint of `'A'`: the string filler stored via
`_record.add("name", n)` does not round-trip back through `_record.item("name")` — it
collapses toward a single real-axis scalar.

This is the **axon filler decode** issue, the string analogue of the numeric one
(`2026-06-05-axon-field-reads-need-real-projection.md`): an axon's role-filler
bind/bundle preserves a *number* well enough that the real-axis projector (`realvec`)
recovers it, but a *string* (a multi-codepoint synthetic-axis array) is not recovered by
any projection — the bundle superposition does not cleanly return the stored codepoint
array. Numbers have `realvec`; strings have no clean inverse from the axon filler.

## Why reverted (not shipped behind a flag)

The field-type-aware read is correct in direction but enables nothing that works:
string record fields do not round-trip regardless, so shipping the field-type map would
add a speculative path with no functioning end-to-end use — exactly the vibe-coded
"half-built path that later gets miswired" hazard CLAUDE.md warns against. Numeric record
fields already work (unchanged: `realvec`); they are the supported scope.

## Remaining work (precise), for when this is picked up

1. **Axon string round-trip** (the real blocker): make `axon.add("f", str)` /
   `axon.item("f")` recover a string filler — i.e. an axon filler decode for strings, the
   string analogue of `realvec` for numbers. This is a substrate/axon-spec question
   (how a codepoint-array filler survives bundle superposition), NOT a transpiler fix.
   Likely needs the axon to store string fields un-bundled, or a per-field key that
   unbinds the codepoint array cleanly. Confirm the intended mechanism against
   `planning/sutra-spec/axons.md` before building.
2. **Then** the transpiler pieces (small, on top of (1)): the field-type-aware read
   (re-add the `_FIELD_TYPES` map), string param-type inference from record fields
   (so `mk a n` types `n : string` without annotation), and string return-type
   propagation (so `main` whose body is a `string`-returning call is typed `String`).

Numeric record fields and record/tuple literals in argument position remain the
supported, substrate-verified scope; string fields are blocked at the axon layer (1).
