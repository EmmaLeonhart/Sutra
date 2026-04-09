# S2 Language Comparisons

This document is a working reference for designing S2 syntax. It does not lock decisions by itself. It exists to compare language shapes, syntax tradeoffs, and semantic defaults before we commit to S2 forms.

## Current S2 Direction

- S2 is not aiming to look like a general-purpose scripting language.
- S2 functions exist independently rather than living inside classes or modules by default.
- S2 uses `function` as the function declaration keyword.
- S2 uses TypeScript-style `if (...) { ... } else { ... }` conditionals.
- S2 uses `return`.
- S2 uses TypeScript-style `while (...) { ... }` looping syntax.
- S2 has `fuzzy` and `bool`, and `defuzzy(...)` converts `fuzzy` to `bool`.
- C# remains a primary comparison language because it is the clearest existing baseline for explicit, readable compiled syntax.
- S2 should probably sit above assembly and below C# in abstraction level.
- S2 has to stay compatible with fuzzy, vector-native semantics rather than pretending values are conventional datatypes.
- Syntax should help with reasoning, not hide the substrate.

## Quick Comparison Matrix

| Language | General Feel | Function Model | Typical Syntax Pressure | Likely S2 Takeaway |
| --- | --- | --- | --- | --- |
| C# | structured, explicit, industrial | functions usually live in classes or types | verbosity, declarations, braces, type surface area | good for readability and names, bad fit for class-centric defaults |
| TypeScript | JavaScript shape with added structure | free functions exist but module patterns dominate | type annotations, object literals, arrow functions | good reference for tooling-heavy design without full OOP commitment |
| JavaScript | lightweight, flexible, multi-style | functions are first-class and can stand alone | too many forms for the same thing, weak semantic discipline | useful for independent functions, weak as a model for language rigor |
| Python | readable, indentation-driven | top-level functions are normal | whitespace significance, dynamic ambiguity, runtime-centric feel | good reference for approachable definitions, maybe too soft for substrate-oriented code |
| Rust | explicit, expression-oriented, systems-minded | free functions are normal; methods are secondary | ownership, types, punctuation density | good model for standalone functions and disciplined syntax |
| Scheme | tiny core, prefix notation, functional | functions are primary and independent | uniform syntax can hide intent for non-Lisp readers | strong reference for small-core language design |
| Lisp | homoiconic, macro-friendly, symbolic | functions are independent and central | parentheses dominate surface readability | useful if S2 needs code-as-structure, risky if readability matters more |

## S2 Decisions Already Made

- Functions exist independently.
- The function declaration keyword is `function`.
- Conditionals use TypeScript-style `if (...) { ... } else { ... }`.
- S2 uses `return`.
- Looping uses TypeScript-style `while (...) { ... }`.
- `fuzzy` and `bool` are distinct types, and `defuzzy(...)` converts `fuzzy` to `bool`.
- C# remains a reference baseline for readability, block structure, and declaration clarity even where S2 diverges from its class model.
- `if (cat)` is a compilation error — classes do not exist at runtime, branching requires `bool` or `fuzzy`.
- Truthiness is geometric (euclidean distance from true/false vectors), accessed only via unsafe cast or unsafeOverride.
- Operators support overloading via `function operator +(vector a, vector b) { ... }`.
- Implicit casts are allowed but must be explicitly defined in source.
- Casting `fuzzy` to `bool` performs `defuzzy(...)` as a special built-in cast.
- The class system is almost entirely user-defined, not special to the runtime — this is why operator overloading is straightforward.

## Readability Notes

Python, C#, and TypeScript all help in different ways, but not equally.

- Python has readable definitions because `def name(...)` plus indentation makes the main shape of a function very easy to scan.
- C# has strong readability because it is explicit, consistent, and visually disciplined. Declarations, blocks, and statements tend to have one obvious mainstream form.
- TypeScript has good ergonomics, but weaker raw readability than C# because it inherits JavaScript's multiplicity of styles: function declarations, arrows, methods, object-literal-heavy code, optional types, and more variation in what "normal" code looks like.

S2 implication:

- When I say TypeScript is useful, I mostly mean syntax direction and tooling model.
- When I say C# is a readability baseline, I mean it is the stronger reference for visual discipline and consistency.
- Python remains useful as a reminder that readable function declarations do not require heavy syntax.

## By Language

## C#

### Useful traits

- Strong naming conventions for declarations.
- Clear block structure.
- Good separation between declarations and statements.
- Reads like a serious compiled language.

### Weak fit for S2

- Too class-centered for the direction currently on the table.
- Type declarations communicate things S2 may not want to pretend it has.
- Property and access-modifier culture adds weight without helping vector semantics.

### S2 lesson

Take seriousness and declaration clarity from C#, but not its class-first worldview.

### Concrete syntax pressure from C#

- C# is still the best mainstream reference for how explicit block-based code should scan.
- S2 should keep comparing new syntax sketches against "would this still feel as readable as C#?".
- Even where S2 adopts `function` from TypeScript, the desired level of structure is still closer to C# than to JavaScript.

## TypeScript

### Useful traits

- Tooling can be load-bearing without turning the source into total ceremony.
- Free functions and modules are normal enough.
- Good balance between readable syntax and modern expression forms.
- Interfaces show how "soft structure" can still be documented explicitly.

### Weak fit for S2

- Structural typing assumes conventional data shapes.
- JavaScript inheritance from the host language brings legacy weirdness.
- Too many equivalent function styles if copied directly.
- Raw visual consistency is weaker than C# because the ecosystem tolerates more syntactic variation.

### S2 lesson

TypeScript is a good reference for a language where tooling matters, but S2 should avoid inheriting JavaScript's excess surface area.

## JavaScript

### Useful traits

- Functions truly exist independently.
- First-class function semantics are natural.
- Modules can stay lightweight.

### Weak fit for S2

- Surface syntax is too permissive.
- Multiple declaration forms weaken stylistic consistency.
- Prototype/object idioms are mostly noise for S2.

### S2 lesson

Keep function independence, reject permissiveness.

## Python

### Useful traits

- Top-level functions read cleanly.
- Syntax is approachable.
- Minimal punctuation can help core ideas stand out.

### Weak fit for S2

- Indentation significance may be too fragile for a substrate-oriented language.
- Dynamic "just run it" culture may work against explicit semantic control.
- Conventional literals and containers imply datatypes S2 may not want.

### S2 lesson

Python is a strong readability reference, but S2 may need more visible structure than indentation alone.

## Rust

### Useful traits

- Free functions are fully respectable.
- Item-oriented layout works well in source files.
- Expression orientation could map well to vector transformations.
- Feels compiled and disciplined without needing classes.

### Weak fit for S2

- Rust's type and ownership machinery is specific to its memory model.
- Syntax can become visually dense quickly.

### S2 lesson

Rust is one of the better mainstream references for "serious language with independent functions."

## Scheme

### Useful traits

- Small number of primitives.
- Functions and composition are central.
- Very good precedent for building a powerful language from a compact semantic core.

### Weak fit for S2

- Uniform prefix notation can make different semantic categories look too similar.
- Readability cost is real for larger codebases if the audience is not already Lisp-native.

### S2 lesson

Scheme is a strong conceptual reference for minimalism and function-first design, even if S2 does not use prefix syntax.

## Lisp

### Useful traits

- Code-as-data is powerful if S2 ever needs self-transforming programs.
- Independent functions are completely natural.
- Symbolic structure is explicit.

### Weak fit for S2

- Surface syntax is polarizing.
- Homoiconicity may be more power than we need at the start.
- Parenthesis-heavy syntax may obscure vector-semantic intent for readers.

### S2 lesson

Lisp is useful as a reminder that a language can center functions and symbolic composition without classes, but its concrete notation should not be adopted casually.

## Cross-Cutting Syntax Questions For S2

## 1. Function Declarations

Because independent functions are already an active decision, the main question is no longer whether S2 has free functions. The declaration keyword is also decided now: S2 uses `function`. The remaining question is what the rest of a function definition should look like.

Reference shapes:

```text
C#         result Blend(a, b) { ... }
TypeScript function blend(a, b) { ... }
JavaScript function blend(a, b) { ... }
Python     def blend(a, b):
Rust       fn blend(a, b) -> Result { ... }
Scheme     (define (blend a b) ...)
Lisp       (defun blend (a b) ...)
S2         function blend(a, b) { ... }
```

Current S2 implication:

- `function` is the active declaration keyword.
- A declaration keyword is better than relying on punctuation alone.
- Return-type syntax should stay optional until S2 has stronger commitments about its type surface.

## 2. Blocks Versus Indentation

Reference split:

- Braces: C#, TypeScript, JavaScript, Rust
- Indentation: Python
- Parenthesized forms: Scheme, Lisp

Early S2 implication:

- Braces are the safest default if S2 needs explicit, unambiguous structure.
- Indentation-only syntax is elegant but easier to make fragile.
- Lisp-style grouping should only be chosen if code-as-structure becomes a core goal.

Current S2 note:

- Current syntax decisions already lean hard toward brace-based structure because conditionals and loops now follow TypeScript-style forms.

## 3. Statement Versus Expression Orientation

Reference split:

- More statement-heavy: C#, JavaScript
- Mixed: TypeScript, Python
- More expression-heavy: Rust, Scheme, Lisp

Early S2 implication:

- Expression-oriented design may fit vector transformations better than a purely statement-driven model.
- S2 probably still needs explicit declaration forms even if most computation is expression-shaped.

## 4. Typing Surface

Reference split:

- Heavy visible types: C#, Rust, TypeScript
- Light or dynamic surface: JavaScript, Python
- Semantic minimalism: Scheme, Lisp

Early S2 implication:

- S2 should be careful not to fake conventional datatypes if the substrate is fundamentally vector-native.
- It may still need lightweight annotation forms for roles such as atomic, predicate, truth-space, transform, or compiled artifact classes.

## 5. Calling Style

Reference split:

- Infix-friendly mainstream syntax: C#, TypeScript, JavaScript, Python, Rust
- Prefix-only functional syntax: Scheme, Lisp

Early S2 implication:

- Infix syntax is probably better for readability when representing algebraic operations.
- Prefix forms might still be useful for primitive substrate operations if they need to be unmistakable.

Current S2 note:

- Primitive operation call syntax is still unresolved and remains a source of confusion.

## Initial S2 Lean

If we stay aligned with the current direction, the strongest influences are probably:

- C# for readability, declaration seriousness, and brace-oriented structure
- Rust for serious free-function structure
- TypeScript for tooling-aware ergonomics
- Python for readability pressure
- Scheme for compact semantic core

The weakest direct influences are probably:

- JavaScript permissiveness
- Lisp concrete notation, unless homoiconicity becomes a central goal

C# is a split influence rather than a weak one:

- strong for readability, statement structure, naming, and explicit blocks
- weak only where it assumes classes, nominal types, and object-model-first design

## Provisional Non-Decisions

These are intentionally not locked yet:

- whether blocks use braces
- whether return annotations exist
- whether modules/namespaces are mandatory, optional, or absent
- whether primitive operations are infix, prefix, or mixed
- whether S2 source is expression-first or statement-first
- cast declaration syntax (the rules are decided, the declaration form is not)
- annotation system for semantic roles

## Next Decisions To Make

- exact shape of top-level function signatures beyond the `function` keyword
- whether S2 has explicit namespaces or just files plus symbols
- whether primitive operations look mathematical, keyword-based, or both
- how the primitive layer is surfaced in user code
- declaration syntax for implicit conversions
- whether there is any lightweight role-annotation system even without conventional datatypes
- expression-versus-statement bias

## Code Comparison Examples

These examples exist to compare syntax shape rather than semantics. They intentionally use roughly equivalent constructs even where the underlying language models differ.

## Example 1: Declare A Simple Function

```text
C#
static Result Blend(Vector a, Vector b)
{
    return Combine(a, b);
}

TypeScript
function blend(a: Vector, b: Vector): Result {
  return combine(a, b);
}

JavaScript
function blend(a, b) {
  return combine(a, b);
}

Python
def blend(a, b):
    return combine(a, b)

Rust
fn blend(a: Vector, b: Vector) -> Result {
    combine(a, b)
}

Scheme
(define (blend a b)
  (combine a b))

Lisp
(defun blend (a b)
  (combine a b))

S2 current lean
function blend(a, b) {
    return combine(a, b);
}
```

## Example 2: Bind A Name To An Intermediate Value

```text
C#
var pair = Bind(left, right);

TypeScript
const pair = bind(left, right);

JavaScript
const pair = bind(left, right);

Python
pair = bind(left, right)

Rust
let pair = bind(left, right);

Scheme
(define pair (bind left right))

Lisp
(let ((pair (bind left right)))
  ...)

S2 questions to resolve
let pair = bind(left, right)
pair = bind(left, right)
value pair = bind(left, right)
```

S2 takeaway:

- This is still open.
- C#, Rust, TypeScript, and Python give the cleanest mainstream references here.
- Scheme and Lisp show that declaration syntax can stay minimal if the rest of the language is structurally consistent.

## Example 3: Conditional Execution

```text
C#
if (isTrue(signal))
{
    return activate(signal);
}
else
{
    return dampen(signal);
}

TypeScript
if (isTrue(signal)) {
  return activate(signal);
} else {
  return dampen(signal);
}

JavaScript
if (isTrue(signal)) {
  return activate(signal);
} else {
  return dampen(signal);
}

Python
if is_true(signal):
    return activate(signal)
else:
    return dampen(signal)

Rust
if is_true(signal) {
    activate(signal)
} else {
    dampen(signal)
}

Scheme
(if (is-true signal)
    (activate signal)
    (dampen signal))

Lisp
(if (is-true signal)
    (activate signal)
    (dampen signal))

S2 design pressure
if (isTrue(signal)) {
    return activate(signal);
} else {
    return dampen(signal);
}
```

S2 takeaway:

- TypeScript-style `if (...) { ... } else { ... }` is now the active S2 decision.
- C# remains one of the clearest readability baselines for branch layout.
- Because S2 truth is fuzzy, the key open question is semantic behavior rather than branch punctuation.

## Example 4: Expression-Oriented Conditional

```text
C#
var result = isTrue(signal) ? activate(signal) : dampen(signal);

TypeScript
const result = isTrue(signal) ? activate(signal) : dampen(signal);

JavaScript
const result = isTrue(signal) ? activate(signal) : dampen(signal);

Python
result = activate(signal) if is_true(signal) else dampen(signal)

Rust
let result = if is_true(signal) {
    activate(signal)
} else {
    dampen(signal)
};

Scheme
(define result
  (if (is-true signal)
      (activate signal)
      (dampen signal)))

Lisp
(setf result
      (if (is-true signal)
          (activate signal)
          (dampen signal)))
```

S2 takeaway:

- C# and TypeScript show the mainstream compact form.
- Rust and Python are strong references if S2 leans expression-oriented.
- C#/TypeScript/JavaScript ternaries are compact, but they may be too lightweight for early S2 readability.
- This is still not an active S2 decision.

## Example 5: Looping

```text
C#
while (!done(state))
{
    state = step(state);
}

TypeScript
while (!done(state)) {
  state = step(state);
}

JavaScript
while (!done(state)) {
  state = step(state);
}

Python
while not done(state):
    state = step(state)

Rust
while !done(&state) {
    state = step(state);
}

Scheme
(let loop ((state state))
  (if (done state)
      state
      (loop (step state))))

Lisp
(loop while (not (done state))
      do (setf state (step state)))
```

S2 takeaway:

- TypeScript-style `while (...) { ... }` is now the active S2 surface decision.
- Iteration semantics are still open at the language-design level.
- C# remains the readability baseline for explicit loop structure.
- Scheme's named recursion is a useful reminder that loops do not require dedicated loop syntax.

## Example 6: Namespace, Module, Or Grouping Pressure

```text
C#
namespace S2.Core;

public static class Basis
{
    public static Result Blend(Vector a, Vector b) { ... }
}

TypeScript
export function blend(a: Vector, b: Vector): Result {
  return combine(a, b);
}

JavaScript
export function blend(a, b) {
  return combine(a, b);
}

Python
def blend(a, b):
    return combine(a, b)

Rust
pub fn blend(a: Vector, b: Vector) -> Result {
    combine(a, b)
}

Scheme
;; usually file/module system dependent
(define (blend a b) ...)

Lisp
(defun blend (a b) ...)
```

S2 takeaway:

- TypeScript and Rust are better references than C# specifically for standalone functions plus optional module structure.
- C# is still useful as the comparison point for how much grouping syntax is too heavy.
- Python's file-level grouping model is also worth considering if S2 stays intentionally small.

## Example 7: Call A Primitive Operation

```text
C#
var result = Bind(left, right);

TypeScript
const result = bind(left, right);

JavaScript
const result = bind(left, right);

Python
result = bind(left, right)

Rust
let result = bind(left, right);

Scheme
(define result (bind left right))

Lisp
(setf result (bind left right))

S2 possible directions
result = bind(left, right)
result = left * right
result = bind left right
```

S2 takeaway:

- If primitive operations are semantically important, a keyword-call form may be clearer than disguising everything as ordinary arithmetic.
- C# method-call readability is still a useful baseline for these operations even if the semantics differ completely.
- Infix operators may still be valuable later for common algebraic operations.
- This area is still unresolved and currently confusing.

## Example 8: Return Early

```text
C#
if (!ready)
{
    return fallback;
}

TypeScript
if (!ready) {
  return fallback;
}

JavaScript
if (!ready) {
  return fallback;
}

Python
if not ready:
    return fallback

Rust
if !ready {
    return fallback;
}

Scheme
(if (not ready)
    fallback
    (continue))

Lisp
(if (not ready)
    fallback
    (continue))
```

S2 takeaway:

- Early return syntax is straightforward in mainstream forms.
- C# remains a good baseline for guard-style readability.
- If S2 becomes strongly expression-oriented, Rust and Lisp-family languages provide cleaner precedents than C#.

## Example 9: Anonymous Function Or Lambda

```text
C#
items.Select(x => Transform(x));

TypeScript
items.map(x => transform(x));

JavaScript
items.map(x => transform(x));

Python
map(lambda x: transform(x), items)

Rust
items.into_iter().map(|x| transform(x));

Scheme
(map (lambda (x) (transform x)) items)

Lisp
(mapcar (lambda (x) (transform x)) items)
```

S2 takeaway:

- Anonymous functions are not yet clearly necessary for S2's first pass.
- If they are added later, TypeScript/Rust/Scheme give better models than C# delegates.

## Example 10: Truth Testing Versus Equality

```text
C#
if (candidate == target) { ... }
if (IsTrue(signal)) { ... }

TypeScript
if (candidate === target) { ... }
if (isTrue(signal)) { ... }

JavaScript
if (candidate === target) { ... }
if (isTrue(signal)) { ... }

Python
if candidate == target:
    ...
if is_true(signal):
    ...

Rust
if candidate == target { ... }
if is_true(signal) { ... }

Scheme
(if (equal? candidate target) ...)
(if (is-true signal) ...)

Lisp
(if (equal candidate target) ...)
(if (is-true signal) ...)

S2 design pressure
if (similar(candidate, target)) { ... }
if (isTrue(signal)) { ... }
```

S2 takeaway:

- S2 should be explicit about the difference between truth-testing and similarity/equality-like checks.
- C# is still a good baseline for visibly separating different predicate forms, even though S2 cannot reuse ordinary `==` semantics directly.
- Mainstream equality syntax is not a safe direct model if S2 semantics are vector-native.
- Whether bare truthiness such as `if (cat)` is legal is still unresolved.

## Example 11: Explicit Return

```text
C#
return result;

TypeScript
return result;

JavaScript
return result;

Python
return result

Rust
return result;

Scheme
result

Lisp
result

S2 current decision
return result;
```

S2 takeaway:

- `return` is the active S2 keyword.
- The open question is whether S2 also permits implicit final-expression returns in some contexts.

## Example 12: Truthiness Versus Explicit Truth Test

```text
C#
if (cat) { ... }                 // only valid if cat is actually bool
if (IsTrue(cat)) { ... }

TypeScript
if (cat) { ... }
if (isTrue(cat)) { ... }

JavaScript
if (cat) { ... }
if (isTrue(cat)) { ... }

Python
if cat:
    ...
if is_true(cat):
    ...

Rust
if cat { ... }                   // only valid if cat is bool
if is_true(cat) { ... }

Scheme
(if cat ...)
(if (is-true cat) ...)

Lisp
(if cat ...)
(if (is-true cat) ...)

S2 decision
if (cat) { ... }                 // COMPILATION ERROR — cat is not bool/fuzzy
if (unsafeCast<fuzzy>(cat)) { ... }  // explicit: treat vector as fuzzy
if (defuzzy(signal)) { ... }     // explicit: collapse fuzzy to bool
```

S2 takeaway:

- This is now decided.
- `if (cat)` is a compilation error because classes do not exist at runtime.
- Truthiness is geometric (euclidean distance from true/false vectors) and only accessible via unsafe cast or unsafeOverride.
- There is no automatic truthiness coercion for arbitrary values.

## Example 13: `fuzzy`, `bool`, And `defuzzy(...)`

```text
C#-style explicit conversion pressure
bool ready = Defuzzy(signal);
if (ready) { ... }

TypeScript-style explicit conversion pressure
const ready = defuzzy(signal);
if (ready) { ... }

Python-style explicit conversion pressure
ready = defuzzy(signal)
if ready:
    ...

S2 design pressure
var ready = defuzzy(signal);
if (ready) { ... }

if (defuzzy(signal)) { ... }
```

S2 takeaway:

- `fuzzy` and `bool` are now distinct concepts in S2.
- `defuzzy(...)` is the explicit bridge from fuzzy truth into boolean truth.
- The open question is whether branching requires explicit defuzzification or can also consume raw `fuzzy` values.

## Example 14: Unsafe Cast Between Classes

```text
C#
var feline = (Cat)animal;
var feline = animal as Cat;

TypeScript
const feline = animal as Cat;

JavaScript
// no built-in cast syntax

Python
feline = cast(Cat, animal)

Rust
// no direct object-style unsafe cast equivalent

Scheme
; typically runtime or library specific

Lisp
; typically runtime or library specific

S2 design pressure
var feline = (cat) animal;
var feline = unsafeCast<cat>(animal);
var feline = unsafeOverride(animal);
```

S2 takeaway:

- C# and TypeScript are the clearest reference points here.
- In S2, safe and unsafe forms should look clearly different.
- `unsafeOverride(...)` is not the same thing as a cast; it overrides function acceptance rules.

## Example 15: Unsafe Cast Up To Primitive Base Layer

The primitive base layer currently described by the design notes is:

- scalar
- vector
- matrix
- tuple
- string

That is five primitive base classes, even though this sometimes gets referred to as "four core primitives" in conversation.

String is a special case:

- It exists mainly for literals and output.
- It is uncommon and awkward for internal computation.
- Most non-trivial internal operations should convert strings into vectors first.

```text
C#
Vector v = (Vector)value;
Matrix m = (Matrix)value;
Tuple t = (Tuple)value;
string s = (string)value;

TypeScript
const v = value as Vector;
const m = value as Matrix;
const t = value as Tuple;
const s = value as string;

Python
v = cast(Vector, value)
m = cast(Matrix, value)
t = cast(TupleValue, value)
s = cast(str, value)

Rust
// would usually require explicit conversion traits or wrappers

Scheme
; library or runtime specific

Lisp
; library or runtime specific

S2 design pressure
var v = (vector) value;
var m = (matrix) value;
var t = (tuple) value;
var s = (string) value;

var v = unsafeCast<vector>(value);
var m = unsafeCast<matrix>(value);
var t = unsafeCast<tuple>(value);
var s = unsafeCast<string>(value);
```

S2 takeaway:

- This needs explicit syntax design.
- If these are primitive base classes, casting up to them should look standardized and unmistakable.
- The syntax should make it clear whether this is a checked conversion, an unsafe reinterpretation, or a semantic projection.
- String should be treated as a special primitive mostly used for literals and output rather than as a common internal compute type.
- Unsafe casting to `vector` exists syntactically as `unsafeCast<vector>(...)`, but the more common practical issue is usually function acceptance rather than forcing a vector reinterpretation.

## Example 16: Function Call With Safe Cast, Unsafe Cast, And Unsafe Override

```text
S2 sketch
function getFur(cat c) {
    return c.fur;
}

getFur((cat) animal);
getFur(unsafeCast<cat>(animal));
getFur(unsafeOverride(animal));
```

S2 takeaway:

- `(cat) animal` is the safe cast form.
- `unsafeCast<cat>(animal)` is the explicit unsafe cast form.
- `unsafeOverride(animal)` does not cast at all; it forces a function call to accept something it would normally reject.

## Example 17: Operator Overloading

```text
C#
public static Vector operator +(Vector a, Vector b) => Bundle(a, b);
public static Vector operator *(Vector a, Vector b) => Bind(a, b);

TypeScript
// no operator overloading in core language

Python
def __add__(self, other): ...
def __mul__(self, other): ...

Rust
impl Add for Vector { ... }
impl Mul for Vector { ... }

Scheme
; operator names are just procedures

Lisp
; implementation dependent

S2 design pressure
function operator +(vector a, vector b) { ... }
function operator *(vector a, vector b) { ... }

// or simply built-in meanings for + and *
```

S2 takeaway:

- Operators support overloading. This is now decided.
- The class system is almost entirely user-defined (not special to the runtime), so operator overloading is straightforward — there is no special machinery needed.
- C# is the clearest reference for the declaration form.
- The S2 form is `function operator +(vector a, vector b) { ... }`.

## Example 18: Implicit Cast Or Conversion

```text
C#
public static implicit operator Vector(Cat c) => c.VectorForm;
Vector v = cat;

TypeScript
// no direct equivalent in core syntax

Python
// usually protocol or constructor based, not true implicit cast syntax

Rust
// usually explicit Into/From patterns rather than silent implicit casts

S2 design pressure
vector v = cat;
var v = cat;
getVector(cat);

// versus requiring explicit conversion
vector v = (vector) cat;
```

S2 takeaway:

- Implicit casts are allowed but must be explicitly defined. This is now decided.
- C# is the strongest direct reference: someone writes `implicit operator Vector(Cat c) { ... }`, then `Vector v = cat;` works.
- S2 follows the same principle: no silent coercions without a visible definition, but call sites can be clean.
- The declaration form for implicit conversions still needs design.

## Example 19: Defuzzy In A Branch

```text
C#-style explicit pressure
if (Defuzzy(signal))
{
    return Proceed();
}

TypeScript-style explicit pressure
if (defuzzy(signal)) {
  return proceed();
}

Python-style explicit pressure
if defuzzy(signal):
    return proceed()

S2 design pressure
if (defuzzy(signal)) {
    return proceed();
}

if (signal) {
    return proceed();
}
```

S2 takeaway:

- This is now one of the most important remaining syntax/semantic decisions.
- The question is whether S2 wants explicit defuzzification in control flow, implicit defuzzification, or both.

## Example 20: Function Parameter Acceptance Pressure

```text
S2 sketch
function getFur(cat c) {
    return c.fur;
}

getFur((cat) animal);
getFur(unsafeCast<cat>(animal));
getFur(unsafeOverride(animal));
```

S2 takeaway:

- This shows the distinction between changing the value and overriding the call-site acceptance rule.
- It is an important comparison point for future argument-checking semantics.

## Example 21: Property Access Or Field Access

```text
C#
var x = point.X;

TypeScript
const x = point.x;

JavaScript
const x = point.x;

Python
x = point.x

Rust
let x = point.x;

Scheme
; usually library specific

Lisp
; usually library specific

S2 design pressure
var x = point.x;
var x = point::x;
x = get(point, x);
```

S2 takeaway:

- This is still open.
- C#, TypeScript, and Python are the clearest readability references if S2 exposes field-like access at all.

## Example 22: Type Or Role Annotation

```text
C#
Vector blend(Vector a, Vector b)

TypeScript
function blend(a: Vector, b: Vector): Vector

JavaScript
// none in core syntax

Python
def blend(a: Vector, b: Vector) -> Vector:

Rust
fn blend(a: Vector, b: Vector) -> Vector

Scheme
; usually external to core syntax

Lisp
; optional, implementation specific

S2 design pressure
function blend(a: vector, b: vector): vector { ... }
function blend(a, b) -> vector { ... }
function blend(a, b) { ... }
```

S2 takeaway:

- This remains open.
- S2 may want role annotations without pretending it has an ordinary mainstream type system.
