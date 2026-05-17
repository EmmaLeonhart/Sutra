> **VERDICT — RESOLVED** (task #15 triage 2026-05-16, banner stamped 2026-05-17; authoritative table: `planning/open-questions/README.md`). Shipped 2026-05-10, commit `6d25f232` (per-key permutation inside `axon_add`/`axon_item` only; free-standing `bind`/`unbind` unchanged). Doc kept for the diagnostic + fix-design rationale.

---

# Axon bind needs per-key permutation for synthetic-block fillers

**Date:** 2026-05-10
**Status:** Empirical bug found + fix designed + fix shipped same day
(see `planning/findings/2026-05-10-axon-permutation-fix.md` for the
post-fix numbers).
**Reporter:** Claude (Opus) under Emma's direction
**Trigger:** Multi-program axon demo. Producer added three numbers to
an axon under three different keys; consumer recovered the **sum** of
all three for every key, instead of the per-key value.

## What the spec says

`planning/sutra-spec/axons.md` — "axons can carry values of any kind;
on the substrate they all become vectors." Implementation in
`_TorchVSA.axon_add`:

```python
if isinstance(value, (int, float)):
    value = self.make_real(float(value))
return axon + self.bind(key_vec, value)
```

So a scalar is wrapped via `make_real`, which puts the value at
`synthetic[AXIS_REAL]` (position 0 of the synthetic block).

## What actually happens

The bind rotation is **block-diagonal: Haar in the semantic block,
identity in the synthetic block** (per the documented design at
`codegen_pytorch.py` line 192). This means:

1. `make_real(42)` produces a vector with semantic block all zero
   and `synthetic[0] = 42`.
2. `bind(R_x, make_real(42))` rotates the (zero) semantic block and
   leaves `synthetic[0] = 42` because rotation is identity there.
3. Bundle is sum, so `synthetic[0]` of the bundled axon = sum of all
   added scalars (42 + 100 + (-7) = 135 in the empirical test).
4. `axon_item(a, "x")` does `unbind(R_x, axon)`, which is also
   identity in synthetic, so `recovered[synthetic[0]] = 135` — for
   every key.

Empirical reproduction:

```
--- Three numbers in axon ---
axon real component (raw sum) = 135.0000  (added 42+100-7=135)
recovered x = 135.0000  (expected 42)
recovered y = 135.0000  (expected 100)
recovered z = 135.0000  (expected -7)
```

The same logic applies to **strings** as fillers. `make_string` puts
codepoint values in synthetic axes; bind doesn't touch the synthetic
block; bundling sums codepoint positions across keys; unbind recovers
the sum, not the individual codepoint array.

## Why bind was designed this way

Several runtime sidecar flags live in the synthetic block and **must
survive bind/unbind round-trips intact**:
- `AXIS_LOOP_DONE = 4` — substrate-side loop completion flag
- `AXIS_PROMISE_FULFILLED = 5` / `AXIS_PROMISE_REJECTED = 6`
- `AXIS_AXON_POPULATED = 7` — distinguishes "value is genuinely zero"
  from "axon entry not yet written"

These flags are *intentionally* preserved through bind because they
ride along with values across role-binding operations. Permuting
them per-role would scramble the loop-completion machinery and the
promise-channel machinery.

So the fix can't just "rotate the synthetic block too." We need a
fix that preserves these sidecar flags through normal bind/unbind
while still giving per-key separation for axon-stored fillers.

## The fix (Emma 2026-05-10)

Per Emma's permutation observation: **binding is the right primitive
for embeddings; permutation is the right primitive for synthetic-axis
fillers.** The two compose cleanly.

Add a separate axon-specific bind path that permutes a slice of the
synthetic block per key, alongside the existing rotation:

```python
def _axon_bind(self, key_vec, value):
    # Apply existing rotation (identity in synthetic block).
    rotated = self.bind(key_vec, value)
    # Apply per-key permutation of the *non-canonical* synthetic
    # block (positions SLOT_BASE..synthetic_dim-1). Canonical axes
    # 0..7 are NOT permuted — they're the sidecar flag region.
    perm = self._axon_permutation_for(key_vec)
    return self._apply_synthetic_permutation(rotated, perm)
```

Crucially: the AXIS_REAL position (where `make_real` writes) IS one
of the canonical axes today (`AXIS_REAL = 0`). So `axon_add` for a
scalar can't use `make_real` directly — it has to put the scalar in
a permutation-eligible position.

Two-part change:
1. `_axon_bind` / `_axon_unbind` apply per-key permutation on the
   non-canonical synthetic-block slice.
2. `axon_add` for scalar fillers wraps the value into a
   permutation-eligible position (the first non-canonical synthetic
   axis, then permutation moves it per-key).

Free-standing `bind` / `unbind` (used for the rotation hashmap, loop
state binding, etc.) keep current behavior. Only `axon_add` /
`axon_item` route through the new path.

## What this preserves

- Sidecar flags (LOOP_DONE, PROMISE_*, AXON_POPULATED) survive bind/
  unbind unchanged because they're not in the permuted region.
- Existing rotation-hashmap / loop / promise behavior unchanged.
- Vector-typed axon fillers still recover correctly (the permutation
  on a near-zero synthetic block is a no-op modulo numerical noise).
- New: scalar and string axon fillers round-trip per key.

## What this does NOT solve

- The crosstalk between bundled fillers when they DO collide at
  permuted positions. With `synthetic_dim - SLOT_BASE = 92`
  permutation-eligible positions and N keys bundled, the expected
  number of collisions per recovered key is ~N/92. So small bundles
  recover cleanly; large bundles still get noise. This is the
  HRR/permutation-binding capacity story (Plate 1995, Kanerva MAP);
  no architecture pushes it to zero, just lower noise floor.

- Cross-program agreement: the per-key permutation must be
  deterministic from the role vector hash (same way the rotation
  cache is). Two programs using the same embedding model will
  compute the same permutation for the same key string, so axons
  round-trip across the wire. Same precondition that already exists
  for rotation binding.

## Decision

Build it now (Emma 2026-05-10: "Let's document the limit and then
build it now. Let's do that. Let's do it quickly."). Implementation
notes in the matching finding doc once it ships.
