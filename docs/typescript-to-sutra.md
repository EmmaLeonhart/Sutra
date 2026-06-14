# TypeScript → Sutra mapping

Sutra's surface syntax was designed to be familiar to TypeScript
programmers. The TS-to-Sutra transpiler walks a `.ts` file and emits a `.su`
file that compiles through the
standard Sutra pipeline. For most JS/TS programs, the two languages
share the same vocabulary — `class`, `function`, `async`,
`await`, `Promise<T>`, `[]` arrays, etc. — and the transpiler is a
syntax-conversion pass, not a concept-translation pass.

This page is the comprehensive mapping. Each section shows what
TypeScript looks like, what Sutra emits, and the reasoning. Where
something **doesn't yet work**, the gap is called out explicitly
with the missing language piece.

---

## Functions

### Plain function declarations — works

```typescript
function double(x: number): number {
    return x * 2;
}
```

```c
function int double(int x) {
    return x * 2;
}
```

The type annotation moves in front of the name (Sutra is C-style,
TypeScript is Pascal-style). `number` becomes `int` for whole-number
return types or `float` if the source uses decimals.

### Arrow functions assigned to const — works

```typescript
const double = (x: number): number => x * 2;
```

```c
function int double(int x) {
    return x * 2;
}
```

The arrow-as-const lowers to a top-level function declaration whose
name is the const's name. Cross-references resolve normally because
the transpiler's pre-pass registers arrow function names in the
function-signature table before the body walk.

### Arrow functions that capture enclosing locals — works (2026-05-09)

```typescript
function main(): number {
    const multiplier: number = 5;
    const scale = (x: number): number => x * multiplier;
    return scale(7);   // 35
}
```

```c
function int scale(int x, int multiplier) {
    return x * multiplier;
}

function int main() {
    int multiplier = 5;
    return scale(7, multiplier);
}
```

Sutra has no closure. The transpiler walks the arrow body, finds
references to enclosing-scope locals (`multiplier`), and lifts them
to extra parameters of the generated top-level function. Every
direct call site (`scale(7)`) gets the captured names appended
explicitly (`scale(7, multiplier)`). No runtime closure machinery,
no anonymous-function values, no environment-capture indirection.

The constraint: the arrow must be called **directly** (not passed
as a value). When the arrow is passed to another function as a
value (e.g., `arr.map(x => x + total)`), the call site that
ultimately invokes it doesn't know what extra args to thread.

### Functions as values — works (2026-05-09)

Passing a function as a value works via the `function` type-name in
parameter position:

```typescript
function double(x: number): number { return x * 2; }
function apply(f: (x: number) => number, v: number): number {
    return f(v);
}
const x = apply(double, 5);   // 10
```

```c
function int double(int x) { return x * 2; }
function int apply(function f, int v) {
    return f(v);
}
function int main() {
    return apply(double, 5);
}
```

The Sutra `function` type is opaque — no signature-level checking
yet. Arrow-function values that need to capture local state still
require closure support, which isn't in. Top-level function
references work fully.

This unlocks calculus-shape patterns (passing the derivative
function as a value), higher-order combinators, and the `.then`-
shaped Promise chain (when the stdlib exposes it).

### Default parameters, rest parameters — does not work yet

`function f(x: number = 5)` and `function f(...args: number[])`
parse but the transpiler doesn't lower them. Both compile to errors.
Smaller scope than first-class functions but not yet in.

---

## Classes

### Class declarations with fields and methods — works

```typescript
class Point {
    constructor(public x: number, public y: number) {}
    distance_squared(): number {
        return this.x * this.x + this.y * this.y;
    }
}
```

```c
class Point extends vector {
    field int x;
    field int y;
    method int distance_squared() {
        return this.x * this.x + this.y * this.y;
    }
}
```

TypeScript's parameter properties (`public x: number` in the
constructor signature) lower to Sutra `field` declarations. The
constructor body is dropped — Sutra's `new ClassName(args)` factory
auto-fills the fields in declaration order.

### Static and instance methods — works

```typescript
class Vec2 {
    constructor(public x: number, public y: number) {}
    add(other: Vec2): Vec2 {
        return new Vec2(this.x + other.x, this.y + other.y);
    }
    static zero(): Vec2 {
        return new Vec2(0, 0);
    }
}
```

```c
class Vec2 extends vector {
    field int x;
    field int y;
    method Vec2 add(Vec2 other) {
        return new Vec2(this.x + other.x, this.y + other.y);
    }
    static method Vec2 zero() {
        return new Vec2(0, 0);
    }
}
```

`new Vec2(3, 4)` works the same in both languages. Instance method
dispatch (`p.add(q)`) routes through Sutra's existing class-method
machinery.

### Class loops — works

A class can have a top-level loop body that runs as part of the
class's instance lifecycle. Sutra-side this lowers to a non-static
class loop function that takes `this` as its first argument. Used
by the `class_loop_counter` fixture.

### Class inheritance — partial

`class B extends A { ... }` parses, but Sutra's inheritance is
single-inheritance and the parent must bottom out at a primitive
class (`vector`, etc.). TypeScript's interface-style multiple
inheritance and mixins don't translate.

### Generics on classes — does not work yet

`class Container<T> { ... }` parses in TS but Sutra classes don't
support type parameters today (only top-level functions do). The
transpiler erases the `<T>` parameter and the resulting class is
non-generic — values flow as `vector` underneath. Mostly fine because
Sutra's runtime is type-erased anyway, but you lose static
type-checking on the wrapped value.

---

## Interfaces and type aliases

### Interfaces — works

```typescript
interface Coord {
    x: number;
    y: number;
}
```

```c
interface Coord {
    int x;
    int y;
}
```

Pass-through mostly. Used as type annotations on parameters and
return types. The runtime is type-erased — interfaces are
compile-time-only structural shape.

### Type aliases — works

```typescript
type ID = number;
type Result = { ok: boolean; value: number };
```

```c
type ID = int;
type Result = { ok: bool; value: int };
```

Lowered as documentation for the transpiler's own type-tracking;
runtime treats the aliased name as the underlying type.

### Discriminated unions — works

The `discriminated_union` fixture demonstrates a TS union with a
`kind` discriminator field lowering cleanly. Pattern matching on the
discriminant becomes a Sutra `select` over the kind values.

---

## Loops

### `while`, `for`, `do-while` — works

```typescript
function sum_to(n: number): number {
    let total = 0;
    let i = 0;
    while (i < n) {
        total = total + i;
        i = i + 1;
    }
    return total;
}
```

```c
while_loop sum_to_loop(i < n, slot int total : int, slot int i : int, int n) {
    pass total + i, i + 1;
}

function int sum_to(int n) {
    slot int total : int = 0;
    slot int i : int = 0;
    loop sum_to_loop(total, i, n);
    return total;
}
```

The transpiler hoists each loop into a top-level `while_loop`
declaration. Mutated variables become `slot` parameters; the loop
body's reassignments become the `pass` statement's outgoing values.
This is a substantial transformation — the TS source looks
imperative but the Sutra output is the substrate-pure tail-recursive
form that compiles to an RNN cell.

`for (let i = 0; i < n; i++) { ... }` and `do { ... } while (cond)`
follow the same hoisting pattern.

### `for...of`, `for...in` — does not work yet

These iterate over arrays / objects respectively. They need either
a Sutra `foreach_loop` over a runtime collection (currently only
compile-time-known array literals work) or first-class iterators.
Today, rewrite to a counted `for (let i = 0; i < arr.length; i++)`
loop.

### `break` / `continue` — does not work yet

The substrate-pure soft-halt loop has one halt scalar, not a
break/continue distinction. Programs that need early exit can
restructure as a `do_while` with the halt condition, but the direct
`break;` / `continue;` keywords aren't lowered.

---

## Conditionals

### `if` / `else` — works via `select`

```typescript
function classify(x: number): string {
    if (x > 0) {
        return "positive";
    } else {
        return "non-positive";
    }
}
```

```c
function String classify(int x) {
    return select(x > 0, ["positive", "non-positive"]);
}
```

Sutra has no `if` / `else` — branches are expressed as fuzzy
weighted superposition via `select`. The transpiler lowers each TS
`if`-as-expression into a `select`. For statement-position `if`s
that mutate state, the transpiler hoists into the loop pattern
above.

### Ternary `cond ? a : b` — works

Lowers to `select(cond, [a, b])`.

### `switch` — partial

Multi-way `switch` with simple value comparisons lowers to a
multi-option `select`. Fall-through (no `break`) and `default` work
in the obvious way; `case` with code blocks that write side effects
needs the loop-hoisting pattern.

### `try` / `catch` — works (2026-05-09)

Lowers to a polarized blend on `AXIS_PROMISE_REJECTED` (the
substrate exception axis):

```typescript
function getOrDefault(p: Promise<vector>, defaultValue: vector): vector {
    try {
        return p;
    } catch {
        return Promise.resolve(defaultValue);
    }
}
```

```c
function vector getOrDefault(Promise<vector> p, vector defaultValue) {
    try {
        return p;
    } catch {
        return Promise.resolve(defaultValue);
    }
}
```

Both branches evaluate (no early exit, no throw) — the polarized
blend `tanh(50 * v_try[AXIS_PROMISE_REJECTED])` selects the catch
branch when the try result has rejected≈1 and the try branch when
rejected≈0. The polarizer has high enough gain that the choice is
effectively binary.

Constraint: both blocks must be a single `return <expr>;`. Multi-
statement bodies need slot hoisting (like the loops do), pending.

---

## Strings

### String literals — works

```typescript
const greeting = "hello";
```

```c
String greeting = String.make_string("hello");
```

TypeScript strings become Sutra `String` values (a substrate-encoded
codepoint array, see [Primitive classes](primitive-classes.md)). The
runtime carries them as vectors with the `AXIS_STRING_FLAG` set.

### String concatenation — works

```typescript
const full = "hello " + name;
```

```c
String full = String.string_concat(String.make_string("hello "), name);
```

The `+` operator on strings dispatches to the `String.string_concat`
intrinsic. TypeScript's mixed string-and-number concat (`"x = " + 5`)
requires the number-to-string conversion the transpiler doesn't
yet emit; a literal-only string program works.

### Template literals — does not work yet

`` `hello ${name}` `` parses as a template_string node in TS but the
transpiler doesn't yet lower it. Workaround: write as
`"hello " + name` which compiles via the path above.

### String methods (`.charAt`, `.length`, `.slice`, `.split`) — partial

`.length` works (lowers to `String.string_length`). `.charAt(i)`
works (lowers to `String.string_char_at`). `.slice` / `.split` /
`.replace` / regex methods don't lower.

---

## Numbers

### Integer and float literals — works

`0`, `42`, `3.14` lower to Sutra `int` / `float` literals. Both
share the synthetic real-axis encoding under the hood.

### Arithmetic operators — works

`+`, `-`, `*`, `/`, `%` all pass through. Comparison operators
(`<`, `>`, `<=`, `>=`, `==`, `!=`) lower to Sutra's polynomial
comparison forms.

### `Math.*` transcendentals — work

`Math.sqrt`, `Math.pow`, `Math.sin`, `Math.cos`, `Math.exp`,
`Math.log`, etc. pass through verbatim. The transpiler recognizes
`Math` as a class-namespace declared in the Sutra-side stdlib, and
the Sutra codegen routes the calls to the matching substrate-pure
runtime intrinsics — `exp` / `log` via interpolated lookup tables,
the trig family via the unit-circle rotation primitive. So a TS
program calling `Math.pow(2, 10)` transpiles and runs end to end.

### Bitwise operators — does not work yet

`&`, `|`, `^`, `<<`, `>>` aren't substrate-pure on the float-encoded
numeric layer. Could lower to Lagrange-interpolated polynomials over
the binary representation, but no design has been written yet.

---

## Arrays

### Array literals and indexing — works

```typescript
const arr: number[] = [10, 20, 30];
const x = arr[0];
const len = arr.length;
```

```c
int[3] arr = [10, 20, 30];
int x = arr[0];
int len = arr.length;
```

The Sutra `T[]` type lowers to a Python list at runtime
(`arr[i]` is a `_VSA.array_get`, `arr.length` is a
`_VSA.array_length`). The compile-time-known array literal form
works; runtime-built arrays need the existing rotation-binding
array machinery (see [`docs/memory.md`](memory.md)).

### Array methods (`.map`, `.filter`, `.reduce`) — does not work yet

Higher-order array operations need first-class function values.
Workaround: write a `for` loop that does the same accumulation,
which the transpiler hoists into a `while_loop`.

### Spread / rest in arrays — does not work yet

`[...arr]` and `[a, b, ...rest]` aren't lowered. Workaround:
explicit copy via a `for` loop.

### `.includes` / `.indexOf` — does not work yet

These need iteration; the transpiler doesn't generate the loop
form automatically. Write the loop explicitly.

---

## Objects and destructuring

### Object literals — partial via `Axon`

```typescript
const person = { name: "Alice", age: 30 };
```

```c
Axon person = new Axon();
person.add("name", String.make_string("Alice"));
person.add("age", 30);
```

The TS object literal lowers to a Sutra `Axon` (a bundle of named
slots, see [Ontology](ontology.md)). Property access `person.name`
becomes `person.item("name")`.

### Object destructuring — does not work yet

`const { name, age } = person;` doesn't lower. Workaround: write
out the field reads manually.

### Spread in objects — does not work yet

`{ ...obj, x: 1 }` doesn't lower. Workaround: explicit `axon_add`
chain.

---

## Async / await / Promise

### `async function`, `await`, `Promise<T>` — works (with caveats)

```typescript
async function fetch_label(q: string): Promise<string> {
    return q;
}

async function chained(q: string): Promise<string> {
    const v = await fetch_label(q);
    return v;
}
```

```c
async function Promise<String> fetch_label(String q) {
    return q;
}

async function Promise<String> chained(String q) {
    JavaScriptObject v = await fetch_label(q);
    return v;
}
```

Both `async function` and `await` pass through the TS transpiler
verbatim into Sutra. The Sutra parser recognises them; a Stage-1
desugar pass rewrites `await x` into `Promise.value(x)` and wraps
bare returns in `Promise.resolve(...)`. The result compiles and runs
end-to-end.

For the full design — including the three-box visualisation (async
→ Promise → tail recursion) — see the [Promises](promises.md) page.

### `try { await ... } catch { ... }` — works (2026-05-09)

Same lowering as the general try/catch above — the polarized blend
on `AXIS_PROMISE_REJECTED` is exactly what an awaited promise's
rejection sets, so this case falls out for free:

```typescript
async function safe_fetch(q: string): Promise<string> {
    try {
        return await fetch_label(q);
    } catch {
        return "default";
    }
}
```

The await unwraps the inner promise, the try/catch sees the
unwrapped value's rejected channel, and the blend selects the
fallback when needed.

### `Promise.all` / `Promise.race` — does not work yet

Multi-promise combinators. Need either first-class function values
or a substrate-level "fuse N halt vectors into one" primitive.
Workaround: write the parallel logic as sequential awaits inside
the same async function.

### Async generators (`async function*`, `for await`) — does not work yet

Generators of any kind don't lower. Substantial work; not on the
near roadmap.

---

## Modules

### `import { … } from "./path"` — works (2026-05-10)

```typescript
// helper.ts
export function double(x: number): number {
    return x * 2;
}
```

```typescript
// main.ts
import { double } from "./helper";

function main(): number {
    return double(21);
}
```

```c
// generated main.su
// --- begin module: ./helper ---
function int double(int x) {
    return x * 2;
}
// --- end module: ./helper ---

function int main() {
    return double(21);
}
```

The transpiler resolves the import at lower time, recursively
lowers `helper.ts` against the same context, and inlines the
resulting Sutra declarations at the top of the importing file's
output bracketed by `// --- begin module: <spec> ---` markers.
Diamond imports — two different files importing the same third
file — are inlined exactly once via a visited set; subsequent
re-imports are silently dropped. Circular imports terminate the
same way without infinite recursion.

The `import` statement itself disappears from the output. The
imported module's declarations land as plain top-level Sutra
function/class declarations, indistinguishable from declarations
the importing file wrote itself. This is the "beta-reduce at
compile time" framing — there is no runtime module system.

Resolution tries `.ts`, then `.tsx`, then `.su` against the
importing file's directory. A `.su` import is read raw and
inlined verbatim (no re-lowering), the same way the Sutra stdlib
loader treats its own `.su` files. Bare specifiers like
`import x from "react"` are not resolved by this MVP — only
relative (`./`, `../`) or absolute (`/`) paths.

### Tree-shaking — not yet

Every declaration in an imported file inlines, regardless of
whether the importing file actually references it. If `helper.ts`
exports `double` and `triple` and you only `import { double }`,
both still come across. A future pass can prune dead inlined
declarations against the import-clause name set — straightforward
follow-on, not blocking.

### `require()`, `import * as ns from "…"`, namespace dispatch — not planned for MVP

CommonJS `require()` is not on the roadmap; everything goes
through ES modules. `import * as ns from "./x"` and aliased
imports parse but the inline-everything MVP doesn't track the
namespace name, so `ns.foo(…)` won't resolve. Use named imports
(`import { foo } from "./x"`) until namespace tracking lands.

---

## What untyped JavaScript looks like

If a TS file uses `any` / no type annotations / accesses arbitrary
properties, the transpiler routes through a `JavaScriptObject`
fallback runtime (`stdlib/javascript_object.su`). This lets untyped
code compile, but the resulting Sutra program doesn't get the
substrate-purity benefits — `JavaScriptObject` is a host-side dict
underneath. Use type annotations whenever possible.

---

## Summary table

| TypeScript construct | Status | Notes |
|---|---|---|
| Function declarations | ✅ | C-style annotation flip |
| Arrow functions (as const) | ✅ | Hoisted to top-level fn |
| Functions as values (top-level refs) | ✅ | `function` type-name in params |
| Closure capture (direct call) | ✅ | Captures lifted to extra params, threaded at call site |
| Closure capture (arrow passed as value) | ❌ | Direct-call only; passing-as-value loses captures |
| Default / rest parameters | ❌ | Smaller scope; not in yet |
| Class fields + methods | ✅ | Parameter properties → `field` decls |
| Static methods | ✅ | |
| Class generics | ⚠️ | Erased; runtime is `vector` underneath |
| Class inheritance | ⚠️ | Single-inheritance, must bottom out at primitive |
| Interfaces | ✅ | Compile-time-only |
| Type aliases | ✅ | |
| Discriminated unions | ✅ | Lower to `select` |
| `while`, `for`, `do-while` | ✅ | Hoist to declared loops |
| `for...of`, `for...in` | ❌ | Use counted loops |
| `break` / `continue` | ❌ | One-halt-scalar substrate model |
| `if` / `else` | ✅ | Lower to `select` |
| Ternary | ✅ | Lower to `select` |
| `switch` | ⚠️ | Simple cases work |
| `try` / `catch` | ✅ | Polarized AXIS_PROMISE_REJECTED blend; single-return blocks |
| String literals | ✅ | |
| String concat (`+`) | ✅ | |
| Template literals | ❌ | Use `+` concatenation |
| `.length`, `.charAt` | ✅ | |
| `.slice`, `.split`, regex | ❌ | |
| Number literals + arithmetic | ✅ | |
| `Math.*` transcendentals | ✅ | `sqrt`/`pow`/`sin`/`cos`/`exp`/`log` route to substrate-pure intrinsics |
| Bitwise operators | ❌ | No substrate-pure design yet |
| Array literals + indexing | ✅ | |
| `.length` on arrays | ✅ | |
| `.map`, `.filter`, `.reduce` | ❌ | First-class fns shipped, but Array method dispatch not wired |
| Spread / rest in arrays | ❌ | |
| Object literals | ⚠️ | Lower to Axon |
| Property access | ✅ | Via Axon `.item()` / class field reads |
| Destructuring | ❌ | |
| Object spread | ❌ | |
| `async function`, `await`, `Promise<T>` | ✅ | Full Stage-1 desugar |
| `try { await ... } catch` | ✅ | Falls out of try/catch + await landing |
| `Promise.all`, `Promise.race` | ❌ | First-class fns shipped, but combinator stdlib not written |
| Async generators | ❌ | |
| `import` / `export` | ⚠️ | Named ES-module imports work (inlined at compile time, 2026-05-10); `import * as ns`, `require()`, and tree-shaking are not in the MVP |

Legend: ✅ works · ⚠️ partial · ❌ not yet

---

## What this means in practice

Most straight-line TS code — classes, functions, loops, arithmetic,
async/await, try/catch, higher-order function calls, and closure-
capturing arrow functions called directly — runs through the
transpiler today.

**On closures specifically:** Sutra has no closure. Period. When
the TS source has an arrow function that references enclosing-scope
locals, the transpiler lifts those locals to extra parameters of
the generated top-level function and threads the captured values
at every direct call site. There is no runtime closure machinery,
no anonymous-function values, no environment-capture indirection.
The closure-shape vanishes at transpile time and the resulting
Sutra program looks like ordinary explicit parameter passing.

The cost: arrow functions that need their captures preserved
across being **passed as values** (e.g. `arr.map(x => x + total)`
where `total` is captured) don't work, because the call site that
ultimately invokes the arrow doesn't know what extra args to
thread. Direct-call usage works fine.

**Patterns NOT planned for Sutra:**
- Container-method dispatch (`arr.map`, `arr.filter`, `Promise.then`,
  `Promise.all`, `Promise.race`). These belong to the JavaScript
  surface ecosystem; Sutra programs that want the same effect write
  explicit loops or sequential awaits. They are deliberately out of
  scope — Sutra keeps a small core surface rather than absorbing the
  full JavaScript standard library.
- Multi-statement try/catch bodies. Single-return blocks cover the
  practical cases; richer multi-statement try blocks would need
  slot-state hoisting and a story for what an "exception type"
  even is in Sutra (there's no throw, no exception object).
- Closure capture across arrow-passed-as-value. Direct-call capture
  is enough for the calculus / higher-order patterns Sutra cares
  about.

If you're starting a TS-style program in Sutra and not sure which
patterns to lean on:

- **Use** classes, typed functions, while/for loops, try/catch,
  async/await, string concat, array literals, top-level functions
  passed as values, arrow functions that capture-and-call directly.
- **Avoid** template literals, object destructuring, regex,
  array-method-chaining (`.map`/`.filter`), arrow functions passed
  as values that need to preserve captures. Rewrite to explicit
  loops, `+` concat, and top-level helper functions.

---

## Other language frontends

TypeScript is the most-developed frontend, but it is no longer the only
one. Sutra has experimental transpiler frontends — in active development,
of varying maturity — that lower other source languages onto the same
`.su` pipeline:

- **OCaml**, **Rust**, **Scala** — the furthest along after TypeScript
- **Clojure**, **Elixir**, **F#**, **Haskell** — growing fixture suites
- **C** — the earliest-stage skeleton

Each is fixture-tested (input source → expected `.su` output); none is as
complete as the TypeScript path yet. The aim is the same in every case: a
syntax-conversion pass onto Sutra's tensor-op runtime, so existing code in
these languages can compile to the substrate without a hand rewrite.

---

## Reference

- Promise-specific design: [Promises](promises.md) page.
- The transpiler source, its TS fixtures, and the canonical language
  spec live in [the Sutra repository](https://github.com/EmmaLeonhart/Sutra).
