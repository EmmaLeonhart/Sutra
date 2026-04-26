# 01 — Hello Sutra

The smallest possible Sutra program is a function that returns a vector. There is no `print("hello world")` in Sutra because *strings are not the primary type* — vectors are. So "hello world" in this language means "construct a vector that encodes the string `hello`, then return it." That is exactly what we are going to do.

## What you'll learn

- Where Sutra files live and what the `.su` extension means
- How to declare a function with a typed return value
- How to construct a `vector` from a string with the `embed(...)` builtin
- How to validate a source file with the reference compiler
- The "everything is a vector" mental model in its smallest form

## The program

Create a new file `examples/hello.su` (or open it from the repo if it already exists):

```c
/// Encode the literal string "hello" as a vector in the current
/// substrate's embedding space and return it.
function vector Hello() {
    return embed("hello");
}

// Files may execute directly. Calling Main at the top level is
// how an .su file becomes a runnable program.
function vector Main() {
    return function.Hello();
}

function.Main();
```

That's the entire program. Five things to notice:

1. **`function vector Hello()`** declares a function named `Hello` that returns a `vector`. The keyword `function` says this is a free function (not attached to an object). The shape mirrors C# closely. There is no `void` return; there is no implicit `null`; everything that returns must return *something*, and that something must be a typed value.

2. **`embed("hello")`** is a builtin. It takes a string literal and returns a `vector` — the embedding-space coordinate that represents the meaning of "hello" in whichever embedding model the runtime is configured for. Calling `embed` on different strings gives you different points in the same space. Calling `embed` on the same string twice gives you the same point.

3. **`return`** does what you expect. The returned `vector` is the function's value.

4. **`function.Hello()`** calls `Hello`. The `function.` prefix is a disambiguator: in Sutra, calling `Hello()` could be ambiguous (is it a method on `this`? a free function?), so the language requires the prefix at the call site. Methods on objects are called with `obj.method()`; free functions are called with `function.name()`.

5. **`function.Main();`** at the top of the file (no `function` keyword in front, just a statement) is how the file becomes a runnable program. Sutra files do not require a `Main` function — you can put any executable statement at the top level and it runs when the file is loaded. By convention, defining and calling a `Main` function gives you a clean entry point if you want one.

## Validate it

The compiler ships as a Python module. From the repo root:

```bash
cd sdk/sutra-compiler
python -m sutra_compiler ../../examples/hello.su
```

If the file is well-formed you should see:

```
ok: 1 file(s) validated, 0 diagnostics
```

If you mistype something — say, `vec` instead of `vector`, or forget the semicolon after `return` — you'll get a structured diagnostic with a stable `AKA####` code, the file path, and a 1-based `line:column`:

```
examples/hello.su:3:5: error: AKA0102: expected return type, got `vec`
```

Every Sutra diagnostic looks like this. The compiler's external annotator inside the IntelliJ plugin produces the same format and surfaces it in the editor as red squiggles, so the same error message you see on the command line is the one you see in the IDE.

## What just happened

You wrote source code that the compiler parsed, validated against the grammar, type-checked (such as the v0.1 type checker can — see the [language spec](https://github.com/EmmaLeonhart/Sutra/tree/master/planning/sutra-spec) for what it actually verifies), and accepted. You did **not** run it on a real embedding model yet — that requires the Sutra runtime, which you'll meet in tutorial 03 when we hook up `snap-to-nearest`.

The mental model shift to start absorbing now:

- The string `"hello"` in your source is *not* the value the program returns. The program returns a *vector*. The `embed` call is the bridge from "human concept written as text" to "coordinate in the substrate."
- The vector that comes back has no canonical numeric value. It depends on the substrate (`nomic-embed-text`, `mxbai-embed-large`, `all-minilm`, etc.). Different substrates produce different coordinates. The structure of the program is substrate-independent; the *numbers* are not.
- Every later tutorial will operate on these vectors using Sutra's primitive operations. You will not see numbers very often. You will see *operations* on vectors.

## What to read next

- **[02 — Bind and unbind](02-bind-and-unbind.md)** — the operation that turns Sutra from "fancy retrieval" into "actual programming." How to associate a key with a value and pull the value back out, using only vector arithmetic.
- The [language spec on operations](https://github.com/EmmaLeonhart/Sutra/blob/master/planning/sutra-spec/operations.md) — the formal definition of every primitive operation.
