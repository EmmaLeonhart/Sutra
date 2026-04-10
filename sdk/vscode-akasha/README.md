# Akasha for VS Code

Syntax highlighting, autocomplete, snippets, and live error reporting for
the **Akasha** programming language — a fuzzy-by-default vector language
whose primitives are hypervectors in embedding space.

## Features

### Syntax highlighting

Full TextMate grammar covering:

- All four comment forms: `//`, `/* */`, `///` doc, `#` hash
- Plain strings `"..."` and interpolated strings `$"... {expr} ..."`
  with nested expressions highlighted inside interpolation
- Keywords: `function`, `method`, `operator`, `var`, `const`, `if`,
  `while`, `for`, `foreach`, `do`, `try`, `catch`, `return`, `this`,
  `static`, `public`, `private`, and others
- Primitive types: `scalar`, `vector`, `matrix`, `tuple`, `string`,
  `bool`, `fuzzy`, `void`
- Built-ins: `embed`, `defuzzy`, `unsafeCast`, `unsafeOverride`,
  `snap`, `similarity`, `Bundle`, `Bind`, `Normalize`, `Blend`
- The `function.` disambiguation prefix
- PascalCase class names as types
- The `|>` pipe-forward operator rendered as an error (the spec
  forbids it)

### Autocomplete

Keyword, primitive-type, and built-in completion is triggered on any
letter. Each item carries a hover card that summarizes what the
keyword does and how it fits into the language.

### Snippets

Snippets for the things you type most often:

| Prefix | Expands to |
|--------|------------|
| `function`    | function declaration |
| `funpub`      | public static function |
| `funpriv`     | private function |
| `method`      | method declaration |
| `smethod`     | static method |
| `operator`    | operator overload |
| `generic`     | generic function |
| `if`          | if / else block |
| `elif`        | else-if branch |
| `while`       | while loop |
| `for`         | C-style for loop |
| `foreach`     | foreach loop |
| `do`          | do-while loop |
| `try`         | try/catch block |
| `var`         | inferred-type var |
| `const`       | inferred-type const |
| `embed`       | `embed("...")` binding |
| `unsafe`      | unsafeCast binding |
| `defuzzy`     | defuzzy-to-bool binding |
| `str`         | interpolated string |
| `fuzzycheck`  | fuzzy-quality-then-branch pattern |
| `main`        | top-level Main() idiom |

### Diagnostics

Run the `akashac` compiler (from `sdk/akasha-compiler`) and surface
its diagnostics in the Problems panel. Supports every diagnostic code
the compiler emits (AKA0001..AKA0113 at the time of writing),
including:

- `AKA0002` unterminated string literal
- `AKA0100` missing `;`, missing `)`, unexpected token
- `AKA0103` `var` combined with an explicit type
- `AKA0110` the `|>` pipe-forward operator
- `AKA0111` `(vector) "string"` — use `embed(...)` instead
- `AKA0112` a declaration marked both `public` and `private`
- `AKA0113` class name used in multiple casings in one file

Diagnostics run on save by default. Set `akasha.validateOn` to
`change` if you want live feedback on every keystroke, or `never` to
disable and use the `Akasha: Validate current file` command manually.

## Setup

1. Install the compiler:
   ```
   cd sdk/akasha-compiler
   pip install -e .
   ```
   (Or just ensure `python -m akasha_compiler` works from your PATH.)

2. In VS Code, open the extension folder and press F5 to launch an
   Extension Development Host. Any `.ak` file in the host window will
   be highlighted and validated.

3. If Python isn't on your PATH or you want a specific interpreter,
   set it in settings:
   ```json
   {
     "akasha.compilerPath": "C:\\Python313\\python.exe"
   }
   ```

## Settings

| Setting                  | Default               | Description |
|--------------------------|-----------------------|-------------|
| `akasha.compilerPath`    | `python`              | Python interpreter to invoke |
| `akasha.compilerArgs`    | `["-m", "akasha_compiler"]` | Arguments before the file path |
| `akasha.validateOn`      | `save`                | `save`, `change`, or `never` |
| `akasha.showAkaCodes`    | `true`                | Show AKA#### codes in Problems panel |

## Commands

- **Akasha: Validate current file** — run the validator on the active
  editor and refresh diagnostics.
- **Akasha: Validate all .ak files in workspace** — walk the workspace
  and validate every `.ak` file.

## Limitations (v0.1)

- No type checking, name resolution, or cross-file analysis yet.
  Those are planned for later SDK versions.
- Completion is purely keyword/primitive/built-in based; there's no
  symbol-level completion from the parsed AST yet.
- Hover information is static per keyword. A full semantic hover
  provider is planned for v0.2.

## License

Same as the rest of the Akasha repository.
