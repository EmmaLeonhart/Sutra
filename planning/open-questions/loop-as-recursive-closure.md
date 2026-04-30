# Loops as named recursive closures (idiomatic alternative)

**Source:** `chats/literal-based-optimization-in-programming-languages.md`
(Emma 2026-04-30, extracted from a Claude.ai conversation about
literal-based optimization, RNN compilation, and function taxonomy).

**Status:** open question. Today's loop forms (`do_while`,
`while_loop`, `iterative_loop`, `foreach_loop` — function declarations
with `pass` keyword for tail-recursive yield) work end-to-end and stay.
This document captures an alternative more idiomatic surface that
Emma wants to *try out additively*, not replace the existing loops with.

## What the chat proposes

A single loop construct: a named recursive closure with the `loop`
modifier on the function declaration. Tail recursion is the call
form. Closure handles the "what's recurrent vs what's compile-time
baked" question.

Sketch from the chat:

```
text book_content = loop readBook(while bookUnread, book);

public text loop readBook(cond bookUnread, book b) {
    // ... body ...
    return readBook(isRead, b_remaining);
}
```

Refined with closure:

```
text book_content = loop readBook(while bookUnread);

public text loop readBook(cond bookUnread) {
    // `b` is captured from enclosing scope, not recurred — gets
    // baked in like any compile-time literal. Only `bookUnread`
    // (in the recursive call args) is the recurrent connection.
    return readBook(isRead);
}
```

## Why it's interesting

The current loop forms (`do_while NAME(...)` etc.) decompose
loops by *control-flow shape*: do-while, while, iterative, foreach.
Each kind has its own substrate cell template. That's four code paths.

The idiomatic form decomposes by *information flow*: the recursive
call signature is *exactly* the recurrent connections, nothing more.
Closure captures everything else and bakes it at compile time. This
falls out of standard closure semantics — no new mechanism needed.

> "It means the runtime loop isn't a special case that needs its own
> machinery — it's just a closure that happens to be tail-recursive.
> The 'loop' keyword is essentially just a hint to the compiler that
> says this recursion compiles to a recurrent structure rather than
> being unrolled."

The four control-flow shapes (do_while, while, iterative, foreach)
become library-level patterns over the one loop construct rather than
language-level distinct kinds.

## Function taxonomy (the larger frame)

The chat establishes a six-cell taxonomy: `{free, static, non-static}
× {loop, non-loop}` — i.e. each function is one of free / static
(class-level) / non-static (instance-bound), and either a loop or
not. **Loops are tail-recursive recurrent structures; non-loops get
fully β-reduced at compile time and disappear into the weight matrix.**

The free/static/non-static distinction primarily determines scope
and what the function can close over:

- **Non-static object loop**: tightest scope, recurring over a
  bounded `this`. Most efficient recurrent cell.
- **Static object loop**: looser, recurring over class-level state.
- **Free function loop**: closure-captured context. Most flexible.

All three are valid. The reason for the distinction isn't
efficiency in the traditional sense — it's *how much the compiler
can verify about what's recurring*.

## What's recurrent ≠ what's accessible

The crucial design point from the chat:

- **Recursive call signature** = recurrent connections (only the
  things that change between iterations).
- **Closed-over free variables** = compile-time baked context (not
  recurred; the network sees them as constants in its weights).

This is exactly what an LSTM/GRU does at the architecture level —
gating what carries forward — except here the programmer says it
explicitly via what they put in the recursive call vs what they
leave in the enclosing scope.

> "In a vanilla RNN everything gets carried through the hidden state
> whether it needs to or not. ... You're exposing that same decision
> to the programmer at the language level, which is more honest but
> much harder."

## Open design questions before implementing

1. **Coexistence with the four kinds.** Today's `do_while NAME(...)`
   form works. Does the idiomatic form *replace* it eventually, or do
   both forms ship and the user picks per-program? Per the user's
   explicit direction 2026-04-30 ("please do not remove the old
   loops"), today's plan is **both**, with the idiomatic form being
   the recommended path once it works.
2. **Call-site syntax.** `text x = loop readBook(args)` vs plain
   `text x = readBook(args)`. The `loop` keyword at the call site
   would make recurrent calls grep-able the way `unsafe` is in Rust.
3. **`return readBook(...)` recursion vs `pass`.** Today's loops
   yield with `pass <values>`. The idiomatic form uses `return
   readBook(...)` — true tail recursion. The compiler would need to
   detect tail calls to itself and translate them to the substrate
   cell, just like the current `pass` translation does.
4. **What about non-tail recursion?** The current spec says non-tail
   recursion is a compile-time error. With the idiomatic form, this
   is enforced naturally: a non-tail-recursive `loop` function fails
   to compile because the body has work after the recursive call,
   which isn't a clean recurrent connection.
5. **Closure capture of non-substrate values.** A `loop` function
   that closes over a Python list (say, an SD card path) compiles
   how? Probably: the closed-over value gets baked into the
   substrate weights at compile time the same way any literal does,
   and the runtime never sees it.
6. **Object loops and `this`.** Non-static loop with `this` access:
   the recurrent cell has access to instance state. If `this` is a
   substrate vector, this works trivially. If `this` is a Python
   object instance, it's a closed-over compile-time bake.

## What to do

Today (2026-04-30): just save this design doc. Don't implement.

Later (queued via queue.md when items 1-5 + paper are done): try the
idiomatic form additively. Three possible paths:

- **Library-level** (cheapest): emit a few `function loop`-style
  templates in `stdlib/` that delegate to the existing four kinds.
  Surface looks idiomatic; codegen unchanged. Probably wrong because
  the language change is the point.
- **New loop-decl syntax + new codegen path** (medium): add `function
  loop NAME(...)` parser + a substrate-pure tail-recursion translation,
  alongside the existing `do_while NAME(...)` etc. forms. Both work.
- **Full migration** (deferred): all four kinds re-expressed as
  patterns over the idiomatic loop. Maybe far future. Don't plan now.

The medium path is what to attempt first. The existing four kinds
have working tests — those don't break. The idiomatic form gets its
own test file and worked example.

## Other things from the chat worth preserving

These came up in the same conversation but aren't loop-specific.
Capturing them here so they don't get lost; they may want to move
out into separate docs eventually:

- **Discrete → continuous handoff** as the language's defining
  shape. Discrete phase: ontology, type checking, OWL, β-reduction,
  closure. Continuous phase: matrix multiplications, embedding
  geometry, similarity, activation. The compiler's job is supervising
  the handoff cleanly.
- **Ontology-oriented, not object-oriented.** Inheritance is
  "every cat has a hair colour" — logical assertions for the
  compiler to reason from. OWL/RDF first-class. Object methods exist
  for compile-time sanity checking, not runtime polymorphism. Closer
  to description logics than OOP.
- **Curry rigor + TypeScript ergonomics + OWL ontology + RDF data
  model + RNN compilation target** as the unique five-way
  combination Sutra inhabits.
- **`unsafeCast` and `override` as the two escape hatches** —
  separate, distinct, both grep-able. `unsafeCast` is broader (asserts
  a thing IS something it's not, propagating through downstream
  geometry); `override` is narrower (just bypasses a single call-site
  check without making downstream claims). Already in
  `examples/uncertain/03-types-and-casts.su`; reaffirmed here.
- **Compiled programs are differentiable w.r.t. source literals.**
  If the cat embedding is baked into weights, you could in principle
  backpropagate through the compiled program and update what "cat"
  means. Worth surfacing in the paper.
