# Non-numeric (string) record fields are blocked on axon string round-trip

> **RESOLVED 2026-06-08 (Emma):** strings are NOT axon fillers — axon fillers are
> numbers/vectors only; strings are separate codepoint-array values. The round-trip
> collapse below is **by design**, so string record fields are UNSUPPORTED-by-design (not
> a bug to fix). See `planning/open-questions/axon-string-filler-roundtrip.md`. The
> measurement record below stands.

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

## Sharper measurement: it is NOT bundle crosstalk

Reduced to raw Sutra, a **single-field** axon string round-trip still fails:

```
function string one() { Axon a; a.add("k", "Hi"); return a.item("k"); }
function string main() { return one(); }
// runs on the substrate -> 72.0   (NOT "Hi"; 72 = codepoint of 'H', the first char)
```

A single field means `add` = `bind(R_k, F)` with **no bundle superposition**, and `item`
= `unbind(R_k, …)` is its exact inverse — so this is *not* the multi-field crosstalk the
numeric finding hit. The string filler itself does not survive store→load: it comes back
decoding to its **first codepoint as a number** (72 = 'H'). So either the string is stored
as a single real-axis scalar (its first codepoint) by `add`, or `bind`/`unbind` does not
preserve the multi-codepoint synthetic-axis structure of a String filler, or the
String-typed read collapses it. The axon vision treats strings as first-class fillers
([[project_axon_ipc_payload_is_strings_and_numbers]]: "string-flag codepoint arrays +
complex-hypervector numbers"), so this is a **spec/implementation contradiction**, not just
a missing transpiler feature — surfaced for Emma (`planning/open-questions/`, A.0).

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
