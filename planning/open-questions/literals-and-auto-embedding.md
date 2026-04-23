# Literals and auto-embedding

**Opened:** 2026-04-23 (this session).
**Status:** Design captured; user said "likely to change a lot as use
case things work well." Keep as open question until the concatenation /
embedding rules settle against real programs.

## The question

What is the literal set of Sutra, and when does a literal in source
code become a vector at runtime vs. stay as its host-world primitive?

The premise: *"embedding is so natural to this language we should be
making it as natural as doing strings."* A programmer writing `"hello"`
inside a vector-typed context should get an embedded vector by default,
not a string object they have to `basis_vector(...)` wrap.

## Current literal set

Per the lexer + parser audit:

| Form | Token | AST node | Lowering |
|---|---|---|---|
| `42` | `INT_LIT` | `IntLiteral` | scalar on number axis (synthetic[0]); integer class is a compile-time tag |
| `3.14` | `FLOAT_LIT` | `FloatLiteral` | same number-axis scalar; integer vs float is compile-time metadata only |
| `"foo"` | `STRING_LIT` | `StringLiteral` | currently: Python string object at runtime |
| `$"foo {x}"` | `STRING_INTERP_START` + chunks | `InterpolatedString` | Python format string; IO-side, not embedded |
| `true` / `false` | `TRUE` / `FALSE` | `BoolLiteral` | scalar on truth axis (synthetic[2]) |
| `[a, b, c]` | `LBRACKET` | array literal | dict of rotation-indexed slots |
| `{k: v}` | `LBRACE` | map literal | `map<K, V>` primitive |
| `basis_vector("name")` | — | `Call` | Ollama-backed embedding at runtime |

## Proposed changes

### 1. String auto-embedding (the central change)

Rule (user, 2026-04-23):

- **Strongly-typed context is the primary signal.** Sutra is strongly
  typed so most sites unambiguously declare whether they want a vector
  or a string.
- **`var x = "x";` default-embeds.** With no type annotation, a bare
  string literal in value position lowers to `basis_vector("x")`.
  Justification: string-typed local variables are rare in Sutra; the
  programmer reaching for a string literal without annotation almost
  always wants a vector.
- **`vector + "y"` auto-embeds the string operand.** In a binary op,
  when the other operand is a vector, a string literal lowers to
  `basis_vector(...)`. Justification: the operand type already tells
  us this is a vector expression.
- **String concat is still string concat when both sides are strings.**
  `"Hello " + $NAME` with `$NAME` an IO-typed string stays a string
  through the concat, then either goes to IO or embeds on entering a
  vector context. Embedding is applied to the fully-assembled string,
  not to each piece.
- **`string`-typed context keeps strings.** `var x : string = "foo"`,
  `map<K, string>` values, function returns typed `string` — these
  preserve the string object. `hello_world.su`'s
  `map<vector, string> PHRASE_NAME` continues to work unchanged.

Equivalent one-line rule: *a string literal auto-embeds wherever the
enclosing type context expects a vector, and stays a string wherever
it expects a string. With no annotation, the default is vector.*

**Why the rule will evolve.** The user noted string concat is used a
lot more than embedding-addition in practice, so the exact trigger
for promote-to-embed vs. stay-as-string will refine as real programs
stress it. The current rule is a starting point, not a commitment.

### 2. Character literal (new)

Syntax: `'a'` — single-quoted single character.

Runtime: a character is **an integer with a char-flag bit set on a
synthetic axis.** The code point occupies `synthetic[AXIS_REAL]` (same
slot an int would use). A dedicated synthetic axis — free, next slot
is `synthetic[3]` — carries `1.0` when the value is a character, `0.0`
otherwise.

Proposed allocation:
- `AXIS_REAL = 0` (existing)
- `AXIS_IMAG = 1` (existing)
- `AXIS_TRUTH = 2` (existing)
- `AXIS_CHAR_FLAG = 3` (new)

So `'a'` lowers to `_VSA.make_char(97)` → a vector with
`synthetic[0] = 97.0`, `synthetic[3] = 1.0`, everything else zero.
Arithmetic with plain ints continues to work (the int/char tag is just
metadata on the vector); the flag lets code downstream discriminate
character values from plain integers.

**Open:** encoding — user noted "we might be able to do some kind of
encoding with that one, but I don't know what to do with it." For now,
store the code point as a plain scalar and revisit when a concrete
use case emerges.

### 3. Fuzzy literal (new — syntax pending)

A fuzzy is a scalar in [−1, +1] typed as `fuzzy` (distinct from float).
Runtime representation: scalar on the truth axis `synthetic[AXIS_TRUTH]`
(same slot as `bool`).

**Syntax is the open piece.** Candidates:

- `0.7f` — suffix marker, similar to how some languages mark floats.
- `fuzzy 0.7` — word prefix. Parseable, verbose.
- `(fuzzy)0.7` — cast. Always available, but not a distinct literal.
- No literal at all; rely on `(fuzzy)0.7` casts for all construction.

The first option is the most syntactically light-weight but collides
with the current lexer's view of floats. The fourth is the cheapest
path that doesn't close off future options.

Unresolved; decide when the first program wants one.

### 4. basis_vector retention

`basis_vector(x)` stays as an explicit form. Reason: bare-string
auto-embed only works for *literal* strings. Embedding an arbitrary
string-typed expression (IO input, concatenation result, map lookup)
still needs the explicit call. The call form is also the natural
anchor for any future variants (learned embedding, substrate-specific
embedding, etc.).

### 5. Int/float — already aligned

Both are already scalars on the number axis per
`tests/corpus/valid/integer_augmented.su` and the `92a9556` commit
("Number axis: integers-only-by-design guarantee"). Int is a compile-
time class tag; runtime is a single float on `synthetic[AXIS_REAL]`.
No structural change needed; only worth re-verifying that float
literals flow through the same runtime path as int literals at codegen
time. The char flag axis above reuses the same representation with a
flag set.

### 6. Interpolated strings — unchanged

`$"..."` stays IO-side per user direction. Output-only until a use
case pulls them into the embedding path.

## What this breaks / doesn't break

**Does not break** (all existing demo behavior intended to survive):
- `hello_world.su` map of `vector → string` — string values stay
  strings (type-position rule).
- `basis_vector("name")` explicit calls — still the supported form
  for non-literal strings.
- Integer arithmetic — unchanged.
- `$"..."` interpolation — unchanged.

**Would break if rolled out naively:**
- Any `.su` file that currently has `var x = "foo"` and expects `x` to
  be a string. Need to audit the example corpus; there are likely a
  few.
- Tests that compare string-valued returns against string literals
  where the return type was inferred, not annotated.

Rollout plan (when we're ready to implement): add the auto-embed rule,
run the example test suite, annotate types on any site that broke.
Keep the rollout as one commit per rule piece (string auto-embed
separate from char literal separate from fuzzy literal) so regressions
are bisectable.

## What remains genuinely open

1. **Fuzzy literal syntax.** See "3" above.
2. **Character encoding.** Store bare code points (UTF-32) or encode
   into the full synthetic block (multiple axes per char)? Parked
   until a program demands it.
3. **String concat in vector context — order of operations.** Given
   `"Hello " + name + vector_var`, does the concat happen first
   (yielding `"Hello <name>"` then embedded, then added to the
   vector) or does the leftmost vector force everything to embed
   immediately? The user's mental model is "concat first, then embed"
   — needs to be verified against the type-system's inference pass.
4. **`var x = "foo"` without annotation.** User said "default-embeds."
   Is there a syntactic escape hatch for the rare "I really want a
   string" case, or do we require an annotation `var x : string =
   "foo"` in that case? Annotation-required is simpler; revisit if
   annoying in practice.

## Pointers

- Conversation source: 2026-04-23 session about literals.
- Canonical axis allocation: `codegen_numpy.py` lines 615–694.
- Current parser literal handling: `parser.py:1197` (`_parse_primary`).
- Current lexer literal tokens: `lexer.py:83-93`.
- Integer class + number axis: `sdk/sutra-compiler/tests/corpus/valid/integer_augmented.su`.
- Complex number axis design (related, parallel pattern):
  `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
