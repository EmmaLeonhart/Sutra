# The REPL — explore Sutra interactively

`sutrac repl` opens an interactive evaluator: type an expression, see its result;
type a declaration, add it to the session. It is the fastest way to get a feel for
how Sutra values behave before you write a `.su` file.

```bash
sutrac repl
```

```
Sutra REPL - type an expression to evaluate it; end a line with ';' or '}' to add a declaration.
Commands: :help  :decls  :reset  :quit
sutra>
```

Running expressions needs the embedding model (the same one `sutrac --run` uses).
With `pip install "sutra-dev[runtime,embed]"` it loads in-process; the first `embed(...)`
downloads the frozen model once (a few hundred MB), prints a one-line notice, then caches
it. (To use an [Ollama](https://ollama.com) daemon instead, set
`SUTRA_EMBED_BACKEND=ollama` and `ollama pull nomic-embed-text`.)

## Two kinds of line

- **An expression** is evaluated and its result shown:

  ```
  sutra> make_real(2.0) + make_real(3.0)
  = 5
  ```

- **A declaration or statement** ends with `;` (or a function ends with `}`), and is
  added to the session so later lines can use it:

  ```
  sutra> vector greeting = embed("hello_world");
  (added)
  ```

## Strings become vectors with `embed(...)`

This is the one rule that trips up a first session: **most operations work on
`vector`s, not on raw strings.** A string enters the substrate through `embed(...)`,
which resolves it to its point in the frozen embedding space. So embed first, then
operate:

```
sutra> vector a = embed("cat");
(added)
sutra> vector b = embed("dog");
(added)
sutra> similarity(a, b)
= 0.681239
```

`embed("cat")` on its own shows the nearest known concept and how close it is:

```
sutra> embed("hello")
~ "hello"  (cos 1.00)
```

A **bare string literal** is a different thing from an embedding, and the REPL now evaluates it directly —
it round-trips to its own text:

```
sutra> "hello"
"hello"
```

So `"hello"` is the literal text (a string value on the substrate), while `embed("hello")` is that text
resolved to its *meaning* vector — the two are distinct, and the REPL shows each for what it is.

## Reading results

- **`= <number>`** — a numeric result (a similarity, a real value).
- **`~ "concept"  (cos 0.NN)`** — a `vector` result, decoded to the nearest string
  the session knows, with the cosine similarity to it. `cos 1.00` means it landed
  exactly on that concept.
- **`"text"`** — a `string` result, shown as its own text (e.g. a bare string literal).
- **`(added)`** — a declaration was accepted into the session.

## Commands

| Command | Effect |
|---|---|
| `:help` | Show the built-in help. |
| `:decls` | Print everything you've added to the session. |
| `:reset` | Clear all session declarations and start fresh. |
| `:quit` / `:q` | Leave the REPL (`Ctrl-D` also works). |

A line that doesn't compile prints a one-line error and leaves the session intact —
you can keep going.

## Where next

- **[Tutorial 01 — Hello Sutra](tutorials/01-hello-sutra.md)** builds the same
  `embed` / `similarity` ideas into a first `.su` program you run with `sutrac --run`.
- **[The I/O model](host-bridge.md)** explains why input enters at `embed(...)` rather
  than a `read` — the REPL is one place that boundary is visible.
