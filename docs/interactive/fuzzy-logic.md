# Fuzzy logic explorer — interactively

Move the two sliders to set the values of `a` and `b`. The cards below show every standard logic gate computed live through its polynomial form. The snap buttons jump `a` or `b` to the three canonical points — **false (−1)**, **unknown (0)**, **true (+1)** — so you can confirm that the polynomial hits the right discrete result on the three-valued grid, and see how it interpolates smoothly everywhere in between.

The page is the visual companion to the [Logical operations](../logical-operations.md) reference page. There you'll find the derivations, truth tables, and historical context; here you just play with it until the polynomial forms feel obvious.

<div id="fuzzy-logic-widget"></div>

<noscript>
This page contains an interactive demo that requires JavaScript. The static reference on <a href="../logical-operations.md">the logical operations page</a> covers the same material, just without the live slider.
</noscript>

## What to try

A few experiments that are worth running deliberately:

- **Walk the three-valued grid.** Click each of the three snap buttons on `a` while `b` stays at true. Every connective should produce one of `{-1, 0, +1}` — Kleene's K₃ three-valued result. Repeat with `b` at `false` and `b` at `unknown`.
- **Leave one fully true, drag the other smoothly from −1 to +1.** Watch how AND and OR fill in the continuous interpolation between the grid's corner cases. XOR and IFF move as straight lines — they're literally `∓a·b`, so with one side pinned the output is linear in the other.
- **Set both to the same value and sweep.** AND and OR trace different parabolas through the `{-1, 0, +1}` points. IFF is `a·b = a²` — always non-negative; it says "a value agrees with itself to the degree that it's decisive." XOR is `-a²` — always non-positive; "a value disagrees with itself only to the degree that it's decisive."
- **Slightly off-grid values.** Set `a = 0.05` and `b` to anything. All the connectives treat this as "weakly positive" rather than "exactly unknown" — you can see the polynomial's smooth transition instead of a binary snap.

## Why this matters

Most programming languages give you boolean logic — two discrete states and branching on them. Sutra is built on continuous truth values in `[-1, +1]`, and the logical operators are smooth polynomials that reduce correctly at the grid points but stay differentiable everywhere. That's what makes it possible to:

- **Compose connectives algebraically** at compile time (no case analysis on `abs`).
- **Differentiate entire logical expressions** end-to-end with standard autograd rules.
- **Run on CUDA** as pure element-wise tensor ops — no kernel launches for `if` statements.

The explorer above is how you feel those properties rather than just read about them. If you drag the sliders slowly and watch every card's bar glide smoothly between the canonical points, you're watching differentiable logic in action.

## Related

- [Logical operations](../logical-operations.md) — the reference with the full derivations.
- [Primitive classes](../primitive-classes.md) — why bool / fuzzy / trit all live on one truth axis.
- [Numeric math](../numeric-math.md) — the same "smooth polynomial on two axes" story for complex numbers.
