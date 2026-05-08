# Strings

> **First cut, 2026-05-08.** Codifies the user's design for how
> strings live on the Sutra substrate. The implementation is wired
> end-to-end through the codegen — see commit `<TBD>` for the
> runtime methods plus the stdlib `String` / `Character`
> declarations.

## Position

A String in Sutra is a synthetic-axis-encoded array of codepoints.
String literals in `.su` source still default to **embeddings**
(auto-converted to basis vectors at the substrate boundary, the
behavior every existing example relies on). To produce a String
*value* — a thing whose codepoints survive round-tripping through
the runtime — the source must explicitly construct one through the
`String` class.

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
