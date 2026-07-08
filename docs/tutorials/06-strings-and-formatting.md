# 06 — Strings & formatting

Strings in Sutra are not host strings with a vector bolted on — they **are** substrate vectors. A `String` packs its codepoints into the synthetic axes of one vector, with a flag axis marking it as text. Concatenation is a permutation-shift-and-add over those axes; formatting an integer is digit extraction by floor division; interpolation desugars into concatenations. Every one of those is a tensor operation. This tutorial builds a small program using all three.

## What you'll learn

- How `+` concatenates strings on the substrate
- String interpolation with `$"..."` — and which interpolants are allowed
- Formatting an integer with `int_to_string`
- Reading a string's length with `string_length`

## The program

This is [`examples/strings_and_formatting.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/strings_and_formatting.su), in full:

```c
// Strings & formatting on the substrate — tutorial 06.
// @embedding: none dim=64

// `+` on two strings concatenates (substrate string_concat).
function string greet(string name) {
    return "hello, " + name + "!";
}

// Interpolation: string-typed interpolants pass through; int-typed
// interpolants format via int_to_string.
function string count_report() {
    string s = "hello";
    int n = string_length(s);
    return $"{s} has {n} letters";
}

// Entry point: build both lines and join them.
function string main() {
    string a = greet("sutra");
    string b = count_report();
    return a + " / " + b;
}
```

Run it:

```bash
sutrac --run examples/strings_and_formatting.su
```

Expected output:

```
hello, sutra! / hello has 5 letters
```

Note the directive at the top: `// @embedding: none dim=64`. This program never embeds anything — it is pure string machinery — so it declares that it needs no embedding model and only a small vector. A program that never touches semantic similarity shouldn't pay for a 768-dimensional substrate.

## `+` concatenates

```c
return "hello, " + name + "!";
```

When both operands of `+` are strings, the compiler dispatches to the substrate's string concatenation instead of numeric addition. Mechanically, concatenation shifts the second string's codepoint block right by the first string's length — a gather by shifted index, the vector-native permutation operation — and adds. There is no character loop.

Mixing types does not concatenate: `"total: " + 5` stays on the numeric paths. To splice a number into text, either cast it — `(string) 5` — or use interpolation, both of which route through the integer formatter described below.

## Interpolation

```c
return $"{s} has {n} letters";
```

A `$"..."` string desugars into a chain of concatenations: each literal chunk becomes a String, each `{...}` interpolant is spliced in between. Two kinds of interpolant are accepted:

- **string-typed** values pass straight through;
- **int-typed** values are formatted by `int_to_string`.

Anything else — a fractional `number`, a fuzzy — is a compile-time error, not a silent render. Formatting `3.14` would require a decimal-expansion design Sutra doesn't have yet, and printing it as `"3"` would be a lie. Declare integer-valued interpolants as `int` and they format exactly.

## Integer formatting

`int_to_string(n)` renders an integer as a String, on the substrate. The interesting part is how it gets digits without a modulo operation: for each place value 10^k it computes

```
digit_k = floor(n / 10^k) − 10 · floor(n / 10^(k+1))
```

— two floor divisions and a multiply-subtract, evaluated for all places at once against a precomputed power table. Leading zeros are masked off by checking which quotients are nonzero (with zero itself special-cased to render `"0"`), a negative sign gates the `-` codepoint into the first slot, and the digits are placed most-significant-first by the same shifted-index gather that concatenation uses.

Precision is bounded by the substrate's float dtype: 7 digits are exact at float32, 15 at float64. That is not a formatter limitation so much as an honesty guarantee — beyond those bounds the integer itself is no longer exactly representable on the substrate.

## Where this leaves you

You can now build, join, and format text entirely on the substrate. Combined with tutorial 05's semantic matching, that's enough to produce real, readable program output — match by meaning, then report the result as a formatted string.
