# `dict<int,int>` is broken — blocks the substrate-faithful array mapping (ISO-5 item 4)

> **RESOLVED 2026-06-13 (Emma's design).** Integers get a SEPARATE dict object
> backed by preallocated synthetic-space slots (one dimension per integer key);
> the compiler routes `dict<int,int>` to `_VSA.int_dict_{new,set,get}` at compile
> time (key type statically scalar). Each key addresses its own slot — no
> rotation, no crosstalk. Addressing is substrate-pure (round + one-hot `==`, no
> host `.item()`). **Verified exact** (`tests/test_int_dict.py`, 5/5): single
> entry = 42; the 3-entry case that returned 148 now reads 42/7/99 per key;
> runtime/variable key + overwrite = 77; absent key = 0; 4 distinct slots sum to
> 100. The body below is the original diagnosis + the measurement that drove the
> design.

**Date:** 2026-06-06
**Context:** ISO-5 needs OCaml arrays (`Array.make` / `arr.(i)` / `arr.(i) <- v`,
e.g. the machine's 256-int `locals`). Sutra's collection options are `dict<K,V>`
(runtime rotation-hashmap, substrate), `list<T>` (compiles to a **Python host
list** — not substrate-faithful, wrong for ISO-5), and `map<K,V>` (compile-time
literal table). The substrate-faithful target is `dict<int,int>` with
`hashmap_get`/`hashmap_set`.

## Measured defect

```sutra
function int main() {
    dict<int, int> a;
    a[0] = 42;
    return a[0];
}
```

`sutra_compiler --run` crashes:

```
File "…", line 504, in hashmap_set
File "…", line 408, in bind
File "…", line 388, in _rotation_for
File "…", line 371, in _role_hash
AttributeError: 'int' object has no attribute 'detach'
```

The dict subscript lowers the integer key/value straight into
`hashmap_set(acc, 0, 42)` as raw Python `int`s. `_role_hash` expects a **tensor**
(it does `role_vec.detach().cpu()...`). The rotation-hashmap was specified and
exercised only for `dict<vector,vector>` (types.md §dict uses
`dict<vector,vector> concept_memory`); the scalar-keyed/valued path was never
wired — scalar keys/values are not lifted to substrate vectors before hashing.

## Why this is not a quick transpiler fix

This is a **core-compiler** gap (dict subscript codegen + the hashmap runtime),
not a `sutra-from-ocaml` issue. A correct fix must:

1. Lift a scalar key to a substrate vector before `_role_hash` (numbers in Sutra
   are vectors — `make_int`/`make_real`), and lift the value, and decode the
   value back to a scalar on read.
2. **Verify exact read-what-you-wrote at array scale.** Open concern, unmeasured:
   `_rotation_for` is "Haar-uniform in the semantic block, **identity in the
   synthetic block**", and numbers live in the synthetic axes — so binding a
   number value under a key rotation may leave its synthetic-axis-encoded
   real part un-rotated, and bundling many entries could superpose those real
   parts (crosstalk). Whether `dict<int,int>` returns exact values for, say, 16+
   distinct integer keys is **not established** and must be measured, not assumed
   (CLAUDE.md §"signal-separation audit").

Per the work-loop hard rails ("don't implement what you don't fully understand —
write the spec/queue item instead"), this is recorded as a blocker rather than
hacked. The OCaml array item stays UNSUPPORTED until the scalar-dict path is wired
and its exactness measured.

## MEASURED root cause (2026-06-13) — the crosstalk concern is now confirmed

Lifting the scalar key/value to substrate vectors (`make_int`) and round-tripping
through `hashmap_set`/`hashmap_get` directly (runtime probe, `runtime_dim=868`):

| entries stored | read key 0 | read key 1 | read key 2 |
|---|---|---|---|
| 1 (k0→42) | **42.0** ✓ | — | — |
| 3 (k0→42, k1→7, k2→99) | 148.0 | 148.0 | 148.0 |

Every key returns **148 = 42 + 7 + 99 = Σ of all stored values**. This is the §2
concern, now measured, not hypothesized: `_rotation_for` is **identity in the
synthetic block**, and a scalar int value lives entirely on the synthetic real
axis, so `bind(key_vec, val_vec) = Q_key @ val_vec` leaves the value's real part
**un-rotated** regardless of key. The accumulator's real axis is therefore the
plain sum of every value, and `unbind(key, acc)` (also identity on the synthetic
block) returns that sum for **any** key. So:

- **Single-entry** `dict<int,int>` is exact (no other entry to superpose).
- **Multi-entry** returns Σ-of-all-values for every key — silently wrong.

So "lift scalars to vectors" stops the crash but ships a wrong answer for the
real (array) use case — **worse than the crash**, which is at least honest. The
rotation-hashmap is structurally right only for `dict<vector,vector>` (values in
the *semantic* block, which the rotation scrambles + recovers). It cannot
address-separate values that live in the synthetic block.

## The fix is a design decision (→ Emma, queue.md A.0)

Three substrate-faithful options, none a mechanical fix:

1. **Route scalar-keyed dicts to a per-instance RAM array.** `dict<int,int> a`
   becomes its own fixed-size substrate tensor; `a[k] = v` → a RAM write at the
   rounded int address, `a[k]` → a RAM read. EXACT (RAM stores clean
   number-vectors — the ISO-5 inline `ramRead`/`ramWrite` surface already proves
   this) and per-instance. This is the array semantics the OCaml port actually
   needs. **Recommended.** Cost: dict subscript codegen must dispatch on
   scalar-key type to the RAM path, and each dict needs its own RAM region/tensor
   (the global `_VSA.ram` device is single-instance).
2. **Embed values into the semantic block** so the key rotation scrambles them —
   but exact int decode then needs a codebook + has VSA capacity limits (~1/√N
   SNR), so it is not exact at array scale either.
3. **Keep `dict<int,int>` UNSUPPORTED**; require `dict<vector,vector>` for the
   hashmap and a distinct array type for integer-keyed storage.

Choosing the mechanism changes what `dict<int,int>` *means* on the substrate, so
it is Emma's design call, not an agent's to invent (CLAUDE.md §"never invent a
thing Emma implies exists"). Surfaced in queue.md A.0.

## Status of ISO-5 transpiler items after this tick

Done & substrate-verified: top-level value bindings, sequence + ref mutation,
`while`→substrate loop (scalar-ref), char→codepoint / string→`String` literals,
closed nested-function hoisting. The ISO-5 reference now shows: 7 nested-fn (all
**closure captures** — a distinct blocker, closure conversion not supported), 4
list, 4 array-get (this blocker), 3 try, 2 while-body (need arrays/try first),
2 tuple, 2 let, 2 ctor, 1 match-guard. Arrays and closures are the two structural
blockers gating the machine core; both are now precisely documented rather than
faked.
