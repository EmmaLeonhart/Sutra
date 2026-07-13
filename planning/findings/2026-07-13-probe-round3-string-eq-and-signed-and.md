# Probe round 3: whole-String equality reads ~equal; `&&` wrong on signed truth in expressions (2026-07-13)

Third reach-probe round (rounds 1-2 produced five fixed compiler defects). Two clean, two real:

## Clean
- `make_string("cat") == make_string("cat")` → +1.0.
- Loop body calling a user function per tick (`acc + double(e)`) → 20.0 exact.

## Defect 6 — String != String reads ~EQUAL
`(number)(make_string("cat") == make_string("dog"))` → **+0.994** (expect strongly negative).
0.994 is the cosine of the two codepoint vectors — so the `==` routes to general cosine `eq`,
not `eq_synthetic` (Euclidean+tanh), despite the docs saying synthetic-axis operands route
synthetic. Any two nonempty ASCII strings have high codepoint-vector cosine → all Strings read
~equal. Suspect: `_is_synthetic_axis_expr` doesn't recognize `make_string(...)` Calls (or the
`_truth_typed`/Call-return-type path returns "String" → falls through to plain `eq`).
Check `_equality_src` routing order in codegen.py:236.

## Defect 7 — `&&` mis-composes on signed truth in EXPRESSION position
Palindrome via `pass ok && (char_at(s,i) == char_at(s, n-1-i))` over "abc" → ok stays **+1.0**
(first pair (a,c) is false; the AND should latch false). Echo of finding
2026-06-17-while-loop-halt-is-single-condition-only: `&&` inlines the [0,1] Zadeh polynomial,
which is wrong on SIGNED ([-1,+1]) comparison truth. That finding fixed LOOP CONDITIONS
(`_translate_loop_condition` → truth_and/truth_or); general expression position still uses the
[0,1] polynomial. Fix candidates: route expression `&&`/`||` on truth-typed operands through
truth_and/truth_or too, or make the polynomial signed-correct. Careful: fizzbuzz-style
arithmetic on [0,1] fuzzies must not change — measure both regimes.

## Repros
In this doc's probes; expected after fixes: "cat"=="dog" strongly negative; palindrome("abc")
negative, palindrome("aba") positive. Tests to add with fixes.
