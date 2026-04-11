# Sutra Syntax Decisions

This is the rolling document for syntax and surface-language decisions. Comparisons and speculation live elsewhere. Decisions recorded here should be treated as the current direction until replaced.

## Established Decisions

### 2026-04-08

#### Functions exist independently

Status: active

Decision:

- Functions are first-class top-level language constructs.
- Sutra does not assume functions live inside classes by default.
- If later grouping constructs exist, they should organize functions rather than own them.

Reasoning:

- This fits the current understanding of Sutra as a serious, compiled, substrate-oriented language rather than an object-model-first language.
- It keeps the language closer to Rust, Scheme, Lisp, Python, and plain functions in TypeScript than to C#'s traditional class-centered shape.
- It avoids forcing an OOP structure onto a language whose semantics are driven by vector operations and fuzzy reasoning.

Implications:

- Top-level function declaration syntax is now a priority decision.
- Any future module or namespace design should preserve standalone functions.
- Method syntax, if it exists later, should be secondary sugar rather than the core model.

Open follow-up:

- Choose the block form.
- Decide whether files imply namespaces.
- Decide how primitive operations are written inside function bodies.

#### Function declarations use C# signature shape with `function` keyword

Status: active

Decision:

- Sutra uses the keyword `function` to introduce a function declaration.
- The rest of the signature follows C# method shape: return type before name, typed parameters, braces.
- Surface form: `function vector Add(vector a, vector b) { return a + b; }`
- Full internal form with modifiers: `function public static scalar operator +(scalar a, scalar b) { return function.add(a, b); }`
- `function.` is a call-site prefix for disambiguation, not part of declarations.

Reasoning:

- C# method declarations have a single predictable shape that reads like a manifest entry.
- `function` replaces C#'s access modifiers and `static` in the surface form, keeping the same visual weight.
- One form for declarations. No arrows, no alternatives, no competing styles.
- `function.` as a call-site prefix gives C#'s `ClassName.Method()` disambiguation without requiring actual classes.

Implications:

- All function declarations follow: `function [return-type] Name([params]) { ... }`
- Calling can use `Add(x, y)` or `function.Add(x, y)` — second form disambiguates.
- Modifiers like `public`, `static` exist in the full form but may be hidden in surface syntax.
- Comparison examples should use the C#-shaped form.

Open follow-up:

- Decide which modifiers are visible in surface syntax vs hidden.
- Decide whether files imply namespaces.
- Decide how primitive operations are written inside function bodies.

#### Conditionals use TypeScript-style `if (...) { ... } else { ... }`

Status: active

Decision:

- Sutra uses TypeScript-style conditional syntax.
- The baseline shape is `if (condition) { ... } else { ... }`.
- This is a surface-syntax decision, not a final semantic decision about truthiness.

Reasoning:

- This gives Sutra a familiar and readable conditional form.
- It preserves explicit braces and keeps branching visually close to C# and TypeScript.
- It avoids prefix-only conditionals while remaining compatible with fuzzy truth semantics underneath.

Implications:

- Comparison examples should treat the TypeScript conditional form as the default Sutra branch syntax.
- The open issue is how truthiness works, not how the branch keywords and punctuation work.

Open follow-up:

- Define truthiness versus explicit boolean checks.
- Decide whether `if (cat)` is legal.
- Decide how `isTrue(...)` interacts with conditional syntax.

#### Use `return`

Status: active

Decision:

- Sutra uses the keyword `return`.

Reasoning:

- `return` is conventional, explicit, and readable.
- It keeps function bodies easy to scan and aligns with the rest of the current mainstream surface direction.

Implications:

- Function examples should use `return` when they need explicit early exits or explicit return points.
- The open design space is expression orientation, not the exit keyword.

Open follow-up:

- Decide whether final expressions can be implicitly returned in some contexts.

#### Looping uses TypeScript-style `while (...) { ... }`

Status: active

Decision:

- Sutra uses TypeScript-style loop syntax for conventional loops.
- The baseline loop shape is `while (condition) { ... }`.

Reasoning:

- This keeps looping syntax readable and familiar.
- It aligns with the same branch-and-block surface style as Sutra conditionals.
- It gives a stable surface form even while loop semantics remain open.

Implications:

- Comparison examples should treat TypeScript-style `while` loops as the current Sutra baseline.
- Semantic questions about convergence, fuzziness, and termination remain open.

Open follow-up:

- Decide whether `for` loops exist.
- Decide whether loop conditions use ordinary truthiness, explicit truth tests, or both.

#### `fuzzy` and `bool` are distinct data types, and `defuzzy(...)` converts `fuzzy` to `bool`

Status: active

Decision:

- Sutra has a data type `fuzzy`.
- Sutra has a data type `bool`.
- `defuzzy(...)` converts a `fuzzy` value into a `bool`.
- Both `fuzzy` and `bool` are still represented as vectors at the substrate level.

Reasoning:

- This preserves the vector-native model without pretending booleans are a separate low-level substrate.
- It gives the language an explicit place where fuzzy truth becomes forced into a two-way decision.
- It avoids overloading ordinary branch syntax with all of the burden of semantic collapse.

Implications:

- Truthiness questions now have to distinguish among raw values, `fuzzy`, and `bool`.
- `defuzzy(...)` is a first-class operation in the language surface, not just a runtime detail.
- Comparisons should show both direct truth-testing pressure and explicit `defuzzy(...)` pressure.

Mechanism note:

- `defuzzy(...)` applies an `isTrue` multiplication loop to a `fuzzy` until it reaches true or false.

Open follow-up:

- Decide whether `if (...)` accepts only `bool`, or also accepts `fuzzy`.
- Decide whether `defuzzy(...)` is required in branching.
- Decide whether there are implicit conversions involving `fuzzy` and `bool`.

#### `if (cat)` is a compilation error

Status: active

Decision:

- `if (cat)` where `cat` is a class instance is a compilation error.
- Classes do not exist at runtime. The runtime operates on vectors, scalars, matrices, tuples, and strings.
- There is no implicit truthiness coercion for arbitrary values.

Reasoning:

- Sutra does not have conventional runtime class instances. A "class" is a compile-time organizing concept, not a runtime entity.
- Allowing `if (cat)` would imply that arbitrary values have truthiness, but in Sutra, truth is a geometric property (euclidean distance from true/false vectors), not a type-level coercion.
- If you want to treat an arbitrary vector as a truth value, you must explicitly use an unsafe cast or unsafeOverride to force it into fuzzy/bool space.

Implications:

- `if (condition)` requires `condition` to be `bool` or `fuzzy`.
- To branch on something that isn't already bool/fuzzy, you must explicitly convert it.
- Truthiness is a runtime geometric property, not a compile-time type coercion. It emerges from treating a vector as a fuzzy value via unsafe operations.

#### Operators support overloading

Status: active

Decision:

- Sutra supports operator overloading.
- The syntax follows the `function operator` pattern.

Reasoning:

- Vector operations like bind and bundle map naturally to `*` and `+`.
- Overloading is a real language feature in C#, Python, and Rust, not a hack.
- It lets primitive operations read as algebra when that improves clarity.

Implications:

- The declaration form is `function operator +(vector a, vector b) { ... }`.
- This applies to user-defined and primitive types.
- Built-in meanings for `+`, `*`, etc. on primitive types may exist alongside user overloads.

#### Truthiness is geometric, not type-level

Status: active

Decision:

- Truthiness and falsiness are determined by euclidean distance from the true and false vectors in embedding space.
- This is a runtime property, not a compile-time type coercion.
- Truthiness only manifests when a value is forced into fuzzy/bool space via unsafe cast or unsafeOverride.

Reasoning:

- Sutra's substrate is embedding space. True and false are specific vectors in that space.
- Any vector has some geometric relationship to true/false, but accessing that relationship is an explicit, unsafe operation.
- This inverts conventional truthiness: instead of the language defining which values are "truthy," the geometry defines it, and the programmer must opt in.

Implications:

- There is no automatic truthiness for arbitrary values.
- `if (x)` requires `x` to already be `bool` or `fuzzy`.
- To get truthiness from a non-bool/non-fuzzy value, use `unsafeCast<fuzzy>(x)` or `unsafeOverride(x)`.
- `defuzzy(...)` then collapses a `fuzzy` into a `bool` for branching.

#### Implicit casts are allowed but must be explicitly defined

Status: active

Decision:

- Implicit casts can happen at call sites and assignments.
- The conversion itself must be explicitly declared in source code.
- There are no silent coercions without a visible definition somewhere.

Reasoning:

- This balances ergonomics with explicitness.
- C# is the direct precedent: `public static implicit operator Vector(Cat c) { ... }` lets `Vector v = cat;` compile, but someone had to write the conversion.
- Sutra avoids surprise coercions while still allowing convenient call-site syntax.

Implications:

- The declaration form for implicit conversions needs to be designed (candidate: similar to C#'s `implicit operator` pattern).
- Call sites can look clean (`getVector(cat)`) as long as the implicit conversion is defined.
- This is distinct from unsafe casts, which bypass the type system rather than defining a conversion.

#### Special cast: `fuzzy` to `bool` performs `defuzzy`

Status: active

Decision:

- Casting a `fuzzy` to `bool` performs the `defuzzy(...)` operation.
- This is a special built-in cast, not a user-defined implicit conversion.

Reasoning:

- `defuzzy(...)` is already the established bridge from fuzzy to bool.
- Making the cast invoke `defuzzy` keeps the language consistent: there is one way to collapse fuzzy truth.

Implications:

- `bool b = (bool) signal;` where `signal` is `fuzzy` is equivalent to `bool b = defuzzy(signal);`.
- This is a safe, well-defined cast, not an unsafe operation.

#### Variable declarations use `var` (inferred) or explicit type, with `const` for immutability

Status: active

Decision:

- `var` declares a mutable binding with inferred type. Used only when no type is stated.
- An explicit type declaration does NOT use `var`: `vector result = Blend(a, b);`
- `var` and an explicit type are mutually exclusive — never `var vector x = ...`.
- `const` declares an immutable binding, same as C#.

Examples:

```
var result = Blend(a, b);            // var: type inferred
vector result = Blend(a, b);        // explicit type: no var
const threshold = 0.85;             // const: immutable, inferred
const scalar threshold = 0.85;      // const with explicit type
```

Reasoning:

- Identical to C# rules. `var` means "infer the type." If you state the type, you don't need `var`.
- Familiar, no learning curve for C# developers.

#### Files do not imply namespaces

Status: active

Decision:

- Files do not automatically create namespaces.
- Code is intended to be quickly written by AI and executed on the spot.
- A file that is not an object declaration can just execute directly.
- Full C#-style solution structures are possible but not required.

Reasoning:

- Sutra is designed for rapid AI-generated code execution, similar to JavaScript's immediacy.
- A half-compilation model is the vision: code can be compiled but can also just run.
- Namespacing is opt-in structure, not forced by the file system.

#### `function` vs `method` distinction

Status: active

Decision:

- `function` declares a free function not attached to any object.
- `method` declares a method attached to an object.
- Functions are public static by default.
- Methods are non-static and public by default.
- Every method is really a static function on the backend. `Adam.getCat()` is really `human.getCat(Adam)`.

Reasoning:

- This preserves C#'s clarity about what's attached to what, while keeping the function/method distinction explicit in the keyword.
- Functions and methods are semantically different at the surface level but collapse to the same thing at the vector operation level.
- The method-to-function desugaring makes the substrate transparent: every method call is really a vector operation with the object as the first argument.

Examples:

```
method Cat getCat() { ... }           // gets the cat of an attached human
static method Cat getCat() { ... }    // gives you the cat of all humanity  
function Cat getCat() { ... }         // gives you a random cat
```

Calling:

```
Adam.getCat();                        // desugars to human.getCat(Adam)
```

#### Method-style dot calls work on objects like C#

Status: active

Decision:

- Dot syntax is used for method calls on objects, exactly like C#.
- This is syntactic sugar; every method call desugars to a static function with the object as the first argument.

#### Everything is public static under function namespace by default

Status: active

Decision:

- Functions are public and static by default.
- Methods are public and non-static by default.
- No access modifiers needed in the common case.
- Access modifiers exist for when you need them, following C# conventions.

#### Loops entirely like C#

Status: active

Decision:

- Sutra uses all C# loop forms: `while`, `for`, `foreach`, `do...while`.
- Loop syntax is identical to C#.

#### Error handling: garbage vectors with try-catch as if-statement sugar

Status: active

Decision:

- Errors generally produce garbage vectors rather than throwing exceptions.
- `try-catch` exists but is essentially an if-statement in disguise: if output matches a failure pattern, execute the catch branch.
- Error handling can also be expressed as complex nested functions.
- Exception handling becomes part of the multiplication math at the substrate level.

Reasoning:

- In a vector substrate, failure is just a vector far from the expected result.
- Hard exceptions are the special case, not the default.
- Try-catch as if-sugar keeps the surface familiar for C# developers while the semantics remain vector-native.

#### String interpolation uses C# style

Status: active

Decision:

- String interpolation uses C#-style `$"Result: {result}"`.

#### All comment forms are allowed

Status: active

Decision:

- `//` line comments
- `/* ... */` block comments
- `/// ...` doc comments
- `# ...` line comments (Python-style)
- All forms are valid. No reason to restrict.

#### Generics use C# style (compile-time only)

Status: active

Decision:

- Generics use C#-style angle bracket syntax: `function T Blend<T>(T a, T b) { ... }`
- Generics are compile-time only. At runtime, everything is vectors.

#### No pipe operator; nested function calls only

Status: active

Decision:

- Chaining uses nested function calls: `var result = Step3(Step2(Step1(input)));`
- No pipe operator.
- Method-style dot chaining is available when calling methods on objects.

#### `embed()` is a function, not a cast; string→vector is real computation

Status: active

Decision:

- Converting a string to a vector uses `embed("cat")`, not `(vector) "cat"`.
- `embed()` is a language built-in (lowercase, like `defuzzy()`), not a user-defined function.
- Casting changes the label on a value. `embed()` performs real computation — it runs the string through the empirically-initiated embedding model to produce a vector.
- `(vector) "cat"` is wrong because it implies the string already is a vector and you're just relabeling it. That's not what's happening.

Reasoning:

- Casting in Sutra means reinterpretation: the underlying data stays the same, only the compiler's view of it changes. `(Cat) myAnimal` works because `myAnimal` is already a vector at runtime — you're just telling the compiler to treat it as a Cat.
- Turning a string into a vector is fundamentally different. It requires running the string through an embedding model — that's a computation with real cost, not a relabeling.
- Making this explicit prevents a category error in the language's semantics: casts are free, `embed()` is not.
- Lowercase `embed()` signals it's a language primitive, consistent with `defuzzy()` and `unsafeCast<>()`.

Implications:

- All code examples must use `embed("...")` for string-to-vector conversion.
- `(vector) someString` is a compilation error — you cannot cast across primitive categories.
- `embed()` accepts string literals and string variables: `embed("cat")`, `embed(name)`.
- `embed()` semantics depend on the substrate chosen at empirical initiation time.

#### Casting stays within the same primitive category

Status: active

Decision:

- A cast relabels a value. It changes what the compiler thinks the value is, not what the value actually is.
- You can cast within the same primitive substrate:
  - vector → vector (e.g., `(Cat) myAnimal`, `(Animal) cat`) — both are vectors at runtime
  - string → string (e.g., a typed string class to another string class)
  - tuple → tuple
  - scalar → scalar
  - matrix → matrix
- You cannot cast across primitive categories. `(vector) "cat"` is wrong — use `embed("cat")`.
- Functions are matrices at the substrate level, so in principle you could cast a function to a matrix class (though this would be rare in practice since there aren't many matrix classes).

Reasoning:

- Casting is a zero-cost operation. It only affects the compiler's acceptance checking.
- Cross-category conversion (string→vector, vector→scalar, etc.) is real computation and must use explicit functions: `embed()` for string→vector, `Cosine()` for vector→scalar, etc.
- This keeps the language honest about what operations actually cost something.

Implications:

- The type system enforces primitive category boundaries at cast time.
- `unsafeCast<>()` can still force cross-category reinterpretation if the programmer explicitly opts in — but this is semantically distinct from `embed()` which computes a new value.
- Each cross-category conversion should have a named function that makes the computation visible.

## Candidate Decisions

- annotation system for semantic roles
- expression-versus-statement bias
- anonymous function exact form (leaning `lambda` keyword)
- which access modifiers exist beyond the defaults
- how the half-compilation / immediate-execution model works
