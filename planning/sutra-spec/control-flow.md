# Control flow

## `select` — the branching primitive

`select` is the main conditional-branching primitive in Sutra.
Single-option `select`, multi-option `select`, and `select ... else
fallback` are the three forms. Semantically `select` is fuzzy
weighted superposition over the named options rather than a
discrete `if`.

`select` is not a primitive vector operation (bind/bundle/…); it is
a separate kind of thing — control flow.

## Loops

There is more than one loop form in Sutra. They split along whether
the loop can be unrolled at compile time:

### `loop[N]` — unrolling loop

A loop with a known compile-time iteration count unrolls. Zero
runtime iteration, zero eigenrotation. The compiler emits the body
`N` times.

### for-each loop — also unrolls

A for-each over a compile-time-known collection unrolls the same
way. Since collections in Sutra are compile-time objects (tuples,
lists that collapse to tuples), the iteration count is known at
compile time and the loop body is emitted once per element.

### C-style iteration loop — `i = 1; ++; until 10`

You can write a loop that looks like a traditional iterating loop
(C# / C / Java style — `for (i = 1; i < 10; ++i)` shape). When the
bounds are compile-time-known, this becomes **the same much
simpler form as `loop[N]`** — it unrolls. The loop counter `i` is
compile-time metadata, not a runtime variable.

### `loop(condition)` — eigenrotation

When a loop **cannot** be unrolled — the termination is data-
dependent, you do not know at compile time how many steps it takes
— the loop works by **eigenrotation**. The loop state rotates
through the vector space on each step, the substrate evaluates the
termination condition, and the loop exits when the condition fires.

There is no while-loop keyword; this data-dependent form is
`loop(condition)`, not `while(condition)`.

## Not a while loop

The user has not adopted a `while` keyword for Sutra. What would
be a while loop in another language is either (a) an unrolling
iteration loop if bounds are known, or (b) `loop(condition)` via
eigenrotation if they aren't.

## Open questions

- Exact semantics of multi-option `select`'s firing threshold and
  of `select ... else` when all named options are low. (Already
  tracked in `todo.md`; carrying forward.)
- Does the C-style iteration loop need its own surface syntax, or
  can every such program be written as `loop[N]` or a for-each?
- When the compiler cannot prove a loop's iteration count is
  compile-time-known, does it silently fall back to
  `loop(condition)`, or does it error and force the programmer to
  write `loop(condition)` explicitly?
- What is the exact rotation operator used for `loop(condition)`
  eigenrotation? Haar-random? A substrate-specific operator? Per
  loop site or per program?
- Can `loop(condition)` exit on something other than a vector-
  similarity check (e.g. a bool crossing a threshold, a counter
  hitting a ceiling)? If so, which of those are first-class?
