# Surface Grammar

This document is the formal grammar for Sutra source files (`.su`). It is the contract between what the programmer writes and what the compiler accepts. The lexer and parser under `sdk/sutra-compiler/sutra_compiler/` are the reference implementation; when this document and the implementation disagree, one of them is wrong and the disagreement must be resolved explicitly (per `CLAUDE.md`).

Syntactic decisions discussed in prose live in [`sutra-syntax-decisions.md`](../../sutra-syntax-decisions.md) at the repo root. This document is the mechanical distillation of those decisions into an EBNF-style grammar the compiler can implement against.

## Status and versioning

**This document is the v0.0.0 grammar.** Everything in this repo is v0.0.0 source, the reference compiler in `sdk/sutra-compiler/` is the v0.0.0 toolchain, and the grammar below is what that toolchain accepts. Nothing in this document is meant to break existing code — v0.0.0 must keep compiling under the current toolchain, because it is the only toolchain that exists.

The grammar is **versioned with the language**. The version a given source tree is written against is pinned by the `sutra_version` field of its workspace or project `atman.toml`. See [`22-workspaces.md`](22-workspaces.md) for the workspace schema and [`25-solution-structure.md`](25-solution-structure.md) for how version pinning propagates through a solution — including what "no `atman.toml` ⇒ implicit v0.0.0" means, and what happens to v0.0.0 trees once a stable v0.1.0 exists.

Treat the grammar below as a snapshot of v0.0.0, not a forward-compatibility commitment. Breaking changes between v0.0.0 and v0.1.0 are explicitly allowed, because the whole point of calling the current state v0.0.0 rather than v0.1 is to keep those breaking changes on the table.

## Notation

The grammar uses ISO 14977-adjacent EBNF with the following conventions:

- `"..."` — literal terminal (keyword, operator, punctuation).
- `UPPER` — lexical class defined in §Lexical grammar below.
- `{ X }` — zero or more repetitions of `X`.
- `[ X ]` — optional `X`.
- `X | Y` — alternation.
- `X , Y` — concatenation (ISO-style; omitted where unambiguous).
- `(* ... *)` — grammar-level comment.

Whitespace and comments are consumed by the lexer between tokens and are not mentioned in the grammar below.

## Top-level

```
module          = { top_level_item } ;

top_level_item  = function_decl
                | method_decl
                | var_decl
                | typed_var_decl
                | statement ;
```

A `.su` file is a sequence of top-level items. There is no explicit module declaration — the file itself is the module, and whether the module is an *object declaration* (a file full of `method` declarations acting as the body of a type) or an *executable file* (top-level code that just runs) is determined by its contents, not by syntax. See `examples/01-objects-and-methods.su` vs `examples/06-executable-file.su`.

## Declarations

### Modifiers

```
modifiers       = { "public" | "private" | "static" } ;
```

Modifiers are legal **before** `function` / `method` and **after** `function` (the "full internal form"). The parser accepts either position and merges them. `static` alone, followed by `method`, is a static method declaration.

### Functions and methods

```
function_decl   = [ modifiers ] , "function" , [ modifiers ] ,
                  ( operator_suffix
                  | type , IDENT , [ type_params ] ,
                    "(" , [ params ] , ")" , block ) ;

method_decl     = [ modifiers ] , "method" ,
                  ( operator_suffix
                  | type , IDENT , [ type_params ] ,
                    "(" , [ params ] , ")" , block ) ;

operator_suffix = "operator" , OVERLOADABLE_OP ,
                  "(" , [ params ] , ")" , block ;

type_params     = "<" , IDENT , { "," , IDENT } , ">" ;
params          = param , { "," , param } ;
param           = type , IDENT ;
```

Operator overloading uses `function operator <op>(...)` or `method operator <op>(...)`. The set `OVERLOADABLE_OP` is `+ - * / % == != < > <= >= !`. Unary `!` and binary arithmetic/comparison operators are the only overloadable tokens in v0.0.0. Assignment, logical, and bitwise operators are **not** overloadable.

### Types

```
type            = IDENT , [ "<" , type_args , ">" ] ;
type_args       = type , { "," , type } ;
```

Primitive type names (`scalar`, `vector`, `matrix`, `tuple`, `string`, `bool`, `fuzzy`, `void`, `permutation`, `map`) are lexed as ordinary identifiers. The parser treats them as types in type position; `map` in particular is a generic container written `map<K, V>`.

### Variables

```
var_decl        = ( "var" | "const" ) , [ type ] , IDENT ,
                  [ "=" , expr ] , ";" ;

typed_var_decl  = type , IDENT , [ "=" , expr ] , ";" ;
```

`var` declares an inferred-type binding and **must not** be combined with an explicit type — `var vector x = ...;` is a diagnostic (`SUT0103`). `const TYPE x = ...;` is legal; `const x = ...;` is a type-inferred constant. `typed_var_decl` is the plain form: `vector x = ...;`.

## Statements

```
statement       = if_stmt | while_stmt | for_stmt | foreach_stmt
                | do_while_stmt | loop_stmt | try_stmt | return_stmt
                | var_decl | typed_var_decl | block | expr_stmt
                | function_decl | method_decl ;

block           = "{" , { statement } , "}" ;

if_stmt         = "if" , "(" , expr , ")" , block ,
                  [ "else" , ( if_stmt | block ) ] ;

while_stmt      = "while" , "(" , expr , ")" , block ;

for_stmt        = "for" , "(" , [ for_init ] , ";" ,
                  [ expr ] , ";" , [ expr ] , ")" , block ;
for_init        = var_decl | typed_var_decl | expr_stmt ;

foreach_stmt    = "foreach" , "(" , ( "var" | type ) , IDENT ,
                  "in" , expr , ")" , block ;

do_while_stmt   = "do" , block , "while" , "(" , expr , ")" , ";" ;

loop_stmt       = "loop" , "(" , loop_header , ")" , block ;
loop_header     = INT_LIT , [ "as" , IDENT ]            (* bounded *)
                | expr ;                                 (* eigenrotation *)

try_stmt        = "try" , block , "catch" , block ;

return_stmt     = "return" , [ expr ] , ";" ;

expr_stmt       = expr , ";" ;
```

`loop` has two forms that look identical at the token level and are disambiguated by the parser: an integer literal (optionally followed by `as IDENT`) is the **bounded** form (unrolled at compile time, no runtime iteration, no eigenrotation); any other expression is the **condition** form (eigenrotation against the substrate's angular state). See [`03-control-flow.md`](03-control-flow.md) for the semantics.

`try`/`catch` is syntactic sugar over fuzzy failure-pattern branching per [`sutra-syntax-decisions.md`](../../sutra-syntax-decisions.md) §"Error handling". The grammar does not require a `catch` parameter.

## Expressions

Expressions are a conventional cascaded-precedence grammar, with the levels (lowest to highest binding) as follows. Each `_<level>` nonterminal below is left-associative unless otherwise noted.

```
expr            = assignment ;

assignment      = logical_or , [ assign_op , assignment ] ;    (* right-assoc *)
assign_op       = "=" | "+=" | "-=" | "*=" | "/=" ;

logical_or      = logical_and , { "||" , logical_and } ;
logical_and     = equality , { "&&" , equality } ;
equality        = comparison , { ( "==" | "!=" ) , comparison } ;
comparison      = additive , { ( "<" | ">" | "<=" | ">=" ) , additive } ;
additive        = multiplicative , { ( "+" | "-" ) , multiplicative } ;
multiplicative  = unary , { ( "*" | "/" | "%" ) , unary } ;
unary           = ( "!" | "-" | "+" ) , unary | postfix ;
postfix         = primary , { postfix_op } ;

postfix_op      = "." , IDENT                                  (* member *)
                | "(" , [ args ] , ")"                         (* call *)
                | "<" , type_args , ">" , "(" , [ args ] , ")" (* generic call *)
                | "[" , expr , "]"                             (* subscript *)
                | "++" | "--" ;                                (* postfix incr/decr *)

args            = expr , { "," , expr } ;
```

**Pipe forward `|>` is explicitly forbidden** (validator diagnostic `SUT0110`). The parser recognizes it to produce a clean root-cause error instead of a cascade of recovery failures; it is never legal in a compiling program.

### Primary expressions

```
primary         = INT_LIT | FLOAT_LIT | STRING_LIT | interp_string
                | BOOL_LIT | IDENT | "this"
                | paren_or_cast | array_literal | map_literal
                | special_call ;

paren_or_cast   = "(" , type , ")" , unary                      (* cast *)
                | "(" , expr , ")" ;                             (* grouping *)

array_literal   = "[" , [ expr , { "," , expr } ] , "]" ;
map_literal     = "{" , [ expr , ":" , expr ,
                           { "," , expr , ":" , expr } ] , "}" ;

special_call    = "unsafeCast" , "<" , type , ">" ,
                      "(" , expr , ")"
                | "unsafeOverride" , "(" , expr , ")"
                | "defuzzy" , "(" , expr , ")"
                | "embed" , "(" , expr , ")" ;
```

`unsafeCast`, `unsafeOverride`, `defuzzy`, and `embed` are **contextual keywords**: they are parsed as language-level special forms when they appear in call position, and as ordinary identifiers otherwise. Trailing commas are not permitted in argument lists, array literals, or map literals.

Two ambiguities the parser resolves with look-ahead:

- `(Type) expr` (cast) vs `(expr)` (grouping): the parser speculatively parses a bare type followed by `)`, and commits to a cast only if the next token can start a unary expression and is not itself `(`.
- `Ident < ... > ( ... )` (generic call) vs `a < b` (less-than): in postfix position, the parser only treats `<` as opening type arguments if the sub-stream lexes as a balanced `< type_args >` followed immediately by `(`.

### String interpolation

```
interp_string   = STRING_INTERP_START ,
                  { STRING_LIT_CHUNK
                  | INTERP_OPEN , expr , INTERP_CLOSE } ,
                  STRING_INTERP_END ;
```

The lexer produces the bracketing tokens (`$"`, `"`, `{`, `}`) so the parser can walk into and out of interpolation holes with the full expression grammar. Brace nesting inside a hole is counted; only the *matching* closing brace returns control to the string body.

## Lexical grammar

The lexer (`sdk/sutra-compiler/sutra_compiler/lexer.py`) is the authoritative reference. Summary:

### Whitespace and comments

Whitespace is any run of `" "`, `"\t"`, `"\r"`, `"\n"`. All four comment forms are recognized and discarded:

```
line_comment_c   = "//" , { any-char-except-newline } ;
line_comment_py  = "#"  , { any-char-except-newline } ;
doc_comment      = "///" , { any-char-except-newline } ;      (* lexed as line comment *)
block_comment    = "/*" , { any-char } , "*/" ;               (* not nested *)
```

### Identifiers and keywords

```
IDENT           = ( letter | "_" ) , { letter | digit | "_" } ;

KEYWORD         = "function" | "method" | "static" | "public" | "private"
                | "var" | "const" | "return"
                | "if" | "else" | "while" | "for" | "foreach" | "in"
                | "do" | "loop" | "as"
                | "try" | "catch" | "this"
                | "operator" | "new" | "implicit"
                | "true" | "false" ;
```

Contextual keywords (parsed as special forms only in call position): `defuzzy`, `embed`, `unsafeCast`, `unsafeOverride`.

### Literals

```
INT_LIT         = digit , { digit } ;
FLOAT_LIT       = digit , { digit } , "." , digit , { digit } ;     (* v0.0.0: no exponent *)
BOOL_LIT        = "true" | "false" ;

STRING_LIT      = '"' , { string_char | escape } , '"' ;
escape          = "\\" , ( "n" | "t" | "r" | "\\" | '"' | "'" | "0"
                         | "{" | "}" | "$" ) ;

(* Interpolated strings are delivered as a token sequence, not a single
   literal; see §String interpolation above. *)
```

### Operators and punctuation

Single-character: `{ } ( ) [ ] ; , . : + - * / % ! ? = < > & | ^`.

Two-character: `== != <= >= && || ++ -- += -= *= /= -> => |> ::`.

`|>` is lexed only so the validator can reject it with a clear diagnostic; it is not legal syntax.

## Diagnostics

The lexer and parser emit diagnostics with stable `SUT####` codes. v0.0.0 codes in the grammar space:

| Code | Meaning |
|---|---|
| `SUT0001` | Unterminated block comment |
| `SUT0002` | Unterminated string literal |
| `SUT0003` | Unexpected character in source |
| `SUT0100` | Parser expected a specific token |
| `SUT0101` | `public`/`private`/`static` used outside `function`/`method` |
| `SUT0102` | Non-overloadable operator in `operator` declaration |
| `SUT0103` | `var` combined with an explicit type |
| `SUT0104` | Expected expression |
| `SUT0105` | `unsafeCast` missing type argument |
| `SUT0110` | `\|>` used (spec forbids pipe forward) |

Codes `SUT2000-SUT2099` are reserved for workspace-model errors; see [`22-workspaces.md`](22-workspaces.md).

## Out of scope for v0.0.0

The following have reserved tokens or partial parser support but no defined semantics in v0.0.0 and are expected to land in a later version:

- `new` keyword — reserved, not used by any production.
- `implicit` keyword — reserved for implicit-conversion declarations (see `sutra-syntax-decisions.md` §"Implicit casts are allowed but must be explicitly defined").
- `foreach` with non-iterable arguments — parsed, but semantics depend on the collection model, which is not fixed in v0.0.0.
- `try`/`catch` failure-pattern matching — parsed; semantics live in the runtime spec.
- Lambda / anonymous function literals — not yet in the grammar (candidate decision per `sutra-syntax-decisions.md`).

None of these should be expected to survive the v0.1.0 cut unchanged.
