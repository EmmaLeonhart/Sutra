# Strings

> **First cut, 2026-05-08.** Codifies the user's design for how
> strings live on the Sutra substrate. The implementation is wired
> end-to-end through the codegen — see commit `<TBD>` for the
> runtime methods plus the stdlib `String` / `Character`
> declarations.

## Position

A String in Sutra is a synthetic-axis-encoded array of codepoints.
String literals in `.su` source are interpreted based on the
**destination type** of the slot the literal lands in (Emma
2026-05-10). See § "Literal coercion" below for the full rule.

To produce a String *value* — a thing whose codepoints survive
round-tripping through the runtime — either:
- Pass the literal to a slot typed `string`, `String`, or
  `Character` (the compiler inserts `make_string` implicitly), or
- Construct one explicitly via `String.make_string("hello")`.

When the destination type wants something else (e.g. `basis_vector`
takes a string and produces an embedding), the literal stays raw —
no auto-wrapping.

## Encoding

A String value lives in the synthetic block of a regular vector,
sharing a layout with complex-valued vectors:

| synthetic axis  | role for a String | role for a complex |
|-----------------|-------------------|--------------------|
| 0 (`AXIS_REAL`) | `char[0]` codepoint | real part |
| 1 (`AXIS_IMAG`) | `char[1]` codepoint | imag part |
| 2 (`AXIS_TRUTH`)| (unused; 0)         | fuzzy truth |
| 3 (`AXIS_STRING_FLAG`) | **1.0 to mark the value as a String** | 0 |
| 4 (`AXIS_LOOP_DONE`) | (unused; 0)    | loop done |
| 5..             | `char[2..]` packed pairwise | 2D Givens slot data |

For `k >= 2`, character `k` lives at `synthetic[k + 3]` —
specifically: `char[2]` at `synthetic[5]`, `char[3]` at
`synthetic[6]`, `char[4]` at `synthetic[7]`, and so on.

This is identical at the bit level to the existing complex-pair
slot encoding the rotation-binding machinery uses. The string flag
distinguishes the interpretations:

- Flag set → "this is a String; read codepoints from
  synthetic[0,1,5,6,7,…]."
- Flag unset → "this is a complex / rotation-bound / numeric
  vector; do not interpret synthetic axes as codepoints."

The user's framing: *"strings are technically the same as
complex-valued vectors"* — same physical layout, different semantic
interpretation, gated on a single flag bit.

> **Note (2026-06-19).** A 2026-06-19 attempt to make `axon_add` write
> `AXIS_AXON_POPULATED[7]` (for an `is_axon` type-test) collided with
> `char[4]` at `synthetic[7]` — a String stored as an axon *value* lost
> its 5th codepoint (`echo`: `in='hello' out='hell\x01'`). That attempt
> was REVERTED, so this encoding is unchanged; `axon_add` does not write
> the flag and Strings survive being bound into axons.

## Length

Length is recovered by **walking from the highest possible char
position down to the first non-zero codepoint**. A trailing-zero
codepoint marks end-of-string. The maximum length depends on
`synthetic_dim`:

```
max_len = 2 + (synthetic_dim - 5)
```

(2 chars at axes 0,1, plus all axes from 5 upward.)

The user's expectation: *"strings are going to be relatively small
most of the time."* Sutra is not a string-processing language; the
budget is fine for typical names, identifiers, short messages.

> **Open question.** What happens if a program needs to encode the
> NUL codepoint (0) inside a string. With the current scheme,
> trailing NULs collapse into "end of string." Two candidates:
> (a) reserve a sentinel codepoint outside Unicode (e.g. `0xFFFF_FFFF`
> as "no character here") and use it instead of literal-zero;
> (b) store an explicit length somewhere (AXIS_TRUTH? a fresh
> reserved axis?). Today: NULs in the middle of a string work fine
> if a non-NUL follows them; trailing NULs are lost.

## Character is a 1-length String

`Character` is a class declared in stdlib as `class Character
extends String { }`. The substrate representation is a 1-length
String. The class hierarchy exists so that:

- A function declared to return `Character` is statically narrower
  than one returning `String`.
- The existing `'a'` character literal in source builds a 1-char
  String with the same codepoint encoding.
- `make_char(codepoint)` is now a thin alias for
  `make_string(chr(codepoint))`.

Earlier versions of Sutra used a separate `AXIS_CHAR_FLAG` for
single-character values. The flag is **renamed to `AXIS_STRING_FLAG`**
(same axis position, broader semantic). `AXIS_CHAR_FLAG` remains as
a backwards-compat alias for code that still references it; new
code uses `AXIS_STRING_FLAG`.

## Literal coercion

**The rule (Emma 2026-05-10):** A string literal in `.su` source —
single-character or multi-character — coerces to a substrate
String value *when the destination type of the slot it lands in
is `string`, `String`, or `Character`*. Anywhere else, the literal
stays as a host-side raw value (because that's what the destination
wanted).

The destinations that trigger the coercion are:

| Where the literal lands | Coercion behavior |
|-------------------------|-------------------|
| Function parameter typed `string` / `String` / `Character` | `make_string(literal)` |
| Variable declaration `string x = "hello";` | `make_string(literal)` |
| `return "hello";` from a function with return type `string` etc. | `make_string(literal)` |
| Class field `field string name;` assigned a literal | `make_string(literal)` |
| `basis_vector("alice")` — destination is the codebook, not a string slot | stays raw (becomes an embedding) |
| Untyped context (`var x = "hello";` with no annotation) | stays raw |
| `axon_add(a, key, "alice")` | already wraps via `make_string` at runtime, per the 2026-05-10 axon permutation work |

Rationale: a function declared `function int len(string s)` is
saying "I expect a substrate String." The caller writing `len("hi")`
shouldn't have to know whether to write `make_string("hi")` —
that's the kind of ceremony a type system is supposed to absorb.
The destination's static type already carries the intent; the
compiler can read it and insert the wrapper.

The same rule applies to `int` / `float` / `complex` literals
flowing into vector-typed slots — they get wrapped via
`make_real` / `make_imaginary` / `make_complex` based on the
destination. (The vector backbone of the language is what makes
this uniform.)

**1-character strings and `Character`.** Because `Character` is a
1-length `String` (see § "Character is a 1-length String" below),
the same rule covers character coercion: a literal `"a"` passed to
a `Character`-typed slot lands as a 1-length substrate String. The
literal type and the destination type don't need to "agree" at
the surface — the compiler reconciles by inserting the wrapper.

### Current implementation state (2026-05-10, updated)

The rule above is wired into the codegen as of commit `895e7a78`
(2026-05-10):

- **Variable declarations** (`string s = "hello";`) emit
  `s = _VSA.make_string('hello')`.
- **Return statements** (`return "direct";` from a function with
  return type `string`) emit `return _VSA.make_string('direct')`.
- **Function call arguments** (`greet("alice")` where `greet`'s
  param is typed `string`) emit `greet(_VSA.make_string('alice'))`.

The codegen now threads destination-type context from these three
sites into `_translate_expr`'s `StringLiteral` case; a new
`Pre-pass C` in `translate()` registers every FunctionDecl's
parameter types (user + stdlib) so call-site translation can look
them up.

Acknowledged residual gaps tracked in
`planning/findings/2026-05-10-host-python-string-bug-chronology.md`:

- Class field initializers from string literals — not yet threaded.
- Post-declaration assignment (`s = "x"` where `s` is already
  declared `string`) — not yet threaded.

These are smaller surfaces than the original bug. Reach for them
when a real program demands the substrate-encoded form at one of
those boundaries; the threading pattern is the same as the three
sites that landed.

`basis_vector("alice")` and similar non-string-destination call
sites continue to receive raw host strings — that path is
correct (the embedding is the substrate form there).

## Surface API

```
String s = String.make_string("hello");
int len = s.string_length();        // 5
int second = s.string_char_at(1);    // 101 ('e')
```

Method-syntax on a typed receiver dispatches through the existing
String stdlib intrinsics (commit registers `String.make_string`,
`String.string_length`, `String.string_char_at`, `String.is_string`
as static intrinsic methods that route to runtime methods of the
same name).

## Integer formatting — `int_to_string` (shipped 2026-07-07)

The number→string formatter, scoped to INTEGERS. `int_to_string(n)` renders an
int-typed number as a substrate String; it is what interpolation
(`$"n={n}"` with an `int` interpolant) and the `(string) n` cast (int source
only) lower to. It stays deliberately integer-shaped: rendering `3.14` would
require a decimal-expansion design that does not exist, so a `number`-typed
(possibly fractional) value still rejects at codegen rather than silently
rendering as its rounded integer.

Mechanism (all tensor ops):

- **Digit extraction is mod-free** — `Math.mod` is banned (measured
  vector-collapse/NaN), and no mod is needed: with `a = round(|n|)` and a
  cached power table `10^k`, `digit_k = floor(a/10^k) − 10·floor(a/10^(k+1))`.
  Two floors and a multiply-subtract give the residue.
- **Leading zeros** are gated by the quotient-significance mask
  `sig_k = (floor(a/10^k) > 0)`; the digit count is `max(Σ sig, 1)` so `0`
  renders `"0"`.
- **Ordering + packing**: output slot `i` takes the digit at place
  `nd − 1 − (i − neg)` via a gather by shifted index — the same VSA-native
  permutation `string_concat` uses — masked to the valid range, `+ 48` to
  codepoints, scattered into the string axes with the STRING flag.
- **Sign**: a negative value gates codepoint 45 (`-`) into slot 0 and shifts
  the digits right by one.

**Exactness bound**: digits are exact while the integer is exactly
representable in the runtime dtype — 7 digits for float32 (2^24 ≈ 1.6·10^7),
15 for float64. Beyond the bound the output is mathematically valid but
unspecified (the input itself is already inexact there) — the
no-runtime-errors posture, same as String overflow saturation.

Declared as `static intrinsic method String int_to_string(int n)` on the
`String` stdlib class; the runtime method lives on the torch backend only
(`supports_string_runtime`).

## Decimal formatting — `num_to_string` (2026-07-08)

The fractional companion to `int_to_string` (Emma re-flagged the interpolation tail
2026-07-08). Contract: render a number as the shortest decimal with at most **6 fractional
digits** (round-half-away at the 6th), trailing fractional zeros trimmed, integral values
rendering with no decimal point (`3.0` → "3" — documented divergence from Python's str).
Exactness rides the dtype mantissa: ~7 significant digits TOTAL at float32, integer and
fraction sharing the budget.

Mechanism — pure composition of shipped machinery:
- split `a = |x|` into `ip = floor(a)` and `f6 = round((a − ip)·10⁶)`, with an exact-indicator
  carry gate for `f6 = 10⁶` (→ ip+1, f6=0);
- **sign**: a gated codepoint-45 scatter at position 0 — `string_concat` reads lengths from the
  codepoint block, so a zeroed sign vector concatenates as the empty string;
- **integer part**: `int_to_string(ip)` unchanged;
- **fraction**: fixed-width 6-digit extraction of f6 (same mod-free two-floor identity,
  KEEPING leading zeros — 3.05 → "05…"), right-trimmed by the trailing-zero mask
  (max position with a nonzero digit — the string_length trick on reversed order), packed
  behind a `.` codepoint, and gated to empty when f6 = 0;
- three `string_concat`s join sign + integer + fraction.

Wired into: interpolation (`number`-family interpolants) and the `(string)` cast wall.
`int_to_string` stays the integer-exact primitive; `num_to_string` is the display formatter.

## What's deferred

- **Concatenation** (`String.concat(a, b)` or `a + b`). Need
  overflow semantics — what happens when `len(a) + len(b) >
  max_len`. The simplest answer is "raise"; alternatives include
  "truncate" or "auto-grow synthetic_dim."
- **Equality** (`String.equals(a, b)` or `a == b`). At the
  substrate level: bit-equality on codepoint axes plus flag check.
  Needs operator-method dispatch which is a separate class-system
  piece.
- **Indexing** (`s[i]` desugaring to `string_char_at`). The
  existing subscript dispatch path needs to recognize String-typed
  locals.
- **Slicing** (`s.slice(start, end)`).
- **Length-storing scheme** if the trailing-zero convention proves
  too lossy.
- **Surface form `String("hello")`** as a one-liner instead of
  `String.make_string("hello")`. Needs constructor-call syntax,
  which Sutra parses as `KW_NEW` + class name today but doesn't
  fully wire.

## Why this design

The user's framing captures three things at once:

1. **Strings reuse existing machinery.** No new substrate
   primitive, no new vector layout — just an interpretation of
   axes Sutra already had.
2. **Strings are a class, not a primitive.** The dictionary-style
   surface (length, char-at) lives on the class; the underlying
   value is a vector. This matches how `Axon` works (class on top
   of bundle/bind/unbind primitives).
3. **Character vs String is a typing refinement.** Same encoding,
   same flag, narrower static type for 1-char values. The class
   hierarchy is what carries that.
