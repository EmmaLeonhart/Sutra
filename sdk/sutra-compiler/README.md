# sutra-compiler

The compiler for the [Sutra programming language](https://sutra.emmaleonhart.com) — a purely functional language whose primitives are tensor operations on frozen-LLM embedding vectors.

## Install

```bash
pip install sutra-compiler            # validator + codegen only
pip install sutra-compiler[runtime]   # adds torch so --emit / --run can execute the generated module
```

Requires Python 3.11+.

## Use

After install, the `sutrac` command is on your `$PATH`.

```bash
# Validate a .su source file.
sutrac path/to/program.su

# Validate every .su file under a directory.
sutrac path/to/directory

# Compile to self-contained PyTorch Python and print to stdout.
sutrac --emit path/to/program.su

# Compile and execute in one step (requires the [runtime] extra installed).
sutrac --run path/to/program.su

# Step-by-step compilation review (source → AST → inline → simplify → emit).
sutrac --review path/to/program.su

# Cross-file class-name casing check.
sutrac --consistency path/to/directory
```

`sutrac --help` lists every flag.

## What is Sutra

A `.su` source file looks like TypeScript — functions, classes, `&&` / `||`, string and numeric literals — but every value is a vector in a frozen LLM embedding space, and every operation is a tensor op on those vectors. The compiler emits self-contained Python that calls a small runtime; chains of `bind` / `unbind` / `bundle` / `similarity` reduce to chains of matrix multiplies that the simplifier folds into cached matrices at compile time.

The result is a program where there are no Python branches, no host-side `if` / `while` on data values, and no JIT — just one straight-line tensor expression.

For a full introduction, see [sutra.emmaleonhart.com](https://sutra.emmaleonhart.com). For the language specification and design rationale, see the [Sutra repository](https://github.com/EmmaLeonhart/Sutra).

## Status

Research-grade. Versions before 1.0 may break source compatibility. The grammar is stable; the codegen and the standard library still move.
