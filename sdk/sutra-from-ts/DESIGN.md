# sutra-from-ts — design notes

> **Skeleton stage — design refinement pass 2026-05-07.** No
> transpilation logic exists yet; this file is the design surface.
> The Sutra-side machinery axons rely on (axon class wired through
> codegen, void-method-as-augmented-assignment, within-function
> SSA-elision) is now in place, so the lowering rules below have a
> concrete target. Open questions are flagged inline.

## What the transpiler accepts

The typed core of TypeScript:

- Function declarations and expressions, including arrow functions.
- Interfaces and type aliases (`type Foo = { x: number; y: number }`).
- Classes, including methods, constructors, and access modifiers (which Sutra parses but ignores today, matching).
- Generics, where the constraints are simple enough to lower (mapped types and conditional types are out of scope for v1).
- Discriminated unions and narrowing (`if (typeof x === "string") { … }`).
- Module imports and exports — but only as a way to surface symbols within the same translation unit; cross-file imports are deferred.
- The primitive types `number`, `string`, `boolean`, `bigint`, and their literal counterparts.

JavaScript is read as TypeScript with type annotations stripped. The transpiler runs the same pipeline on a `.js` file, but unlike "untyped TS" — where unannotated locals would be `any` — JavaScript values get a concrete fallback class on the Sutra side. See §"JavaScriptObject" below.

## What the transpiler explicitly rejects

- `eval`, `Function` constructor, dynamic code generation. User-facing error: "dynamic code generation is not supported."
- Prototype mutation (`obj.__proto__ = …`, `Object.setPrototypeOf`). The static structure of a Sutra class is set at compile time; mutating it at runtime has no lowering.
- `with` statement. Banned in TS strict mode anyway.
- Decorators with side effects. The decorator surface in TS is flexible enough that the transpiler v1 will accept only annotation-shaped decorators (no class transformation).
- `Object.defineProperty`, `Proxy`, `Reflect`. Same reason as prototype mutation.
- Generators, async/await, promises. The Sutra side has no concurrency primitives that match Promise semantics today; deferred until `concurrency.md` consolidates.

## JavaScriptObject — the JS fallback type

JavaScript is dynamically typed. A `.js` file has no type annotations; in TypeScript-with-no-type-info mode every value is `any`. Mapping `any` to Sutra's `vector` is technically correct but loses too much structure — vector ops don't have field semantics, and TS's `any` does.

**Resolution:** every JS value whose type cannot be resolved gets the concrete class `JavaScriptObject` on the Sutra side. `JavaScriptObject` is a class declared in the transpiler's runtime stdlib (concretely: a `class JavaScriptObject extends Axon { … }` decl that ships with `sutra-from-ts`). Its surface API mirrors a JS object's: dynamic property access, the `[]` accessor, etc.

```ts
// JavaScript
let x = something();
x.foo = 5;
let y = x.bar;
```

→

```
JavaScriptObject x = something();
x.set("foo", 5);                       // JS property assignment
JavaScriptObject y = x.get("bar");     // JS property read
```

A TypeScript value with a real type keeps that type; `JavaScriptObject` only kicks in for values that would have been `any`. So in mixed-type code:

```ts
function foo(x: number, y) {           // x typed, y is implicit any
    return x + y.size;
}
```

the transpiler emits `int x` (or `float x`, depending on inference) and `JavaScriptObject y` — it does not promote everything to JavaScriptObject.

> **Open question.** What `JavaScriptObject` is *underneath*. Plausible candidates: (a) just an `Axon` with a string-keyed convention; (b) a separate class that wraps an Axon plus a small extra payload for prototype-chain emulation; (c) a richer construct that doesn't lower until the runtime supports prototype-chain semantics. (a) is the cheapest and closest to what we have today.

> **Open question.** What `Object` (the TypeScript class) lowers to — same as `JavaScriptObject`, or something stricter for typed-object usage. Probably the same.

## Strings — deferred

This is the largest known hole. **In Sutra source, a string literal `"hello"` is an embedding** (auto-embedded into a basis vector via the substrate). To carry an actual text-string value through a program — for printing, equality comparison, indexing into character arrays — you need a separate `String` class wrapping the literal. The user's framing: a string literal *requires* explicit wrapping in a `String` class to be treated as a string-valued thing rather than an embedding.

The `String` class **does not exist yet** in Sutra. The plan is for it to be a synthetic-vector representation (analogous to how `int`, `float`, `complex` live on synthetic axes), but the design isn't pinned. See `planning/sutra-spec/types.md` open questions.

For the transpiler:

- A JS / TS `string` value lowers to `String("hello")` — explicit wrapping.
- A JS / TS string-valued operation (`s.length`, `s + t`, `s.charAt(i)`) lowers to method calls on the wrapped String.
- Until the Sutra `String` class lands, the transpiler can **emit** these forms but the emitted `.su` won't compile and run end-to-end. The lowering is design-completable now; the runtime is gated on the String class.

```ts
const greeting: string = "hello";
const length: number = greeting.length;
```

→

```
String greeting = String("hello");
int length = greeting.length();
```

> **Open question.** What `String` actually is on the Sutra substrate (synthetic-vector encoding, codebook-of-codepoints, character-as-axis, …). The transpiler doesn't need to decide this; it needs the surface API to be stable.

## Lowering rules (sketches)

### Functions

```ts
function add(a: number, b: number): number {
    return a + b;
}
```

→

```
function int add(int a, int b) { return a + b; }
```

TypeScript's `number` is double-precision IEEE-754 float, but Sutra's typed surface separates `int` and `float`. The transpiler picks based on usage analysis. **Open question:** how to handle `number` values that flow between integer and float contexts.

### Interfaces and typed objects → axon-shaped values

```ts
interface Point { x: number; y: number }
const p: Point = { x: 3, y: 4 };
const px: number = p.x;
```

→

```
Axon p;
p.add("x", 3);
p.add("y", 4);
int px = p.item("x");
```

The Sutra-side axon machinery is now wired (commits `6035344`, `aac0db2`, `4afbdd5`):

- `Axon a;` constructs an empty axon.
- `a.add(k, v);` is augmented assignment — the compiler beta-reduces it to `a = Axon.axon_add(a, k, v)`.
- `a.item(k)` is read-only.
- Within-function SSA-elision drops `add` calls whose keys are never read (provided `a` doesn't escape).

**Open question:** does `interface B extends A` lower as a single flat axon (extends the key set), or as a nested axon (B has an "_super" key whose value is an A-shaped axon)? Flat is simpler; nested is more faithful to JS prototype semantics.

### Classes

```ts
class Point {
    constructor(public x: number, public y: number) {}
    distance_to(o: Point): number {
        return Math.sqrt((this.x - o.x) ** 2 + (this.y - o.y) ** 2);
    }
}
```

→ structurally:

```
class Point extends vector {
    method int distance_to(Point o) {
        return Math.sqrt((this.x - o.x) ** 2 + (this.y - o.y) ** 2);
    }
}
```

Method bodies use the void-method augmented-assignment rule (commit `0893675`) when a method mutates `this`. End-to-end execution requires `Math.sqrt` (transcendentals are currently disabled per `numeric-math.md`).

### Discriminated unions and narrowing

```ts
type Shape = { kind: "circle"; r: number } | { kind: "square"; side: number };
function area(s: Shape): number {
    if (s.kind === "circle") return Math.PI * s.r ** 2;
    return s.side ** 2;
}
```

→ a `select` over the discriminator, one branch per case. **Open question:** how Sutra's `select` interacts with TS's exhaustiveness checking.

### Loops and side-effect-heavy bodies

The transpiler's standard pattern for `for` / `while` / `do-while` is:

1. Hoist every variable referenced in the loop body into an axon.
2. Lower the loop into a tail-recursive Sutra function whose state is that axon.
3. The loop body becomes the function body, with mutations rewritten as `a.item("varname") = ...` augmented assignments.

This is the user's "cheat way of doing tail recursion" pattern from the axon spec. Smarter analyses can prune variables that don't escape the loop, but the dumb form is robust to side effects. See `planning/sutra-spec/axons.md` §"Axons as loop carriers" for the worked example.

### Untyped values (JavaScript / implicit `any`)

A `.js` file's `function f(x) { return x + 1 }` lowers to:

```
function JavaScriptObject f(JavaScriptObject x) {
    return JavaScriptObject.add(x, 1);
}
```

`JavaScriptObject.add` is the JS `+` semantics on the wrapping class — string concatenation, numeric coercion, etc. This lowers cleanly once `JavaScriptObject` is defined.

## Architecture (planned)

```
input.ts (or .js)
   │
   ▼
tree-sitter-typescript  (third-party; produces a tree-sitter parse tree)
   │
   ▼
type-resolve.py  (this package; runs a small type-inference pass over the
                 tree, mostly for narrowing and "could this number be an
                 int". Does NOT replace tsc.)
   │
   ▼
lower.py   (this package; walks the tree, emits Sutra IR)
   │
   ▼
emit.py    (this package; renders Sutra IR to .su source text)
   │
   ▼
output.su
```

The Sutra IR is local to this package — no shared shape with `sutra_compiler.ast_nodes`. The output is rendered `.su` text fed downstream to `sutra-compiler`.

## Why tree-sitter, not tsc

Two reasons. First, calling `tsc` from Python means a Node.js dependency, which makes the `pip install` story messier. Second, `tsc`'s AST is undocumented and unstable across versions; tree-sitter's grammar is versioned and stable. The trade-off is that tree-sitter doesn't do type inference — the transpiler does its own narrow inference pass good enough for the lowering decisions we need (integer-vs-float, narrowed-discriminator, is-this-`any`-or-typed).

If full TypeScript type-inference fidelity becomes necessary, the parser can be swapped out for `tsc --emit-ast` later.

## What blocks end-to-end execution today

The lowering rules above are mostly design-completable now. End-to-end *execution* (transpile a `.ts` file, then `sutrac --run` the resulting `.su`) is gated on:

1. **The `String` class.** Until Sutra has one, any TS program that uses string operations stops at the runtime layer.
2. **`JavaScriptObject` runtime.** Likely a thin wrapper over `Axon` with JS-semantics methods (the `+`-as-concat-or-coerce surface, `===`, etc.). Easy to define once `String` lands.
3. **`Math.*` shims.** Transcendentals are disabled in Sutra (`numeric-math.md`); any TS program using `Math.sqrt`, `Math.PI`, etc. won't run.
4. **Async / Promise.** Sutra has no concurrency surface yet.
5. **Cross-file modules.** v1 is single-file; multi-file resolution comes after.

It is fine to design and partially implement the transpiler against these gaps — the lowering rules are stable, the emitted `.su` is just non-runnable until the dependencies land.

## Open questions blocking implementation

1. **Integer vs float distinction.** TS's `number` is one type; Sutra's typed surface separates `int` and `float`. How aggressive is the transpiler's inference?
2. **Interface inheritance.** `interface B extends A` — extend the key set (flat axon), or nest A inside B (`b.item("_super")` returns the A-shaped sub-axon)?
3. **`String` class shape.** Synthetic-vector encoding? Codebook? Other?
4. **`JavaScriptObject` underlying form.** Axon with string keys, or richer construct?
5. **`Math.*` and standard library shims.** TS code leans heavily on `Math.sqrt`, `Math.PI`, `String.prototype.*`. Transpiler emits the shim names; runtime support is gated on Sutra's transcendentals landing.
6. **Async / Promise.** Deferred until Sutra's `concurrency.md` has a user-confirmed surface.
7. **Module imports.** Cross-file lowering is deferred; v1 is single-file.

(1) is needed for arithmetic to come out right. (2)-(4) are needed for end-to-end execution. (5)-(7) gate specific TS programs but can be deferred behind explicit errors.
