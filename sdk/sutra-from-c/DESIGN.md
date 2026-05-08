# sutra-from-c — design notes

> **Skeleton stage — design refinement pass 2026-05-07.** No
> transpilation logic exists yet; this file is the design surface.
> The Sutra-side machinery this transpiler targets — axons (commit
> `6035344`), instance-method dispatch on typed locals (`aac0db2`),
> void-method-as-augmented-assignment (`0893675`), within-function
> SSA-elision (`4afbdd5`) — is now wired, so the lowering rules
> below have a concrete target.

## What the transpiler accepts

A restricted C subset, sufficient to lower hand-written code that does not lean on the preprocessor or inline asm:

- Function definitions and declarations.
- Built-in scalar types: `int`, `long`, `unsigned`, `float`, `double`, `char` — lowered as Sutra `int` / `float` per `numeric-math.md`.
- Struct definitions. **Each field becomes a key on an axon.** A struct value lowers to an `Axon` whose key set is the struct's field set.
- Pointers, with restrictions. Pointer-to-scalar, pointer-to-struct, and function pointers are accepted; pointer arithmetic, void pointers, and casts between unrelated pointer types are rejected.
- Function pointers lower to axons. **Open question:** how exactly — see below.
- Control flow: `if`, `while`, `for`, `do-while`, `switch`, `return`, `break`, `continue`. All lower to Sutra's existing surfaces (`select`, declared-function loops).
- Local variables, parameters, return values.
- Top-level constants (`const int FOO = 42;`).
- `#include` of standard headers, but only as a way to surface declarations the transpiler already knows about (math intrinsics, `printf` shims, etc.). No actual preprocessor expansion.

## What the transpiler explicitly rejects

- The preprocessor (`#define`, `#if`, conditional compilation, function-like macros). User-facing error: "preprocessor directives are not supported; pre-process the file with `cpp` first or remove."
- Inline assembly (`__asm__`, `asm` blocks).
- Variadic functions (no `...` parameters; `printf` is treated as a special-cased shim).
- Pointer arithmetic. `p + 1` does not have a clean axon-side meaning; the transpiler errors. The user can rewrite as array indexing.
- Casts between unrelated pointer types. `(struct A*)(struct B*)` is an error.
- Setjmp / longjmp.
- VLAs (variable-length arrays).

## Strings — deferred

C string literals (`char*`, `"hello"`) are the same problem the TS transpiler hits. **In Sutra source, a string literal `"hello"` is an embedding** — auto-embedded into a basis vector. To carry an actual text-string value (for printf, comparison, indexing), you need a separate `String` class wrapping the literal.

The Sutra `String` class **does not exist yet** — see `sdk/sutra-from-ts/DESIGN.md` §"Strings — deferred" for the same caveat. The plan:

- A C `char *s = "hello";` lowers to `String s = String("hello");` — explicit wrapping.
- C string-pointer operations (`strlen(s)`, `strcmp(s, t)`, `s[i]`) lower to method calls on the wrapped String.
- C `char` (single-character) values are also `String`-shaped at v1; treating them as integer codepoints is a possible later refinement.

Until the Sutra `String` class lands, the transpiler can **emit** these forms but the emitted `.su` won't run end-to-end. The lowering is design-completable now; runtime behavior is gated.

## Lowering rules (sketches)

### Scalars

```c
int x = 5;
```

→

```
int x = 5;
```

**Open question:** axon width specification — flag, manifest, or inferred from struct sizes?

### Structs → axons

```c
struct Point { int x; int y; };
struct Point p = { .x = 3, .y = 4 };
int px = p.x;
```

→

```
Axon p;
p.add("x", 3);
p.add("y", 4);
int px = p.item("x");
```

The axon machinery is wired:

- `Axon p;` constructs an empty axon (substrate: zero vector).
- `p.add(k, v);` is augmented assignment — beta-reduces to `p = Axon.axon_add(p, k, v)`.
- `p.item(k)` is a read.
- Within-function SSA-elision drops `add` calls whose keys are never read (when the axon doesn't escape).

The string-literal keys (`"x"`, `"y"`) are compile-time identifiers per the axon spec, not runtime hash-map keys. The substrate auto-embeds the string into a basis-vector role at the call boundary. Field names in C source map directly to these key strings.

The `class Point extends vector { }` declaration is **not strictly necessary** — `Axon` is the carrier — but the transpiler may emit one anyway as documentation, since C struct definitions carry intent that's worth preserving.

### Function definitions

```c
int add(int a, int b) { return a + b; }
```

→

```
function int add(int a, int b) { return a + b; }
```

Direct mapping.

### Function pointers → axons

```c
int (*op)(int, int) = &add;
int r = op(3, 4);
```

→ deferred. The axon spec says higher-order axons (binding programs as fillers) are research-grade. Two candidates for v1:

- (a) Reject function pointers entirely with a clear error.
- (b) Lower function pointers to a host-side dispatch table — concretely, an integer index into a static array of function symbols. Loses the differentiability story but works.

The user has not picked one. Recommendation: (a) for v1 since most C code that uses function pointers can be rewritten with `if/else` over a known set of functions.

### Loops → tail-recursive functions over an axon state

This is the load-bearing pattern:

```c
int sum = 0;
for (int i = 0; i < 10; i++) {
    sum += i;
}
```

The transpiler hoists every variable referenced in the loop body into an axon, lowers the loop into a tail-recursive function, and rewrites mutations as `axon.item(...)` augmented assignments:

```
function Axon loop_body(Axon a) {
    if (a.item("i") >= 10) return a;
    a.item("sum") = a.item("sum") + a.item("i");
    a.item("i") = a.item("i") + 1;
    return loop_body(a);
}

function int outer() {
    Axon state;
    state.add("sum", 0);
    state.add("i", 0);
    state = loop_body(state);
    return state.item("sum");
}
```

This is the user's "cheat way of doing tail recursion." Smarter analyses can prune variables that don't escape the loop, but the dumb form is robust to side effects and is the right fallback. See `planning/sutra-spec/axons.md` §"Axons as loop carriers."

### Control flow

`if` → `select`. `switch` → multi-option `select`. `while` / `for` / `do-while` → declared-function loop forms (per the loop pattern above).

## Architecture (planned)

```
input.c
   │
   ▼
pycparser  (third-party, pure Python C99 parser)
   │   produces a c_ast.FileAST
   ▼
lower.py   (this package; walks the c_ast, emits Sutra IR)
   │
   ▼
emit.py    (this package; renders Sutra IR to .su source text)
   │
   ▼
output.su
```

The Sutra IR is whatever shape makes lowering convenient — it does not need to match `sutra_compiler.ast_nodes`. After emission, the output is fed to `sutra-compiler` to validate.

## Why pycparser, not libclang

Pycparser is pure Python, no external library, easy to install, easy to vendor. It does not handle the preprocessor — but the transpiler explicitly rejects the preprocessor anyway, so this matches the scope. If the scope expands later (preprocessor, full C99/C11 conformance), the parser swap to libclang is a localized change.

## What blocks end-to-end execution today

The lowering rules above are mostly design-completable now. End-to-end *execution* — transpile a `.c` file, then `sutrac --run` the resulting `.su` — is gated on:

1. **The `String` class.** Until Sutra has one, any C program that uses string operations (printf, strlen, strcmp, …) stops at the runtime layer.
2. **Function pointers.** v1 likely rejects; lifting requires either a host-side dispatch table or higher-order axons.
3. **`stdio.h` / IO surface.** Sutra has no host-side IO concept. `printf`, `scanf`, `fopen`, etc. all need shims.
4. **`math.h`.** Transcendentals are disabled in Sutra (`numeric-math.md`); any C program using `sqrt`, `sin`, etc. won't run.
5. **Heap allocation.** `malloc`/`free` have no Sutra surface today. Programs that lean on dynamic allocation can't lower.

It's fine to design and partially implement against these gaps — the lowering rules are stable, the emitted `.su` is just non-runnable until the dependencies land.

## Open questions blocking implementation

1. **Axon width specification.** Flag, manifest, or inferred from struct sizes?
2. **Function pointers.** Reject for v1, or lower via host-side dispatch table?
3. **`String` class shape.** Synthetic-vector encoding? Codebook? (Same question the TS transpiler has.)
4. **`stdio.h` shim.** What does `printf("%d\n", x)` lower to? Sutra has no host-side IO concept yet.
5. **Heap allocation.** Reject `malloc` for v1, or lower to something axon-shaped?
6. **`char` type.** String-shaped (single-codepoint String) or integer-shaped (codepoint as `int`)?

(1)-(3) gate end-to-end execution. (4)-(6) can be deferred behind compile-time errors until they have answers.
