# Loops

Sutra has four looping constructs: `loop`, `while`, `do`/`while`, and `foreach`. Each compiles to one of two patterns:

- **Compile-time unroll** — the loop body is emitted once per iteration directly into the output, no loop exists at runtime.
- **Eigenrotation** — the loop state is rotated by a fixed matrix each step; termination is a prototype-match test in vector space. The brain (or GPU tensor code) iterates; Python doesn't.

Which pattern a given loop uses is determined by whether the iteration count is known at compile time.

---

## `loop(N)` — compile-time unroll

```c
loop (3) {
    x = x + step;
}
```

When `N` is an integer literal, the body is emitted three times:

```python
x = x + step
x = x + step
x = x + step
```

No runtime loop. No iteration counter on the host. The emitted code is straight-line and the compiler can simplify across the copies.

### With an index

```c
loop (3 as i) {
    use(i);
}
```

The index variable `i` takes values `0, 1, 2`. Emits a real `for i in range(3)` when the count isn't a pure literal, otherwise unrolls.

Use `loop(N)` for small fixed repetitions — stacking a few transformations, generating a short codebook, initializing a banks. It's syntactic sugar over straight-line code.

### Planned: the `iterator` reserved keyword

A planned addition to the unrolling-loop form: a reserved keyword `iterator` that refers to the current iteration's index without needing the `as i` binding.

```c
var n : int = 0;
loop[5] {
    n += iterator;
}
// n == 1 + 2 + 3 + 4 + 5 == 15   (or 0..4, undecided)
```

Because `loop[5]` has a compile-time-constant bound, the compiler unrolls and substitutes `iterator` with the per-copy constant:

```c
n += 1;
n += 2;
n += 3;
n += 4;
n += 5;
```

`iterator` is **never a runtime variable**. Each unrolled copy gets a different compile-time constant. The keyword is contextual — only meaningful inside an unrolling loop body — and a compile-time error elsewhere.

This is the language's canonical demonstration of "Sutra has no memory points": where C's `for (int i = 0; i < 5; i++)` puts `i` in memory and mutates it, Sutra's `loop[5] { n += iterator; }` substitutes five different compile-time constants and emits straight-line code with nothing to point at. See [paradigms](paradigms.md) § Imperative — C for the wider framing.

**Status (2026-04-26):** not yet implemented. Tracked under `STATUS.md` as next-active-session work. Open design questions: 0-based vs 1-based; whether `iterator` should also work inside `foreach` over array literals (probably yes — same unroll mechanism); whether the existing `loop(N as i)` form coexists with `iterator` or is replaced by it.

---

## `loop(condition)` — eigenrotation

```c
loop (x.truth() > 0.5) {
    x = step(x);
}
```

When the loop header is a condition (not an integer), the loop compiles to a **geometric rotation** on the state vector with termination by prototype match:

1. Compile the body to a single rotation matrix `R`.
2. Compile the condition into a codebook of target prototypes.
3. Emit `_VSA.loop(state, R, prototypes)` — the runtime applies `R` to the state, checks against the prototypes, and terminates when the match crosses a threshold.

The iteration happens on the substrate. Python does not see the loop counter. The loop terminates because the rotated state enters the target prototype's basin, not because a host counter hit a limit. There's a `max_iters` safety cap in the runtime, but the semantic terminator is the prototype match.

This is the form that makes Sutra effectively a linear bounded automaton rather than just a feedforward circuit — runtime-conditional iteration over runtime-evolving state.

---

## `while(cond)` — same eigenrotation machinery

```c
while (x.truth() > 0.5) {
    x = step(x);
}
```

Semantically identical to `loop(condition)`. Kept as a keyword because people coming from C-family languages reach for `while` first. Compiles through the same `_translate_while_as_geometric_loop` path.

---

## `do { body } while (cond)` — desugars

```c
do {
    x = step(x);
} while (x.truth() > 0.5);
```

Desugars to: body executes once, then a `while (cond) { body }`. The while half compiles to eigenrotation. The desugar happens at the AST level — there's no do-while-specific runtime.

---

## `for(init; cond; step)` — bounded geometric loop

```c
for (int i = 0; i < 10; i++) {
    x = step(x);
}
```

Compiles to a **bounded** eigenrotation loop. The bound (`i < 10`) is extracted at compile time, and the rotation is pre-scaled so `N` iterations equals the intended total angle. Emits `for i in range(N): …` around a rotation application.

The structure is the same as `loop(N)` in spirit — fixed count, no runtime termination test — but with the geometric-rotation semantic that the brain expects.

---

## `foreach(x in [a, b, c])` — compile-time expansion over array literals

```c
foreach (step in [step_a, step_b, step_c]) {
    x = step(x);
}
```

When the iterable is a compile-time-known array literal, the body is emitted once per element with `step` substituted. Three calls in straight line, no runtime iteration. This is how Sutra writes out a fixed sequence of operations that would be a for-each-item loop in other languages.

`foreach` over a runtime-known array (not a literal) is not currently supported — the array has to be known at compile time so the unrolling can happen.

---

## Choosing between them

| you want | use |
|---|---|
| N fixed at compile time, small | `loop(N)` |
| N fixed, need the index | `loop(N as i)` |
| iterate a fixed list of items | `foreach(x in [...])` |
| iterate until a state converges | `loop(condition)` or `while(condition)` |
| do-at-least-once with a continue-condition | `do { } while` |
| C-style three-part index loop | `for(init; cond; step)` |

The common theme: loops that unroll at compile time stay straight-line in the emitted code and let the compiler simplify across iterations. Loops that depend on runtime state evolve the state via rotation and terminate by prototype match.
