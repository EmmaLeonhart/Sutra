# Per-key permutation fixes axon round-trip for synthetic-axis fillers

**Date:** 2026-05-10
**Author:** Claude (Opus) under Emma's direction
**Open question this closes:** `planning/open-questions/axon-bind-needs-permutation-for-synthetic-fillers.md`
**Implementation:** `_TorchVSA._axon_permutation_for` /
`_axon_permute_synthetic` / `_axon_unpermute_synthetic` plus rewrites
of `axon_add` / `axon_item` in `codegen_pytorch.py`.

## What the bug was

The axon implementation wraps Python scalars via `make_real` (puts
the value at `synthetic[AXIS_REAL]`) and Python strings via
`make_string` (puts codepoints at `synthetic[_string_axis(k)]`),
then calls `bind(role, value)`. But `bind` is **identity in the
synthetic block** by design — the rotation operates only on the
semantic block. So:

- Bundling `axon_add(a, "x", 42)` + `axon_add(a, "y", 100)` +
  `axon_add(a, "z", -7)` produced an axon with `synthetic[0] = 135`
  (the sum) and rotated-but-cancelling-on-average noise in semantic.
- `axon_item(a, "x")` returned `135` for every key, not `42`.

Same logic broke string fillers: codepoint positions accumulated
across all bundled strings.

Empirical confirmation pre-fix:

```
recovered x = 135.0000  (expected 42)
recovered y = 135.0000  (expected 100)
recovered z = 135.0000  (expected -7)
```

## The fix

Per Emma 2026-05-10: **bind is the right primitive for embeddings;
permutation is the right primitive for synthetic-axis fillers.** The
two compose. Add per-key permutation of the synthetic block on top
of the existing rotation, applied **only inside `axon_add` /
`axon_item`** so free-standing `bind` / `unbind` stay unchanged
(loop carriers, rotation hashmap, promise channels are untouched).

Implementation shape:

```python
def _axon_permutation_for(self, role_vec):
    # Deterministic from role hash, cached.
    rng = np.random.RandomState(self._role_hash(role_vec) ^ 0xA50A_F00D)
    perm = rng.permutation(self.synthetic_dim)
    return torch.as_tensor(perm, device=self.device)

def axon_add(self, axon, key, value):
    # ... wrap scalars via make_real, strings via make_string ...
    rotated = self.bind(key_vec, value)
    perm = self._axon_permutation_for(key_vec)
    return axon + self._axon_permute_synthetic(rotated, perm)

def axon_item(self, axon, key):
    perm = self._axon_permutation_for(key_vec)
    unpermuted = self._axon_unpermute_synthetic(axon, perm)
    return self.unbind(key_vec, unpermuted)
```

The permutation cache uses `key ^ 0xA50A_F00D` so the permutation
draw is uncorrelated with the rotation cache draw at the same
role hash.

## Post-fix numbers

```
--- Three numbers in axon (after permutation fix) ---
  recovered x = 42.0000   (expected 42)   ✓
  recovered y = 100.0000  (expected 100)  ✓
  recovered z = -7.0000   (expected -7)   ✓

--- Vector filler regression check ---
  cos(recovered animal, dog) = 0.6847  (expected high; was 0.40 pre-fix)
  cos(recovered animal, cat) = 0.3914  (expected low — crosstalk only)

--- Single string in axon ---
  string_to_python = 'alice'   (expected alice) ✓
  string_length    = 5         ✓

--- Mixed: 2 numbers + 1 string in axon ---
  recovered count = 42.0000           ✓
  recovered rate  = -3.1400           ✓
  recovered name (first 5 chars) = 'alice'   ✓
```

Numbers round-trip exactly. Vectors actually got *better* margin
because the permutation also helps separate semantic-block crosstalk
between vector fillers when there's any synthetic content. Mixed
axons (numbers + strings + vectors) work as expected.

## Known follow-on (not part of this fix)

`string_to_python` over-reads when there are multiple strings in the
same axon. The permutation places each string's codepoints at the
correct positions for its key, but the OTHER strings' codepoints
also land at scattered positions for this key, so positions past the
recovered string's end have crosstalk codepoints. The current
`string_to_python` reads `string_max_length` characters and includes
them all (including the leaked tail). Two-string-axon recovery shows
the leading "alice" / "beta" correctly, then garbage tail.

Single-string axons (the common case) work cleanly because there's
no other string to leak from.

The fix is a length sidecar at decode time — either store the
string's true length in a synthetic axis that survives bind/unbind,
or detect the first low-confidence position from the back. Logged
but not done in this commit.

## What this preserves

- **Loop carriers** — loops carry their own state vectors directly,
  not as axon entries. `bind` / `unbind` are unchanged for them.
- **Rotation hashmap** — uses `bind` / `unbind` directly, not
  through `axon_add` / `axon_item`. Unchanged.
- **Promise channels** — promises are passed as standalone vectors
  with `AXIS_PROMISE_*` flags. The flags survive any `bind` /
  `unbind` round-trip cleanly because that path is unchanged. If a
  promise is ever stored INSIDE an axon, the flag's exact survival
  becomes statistical (per-key permutation can scatter it). Not a
  pattern we currently use.
- **Existing axon vector recovery** — vector fillers still recover
  correctly (the multi-program axon demo still passes with margins
  +0.20, +0.20, +0.26).
- **All 34 + 20-subtest TS-transpiler + transcendental tests** —
  green.

## Connection to the broader axon framing

Per the 2026-05-10 user reframings:
1. **Axons are serialization** — binary serialization that lives on
   the substrate. The producer and consumer don't need the same
   runtime representation.
2. **OS IPC payload is strings and numbers**, not LLM embeddings.

Without this fix, axons could not actually serve as serialization
for the dominant OS payload types. With it, they can. This is what
makes mixed-type axons (numbers + strings + vectors keyed together)
a real wire format rather than an aspiration.
