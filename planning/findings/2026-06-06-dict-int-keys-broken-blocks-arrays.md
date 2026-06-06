# `dict<int,int>` is broken — blocks the substrate-faithful array mapping (ISO-5 item 4)

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

## Status of ISO-5 transpiler items after this tick

Done & substrate-verified: top-level value bindings, sequence + ref mutation,
`while`→substrate loop (scalar-ref), char→codepoint / string→`String` literals,
closed nested-function hoisting. The ISO-5 reference now shows: 7 nested-fn (all
**closure captures** — a distinct blocker, closure conversion not supported), 4
list, 4 array-get (this blocker), 3 try, 2 while-body (need arrays/try first),
2 tuple, 2 let, 2 ctor, 1 match-guard. Arrays and closures are the two structural
blockers gating the machine core; both are now precisely documented rather than
faked.
