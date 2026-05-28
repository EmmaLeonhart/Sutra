# Arbitrary-precision integers: digit-array representation and add-with-carry primitive

**Opened:** 2026-05-27.
**Status (2026-05-28):** TOP-LEVEL CHOICE LOCKED — **Option A (associative-scan substrate intrinsic)** per Emma sweep Q3. The 1-2 digit substrate parser (`examples/parse_int2.su`) ships in commit `22d785db` and runs substrate-pure on CUDA. The full unbounded-precision design now proceeds along the Option A path: a new substrate intrinsic for parallel carry propagation via associative scan (Hillis-Steele / Blelloch). The four sub-decisions (BigInt typing, digit layout, max width, integer-division primitive) are still open and need Emma input before the spec doc at `planning/sutra-spec/arbitrary-precision.md` is finalized.

**Related:**
- `planning/findings/2026-05-27-arbitrary-precision-parser.md` — the bounded "first piece" that shipped + the analysis this dossier reduces to a decision.
- `queue.md` § "Formal verification — next concrete work" #2 (where the queue item lives).
- `planning/sutra-spec/control-flow.md` — the soft-halt loop primitive, candidate for the sequential path.
- `planning/sutra-spec/strings.md` — the axis-packed-sequence layout that the digit-array idea may adapt.

## The question, in one paragraph

What is the substrate representation of an unbounded-precision integer, and what is the add-with-carry primitive operating on that representation? The straightforward shape — a sequence of digits in `[0..9]`, one per slot of either an axon-keyed bundle or a synthetic-axis sequence — has two plausible implementations of `add(a, b)`: (a) a tensor-shaped associative scan that processes all carry positions in parallel, exposed as a new substrate intrinsic; (b) the existing soft-halt loop accumulating state across positions one at a time. Both compute the same result; they differ on runtime cost surface, ABI cost, and what users see at the language level.

## What ships today

`examples/parse_int2.su`:

```sutra
function int parse_int2(String s) {
    int d0 = s.string_char_at(0) - 48;
    int d1 = s.string_char_at(1) - 48;
    return 10 * d0 + d1;
}
```

Substrate-pure, fixed-width 2 digits, no carry. `parse_int2("47")` → `tensor(47., device='cuda:0')`. This proves digit extraction and small-width arithmetic work on the substrate, but does not address either representation choice (the result lives on the number axis as a single value, not as a digit array) or the carry-propagation question.

## Option A — Associative-scan substrate primitive

Expose `digit_array_add(a, b)` (and corresponding subtract / multiply) as substrate intrinsics. The runtime implements them as parallel prefix scans: a tensor of pairwise sums, then a tensor of carry bits, then a scan reduction that propagates carries in O(log N) parallel steps using the standard associative scan trick (e.g. Hillis-Steele or Blelloch).

**Force.** Matches the substrate's "every op is a tensor op" discipline. Stays in the tensor-uniformity contract that the rest of the language honors. Performance is asymptotically better than the sequential path. The language surface stays simple — `a + b` for `BigInt`-typed `a, b` just dispatches to the intrinsic.

**Cost.** A new substrate primitive expands the runtime ABI surface — every future codegen target (currently PyTorch; later potentially something else) must implement it. The Hillis-Steele scan has a specific tensor shape and carry-mask construction that has to be formally specified. The intrinsic IS hard-coded; if Emma later decides digit arrays should use a different layout (e.g. radix-2^k instead of radix-10, or signed-digit redundant), the intrinsic has to be re-specified.

**Decoupled question this raises:** what `BigInt` typing surface lights it up — a new `class BigInt extends int { ... }` (sutra-spec) that the operator dispatcher recognises, or a special-cased function (`BigInt.add(a, b)` only)?

## Option B — Sequential soft-halt loop

No new primitive. A `BigInt` is a number-axis vector whose synthetic axes carry the digits (reusing the String layout pattern from `strings.md`). The add function is written *in Sutra*, using the existing soft-halt loop:

```sutra
function BigInt add_bigint(BigInt a, BigInt b) {
    // Pseudocode shape — actual surface depends on the BigInt class.
    loop add_loop(position < max_digits, carry, result) {
        var d_a = digit_at(a, position);
        var d_b = digit_at(b, position);
        var sum = d_a + d_b + carry;
        result = set_digit_at(result, position, sum mod 10);
        carry = sum / 10;
        pass position + 1, carry, result;
    }
    return result;
}
```

**Force.** Stays inside the existing language. No new intrinsic, no new ABI. The carry semantics are visible in the source — auditable, FV-friendly. The "loops are substrate-pure" claim already in the FV paper applies; no new claim to defend.

**Cost.** Sequential: `N` substrate-loop iterations for N digits. The soft-halt loop runs to its bound `max_iters` either way (the halt signal saturates) — so the wall is O(max_digits) per call, paid every time, regardless of the actual operand size. For real BigInt sizes (say ≤32 digits for double-precision-equivalent work, or ≤256 for crypto-shaped numbers) this is acceptable on CPU, plausibly fine on GPU, and definitively slower than Option A's O(log N) scan.

**Decoupled question this raises:** integer division on the substrate. `sum / 10` and `sum mod 10` aren't currently primitives; `modulus.su` has `rotation_mod` / `fmod` and the literate `Math.div_int` could lift from these, but neither has been pressure-tested for a hot inner loop.

## Hybrid — declare the loop, fuse to the scan

A third path: write the add in Sutra (Option B's surface), and have an egglog rewrite or a dedicated compiler pass recognise the add-with-carry shape and lower it to the parallel scan kernel (Option A's runtime). The surface stays auditable; the runtime gets the asymptotic improvement. This depends on having the scan kernel anyway, so it doesn't avoid Option A's ABI cost, but it does avoid forcing users to call a different surface for "scalar add" vs "BigInt add."

## What would close this question

A decision from Emma on path (A) vs (B) vs (hybrid). The pieces that need to go with that decision:

1. **`BigInt` typing.** Is it a new class extending `int`, a typedef on a synthetic-axis layout, or implicit? Affects the parser + operator dispatcher.
2. **Digit layout.** Radix-10 (matches the parser's representation; easiest to reason about), radix-2^k for some k (denser, more carries, faster scan), or signed-digit redundant (no carry chain at all, but harder to convert back to canonical form). Affects the substrate intrinsic OR the Sutra-side loop body.
3. **Maximum width.** Unbounded means "the synthetic block can hold up to `synthetic_dim - 5` digits using the String layout pattern." Real ceiling is `synthetic_dim`. Should `max_digits` be a compile-time parameter, a runtime parameter, or fixed?
4. **Integer-division primitive.** Whichever path wins, the inner step needs `(sum / 10, sum mod 10)` on the substrate. `modulus.su` is the lift point.

Until those four are settled, the carry loop stays unbuilt. The bounded first piece (`parse_int2.su`) is already in the corpus and demonstrates digit extraction; it does not commit the project to either path.

## What would NOT close it

- A "let's just try Option B and see" implementation that ships a working `add_bigint` without picking the layout. The implementation choices become load-bearing without ever being decided, and a future session that wants Option A has to fight the de-facto layout the implementation picked.
- A spec doc that lists both options without picking one. The spec needs a single answer; the dossier is the place where both options live until Emma picks.
