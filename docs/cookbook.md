# Cookbook — everyday programs

The classic first programs, written the idiomatic Sutra way. Every snippet on this page
compiles, runs on the substrate, and produces exactly the output shown.

Two conventions to know up front:

- **Truth is signed.** `(number)` on a condition gives `+1` (true) / `−1` (false) / `0`
  (unknown) — the Kleene scale. A 0/1 counter maps via `((number) cond + 1) / 2`.
- **Sharpen `select` with gain.** `select` is a softmax blend; multiply scores by ~10 when
  you want a near-hard choice.

## Sum an array

```sutra
foreach_loop total(arr, int acc) { pass acc + element; }

function int main() { return loop total([3, 1, 4, 1, 5], 0); }   // 14
```

## Max of an array

```sutra
foreach_loop maxi(arr, int best) {
    int e = element;
    number s = 10 * (number)(e > best);
    pass select([s, 0 - s], [e, best]);
}

function int main() { return loop maxi([3, 1, 4, 1, 5], 0); }    // 5
```

No `if` — the winner is a gain-sharpened `select` between the candidate and the incumbent.

## Count matches

```sutra
while_loop count(i < 3, int n, String s, int i) {
    pass n + ((number)(string_char_at(s, i) == 97) + 1) / 2, replace, i + 1;
}

function int main() {
    (n, s2, i) = loop count((0 < 3), 0, make_string("aba"), 0);
    return n;                                                    // 2
}
```

`string_char_at` returns the codepoint (`97` = `'a'`); the `(±1 + 1) / 2` maps signed truth
onto a 0/1 increment.

## Reverse a string

```sutra
while_loop rev(i > 0, String out, String s, int i) {
    pass string_concat(out, make_char(string_char_at(s, i - 1))), replace, i - 1;
}

function string main() {
    (out, s2, i) = loop rev((3 > 0), make_string(""), make_string("abc"), 3);
    return out;                                                  // "cba"
}
```

`make_char` lifts a codepoint back into a 1-character `String` for concatenation. `replace`
keeps `s` at its call-time value each tick.

## Fibonacci

```sutra
iterative_loop fib(8, int a, int b) {
    pass b, a + b;
}

function int main() {
    (a, b) = loop fib(8, 1, 1);
    return a;                                                    // 34
}
```

Multi-value `pass` assigns in parallel — `a + b` reads the pre-tick `a`, exactly like a
simultaneous recurrence.

## Palindrome check

```sutra
while_loop pal(i < 3, fuzzy ok, String s, int i) {
    pass ok && (string_char_at(s, i) == string_char_at(s, 3 - 1 - i)), replace, i + 1;
}

function int main() {
    (ok, s2, i) = loop pal((0 < 3), true, make_string("aba"), 0);
    return (number) ok;                          // "aba" → 1;  "abc" → ≈ −1
}
```

## Find a character (index-of)

```sutra
while_loop find((i < 3) && (string_char_at(s, i) != 98), int i, String s) {
    pass i + 1, replace;
}

function int main() {
    (i, s2) = loop find((0 < 3), 0, make_string("aba"));
    return i;                                                    // 1  ('b' = 98)
}
```

The compound halt (`&&` of a bound and a character test) runs on the substrate like
everything else.

## Parameterize an iteration count

Loop functions have no outer-scope access — thread a caller's value as a state parameter:

```sutra
while_loop tri(i <= n, int acc, int i, int n) {
    pass acc + i, i + 1, replace;
}

function int triangular(int k) {
    (acc, i, n) = loop tri((1 <= 1), 0, 1, k);
    return acc;
}

foreach_loop total(arr, int sum) {
    int e = element;
    pass sum + triangular(e);
}

function int main() { return loop total([1, 2, 3], 0); }         // 10
```

Loops calling functions calling loops compose freely.

## FizzBuzz

The classic lives in the demos: [FizzBuzz on the demos page](demos.md) — a softmax `select`
superposition picks each word, and a loop threads the growing `String` accumulator.

For the loop surface itself (all three call forms), see [Loops](loops.md).
