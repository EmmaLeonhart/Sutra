# sutra-from-c — design notes

> **Skeleton stage.** No transpilation logic exists yet. This file is the
> design surface for what the transpiler will do once it's implemented.
> Open questions are flagged inline.

## What the transpiler accepts

A restricted C subset, sufficient to lower hand-written code that does not lean on the preprocessor or inline asm:

- Function definitions and declarations.
- Built-in scalar types: `int`, `long`, `unsigned`, `float`, `double`, `char` — lowered as Sutra `int` / `float` / `complex` per `numeric-math.md` (no separate fixed-width integer surface yet).
- Struct definitions. **Each field becomes a role.** A struct value lowers to an axon whose role set is the struct's field set.
- Pointers, with restrictions. Pointer-to-scalar, pointer-to-struct, and function pointers are accepted; pointer arithmetic, void pointers, and casts between unrelated pointer types are rejected.
- Function pointers lower to axons. **Open question:** how exactly — see below.
- Control flow: `if`, `while`, `for`, `do-while`, `switch`, `return`, `break`, `continue`. All lower to Sutra's existing surfaces (`select`, `loop`, declared-function loops).
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

## Lowering rules (sketches)

These are first cuts. They want the [axon spec](../../planning/sutra-spec/axons.md) to stabilize before they harden.

### Scalars

```c
int x = 5;
```

→

```
int x = 5;
```

Sutra's `int` is a fuzzy-by-default vector with the integer in the synthetic real axis (see `numeric-math.md`). The transpiler picks an axon width per program; the width is part of the program's compile-time configuration. **Open question:** how the user specifies width — flag, manifest, or inferred.

### Structs → axons

```c
struct Point { int x; int y; };
struct Point p = { .x = 3, .y = 4 };
```

→

```
class Point extends vector { }
vector p = bundle( bind(R_x, 3), bind(R_y, 4) );
```

Each field name becomes a role; the struct value is the role/filler bundle. **Open question:** does the role notation `R_x` use a prefix in `.su` source or just the bare field name? See `axons.md` open question on `R_x` / `F_x` shorthand.

### Function definitions

```c
int add(int a, int b) { return a + b; }
```

→

```
function int add(int a, int b) { return a + b; }
```

Direct mapping, since Sutra already has functions with the same surface shape (TypeScript-flavored).

### Function pointers → axons

```c
int (*op)(int, int) = &add;
int r = op(3, 4);
```

→

(deferred — depends on Sutra's higher-order axons being figured out, which the axon spec marks as research-grade today)

**Open question:** what does a function pointer transpile to before higher-order axons exist? Two candidates: (a) reject function pointers entirely until the axon spec lifts the restriction; (b) lower function pointers to a host-side dispatch table that the runtime looks up — loses the differentiability story, but works.

### Control flow

`if`, `while`, `for`, `do-while`, `switch` all have direct lowerings — `if` becomes `select`, `while` / `for` / `do-while` become Sutra's declared-function loop forms, `switch` becomes a multi-option `select`. The transpiler's job here is mostly mechanical syntax rewriting once the field assignments and axon types are sorted.

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

The Sutra IR is whatever shape makes lowering convenient — it does not need to match `sutra_compiler.ast_nodes`, since the only thing we hand off downstream is the rendered `.su` text. After emission, the output is fed to `sutra-compiler` to validate.

## Why pycparser, not libclang

Pycparser is pure Python, no external library, easy to install, easy to vendor. It does not handle the preprocessor — but the transpiler explicitly rejects the preprocessor anyway, so this matches the scope. If the scope expands later (preprocessor, full C99/C11 conformance), the parser swap to libclang is a localized change.

## Open questions blocking implementation

These are the things that need to settle before the transpiler can have a stable lowering:

1. **Axon-side surface syntax for roles.** Today `axons.md` uses `R_x` / `F_x` as a thinking shorthand; `.su` source uses bare identifiers. The transpiler needs to know which to emit.
2. **Function pointers.** Reject for v1, or lower via host-side dispatch?
3. **Axon width specification.** Flag, manifest, or inferred from struct sizes?
4. **Provenance role default.** If Yantra-style provenance roles are ever default-on, the transpiler needs to know whether to emit them.
5. **`stdio.h` shim.** What does `printf("%d\n", x)` lower to? Sutra has no host-side IO concept yet.

The transpiler is blocked on resolving (1)–(3) at minimum. (4) and (5) can be deferred behind compile-time errors until they have answers.
