# 01 — Hello Sutra

The smallest real Sutra program is `examples/hello_world.su`. You can't write `print("hello world")` halfway through a function — not because Sutra lacks I/O (I/O is core), but because the whole program runs all at once as one synchronous neural network, so there's no mid-computation point to print at. I/O happens at the program's boundaries; here the output is the value `main()` **returns** at the end. So "hello world" means: construct the *vector* for a greeting, identify it against a small set of known phrases, and return the matching phrase's name — that return is the program's output. (How inputs and outputs attach at the four program/loop boundaries: [the I/O model](../host-bridge.md).)

## What you'll learn

- Where Sutra files live and what the `.su` extension means
- How to turn a string into a `vector` with `embed(...)`
- What a **codebook** (`map<vector, string>`) is and how `argmax_cosine` reads from it
- How to declare functions and the `main()` entry point
- How to validate and run a source file
- The "everything is a vector" mental model in its smallest form

## The program

This is [`examples/hello_world.su`](https://github.com/EmmaLeonhart/Sutra/blob/main/examples/hello_world.su), in full:

```c
// The greeting, as a vector in the space.
vector greeting = embed("hello_world");

// A small codebook of candidate phrases.
vector v_hello    = embed("hello_world");
vector v_goodbye  = embed("goodbye");
vector v_question = embed("are_you_there");

map<vector, string> PHRASE_NAME = {
    v_hello:    "hello world",
    v_goodbye:  "goodbye",
    v_question: "are you there"
};

// `say` is the whole program: identify `greeting` against the codebook
// by cosine similarity and return its name.
function string say() {
    vector winner = argmax_cosine(greeting, [v_hello, v_goodbye, v_question]);
    return PHRASE_NAME[winner];
}

// Entry point: `sutrac --run` invokes main() and prints its return value.
function string main() {
    return say();
}
```

Five things to notice:

1. **`vector greeting = embed("hello_world");`** binds a `vector` to the name `greeting`. `embed(s)` resolves the string `s` to its point in the frozen embedding space — it is the bridge from "a name written as text" to "a coordinate in the substrate." The same string always resolves to the same point.

2. **`map<vector, string> PHRASE_NAME`** is a **codebook**: a content-addressed table pairing each known phrase *vector* with the string you want back when that phrase wins. You look it up with a vector, not an index.

3. **`argmax_cosine(greeting, [v_hello, v_goodbye, v_question])`** is the whole matching engine: it returns the candidate vector closest to `greeting` by cosine similarity. Here `greeting` *is* `v_hello`, so `v_hello` wins. (This is the cleanup primitive — [tutorial 03](03-snap-to-nearest.md) goes deep on it.)

4. **`function string say()`** declares a free function returning a `string`. A free function that produces a value returns a typed value like this (not bare `void`) — `void` exists, but as a *method* return type for side-effect-style methods, not for `main()`. Functions are called by name — `say()` — directly.

5. **`function string main()`** is the entry point. `sutrac --run` calls `main()` and prints whatever it returns. By convention `main()` is your clean entry point.

## Validate it

Validation needs only the compiler — no model, no torch:

```bash
pip install sutra-dev
sutrac examples/hello_world.su
```

If the file is well-formed you'll see:

```
ok: 1 file(s) validated, 0 diagnostics
```

If you make a syntax error — say, forget the semicolon after `return` — you get a structured diagnostic with a stable `SUT####` code and a 1-based `line:column`:

```
examples/hello_world.su:34:1: error: expected `;` after `return`, got `}` [SUT0100]
```

Every Sutra diagnostic looks like this, on the command line and (via the same compiler) as red squiggles in the IntelliJ plugin. The validator also resolves names: a mistyped function or type is flagged at compile time with a suggestion —

```
program.su:3:16: warning: unknown function `argmaxcosine` — did you mean `argmax_cosine`? [SUT0201]
  hint: `argmaxcosine` resolves to no function, builtin, stdlib call, or local — the closest known name is `argmax_cosine`
```

(the same pass covers unknown types, misspelled fields, and unresolvable calls — SUT0200/0201/0203/0205).

## Run it

Running resolves `embed(...)` to real coordinates, so it needs the embedding model. The model loads **in-process** — no separate server:

```bash
pip install "sutra-dev[runtime,embed]"
sutrac --run examples/hello_world.su
```

```
hello world
```

(The `examples/` programs ship in the [source repo](https://github.com/EmmaLeonhart/Sutra),
not the pip package — if you installed only from PyPI, save the source above to a local
`hello_world.su` and run `sutrac --run hello_world.su`.)

The first run downloads the frozen model once (a few hundred MB; it prints a one-line notice and caches it). `greeting` was identified against the codebook and `say()` returned the matching name.

## The mental model to start absorbing

- A string in your source is *not* the value a function returns. The program returns a **vector**; `embed` is the bridge from "concept written as text" to "coordinate in the substrate." That return value is also the *only* thing the program hands back to the host — Sutra has no `print`/stdin/file-read. The full picture of what crosses that boundary is [The host bridge — Sutra's I/O model](../host-bridge.md).
- A vector has no canonical numeric value — it depends on the substrate (`nomic-embed-text` by default). Different substrates produce different coordinates. The *structure* of the program is substrate-independent; the *numbers* are not.
- Computation is geometry. The next tutorials operate on these vectors with Sutra's primitives — you will see *operations on vectors* far more often than you see numbers.

## What to read next

- **[02 — Bind and unbind](02-bind-and-unbind.md)** — the operation that turns Sutra from "fancy retrieval" into actual programming: associate a key with a value and pull the value back out, using only vector arithmetic.
- The [Operations and operators reference](../operators.md) — the formal definition of every primitive operation.
