# Formal Sutra grammar (EBNF)

Derived from `sdk/sutra-compiler/sutra_compiler/lexer.py` + `parser.py`,
reconstructed 2026-04-13. Authoritative source is the parser; this is a
readable summary.

```ebnf
(* Module structure *)
module          = { top_level } EOF ;
top_level       = function_decl | method_decl | operator_decl ;
modifiers       = { "public" | "private" | "static" | "implicit" } ;

function_decl   = modifiers "function" IDENT [ type_params ] param_list
                  [ ":" type ] block ;
method_decl     = modifiers "method" IDENT [ type_params ] param_list
                  [ ":" type ] block ;
operator_decl   = modifiers "operator" operator_symbol [ type_params ]
                  param_list [ ":" type ] block ;
type_params     = "<" IDENT { "," IDENT } ">" ;
param_list      = "(" [ param { "," param } ] ")" ;
param           = IDENT ":" type ;
type            = IDENT [ "<" type { "," type } ">" ] ;

(* Statements *)
block           = "{" { statement } "}" ;
statement       = var_decl | if_stmt | while_stmt | for_stmt
                | foreach_stmt | do_while_stmt | loop_stmt
                | try_stmt | return_stmt | expr_stmt ;

var_decl        = ( "var" | "const" ) IDENT [ ":" type ]
                  [ "=" expr ] ";" ;
if_stmt         = "if" "(" expr ")" block [ "else" ( if_stmt | block ) ] ;
while_stmt      = "while" "(" expr ")" block ;
for_stmt        = "for" "(" [ var_decl | expr_stmt ] ";"
                  [ expr ] ";" [ expr ] ")" block ;
foreach_stmt    = "foreach" "(" IDENT "in" expr ")" block ;
do_while_stmt   = "do" block "while" "(" expr ")" ";" ;
try_stmt        = "try" block "catch" block ;
return_stmt     = "return" [ expr ] ";" ;
expr_stmt       = expr ";" ;

(* The core Sutra iteration construct *)
loop_stmt       = "loop" "(" loop_header ")" block ;
loop_header     = INT_LIT [ "as" IDENT ]   (* bounded: unrolled at compile time *)
                | expr ;                    (* condition-based: eigenrotation *)

(* Expressions — precedence from low to high *)
expr            = pipe_forward ;
pipe_forward    = assignment { "|>" assignment } ;
assignment      = logical_or [ ( "=" | "+=" | "-=" | "*=" | "/=" ) assignment ] ;
logical_or      = logical_and { "||" logical_and } ;
logical_and     = equality { "&&" equality } ;
equality        = comparison { ( "==" | "!=" ) comparison } ;
comparison      = additive { ( "<" | ">" | "<=" | ">=" ) additive } ;
additive        = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative  = unary { ( "*" | "/" | "%" ) unary } ;
unary           = [ "!" | "-" | "++" | "--" ] postfix ;
postfix         = primary { "." IDENT | "(" arg_list ")"
                          | "<" type_args ">" "(" arg_list ")"
                          | "[" expr "]" | "++" | "--" | "as" type } ;

primary         = INT_LIT | FLOAT_LIT | STRING_LIT | interp_string
                | "true" | "false" | "this"
                | IDENT | special_call | map_literal | array_literal
                | "(" expr ")" ;

special_call    = ( "unsafeCast" | "unsafeOverride"
                  | "defuzzy" | "embed" )
                  [ "<" type { "," type } ">" ] "(" expr ")" ;
map_literal     = "{" [ map_entry { "," map_entry } ] "}" ;
map_entry       = ( IDENT | STRING_LIT ) ":" expr ;
array_literal   = "[" [ expr { "," expr } ] "]" ;
interp_string   = "$\"" { STRING_LIT_CHUNK | "{" expr "}" } "\"" ;

arg_list        = [ expr { "," expr } ] ;
type_args       = type { "," type } ;
operator_symbol = "+" | "-" | "*" | "/" | "==" | "<" | ">" | "<=" | ">="
                | "[]" | "[]=" ;

(* Reserved keywords (from lexer KEYWORDS table) *)
(* function method static public private var const return
   if else while for foreach in do loop as try catch this
   operator new implicit true false                           *)
```

## Notes on the grammar

- `loop` is the only iteration construct that Sutra *semantically*
  distinguishes between a bounded (compile-time unrolled) form and a
  condition-based (eigenrotation on the substrate) form. `while`,
  `for`, `foreach`, `do_while` are host-side iteration; they compile
  to scaffolding, not to substrate eigenrotation.
- Sutra has no dedicated `bind`, `bundle`, `snap`, `similarity`, etc.
  keywords. These are ordinary functions in the runtime — calls written
  with regular `IDENT "(" arg_list ")"` syntax. The special-call
  production only covers the four forms (`unsafeCast`, `unsafeOverride`,
  `defuzzy`, `embed`) that need compiler-internal AST nodes rather than
  regular function dispatch.
- `if`/`else` is present in the grammar but is *host-side* control
  flow. Sutra programs that need substrate-side branching use fuzzy
  weighted superposition (spec §03) expressed as ordinary function
  calls, not an `if`-tree. The compiler does not reject `if` — it
  emits host Python `if`, same as any other scaffolding construct.
- `defuzzy(expr)` is the opt-in defuzzification marker (spec §04),
  lowered to `_VSA.is_true(...)` when the runtime supports it.
  `embed(expr)` is the string-to-vector primitive for codebook
  construction.
- The surface syntax is C-family: braces, semicolons, `==`/`!=`,
  dot-access, postfix `++`/`--`. This is deliberate — the novel
  semantics live in the runtime (fuzzy-by-default, vector operations
  on the substrate), not in the syntax.
