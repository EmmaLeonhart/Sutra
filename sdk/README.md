# Akasha SDK

Language tooling for **Akasha** — the fuzzy-by-default vector
programming language. This directory contains the compiler/validator
and the VS Code extension that uses it.

```
sdk/
  akasha-compiler/      Python package: lexer, parser, validator, CLI
    akasha_compiler/
      lexer.py
      parser.py
      validator.py
      diagnostics.py
      ast_nodes.py
      __main__.py       CLI entry: `python -m akasha_compiler`
    tests/
      corpus/
        valid/          20 .ak files, zero diagnostics expected
        invalid/        12 .ak files, each with a known error code
      test_lexer.py     22 lexer unit tests
      test_parser.py    25 parser unit tests
      test_corpus.py     8 corpus-walking tests
  vscode-akasha/        VS Code extension
    package.json
    language-configuration.json
    syntaxes/akasha.tmLanguage.json
    snippets/akasha.json
    src/extension.ts
    README.md
```

## Quickstart

### Validate existing Akasha code

From the repo root:

```bash
cd sdk/akasha-compiler
python -m akasha_compiler ../../akasha-demo-program.ak ../../examples ../../fly-brain
```

This walks every `.ak` file under the given paths and reports any
lexical, syntactic, or semantic issues in the standard
`file:line:col: level: message [code]` form.

### Check cross-file consistency

```bash
python -m akasha_compiler --consistency ../../akasha-demo-program.ak ../../examples ../../fly-brain
```

Reports class names that appear in multiple casings across the file
set (e.g. `animal` in one file and `Animal` in another — which is
exactly the kind of drift we found in the existing repo).

### JSON output (for editors / CI)

```bash
python -m akasha_compiler --json path/to/file.ak
```

### Summary table

```bash
python -m akasha_compiler --summary tests/corpus/valid tests/corpus/invalid
```

### Run the unit tests

```bash
cd sdk/akasha-compiler
python -m unittest discover -s tests -t .
```

55 tests, ~0.03s. No external dependencies — just Python stdlib.

## Diagnostic codes (v0.1)

| Code     | Meaning |
|----------|---------|
| AKA0001  | Unterminated block comment |
| AKA0002  | Unterminated string literal |
| AKA0003  | Unexpected character |
| AKA0100  | Generic parse error ("expected X, got Y") |
| AKA0101  | Modifier used in a position where it doesn't apply |
| AKA0102  | Operator is not overloadable |
| AKA0103  | `var` combined with an explicit type |
| AKA0104  | Expected expression, got something else |
| AKA0105  | `unsafeCast` missing its required type argument |
| AKA0110  | `|>` pipe-forward operator is not supported |
| AKA0111  | Casting a string literal to a primitive (use `embed(...)`) |
| AKA0112  | Declaration marked both `public` and `private` |
| AKA0113  | Class name used in multiple casings in one file (warning) |

## Scope for v0.1

**In scope:**
- Full tokenization (all comment forms, interpolated strings, operators, literals)
- Recursive-descent parsing of declarations, statements, expressions
- Cast/generic disambiguation
- Structural validation + the specific rules listed above
- CLI with text, JSON, summary, and cross-file consistency modes
- Test corpus + unit tests as regression harness
- VS Code extension: syntax highlighting, snippets, autocomplete, live diagnostics

**Out of scope for v0.1** (will land in v0.2+):
- Type checking across declarations
- Name resolution (unknown identifier detection)
- Arity checking on calls
- Return-statement coverage
- Cross-file / solution-level symbol tables
- Code generation / runtime lowering
- An LSP server (current extension shells out to the CLI)

## Solution structures

The Akasha spec mentions C#-esque solution structures as a
*permitted* but optional layout. The v0.1 SDK doesn't know about
solution files — it operates on individual `.ak` sources and
command-line file lists. A future version will add a `.aksol` or
equivalent manifest that declares the set of files in a project and
lets the compiler resolve cross-file references.

For now, the recommended layout if you want one is:

```
src/
  Models/
    Animal.ak       # object-declaration file (methods live here)
    Cat.ak
  Services/
    Classifier.ak
  main.ak           # executable file
```

But nothing in the tooling enforces this. A single executable `.ak`
file that just runs top-to-bottom is equally valid, as demonstrated
by `examples/06-executable-file.ak` in the repo root.

## Development

The compiler is pure Python stdlib. No build step. No dependencies.
The VS Code extension uses TypeScript for its small activation
module — run `npm install && npm run compile` in `vscode-akasha/`
before pressing F5 to launch an Extension Development Host.

See `vscode-akasha/README.md` for editor-specific setup.
