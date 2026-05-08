# sutra-from-ts — design notes

> **Skeleton stage.** No transpilation logic exists yet. This file is the
> design surface for what the transpiler will do once it's implemented.
> Open questions are flagged inline.

## What the transpiler accepts

The typed core of TypeScript:

- Function declarations and expressions, including arrow functions.
- Interfaces and type aliases (`type Foo = { x: number; y: number }`).
- Classes, including methods, constructors, and access modifiers (which Sutra parses but ignores today, matching).
- Generics, where the constraints are simple enough to lower (mapped types and conditional types are out of scope for v1).
- Discriminated unions and narrowing (`if (typeof x === "string") { … }`).
- Module imports and exports — but only as a way to surface symbols within the same translation unit; cross-file imports are deferred.
- The primitive types `number`, `string`, `boolean`, `bigint`, and their literal counterparts.

JavaScript is read as TypeScript with type annotations stripped. The transpiler runs the same pipeline on a `.js` file; everything that would have been typed becomes `vector` (Sutra's bottom of the typed surface) and narrowing checks become explicit `select` branches.

## What the transpiler explicitly rejects

- `eval`, `Function` constructor, dynamic code generation. User-facing error: "dynamic code generation is not supported."
- Prototype mutation (`obj.__proto__ = …`, `Object.setPrototypeOf`). The static structure of a Sutra class is set at compile time; mutating it at runtime has no lowering.
- Implicit `any`. A function or variable whose type cannot be inferred and is not annotated is rejected.
- `with` statement. Banned in TS strict mode anyway.
- Decorators with side effects. The decorator surface in TS is flexible enough that the transpiler v1 will accept only annotation-shaped decorators (no class transformation).
- `Object.defineProperty`, `Proxy`, `Reflect`. Same reason as prototype mutation.
- Generators, async/await, promises. The Sutra side has no concurrency primitives that match Promise semantics today; deferred until `concurrency.md` consolidates.

## Lowering rules (sketches)

These are first cuts and want the [axon spec](../../planning/sutra-spec/axons.md) to stabilize before they harden.

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

The closest mapping. TypeScript's `number` is double-precision IEEE-754 float, but in Sutra's typed surface the equivalent is `int` for integer-shaped values and `float` for fractional ones — the transpiler picks based on usage analysis. **Open question:** how to handle `number` values that flow between integer and float contexts.

### Interfaces / type aliases → axon types

```ts
interface Point { x: number; y: number }
const p: Point = { x: 3, y: 4 };
```

→

```
class Point extends vector { }
vector p = bundle( bind(R_x, 3), bind(R_y, 4) );
```

Each interface field becomes a role; an instance is a role/filler bundle. Same pattern as the C struct lowering. **Open question:** how interface inheritance (`interface B extends A`) lowers — likely by extending the role set, but the type-checking story isn't worked out.

### Classes

```ts
class Point {
    constructor(public x: number, public y: number) {}
    distance_to(o: Point): number {
        return Math.sqrt((this.x - o.x) ** 2 + (this.y - o.y) ** 2);
    }
}
```

→

(deferred until `Math.sqrt` and other transcendental shims have an answer; the structural part lowers cleanly to `class Point extends vector { ... }` plus methods, but `**` and `sqrt` block end-to-end execution today.)

### Discriminated unions and narrowing

```ts
type Shape = { kind: "circle"; r: number } | { kind: "square"; side: number };
function area(s: Shape): number {
    if (s.kind === "circle") return Math.PI * s.r ** 2;
    return s.side ** 2;
}
```

→

A `select` over `s.kind` with one branch per discriminator, each branch decoding the appropriate role. **Open question:** how Sutra's `select` semantics interact with TS's exhaustiveness checking — TS guarantees the union is closed, Sutra's `select ... else` does not assume closure.

### Untyped values (JavaScript)

A `.js` file's `function f(x) { return x + 1 }` lowers to `function vector f(vector x) { return x + 1; }` — every argument is `vector`, every return is `vector`. The user gets fewer guarantees but the program still compiles. The transpiler emits a warning per untyped surface so the user can see where `any`-equivalent slop is.

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

Two reasons. First, calling `tsc` from Python means a Node.js dependency, which makes the `pip install` story messier. Second, `tsc`'s AST is undocumented and unstable across versions; tree-sitter's grammar is versioned and stable. The trade-off is that tree-sitter doesn't do type inference — the transpiler does its own narrow inference pass good enough for the lowering decisions we need (mostly: integer-vs-float, narrowed-discriminator, is-this-`any`).

If full TypeScript type-inference fidelity becomes necessary, the parser can be swapped out for `tsc --emit-ast` later.

## Open questions blocking implementation

1. **Integer vs float distinction.** TS's `number` is one type; Sutra's typed surface separates `int` and `float`. How aggressive is the transpiler's inference?
2. **Interface inheritance.** `interface B extends A` — extend the role set, or fail?
3. **`Math.*` and standard library.** TS code leans on `Math.sqrt`, `Math.PI`, `String.prototype.*` heavily. The transpiler needs a shim layer; see Sutra's `numeric-math.md` for the disabled-transcendentals state.
4. **Async / Promise.** Deferred until Sutra's `concurrency.md` has a user-confirmed surface.
5. **Module imports.** Cross-file lowering is deferred; v1 is single-file. When it lifts, the transpiler needs an answer for what a TS module corresponds to in Sutra's `program-structure.md`.

The transpiler is blocked on (1)–(2) for the typed surface to lower at all. (3) blocks `Math.*`-using programs from running end-to-end. (4) and (5) can be deferred behind explicit errors.
