# The host bridge — Sutra's I/O model

Sutra has **no I/O primitives**. There is no `print`, no `read`, no stdin, no file
open/read/write as a language feature. A `.su` program is a pure function over
vectors: it takes the inputs it was given, computes geometry on the substrate, and
returns one value. This page explains *why* that is, and the small, explicit set of
places where data does cross the boundary between the host (Python, your terminal,
the model) and a running Sutra program — **the host bridge**.

If you came here from a tutorial wondering "how does my program actually *read* what
the user typed?", the short answer is: in core Sutra, it doesn't — you embed the
input at the source or load it as a matrix, and the program is recompiled/rerun per
input. The longer answer, and where that may change, is below.

## Why there is no I/O

The rule is downstream of one design commitment: **Sutra has no way to read a value
off the substrate.** No readout, no logging, no scalar accessor — by design, not as a
missing feature. A vector lives on the substrate; pulling a number out of it would
run the rest of your computation on the host CPU and sever the differentiable graph.
The language keeps everything *on* the substrate so that a whole program is a single,
exact, end-to-end-differentiable tensor expression.

General-purpose I/O is the same kind of escape hatch as readout: a `read_line()` or a
`print(v)` inside an operation would be a host call in the middle of substrate
computation. So the core language has none. What it has instead is a deliberately
narrow bridge at the *edges* of a run — inputs fixed before the computation starts,
and a single value handed back when it ends.

## What crosses the boundary

### Inputs (host → Sutra), fixed before the run

- **`embed("...")`** — resolves a **source-literal string** to its point in the frozen
  embedding space, via the model, at runtime. This is the main way text enters a
  program: you write the string in the source, and `embed` turns it into a `vector`.
  The string is part of the program, not something read from a live user.
- **`load_matrix("weights.csv")`** — reads a CSV of floats (one row per line) into a
  frozen substrate matrix on the runtime device, cached by path. This is how *large*
  data — trained weights, a precomputed codebook, a dataset matrix — enters a program
  without being spelled out as a giant inline literal. It is the file-backed
  counterpart to a matrix literal, and the closest thing Sutra has to "reading a file":
  a constant loaded at startup, not a stream you pull from during the run.
- **The `// @embedding: <model>` directive** — picks which substrate the program's
  `embed` calls resolve against. It selects the geometry; it is not data input.

All of these are resolved **before** the computation proper. By the time `main()`
runs, the inputs are already vectors and matrices on the substrate.

### Output (Sutra → host), one value at the end

- **`main()`'s return value** is the single value that crosses back to the host. The
  terminal decodes it at the one sanctioned boundary: a `string` returns as text; a
  number-vector is read at its real axis for display; anything already host-shaped
  prints as-is. This final decode is the *only* place a value is read off the
  substrate, and it happens *after* the program is done — it is the terminal printing a
  result, the same as returning a value from any function. It is **not** in-program
  introspection, which does not exist.

That is the whole bridge: literal/`embed`/`load_matrix` in, one `main()` value out.

## What this means in practice

Because inputs are fixed before the run, a Sutra program does not interactively read
from a user. The [semantic FAQ matcher](tutorials/05-semantic-faq.md) embeds its query
string directly in the source —

```c
function string ask_password() { return answer(embed("I forgot my login and need to change it")); }
```

— precisely because there is no `read_line()` to fetch a live question. To answer a
*different* question you change the embedded string (or load a batch of queries as a
matrix) and run again. The matching engine is real; the *input delivery* is the part
that lives at the host edge, not inside the language.

This is a feature for the language's intended use — a Sutra program is a
differentiable computation you compile once and call many times, like a model, not a
REPL — but it is a genuine limit on building an interactive CLI tool *in core Sutra
alone*.

## Where live input may come from (open, not decided)

Whether core Sutra should grow a **minimal input primitive** — a live `read`-style
host axon, a way to feed one value per invocation without recompiling — is a
language-design question, and an open one. It is **not** settled here, and this page
does not propose an answer.

The current direction puts live, external I/O in a **separate desktop layer** rather
than the core language: an I/O orchestrator that resolves *external axons* and
*promises* over time (a value the host writes into an awaited slot), plus the
window/clicks/paint surface — see the [GUI and desktop surface](gui.md) notes. Under
that model the core language stays pure (no readout, no I/O), and "reading input" is
something the surrounding orchestrator does, handing resolved vectors to the substrate.
Whether a smaller, in-language input primitive is *also* worth having is the part left
genuinely undecided.

## See also

- [01 — Hello Sutra](tutorials/01-hello-sutra.md) — where the "return value is the one
  thin bridge back to the host" idea first appears.
- [05 — Build a semantic FAQ matcher](tutorials/05-semantic-faq.md) — the program whose
  hardcoded query motivates this page.
- [GUI and desktop surface](gui.md) — the desktop layer where live external inputs are
  envisioned.
