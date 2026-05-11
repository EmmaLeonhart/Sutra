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

### Current implementation state (2026-05-10)

The rule above is the **design target**. Today the codegen emits
string literals as raw Python strings (`repr(expr.value)`) in every
context — there is no destination-type-driven wrapping in the
Sutra-side codegen. The behaviors that work today work because:

- `axon_add(a, key, value)` runtime-detects `isinstance(value, str)`
  and wraps via `make_string` at the runtime boundary.
- `basis_vector("alice")` runtime-embeds the raw string.
- A function `function string greet(string name)` returning `name`
  passes the raw Python string through end-to-end (so `greet("hi")`
  returns the host string `'hi'`, not a substrate String value).

The third case is the **gap relative to this spec**. Wiring it
requires the codegen to thread destination-type context through
literal emission (call-site param types, variable-decl types,
return-statement function return types). The plumbing is small but
touches several emit sites; tracked as the follow-on implementation
task once a real program needs the substrate-encoded form at a
non-axon boundary.

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
