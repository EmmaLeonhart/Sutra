# Types

## Base types

Three base types at the bottom of the hierarchy:

- **Matrix**
- **Vector**
- **Scalar**

Almost everything in Sutra is a subtype of vector (or, less often,
matrix or scalar). At runtime it is all math — linear algebra, but
not restricted to any one formulation.

## Subtypes of vector

- **`fuzzy`** — a subclass of `vector`. Fuzzies are vectors that
  represent a quantity between false and true. They are the default
  scalar-valued-ish thing in Sutra; "scalar" in the base-type sense
  is rarely what a program reaches for.
- **`bool`** — a subclass of `fuzzy`. Bools are vectors, not crisp
  single-bit values. They carry a defuzzification counter as
  compile-time metadata (so two bools produced by different chains
  of defuzzification can be distinguished by the compiler). A bool
  is usable in code the way a C-style bool would be — `if whatever
  > this` reads naturally — but operationally it is still a fuzzy
  vector, and it never becomes crisp.

## Tuples and lists

Tuples exist in Sutra but **are not a runtime type** — they exist at
compile time. Lists are similar: you can write them, but they
compile down to tuples (and further) so that at runtime everything
is vectors/matrices/scalars. Runtime is math; tuples and lists are
compile-time scaffolding for writing the math.

## Functions and matrices

Many functions in Sutra *are* matrices, or compile down to formulas
over matrices. Not all — but a large fraction of practical Sutra
functions are matrix-shaped. The compilation path for a function
that is matrix-shaped is different from the compilation path for
one that isn't. (Spec for this compilation split: open question.)

## Defuzzification as matrix multiplication

The user's working picture for defuzzification: a **defuzz matrix**
exists such that multiplying a fuzzy by it produces a version of
that fuzzy that has been defuzzified by a certain amount. A bool
is the result of chaining these defuzz multiplications; the
compile-time defuzz counter tracks how much defuzzification the
value has been through.

## Scalars

Scalars exist as a base type but are rarely user-facing. The
user's intuition: scalars are mostly *inputs* — e.g. thresholds,
angles, iteration counts — not values you compute with at runtime.
Whether Sutra programs can return scalars, or whether scalars only
enter as literals in source, is an open question.

## Open questions

- How exactly are "matrix-shaped" and "non-matrix-shaped" functions
  distinguished at compile time? What decides which path is used?
- What is the exact construction rule for the defuzz matrix?
  A single canonical matrix? A family indexed by "how much"? A
  matrix generated per-target?
- Does `bool`'s defuzz counter have a ceiling? What happens when
  it hits? (A bool that has been defuzzified "all the way" — does
  it become a distinguished value?)
- Can scalars appear as function results, or only as inputs?
- Are there other subtypes of vector beyond `fuzzy` and `bool` that
  the language needs? (E.g. `probability`, `angle`, `unit_vector` —
  not claimed, just the obvious candidates if more subtyping is
  wanted.)
- Do matrices have subtypes (rotation matrix, defuzz matrix, is-X
  matrix) as first-class types, or are those just conventional
  shapes?
