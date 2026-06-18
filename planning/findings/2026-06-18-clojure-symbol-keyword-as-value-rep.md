# Clojure keyword / symbol as a Sutra value — string-flag codepoint array rep

**Date:** 2026-06-18 (queue §0.5)
**Decision doc + measured foundation for the lowering.**

## The gap

A bare Clojure keyword (`:foo`) or quoted symbol (`'foo` / `(quote foo)`) in **value
position** had no Sutra representation — `_lower_expr` emitted
`/* UNSUPPORTED-EXPR: kwd_lit */`. This blocked keyword/symbol equality (`(= k :foo)`),
keyword/symbol arguments, and (downstream) a `case` form whose members are keywords or
symbols. Keywords as map *keys* already worked (they become a static axon field name via
`_field_name`); this is the *value* position.

## Decision: keyword / symbol / string → string-flag codepoint array

Per the axon-IPC payload model (`project_axon_ipc_payload_is_strings_and_numbers`: axon
fillers are string-flag codepoint arrays + complex-hypervector numbers), a keyword or symbol
value lowers to a **Sutra string literal** — a codepoint array carrying the AXIS_STRING_FLAG.
The reader sigil is preserved in the codepoints so the three kinds stay distinct where it is
cheap to do so:

| Clojure value | Sutra rep | rationale |
|---|---|---|
| keyword `:foo` | string `":foo"` | colon sigil kept → keyword ≠ plain string ≠ symbol |
| symbol `'foo` / `(quote foo)` | string `"foo"` | the symbol's name |
| string `"foo"` | string `"foo"` | identity |

**Known limitation (documented, not a bug):** a quoted symbol and a plain string with the
same characters share this rep (both are codepoint arrays) — Clojure distinguishes them, the
substrate value domain does not. The stated use cases (symbol map keys, `case` members) do
not require the distinction; a keyword keeps its `:` so it never collides with either. If a
program genuinely needs symbol≠string, a synthetic-axis tag is the future extension.

## Why equality works — measured

Equality on these values MUST route to `eq_synthetic` (Euclidean distance on the codepoint
array), NOT cosine `eq`. Measured at runtime (`make_string`):

| pair | cosine `eq` truth | `eq_synthetic` truth |
|---|---|---|
| `"foo"` vs `"foo"` | 1.000 | +1.0 |
| `"foo"` vs `"bar"` | **0.998** (useless) | **−1.0** (clean) |

Cosine cannot separate two short strings; `eq_synthetic` separates them perfectly. The
existing `==` dispatch (`_equality_src` → `eq_synthetic` when both operands are
`_is_synthetic_axis_expr`) already routes correctly here: the Clojure frontend types params
as `number` (in `_SYNTHETIC_AXIS_TYPES`) and a Sutra string literal is a `StringLiteral`
(also synthetic-axis), so `(= k :foo)` → `k == ":foo"` → `eq_synthetic`. This is why the
keyword must lower to a string **literal** (a `StringLiteral` AST node), not a
`String.make_string(...)` call (a `Call` node, which `_is_synthetic_axis_expr` does not
recognise → would fall to cosine and fail).

Verified end-to-end: `(defn classify [k] (if (= k :foo) 10 20))
(defn main [] (+ (classify :foo) (classify :bar)))` → **30** on the substrate
(`classify :foo` = 10, `classify :bar` = 20). Fixture `kwd_value` in the Clojure suite.

## Latent issue noticed — FIXED 2026-06-18

`_SYNTHETIC_AXIS_TYPES` contained lowercase `"string"`/`"char"` but the user-facing class
types are `String`/`Character` (capitalised). A var explicitly typed `String` therefore did
NOT route `==` through `eq_synthetic` (it fell to cosine — measured `classify("foo")+
classify("bar")` = 20, wrong, vs 30 expected). The Clojure path sidesteps it (params stay
`number`-typed), but any hand-written Sutra program using `String x` for equality hit the
cosine path. **Fixed:** added `"String"`/`"Character"` to `_SYNTHETIC_AXIS_TYPES` (the codegen
already treated `("string","String","Character")` together for return types; this set was the
one place missing them). Regression test `tests/test_string_equality.py` (RUN → 30).
