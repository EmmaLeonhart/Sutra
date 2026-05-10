# TypeScript → Sutra mapping

Sutra's surface syntax was designed to be familiar to TypeScript
programmers. The TS-to-Sutra transpiler (`sdk/sutra-from-ts/`)
walks a `.ts` file and emits a `.su` file that compiles through the
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

### Arrow functions as values — does not work yet

Passing an arrow function as data — say to `array.map(x => x * 2)`
— requires Sutra to have first-class function values. Sutra's
arrow functions today get hoisted to top-level functions with
no values-of-function-type. This blocks `map` / `filter` /
`reduce` / `.then(callback)` and every other higher-order pattern.
Tracked at the top of `todo.md`; substantial work.

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

### `try` / `catch` — does not work yet

Sutra has no raise/throw primitive, so the question "what would
catch catch" doesn't have a substrate-level answer in general. For
the async/await context specifically, `try { await x } catch { ... }`
should lower to a fuzzy-blend on a synthetic-axis exception flag —
that work is tracked as the next promise-spec phase.

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
codepoint array, see [`docs/primitive-classes.md`](primitive-classes.md)
and `planning/sutra-spec/strings.md`). The runtime carries them as
vectors with the `AXIS_STRING_FLAG` set.

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

### `Math.*` — does not work yet

`Math.sqrt`, `Math.sin`, `Math.PI`, `Math.floor`, etc. all fail at
the Sutra codegen layer. The Sutra-side stdlib has stub
declarations (`stdlib/math.su`) but the underlying transcendentals
need a compile-time-approximation pass — a polynomial / lookup-table
approximation that the codegen folds into a single matmul.

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
slots, see [`docs/ontology.md`](ontology.md) and
`planning/sutra-spec/axons.md`). Property access `person.name`
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

### `try { await ... } catch { ... }` — does not work yet

Same as the general `try` / `catch` story above. Tracked as the
next promise-spec phase.

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

### `import` / `export` — does not work yet

The TS transpiler is single-file per pass — each `.ts` file lowers
independently. Cross-file resolution needs a Sutra-side module
system first, which doesn't exist
([`planning/sutra-spec/program-structure.md`](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/program-structure.md)
explicitly notes there is no `import` today). Workaround: write
single-file programs.

### `require()` — never planned

CommonJS isn't on the roadmap; everything goes through ES modules
when the import system lands.

---

## What untyped JavaScript looks like

If a TS file uses `any` / no type annotations / accesses arbitrary
properties, the transpiler routes through a `JavaScriptObject`
fallback runtime (`stdlib/javascript_object.su`). This lets untyped
code compile, but the resulting Sutra program doesn't get the
substrate-purity benefits — `JavaScriptObject` is a host-side dict
underneath. Use type annotations whenever possible.

Fixture: `sdk/sutra-from-ts/tests/fixtures/untyped_js/`.

---

## Summary table

| TypeScript construct | Status | Notes |
|---|---|---|
| Function declarations | ✅ | C-style annotation flip |
| Arrow functions (as const) | ✅ | Hoisted to top-level fn |
| Arrow functions (as values) | ❌ | Needs first-class function values |
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
| `try` / `catch` | ❌ | Pending AXIS_EXCEPTION work |
| String literals | ✅ | |
| String concat (`+`) | ✅ | |
| Template literals | ❌ | Use `+` concatenation |
| `.length`, `.charAt` | ✅ | |
| `.slice`, `.split`, regex | ❌ | |
| Number literals + arithmetic | ✅ | |
| `Math.*` | ❌ | Needs transcendental approximation |
| Bitwise operators | ❌ | No substrate-pure design yet |
| Array literals + indexing | ✅ | |
| `.length` on arrays | ✅ | |
| `.map`, `.filter`, `.reduce` | ❌ | Needs first-class function values |
| Spread / rest in arrays | ❌ | |
| Object literals | ⚠️ | Lower to Axon |
| Property access | ✅ | Via Axon `.item()` / class field reads |
| Destructuring | ❌ | |
| Object spread | ❌ | |
| `async function`, `await`, `Promise<T>` | ✅ | Full Stage-1 desugar |
| `try { await ... } catch` | ❌ | Pending AXIS_EXCEPTION work |
| `Promise.all`, `Promise.race` | ❌ | Needs first-class fn values |
| Async generators | ❌ | |
| `import` / `export` | ❌ | No Sutra module system yet |

Legend: ✅ works · ⚠️ partial · ❌ not yet

---

## What this means in practice

Most straight-line TS code — classes, functions, loops, arithmetic,
async/await on already-resolved promises — runs through the
transpiler today. The patterns that don't work are concentrated in
**higher-order programming** (callbacks, map/filter, Promise
combinators) and **runtime-keyed iteration** (for-of, for-in, object
destructuring). Both blocked on the same underlying piece — Sutra
needs first-class function values, which is the single biggest
leverage point for TS coverage.

If you're starting a TS-style program in Sutra and not sure which
patterns to lean on:

- **Use** classes, typed functions, while/for loops, async/await,
  string concat, array literals.
- **Avoid** map/filter/reduce, template literals, object
  destructuring, regex. Rewrite to explicit loops and `+` concat.
- **Wait for** first-class function values before depending on
  `.then(callback)` patterns.

---

## Reference

- TS transpiler source: `sdk/sutra-from-ts/`
- Working TS fixtures: `sdk/sutra-from-ts/tests/fixtures/`
- Sutra side of the surface forms: `planning/sutra-spec/` (canonical
  spec) and the rest of these website pages (more readable for
  humans).
- Promise-specific design: [Promises](promises.md) page.
