# Zero as explicit neutrality on the truth axis

**Opened:** 2026-04-23.
**Status:** Known design question around fuzzy/bool semantics. Not
blocking — the runtime does the right thing in both interpretations
— but the conceptual framing matters for how future language features
behave.

## The observation

The 2026-04-23 fuzzy-literal slice (commit 7fb7b50) maps:

- `fuzzy f = true;`  → `_VSA.make_truth(+1.0)`
- `fuzzy f = false;` → `_VSA.make_truth(-1.0)`
- `fuzzy f = 0;`     → `_VSA.make_truth(0.0)`
- `fuzzy f = 0.7;`   → `_VSA.make_truth(0.7)`

That third case is the interesting one. An integer `0` in a fuzzy-
typed slot lands at the origin of the truth axis — **neither true
nor false, but something in between.** The user's framing:

> This is kind of an interesting thing because it both doesn't throw
> an error because it can't, but it's also explicitly neutral. It
> doesn't throw an error because it can't, but it's explicitly
> neutral, and that's what's kind of interesting to me. … My
> inclination is that this is the opposite of truthy and falsy. This
> is kind of an explicit neutrality on truth that's for a non-fuzzy,
> non-binary. This is a direct declaration of not doing this.

## Why it's not truthy/falsy

In most languages:

- *Truthy* — a value that "reads as true" in a boolean context (e.g.
  a nonzero int, a non-empty string).
- *Falsy* — a value that "reads as false" in a boolean context (e.g.
  `0`, `""`, `null`).

Sutra's truth axis is a continuum on [−1, +1]. `0` is geometrically
at the origin — maximally distant from both `+1` (true) and `−1`
(false). So `0` is not "false-ish" the way Python's `0` is; it is
*explicitly not-taking-a-side*. Compared to Python/C's `0 == false`
this is almost the opposite: zero is a first-class declaration of
neutrality, not a degenerate form of false.

This shows up concretely in every truth-axis consumer:

- `defuzzify(f)` with `f` near 0 doesn't collapse to either pole.
- A logical `and`/`or` using `min`/`max` treats `0` as unknown, not
  false.
- `if (f)` (when/if that gets runtime semantics on the truth axis)
  would not branch as if `f` were false.

## Why it's not an error either

A type-strict language could refuse `fuzzy f = 0;` ("0 is an int, not
a fuzzy") or refuse `fuzzy f = 0.7;` ("0.7 is not in {−1, +1}"). We
don't, for two reasons:

1. **The value is in the fuzzy's legal range.** `0 ∈ [−1, +1]` is a
   valid truth-axis coordinate. Refusing it would reject arithmetic
   identities that should hold (`true * 0 = unknown`, for instance).
2. **It's syntactically how the user writes neutrality.** Reading
   `fuzzy f = 0;` as "explicitly neutral" matches what a human
   reader would infer from the context. Making them write
   `fuzzy f = unknown;` or `fuzzy f = (fuzzy)0;` adds ceremony
   without adding information.

## Where this could bite

The "it doesn't error because it can't" property is interesting
precisely because it creates room for surprises. Concrete cases that
future design needs to be explicit about:

1. **Bool → fuzzy coercion.** Going the other direction from the
   slice 2 work: in a `fuzzy`-typed slot, `false` is `−1`. In a
   `bool`-typed slot, `false` is (still?) Python `False`. If the
   language later adds a `bool ⊂ fuzzy` subsumption, the neutral
   point `0` has no bool representative. What happens to
   `bool b = neutral_fuzzy;`?
2. **Truth-axis conditional branching.** `if (f)` with `f` a fuzzy —
   does `f = 0` branch as true, false, neither (and block), or
   probabilistically? Each answer tells us something different
   about what the language means by "conditional."
3. **Comparison operators.** `f == false` vs. `f == 0`. If they
   return different answers, the language has three truth states;
   if they return the same answer (both true, meaning `0 == false`),
   we're back to Python's truthy/falsy flattening.
4. **Integer literals in bool context.** `bool b = 0;` currently
   takes the int path (nothing in slice 2 rewrites this — only the
   `fuzzy` case rewrites). Should this be "explicit neutrality on a
   bool" and become some three-state thing, or is it still
   int-as-false like everywhere else?

## What the current implementation does

For now:

- `fuzzy f = 0` emits `_VSA.make_truth(0.0)` — a truth-axis vector
  at the origin. This is a genuine value, not a sentinel.
- `bool b = 0` (if written) stays on the int/bool path — currently
  not rewritten to truth-axis.
- Operations that read the truth axis (the `truth()` accessor and
  related) will report `0.0` for a neutral fuzzy.

The "neutral is a real value" story is coherent on the numpy/pytorch
runtime right now. What's undecided is how future language-level
consumers (conditional branching, comparisons, bool coercion) handle
the neutral point.

## Candidate resolutions

- **A. Three explicit truth states.** `true`, `false`, and `unknown`
  are all first-class. Comparisons, branching, and coercions all have
  three-way answers. Most expressive, most complex.
- **B. Neutral ≠ false, but branching treats it as "don't know."**
  `if (neutral)` is either a static-analysis error or a runtime
  exception; the language pushes the user to decide explicitly.
  Middle ground.
- **C. Collapse to binary at branch time.** At `if`/`while`/etc.
  points, the truth axis gets defuzzified (with the existing
  `defuzzify` rule). Neutral becomes indeterminate → one-sided
  default (probably false). Compatible with truthy/falsy intuitions
  but loses the "explicit neutrality" framing.
- **D. Do nothing yet.** The current runtime is fine; revisit when
  a concrete program actually hits this case. User direction
  2026-04-23 leaned toward "probably this is something that we
  would only need to deal with at compile time for most situations
  and not a big deal."

D is the current behavior. A-C are the choices when someone writes
the first program where the distinction matters.

## Pointers

- Slice 2 implementation: `codegen_numpy.py:_fuzzy_literal_init_src`.
- Validator range-warning: `validator.py:visit_VarDecl` (SUT0120).
- Related axis design: `planning/findings/2026-04-21-extended-state-and-rotation-binding.md`.
- Fuzzy spec draft: `planning/sutra-spec/equality-and-defuzzification.md`.
