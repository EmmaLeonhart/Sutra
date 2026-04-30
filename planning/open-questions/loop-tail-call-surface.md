# Loop tail-call surface (`return NAME(args)` as `pass` alternative)

**Source:** Emma 2026-04-30, originally explored in
`chats/literal-based-optimization-in-programming-languages.md`
(framed as "closure-loop"), then narrowed into the actual design
the user wanted.

**Status:** **shipped** as of 2026-04-30. Surface implemented in
codegen_base.py; 23/23 loop tests pass on the PyTorch backend
including three new tests in `TestReturnTailCallSurface`. The
existing `pass values` surface and the four explicit loop kinds
(`do_while`, `while_loop`, `iterative_loop`, `foreach_loop`) all
remain — the new surface is purely additive.

## What it actually is (NOT what the original chat called it)

The original chat used the term "closure-loop." Emma walked back
that framing 2026-04-30:

> "I don't actually want it to have closure. I kind of made a
> mistake. ... I don't think this language is actually going to
> even have closure."

What Emma *does* want:

1. **File-scope access for free (non-object) functions.** A free
   function can read any variable declared at the file's top level,
   because the function can only be used in that file anyway. This
   is **not closure** — it's just module-level scope visibility,
   the same thing Python free functions get for free. Already works
   today via the emitted Python's natural scoping.
2. **`return NAME(args)` as an alternative to `pass values`** for
   the tail step inside a loop function body. Same semantics,
   prettier surface. The two forms are interchangeable.
3. **Specified return type** stays on the loop function decl. The
   recursive call doesn't *return* in the conventional sense; the
   tail call's args are recurrent state for the next tick, not the
   final value. The final value is whatever the substrate cell
   produces after halt-mux, which gets written back to the caller's
   slot vars via the existing `loop NAME(args);` call statement.

That's the whole design. No closure machinery, no new AST node, no
new semantics — just a new surface for the existing tail step.

## Surface

Both forms work; pick whichever reads cleaner per program.

**`pass` form** (original):
```sutra
do_while addNumber(x < 11, int x) {
    pass x + 1;
}
```

**`return NAME(args)` form** (added 2026-04-30):
```sutra
do_while addNumber(x < 11, int x) {
    return addNumber(x + 1);
}
```

Both compile to the exact same substrate cell. The codegen detects
`return NAME(args)` where `NAME` is the enclosing loop name and
treats it identically to a `pass` with the same values.

Works for all four loop kinds (`do_while`, `while_loop`,
`iterative_loop`, `foreach_loop`). The `iterator` and `element`
contextual keywords work in tail-call args same as in `pass` values.

## What does NOT change

- **All four explicit loop kinds stay.** Per Emma 2026-04-30: "I
  don't want to delete the old loops." `do_while`, `while_loop`,
  `iterative_loop`, `foreach_loop` are the canonical kinds; the
  tail-call surface is just a syntactic alternative to `pass`.
- **Loop call site stays `loop NAME(...)`.** No "regular function
  call" surface for loops. The call-site `loop` keyword is
  load-bearing (grep-able marker for recurrent computation) and the
  caller writes back to its own slot vars from the loop's mutated
  state — the call statement, not the loop function, is what
  produces a usable result.
- **State params still on the decl line, with types.** The decl
  shape is unchanged; only the body's tail-step keyword choice
  changes.
- **The body still re-runs each tick** — the substrate cell unrolls
  T=50 inline cell evaluations regardless of whether the body uses
  `pass` or `return`.

## Why the new surface is good

Emma 2026-04-30:

> "It's much easier than I thought. ... The combination of file-
> space access, the tail recursion, and the specified return value,
> I think, gives a good [surface]. It actually relatively
> specifically gives much better semantics for explaining which
> things are inherited from the next, which things are recurrent,
> and what is the actual end thing."

Three things the new surface clarifies:

1. **What's inherited from the next [tick]** — the tail-call args
   are explicitly the values that flow into the next tick. With
   `pass`, the order maps to state-param order; with `return
   NAME(args)`, the names line up syntactically with the decl.
2. **What's recurrent** — only what appears in the tail-call args.
   With `pass`, you might forget a state param; with `return
   NAME(args)`, the arity check is unmissable.
3. **What is the actual end thing** — the loop's return type on the
   decl line is the type of what the loop ultimately produces; the
   tail call doesn't actually "return" that, it just hands off
   state to the next tick. The end-thing is what's in the slot var
   after halt.

The new surface reads as recursive functional code; the underlying
machinery is unchanged. Both surfaces produce the same emitted
Python.

## What does change (informally — for free functions)

Free (non-object) functions get file-scope access. This is a
natural property of how Python emits — module-level names are
visible to any function defined in the same module. Sutra's
free functions are emitted as Python module-level functions, so
this just works.

> "All I want is for generic, not object-bound, functions to have
> access to basically all variables on the file that they're in
> because they can only be used in that file. That's basically it."
> — Emma 2026-04-30

This is **file-level scope visibility, not closure.** Closure
would mean the function captures a snapshot of variables at decl
time and carries them forward; that's not what's happening. The
free function reads file-scope vars at call time, same as any
Python function reading its enclosing module.

The "compile-time bake" story: when a free function references a
file-scope value that's a literal or compile-time-fold-able, the
folder pass replaces it with the constant. When it's a runtime
value, the function reads the module-level variable at call time.
Both cases work without new machinery.

## Implementation notes

- `codegen_base.py:_translate_stmt` handles `ReturnStmt` with a
  `Call` to the enclosing loop's name as the same shape as
  `PassStmt` (assigns each arg to the corresponding state local).
  Falls through to regular `return <expr> * _program_halt` for any
  other return value.
- `_loop_state_stack` now stores `(loop_name, [state_names...])`
  tuples so the tail-call recognizer knows which call to consider
  recursive.
- Arg-count mismatch errors with a clear "tail call expects N
  args" message.
- `replace` keyword is NOT supported in tail-call args (it's a
  `pass`-value parser feature). If someone needs `replace`, they
  use `pass` for that loop function. Documented as a deliberate
  scoping choice, not an oversight.
- Three new tests in `TestReturnTailCallSurface` confirm the
  semantic equivalence to `pass`: do_while, iterative_loop with
  `iterator`, and the arg-count error.

## Object encapsulation (deferred)

Per Emma 2026-04-30: object-bound functions (static and non-
static) do NOT have file-scope access — they're encapsulated
within the class boundary. **If encapsulation isn't already
working at all today, that's a separate todo.md item, not this
work.** Today's compiler doesn't really exercise object methods
in load-bearing ways, so the encapsulation rule is currently
implicit (free functions get file scope, object methods get class
scope, but the latter isn't tested or enforced). Make this
explicit and enforced when objects start being used for real.

This was added to `todo.md` so it doesn't fall off the radar.

## What about the broader function taxonomy?

The chat sketched a six-cell taxonomy `{free, static, non-static}
× {loop, non-loop}`. The non-loop cells are
β-reduced-and-disappear at compile time; the loop cells are the
substrate cells described here.

Today the compiler implements free functions cleanly (both loop
and non-loop). The object cells (static method, non-static method,
their loop variants) are deferred — see
`function-taxonomy-and-closure.md` for the design vision and
`todo.md` for the deferred-impl tracking item.
