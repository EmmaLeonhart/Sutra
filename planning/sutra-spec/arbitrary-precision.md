# Arbitrary-precision integers — spec sketch (Option A)

**Status:** DRAFT. Top-level path AND all four sub-decisions locked per Emma sweep 2026-05-28 (Q3 + sub-Q1..Q4):

- Path: **Option A** — associative-scan substrate intrinsic for parallel carry propagation (Hillis-Steele / Blelloch).
- Sub-1 BigInt typing: **new class `BigInt`** with operator overloads.
- Sub-2 Digit layout: **radix-10** (matches `parse_int2.su` and print-back; 1 ASCII char ↔ 1 digit).
- Sub-3 Maximum width: **compile-time constant `BigInt<MAX>`** (type-parameter; codegen allocates the digit block to fit).
- Sub-4 Integer-division primitive: **new substrate intrinsic `_int_div_mod(x, m) -> (q, r)`**.

The remaining work is implementation: build the substrate intrinsics (`_digit_array_add`, `_int_div_mod`), the `BigInt<MAX>` parser/dispatcher surface, the radix-10 digit-block layout, and the print/parse round-trip. The four sub-decisions below stay in this doc as historical context for "why this is the shape" — but they are no longer open.

## Goal

Unbounded-precision exact integers on the Sutra substrate, with `add`, `subtract`, `multiply`, `compare`, `print` (and division — see open sub-decision) running as tensor ops with no host scalar leak. Per the "every op trainable" vision and the FV paper's branchless polynomial framing, BigInt operations must dispatch to substrate-only primitives.

## The substrate representation

A `BigInt` value lives as a digit array packed into the synthetic axes of a single substrate vector. Following the `strings.md` layout pattern (synthetic-axis-encoded codepoint arrays), positions 0..N−1 of the digit block hold the digit values (in the chosen radix); a length axis records the number of valid digits. The full layout binds to:
- semantic block: zero (BigInt has no LLM-codebook meaning),
- synthetic block: digits (positions 0..max_digits−1) + length + sign,
- truth/real/imag/etc.: as defined per the substrate's normal axis allocation.

The actual digit layout (radix-10 vs radix-2^k vs signed-digit redundant) is open sub-decision #2 below.

## The new substrate intrinsic: `_digit_array_add`

The intrinsic implements add-with-carry across the digit array via parallel prefix scan. Signature (PyTorch backend):

```
def _digit_array_add(self, a: Tensor, b: Tensor, max_digits: int, radix: int) -> Tensor:
    """
    Add two BigInt-shaped substrate vectors. Both `a` and `b` are full
    substrate vectors with their digit blocks at synthetic[DIGIT_BASE:
    DIGIT_BASE + max_digits].

    Implementation: Hillis-Steele parallel prefix scan over the digit
    positions. Per-position pairwise sum + carry-out, then log2(max_digits)
    steps propagating carries. O(log N) parallel depth, O(N log N) total
    work, every step a tensor op.

    Returns a fresh substrate vector with the resulting digit block, length,
    and sign axes populated. The runtime saturates at max_digits (overflow
    drops the top digits) rather than raising — same posture as String
    overflow.
    """
```

Why this is the right shape for the FV paper. Each operation in the scan is a closed-form tensor op (element-wise add, mod, div by radix, compare, scatter). The compiled graph has no path enumeration; the "carry propagation" is `log2(max_digits)` straight-line scan steps, each a polynomial in the input digits. Range-soundness reduces to per-step polynomial bounds (each step keeps digits in `[0, radix)` by mod-radix; carries are in `{0, 1}` by construction). Termination is structural (fixed `log2(max_digits)` steps, not a runtime convergence loop).

## Sub-decisions — all locked 2026-05-28

The four sub-decisions are recorded with their chosen options first; the alternatives are kept beneath each one as historical context.

### Sub-decision 1: BigInt typing → **new class `BigInt`** (LOCKED)

How does the language know a value is a BigInt vs a regular `int`?

- **Option 1.1:** New class — `class BigInt { ... }` with operator overloads. Parser+dispatcher route `a + b` to `BigInt.add` when types are `BigInt`.
- **Option 1.2:** Typedef on the synthetic-axis layout — `BigInt` is a structural alias for the digit-array layout, no class machinery, the operator dispatch reads the layout at runtime.
- **Option 1.3:** Implicit — any `int` that overflows the float32 exact-integer range (2^24) auto-promotes to digit-array form. (Simpler surface, harder to reason about.)
- **Option 1.4:** Explicit annotation — `int<bignum>` or similar type-parameter syntax; everything else stays float32.

### Sub-decision 2: Digit layout → **radix-10** (LOCKED)

- **Option 2.1:** Radix-10 — matches `parse_int2.su` and `print`-back; 1 ASCII char ↔ 1 digit; easiest to reason about. Density: ~3.32 bits/digit. For 256-digit BigInt: ~850 bits.
- **Option 2.2:** Radix-2^k for some k (e.g. k=8 → byte-radix, k=16, k=30 → fits in 32-bit lane with carry room). Denser, fewer scan steps. Conversion to/from base-10 print needs its own pass.
- **Option 2.3:** Signed-digit redundant (e.g. radix-10 with digits in `[-9, 9]`). No carry chain in add — add becomes truly parallel without a scan. But canonical-form conversion is its own pass.

### Sub-decision 3: Maximum width → **compile-time constant `BigInt<MAX>`** (LOCKED)

- **Option 3.1:** Compile-time constant — `BigInt<MAX>` where MAX is a type parameter; the codegen allocates the digit block to fit.
- **Option 3.2:** Runtime parameter — every program has a `_VSA.max_digits` knob; can be changed at boot.
- **Option 3.3:** Fixed at substrate construction — `synthetic_dim` already caps it; max_digits = some fraction of `synthetic_dim`.

### Sub-decision 4: Integer-division primitive → **new substrate intrinsic `_int_div_mod(x, m)`** (LOCKED)

`sum / radix` and `sum mod radix` are needed inside the scan. Two paths:

- **Option 4.1:** Use `modulus.su`'s existing `rotation_mod` / `fmod`. They're literate Sutra; the inner step would call them.
- **Option 4.2:** New substrate intrinsic `_int_div_mod(x, m) -> (q, r)`. Smaller surface, single op.
- **Option 4.3:** Inline lookup table for small `radix` (e.g. radix-10 → 100-entry lookup of `(x%10, x/10)` for x in `[0..99]`).

## Next implementation steps (sub-decisions all locked)

1. **Add `BigInt<MAX>` parser/type-check surface.** Type parameter is a compile-time integer literal; parser accepts `BigInt<256>` syntax; type-checker treats `BigInt<MAX>` as a class extending the digit-array layout.
2. **Add the `_int_div_mod(x, m)` substrate intrinsic.** Two-output substrate op: `(q, r) = (x // m, x % m)`. Substrate-pure; both outputs are 0-d tensors. Adds one ABI entry.
3. **Add the `_digit_array_add(a, b, max_digits, radix=10)` substrate intrinsic.** Hillis-Steele parallel scan; per-position pairwise sum + carry-out via `_int_div_mod(sum, 10)`, then `log2(max_digits)` scan steps propagating carries. All tensor ops; saturate at `max_digits` (overflow drops top digits, no raise).
4. **Wire `BigInt + BigInt` to dispatch to `_digit_array_add`.** Operator overload in the `BigInt` class; same shape as the existing `int + int` dispatch.
5. **Worked example test:** `add_bigint("99999", "1") = "100000"` showing carry propagation step-by-step. Plus a 100-digit case for canonical-form behavior.
6. **Range-soundness proof obligation:** per-step polynomial bounds keep digits in `[0, 10)`; carries in `{0, 1}` by construction.
7. **Termination obligation:** `log2(max_digits)` fixed scan steps; no convergence loop.
8. **Wire into the FV paper's §3 obligation framework** once the intrinsics ship.

## Cross-refs

- `planning/open-questions/arbitrary-precision-digit-array.md` — the dossier (now showing the locked top-level choice).
- `planning/findings/2026-05-27-arbitrary-precision-parser.md` — `parse_int2.su` substrate-pure bounded parser.
- `planning/sutra-spec/strings.md` — synthetic-axis-encoded codepoint arrays (the layout pattern this borrows).
- `planning/sutra-spec/control-flow.md` — soft-halt loop (the Option B fallback this avoids).
- `examples/parse_int2.su` — the shipped bounded piece.
- `paper/formal-verification/paper.md` §3 — obligation framework this will plug into.
