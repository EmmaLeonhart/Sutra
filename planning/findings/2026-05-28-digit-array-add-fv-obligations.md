# 2026-05-28 — FV obligations for `digit_array_add` (range-soundness + termination)

Per `planning/sutra-spec/arbitrary-precision.md` "Implementation plan" steps 6 and 7 (range-soundness + termination obligations). The `digit_array_add` substrate intrinsic shipped in `2ee0fe54` (v1 N stride-1 carry-propagation steps; the v2 Hillis-Steele log2(N) form is queued). This finding documents the proof obligations the v1 runtime discharges.

## Range-soundness

**Claim.** Every digit in the working array stays in `[0, radix)` and every carry stays in `{0, 1}` at every step of the algorithm, by induction.

**Inputs.** `digits_a` and `digits_b` are 1-d tensors of length N, each element in `[0, radix)` by precondition. `radix` = 10 in the shipped path; the argument is fixed by the call site.

### Step 1 — initial pairwise sum and split

```
s = a + b           # s[i] ∈ [0, 2*radix)  since a[i], b[i] ∈ [0, radix)
c = floor(s / r)    # c[i] ∈ {0, 1}        since s[i] < 2*radix
d = s - c * r       # d[i] ∈ [0, radix)    by floor-division identity
```

The carry `c[i]` is either 0 (when `a[i]+b[i] < radix`) or 1 (when `a[i]+b[i] >= radix`). The initial digit `d[i] ∈ [0, radix)` by the floor-division identity `x = floor(x/r)*r + (x mod r)`.

### Step k — shift-and-propagate

For each of N iterations:

```
c_shifted = [0, c[0], c[1], ..., c[N-2]]
d_new     = d + c_shifted
new_c     = floor(d_new / r)
d         = d_new - new_c * r
c         = new_c
```

**Invariant going in:** `d[i] ∈ [0, radix)` and `c[i] ∈ {0, 1}` (from the previous step or from step 1).

**After `d_new = d + c_shifted`:** `d_new[i] ∈ [0, radix + 1)` because `d[i] ∈ [0, radix)` and `c_shifted[i] ∈ {0, 1}`. The maximum value `d_new[i] = radix` happens when `d[i] = radix - 1` and the incoming shifted carry is 1; this is exactly the "9 + 1" cascade case.

**After re-extracting:** `new_c[i] = floor(d_new[i] / r) ∈ {0, 1}` since `d_new[i] < radix + 1 = r + 1 <= 2r`. And `d[i] = d_new[i] - new_c[i] * r ∈ [0, radix)` by floor-division identity.

**Invariant preserved.** By induction every step ends with digits in `[0, radix)` and carries in `{0, 1}`.

### Conclusion

The output digit array contains values in `[0, radix)` only. No undefined or out-of-range values can appear. The terminal carry `c[N-1]` is dropped (overflow saturates, by design).

## Termination

**Claim.** The runtime executes exactly N steps where N is the digit-array width, then returns.

**Proof.** The runtime is:

```python
n = d.shape[0]
for _step in range(n):
    # body — all tensor ops, no break, no continue
```

- `n` is a Python int read from the input tensor's structural shape — a structural parameter per Audit #4's 2026-05-17 reclassification (not a data-dependent value).
- `range(n)` produces exactly `n` integers.
- The loop body has no `break`, no `continue`, no exception path that exits early. Every iteration runs to completion.
- Each iteration is a finite composition of tensor ops (`cat`, `+`, `floor_div`, `*`, `-`). All run in constant time per element on the substrate.

The total work is `O(N²)` element-wise tensor ops (`N` iterations × `N`-wide tensor per iteration). The v2 Hillis-Steele log2(N) form would reduce this to `O(N log N)` by combining generate/propagate signals; v1 ships the correct simpler form.

**No data-dependent branch.** The loop count depends only on the digit-array width (a structural parameter), not on any digit value. Termination is structural, not measured — the runtime cannot "fail to halt" on any input.

## Substrate purity

These obligations rest on the substrate-purity claims from `Audit.md` REAL LEAK #2 (`defuzzify_trit` fix) and the existing `int_div` / `int_mod` / `digit_array_add` runtime emit:

- No `.item()` calls inside the op body — verified by `experiments/substrate_leak_sweep.py`'s runtime-prelude scan (extended in `c270acc0`).
- No `float()` extraction of digit values — verified by inspection: every operation is a tensor op (`floor_div`, `mul`, `sub`, `cat`, `+`).
- No host scalar branch on a digit value — the `for _step in range(n)` loop branches on a structural index only.

These two FV obligations plus the substrate-purity claim discharge the safety properties an FV-checker would need to admit `digit_array_add` into the trusted base.

## What this does NOT cover

- **Range-soundness for `radix != 10`.** The runtime accepts arbitrary radix but the proof above is general (any positive integer radix works). Other radix values (e.g., 2 for binary, 16 for hex, 2^30 for word-radix BigInt) would inherit the same invariants. The shipped path is radix=10 per the BigInt spec sub-decision 2.
- **Signed BigInt.** v1 ships unsigned digit arrays. Signed BigInt (two's complement or sign+magnitude) is a v2 extension and would need its own range-soundness proof.
- **Per-step polynomial bounds in the FV paper's §3.2 style.** This finding documents the obligations at the level of "what holds at the end of step k"; wiring into the FV paper's polynomial-Kleene framework would express the same proof using polynomial range-bounding (the same shape as the `&&` / `||` connective bounds). That's planning/sutra-spec/arbitrary-precision.md step 8.

## Cross-refs

- `planning/sutra-spec/arbitrary-precision.md` — the canonical spec.
- `sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` — the runtime emit.
- `sdk/sutra-compiler/sutra_compiler/stdlib/logic.su` — the source-level intrinsic declarations.
- `sdk/sutra-compiler/sutra_compiler/stdlib/bigint.su` — the literate `bigint_add` wrapper.
- `experiments/bigint_worked_example.py` — 9-case end-to-end demonstration.
- `Audit.md` — the substrate-purity audit list (REAL LEAK #2 fixed defuzzify_trit; this shipped `digit_array_add` follows the same pattern).
- `paper/formal-verification/paper.md` §3 — the FV obligation framework this should wire into (deferred to a separate session).
