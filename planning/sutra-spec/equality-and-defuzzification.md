# Equality and defuzzification

## Equality as matrix multiplication

Equality in Sutra is not a comparison on two atomic values. It is
a matrix-mediated operation:

1. A function maps a vector to a **matrix** that acts as an
   "is-this-thing" test.
2. To test whether `x` equals `cat`, you use that function on `cat`
   to get the **`is_cat` matrix**, then multiply that matrix by `x`.
3. The result is a truth-valued vector (fuzzy / bool) that says
   how much `x` is `cat`.

So "x == cat" is not a single scalar comparison — it's the function-
of-vector → matrix → matrix-vector-product pipeline. `is_cat` is
itself a reusable object; once you have it, you can apply it to
many candidate `x`s.

This is the reason many Sutra functions compile to matrices (see
`types.md` — "Functions and matrices"). An "is-X" predicate is
literally a matrix.

## Defuzzification

Defuzzification is also a matrix operation. The user's working
picture: a **defuzz matrix** exists such that multiplying a fuzzy
value by it produces a defuzzified-by-a-certain-amount version of
that fuzzy. Repeated application drives a fuzzy value toward a
bool, and the compile-time defuzz counter on `bool` tracks how
many rounds it has been through.

The rule: defuzzification **polarizes** — it sharpens a fuzzy value
along a target axis — but it **does not binarize**. The output is
still fuzzy, still differentiable, still a vector. A value that has
been defuzzified "fully" is not a crisp 0/1; it is a bool
(subclass of fuzzy) with the defuzz counter recording how many
polarization steps it has been through.

`is_true` is the operation that performs this polarization. It can
be applied repeatedly; each application increments the counter.

## Open questions

- What is the exact construction of the "is-X" matrix? Is it a
  single canonical function per type, or user-definable per
  predicate?
- What is the exact construction of the defuzz matrix? Is it
  substrate-dependent?
- Does the defuzz counter have a ceiling (after N defuzz steps the
  value is in a distinguished state)? Or is it open-ended?
- Is `is_true` the only defuzzification primitive, or are there
  others (e.g. `is_false`, `is_near`, `is_in`)?
- Equality as matrix multiplication gives a truth-vector. Is that
  vector itself a `fuzzy`, a `bool`, or something else in the
  type system? (Presumably `fuzzy` if no defuzz has been applied,
  `bool` if one has — but this needs to be stated.)
