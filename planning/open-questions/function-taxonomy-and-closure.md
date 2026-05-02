# Function taxonomy and namespace-access semantics

**Source:** Emma 2026-04-30 (clarification on top of
`loop-as-recursive-closure.md`, extending the design absorbed into
`docs/paradigms.md` § "Literal-driven compilation: where Sutra
sits in the design space"). The original chat file was deleted
2026-05-02 once the relevant content was inlined into the
paradigms page.

**Naming correction (Emma 2026-05-01):** there is no closure in
Sutra. Earlier framings here used the word "closure," but what
the design actually describes is **namespace-access scoping** —
free functions read file-level top-level names; methods see only
their class. No environment is captured at function-creation time
the way closures in Lisp / JS / Python work. The word "closure"
in headings and prose below should be read as "scope" / "namespace
access" instead.

## Current state of objects in Sutra

> "I don't think we've really properly implemented the way that
> we're doing objects." — Emma 2026-04-30

The vision below describes the *target*, not what the compiler does
today. Today's compiler has free functions (`function int foo()`)
and the four loop kinds (`do_while NAME(...)` etc.); object methods
exist in the parser but the closure-and-encapsulation semantics are
not load-bearing. This doc captures where it should land.

## Two-axis taxonomy

The primary cut is **loop vs non-loop** because that determines
*how the function compiles*:

- **Non-loops** get fully β-reduced at compile time. They cease to
  exist as callable things; they become part of the weight matrix.
  Includes both regular functions and *bounded loops*
  (`loop(N) { body }` with literal N — fully unrolled at compile
  time, indistinguishable from a non-loop after compilation).
- **Loops** survive compilation as actual recurrent cells. They have
  to, because they represent runtime data-dependent recurrence.
  The recursive call args become the recurrent connections; the
  closed-over context becomes baked weights.

The secondary cut is **scope/closure**:

| Kind | Closure source | Compile-time substitution |
|---|---|---|
| **Free function** | File-level scope (everything declared in the same `.su` file is visible and bake-able) | Free vars get baked into weights |
| **Static method** | Class as namespace; no closure over enclosing scope | The class is just a namespace; method takes only its declared params |
| **Non-static method** | Instance scope (`this` only); no other closure | `this` is the encapsulation boundary |

> "Three functions have closure. Objects attached, whether static or
> non-static, do not have closure, because they're based off of
> encapsulation. I would say it's a bit of a different kind of
> closure." — Emma

The "different kind of closure" for objects is the encapsulation
story: a method has access to its instance's fields (or class's
static fields), but the boundary is explicit and bounded by the
class declaration, not by lexical enclosing scope.

## Free functions and file scope

> "A generic function is typically found on the same file. I don't
> know if I'd necessarily make this strictly formalised, because
> I'm not entirely sure about file creation semantics. A generic
> function is supposed to be on the same file. It can be a loop or
> not a loop, and it has access to everything on the file." — Emma

So free functions close over **the entire file** they're declared
in. Anything declared at the top level of the same `.su` source
file is visible to a free function in that file and bake-able into
its compilation.

The "not strictly formalised" part is whether cross-file closure
should be possible (e.g. via `import`). Today the answer is "no":
imports bring symbols into scope, but the closure relationship is
file-local. Cross-file is left open as a future design question.

## Operators and stdlib are static methods

> "A lot of our operators and stuff like that don't have closure
> because they're attached to the math object or something like
> that. All standard library functions are kind of like static
> methods of the object of the class. Which acts like a namespace
> since the class is abstract." — Emma

Two patterns called out:

1. **Operators** (e.g. `+`, `*`, `==`, `bind`, `bundle`, `unbind`,
   `similarity`) are defined as static methods on a small set of
   abstract classes (`Math`, `VSA`, etc.). They have no closure;
   their only inputs are their declared operands. The class exists
   as a namespace, not a runtime object.
2. **Standard library functions** (e.g. `make_random_rotation`,
   `compile_prototypes`, the future `argmax_cosine`) are static
   methods of abstract classes for the same reason: they're
   namespaced for grep-ability and ontological grouping, but they
   don't close over anything outside their declared params.

The "abstract class as namespace" pattern is essentially the
TypeScript/Java static-only-class convention — the class never
gets instantiated; it's a namespace tag. The compiled artifact
doesn't see classes as objects; it sees them as compile-time
disambiguation markers for which static method is which.

## Six-cell matrix (full taxonomy)

|  | Loop | Non-loop |
|---|---|---|
| **Free function** | Free function loop. File-level closure is recurrent or baked depending on what's in the recursive call signature. | Free function. β-reduced at compile time; file-level closure baked. |
| **Static method** | Static loop. No closure. Recurrent connections = recursive call args; nothing else. | Static method. β-reduced; no closure. |
| **Non-static method** | Non-static loop. Closes over `this` only. Recurrent connections = recursive call args; `this` is the bounded encapsulation. | Non-static method. β-reduced; `this` is the only context. |

All six are valid. The reason for the distinction is *how much the
compiler can verify about what the function is doing*:

- **Non-static methods** have the tightest scope (`this`) and the
  compiler can statically prove what state they touch.
- **Static methods** have no instance state — they're pure functions
  over their params, with the class as a namespace tag.
- **Free functions** have the loosest scope (whole file), so the
  programmer has to be more explicit about what's recurrent vs
  baked when using them in loop form.

## Why this matters for compilation

Each scope tier is a different kind of bake at compile time:

- **Static method** body: every reference is to a declared param or
  to a sibling static method (also bake-able). Pure tree, fully
  reducible.
- **Non-static method** body: every reference is to a declared
  param or to `this.field` (where `this` is bounded). The instance
  fields become indexed reads into a substrate vector representing
  `this`. Still fully reducible.
- **Free function** body: references can include file-level `slot`
  vars, codebook entries, role declarations, other free functions
  in the same file. The compiler walks the file scope, decides
  which references are constants (codebook prototypes, role
  names) vs which are recurrent (loop arguments), and bakes
  accordingly.

Free functions are the hardest to compile cleanly because the
file-level scope is largest. Static and non-static methods are
easier because the scope is bounded by class/instance.

## Implementation status (today, 2026-04-30)

What works:

- `function int foo(...)` declarations parse and compile.
- The four loop kinds (`do_while`, `while_loop`, `iterative_loop`,
  `foreach_loop`) work end-to-end as free function loops.
- `loop(N) { body }` with literal N unrolls at compile time
  (the bounded non-loop case).

What's deferred (this doc captures the design but not the impl):

- Object methods (static or non-static) with proper encapsulation
  semantics.
- File-level scope as the closure scope for free functions, with
  compile-time bake of file-level values.
- Stdlib reorganization to use `class` as namespace for operators
  and stdlib functions.

## Implementation order, when picked up

**0. Encapsulation-rule enforcement (landed 2026-05-01).** The
validator emits **SUT0144** when a method body reads any
file-scope name (top-level FunctionDecl / MethodDecl / VarDecl /
LoopFunctionDecl — class names are exempt, see below) that isn't
bound locally (param or in-body var). This bites before any of the
steps below land — methods today still don't have working codegen,
but the encapsulation rule is now load-bearing at the validator
level so when methods become real, the rule is already enforced.
Test: `tests/corpus/invalid/21_method_reads_file_scope.su`.
Existing corpus stress test `tests/corpus/valid/20_kitchen_sink.su`
was refactored to inline `PetLikeness` into `Describe()` since the
free-function-call-from-method pattern now violates SUT0144.

**0.5. Class bodies with method declarations (landed 2026-05-01).**
The parser now accepts method declarations inside class bodies:
`method ...`, `static method ...`, `intrinsic method ...;`, and
`static intrinsic method ...;`. `ClassDecl.methods` carries them;
the validator walks them via the existing visit_MethodDecl path,
so SUT0144 fires for in-class method bodies the same way it does
for top-level methods. Class names themselves are exempt from the
file-scope encapsulation rule (you can call `Math.log(x)` from a
method body — class names are namespace anchors, not file-scope
reads).

**1. Static-method-as-namespace dispatch (landed 2026-05-01).**
Slice 1 codegen + stdlib-loader infrastructure:
- Static methods inside class bodies emit as mangled top-level
  Python functions (`{ClassName}_{method_name}`).
- Calls of the form `Math.foo(x)` dispatch to the mangled name
  via a pre-pass over module items (so forward references work).
- Static intrinsic methods (`static intrinsic method ...;`)
  dispatch directly to `_VSA.<method>(args)` with no wrapper.
- Non-static methods on user classes raise CodegenNotSupported
  pointing at the deferred instance-dispatch work (step 3 below).
- `stdlib_loader.load_stdlib()` now picks up class-bodied static
  methods alongside top-level FunctionDecl, registering them
  under both the bare name (backward-compat) and the namespaced
  form (`Math.log`).
- Tests: `TestClassStaticMethodDispatch` in test_codegen.py;
  examples/class_static_dispatch.su runs end-to-end.

What remains for the **actual stdlib migration**: rewriting
stdlib/math.su, stdlib/rotation.su, stdlib/similarity.su, etc.
to wrap their declarations in `class Math { ... }` /
`class VSA { ... }` / etc. The loader infrastructure accepts both
shapes today, so the migration is a series of small, individually
shippable file rewrites — none of them break existing user code
that still calls bare names.

2. **Static-method-as-namespace migration of stdlib.** Migrate the
   existing stdlib (`stdlib/math.su`, `stdlib/rotation.su`,
   `stdlib/similarity.su`, etc.) to declare its functions as static
   methods of a class-as-namespace. The loader / dispatch
   infrastructure (step 1) accepts both shapes already, so this is
   a series of small, individually shippable file rewrites — none
   break existing user code calling bare names.
3. **Free-function file-level scope (no-op).** Free functions
   already read file-level names — that's just Python's natural
   scoping in the emitted code. The "closure" phrasing in earlier
   docs was a misnomer (Emma 2026-05-01: "there is no closure in
   this language"). This step is therefore a documentation
   correction rather than implementation work.
4. **Non-static method dispatch (landed 2026-05-01).** Non-static
   methods now compile to `def {Class}_{method}(this, *params)`,
   with `this` threaded as the implicit first parameter.
   `this.method(args)` inside a method body dispatches to
   `{CurrentClass}_{method}(this, *args)`. `Class.method(instance,
   args)` also works. Instance-syntax dispatch on a typed variable
   (`g.method(args)` for `Greeter g`) needs variable type tracking
   and is deferred. (Commit `2429d76`.)
5. **Class-level slots (gated on field declarations).** Static
   methods can call sibling static/intrinsic methods through the
   class namespace today. Per-class state would require field
   declarations inside class bodies (`field x : int;`) — that
   surface doesn't exist yet, so step 5 is gated. When fields land,
   class-level state becomes meaningful and the codegen can emit a
   class-scope state vector that static methods read.
6. **Object loops (landed 2026-05-01, partial).** Loop function
   declarations inside class bodies now parse and emit as
   `_loop_{Class}_{name}`. `loop Class.name(...)` call sites
   dispatch correctly. The `this`-as-recurrent-state threading for
   non-static object loops (per Emma's design — every iteration
   gets the same instance with all its properties) is the
   remaining piece; today class loops behave equivalently to
   static loops. (Commit `4bf73b6`.)

This is a substantial refactor — likely a separate plan when the
slot at the front of the queue rolls around to it. Probably comes
after the paper is shipped, since the paper's substrate-purity
story doesn't depend on object semantics being load-bearing.

## Connection to the paper

The paper's empirical foundation (relational displacements in frozen
embedding spaces) and substrate story (bind/unbind/bundle as tensor
ops) don't require objects to be load-bearing. The taxonomy here is
mostly about *language ergonomics* and *compile-time scope rules*,
not about the substrate operations themselves. So the paper can ship
with today's free-function-only compiler; objects come later.

What the paper *can* claim about objects: "Sutra's design includes
ontology-oriented objects (closer to OWL classes than OOP) for
compile-time semantic checking; the compiler's current
implementation focuses on the substrate-pure tensor-op core, with
object encapsulation deferred."

That's an honest scoping. The full vision (this doc) is the design
target the language is built toward.
