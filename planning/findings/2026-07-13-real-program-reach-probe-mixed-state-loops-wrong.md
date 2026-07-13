# Real-program-reach probe: mixed String+scalar multi-state loops give WRONG VALUES (2026-07-13)

Pinned-tail audit, "real-program reach" surface. Method: write the programs a newcomer would
actually try (model-free, PyTorch backend, default dim) and record precisely what runs vs.
breaks. Four probes; two clean, two real defects.

## Clean

- **sum_array** — `foreach_loop total(arr, int acc) { pass acc + element; }` +
  `return loop total([3,1,4,1,5], 0);` → **14.0**. Correct.
- **count-to-N** (`iterative_loop`, scalar state, expression form) → correct.

## Defect A — relational comparisons can't be `(number)`-cast (equality can)

```sutra
foreach_loop maxi(arr, int best) {
    int e = element;
    pass select([(number)(e > best), (number)(best >= e)], [e, best]);
}
```
→ `CodegenNotSupported: cannot cast to `number` here: the operand's static type can't be
inferred, and truth/number casts need it to pick between relabel and axis-move.`

The same cast on an EQUALITY works — `fizzbuzz.su` ships `(number)((n % 3) == 0)`. So the
static truth-type inference covers `==`/`!=` but not `<`/`>`/`<=`/`>=`. Newcomer impact:
max-of-array — one of the first programs anyone writes — is unreachable via the natural
`select`-on-comparison idiom. Typed intermediaries do NOT help (probe used `int e`, `int best`).

## Defect B — mixed String+scalar multi-state loop state goes WRONG at runtime

**Probe B1 (reverse a string):**
```sutra
while_loop rev(i > 0, String out, String s, int i) {
    pass string_concat(out, string_char_at(s, i - 1)), replace, i - 1;
}
function string main() {
    (out, s2, i) = loop rev((3 > 0), make_string(""), make_string("abc"), 3);
    return out;
}
```
→ decodes to `'c'` followed by ~98 `'a'`s (string capacity cap), instead of `"cba"`.
Read: tick 1 appended `s[2]='c'` correctly; every later tick appended `s[0]='a'` — i.e. the
int state `i` appears NOT to decrement across ticks once String states are siblings, so the
halt (`i > 0`) never fires and the loop runs to the cap.

**Probe B2 (count matching chars):**
```sutra
while_loop count(i < 3, int n, String s, int i) {
    pass n + (number)(string_char_at(s, i) == make_string("a")), replace, i + 1;
}
```
over `"aba"` → **1.0689** instead of 2. Wrong value, not a crash. (Note the `(number)` cast on
`==` compiled fine — consistent with Defect A being relational-only.)

## Why this matters / context

Mixed String+scalar multi-state loops were IMPOSSIBLE before the 2026-07-12 loop-state epic
(String loop state crashed outright — finding 2026-07-08), so this is newly-reachable surface,
not a regression. But wrong-value is worse than crash: nothing warns the user. The B3 durability
sweep covered scalar multi-state and single-String state; the mixed shape was unprobed until now.

Suspects (unverified — for the investigation): the per-tick soft-mux
`state ← (1-halted)·new + halted·old` or the halt-condition evaluation when sibling states are
d-dim vectors; the `replace` marker's interaction with String state; `string_char_at`'s index
argument receiving a number-vector `i` in this configuration. The destructure path threads
plain locals (no slots), so the slot representation itself is likely NOT the cause.

## Disposition

Two queue items filed (top of ACTIVE): investigate+fix Defect B (wrong values, priority);
extend truth-type inference to relational comparisons (Defect A). Probes above are the repro
commands; they should become tests when fixed (expected: "cba", 2, and max_array → 5).

## RESOLUTION of Defect B (same day, instrumented tick-by-tick)

The loop machinery was INNOCENT — the per-tick trace showed `i` decrementing 3→2→1→0 and the
halt firing exactly on time. Two real causes underneath:

1. **`string_char_at` index boundary (FIXED).** `_st(i)` passed a d-dim NUMBER-VECTOR index
   (what a loop-threaded `i - 1` is) through unprojected → `cps[ci]` became a d-wide gather →
   a d-dim garbage "codepoint" poisoning downstream ops. Fix: `_scalar(i)` (projects the
   real-axis value; passes 0-d/host through) — the same boundary as the B1a count fix. After
   the fix the spec-correct reverse-string (`string_concat(out, make_char(string_char_at(s,
   i-1)))`) decodes to **"cba"**; locked in as a test (`TestStringCharAtNumberVectorIndex`).
   Note the spec point: char_at returns `int` (the codepoint) BY DESIGN (strings.md §"Character
   is a 1-length String"; stdlib decl `intrinsic method int string_char_at`); the probe's
   original `string_concat(out, char_at(...))` passed an int where a String belongs — the
   correct idiom lifts via `make_char`.

2. **`==` on int-returning intrinsic calls routes to general vector `eq`, which reads ANY two
   numbers as equal (STILL OPEN — new queue item).** Measured: `_VSA.eq(98, 97)` → truth +1.0
   while `num_eq(98, 97)` → correctly false. The count-chars probe lowers
   `string_char_at(s,i) == 97` to `eq` (the codegen doesn't know char_at returns int; two
   statically-int operands like fizzbuzz's `(n%3)==0` correctly route to num_eq). So the count
   probe reads 3 instead of 2 — every char "equals" 97. The fix is in the ==-routing: consult
   the intrinsic's declared return type (`int`) so number-family comparisons route to num_eq.
   Deeper question for the routing owner: general `eq`'s any-two-numbers-equal geometry is a
   trap wherever an inferred type is missing — worth a defensive note in equality docs.
