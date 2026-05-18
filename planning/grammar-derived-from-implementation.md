# Sutra — formal grammar and language specification

> ⚠️ **READ THIS FIRST — descriptive, not prescriptive.** This doc
> was requested by Emma 2026-05-17 ("a formal grammar and
> specification … for more PL theory stuff"). It is **mechanically
> derived by reading the real lexer/parser/AST** this session, not
> authored from VSA literature or invented taxonomy. It deliberately
> lives at `planning/` root, **NOT** in `planning/sutra-spec/`,
> because that directory is intentionally kept minimal:
> `planning/sutra-spec/README.md` records a meta-failure where a
> prior Claude filled the spec dir with content that "sounded
> spec-shaped" (tier hierarchies, an EBNF grammar) but did not match
> Emma's design, and the deprecated spec (incl. its grammar) is
> quarantined at `planning/sutra-spec-deprecated/`. To not repeat
> that: this file claims authority over **exactly one thing — what
> the current parser actually accepts**. Where it and Emma's
> intended design differ, that is a *description bug to fix here*,
> not a design assertion. It is not the canonical language spec and
> must not be cited as one. The prose section specs in
> `planning/sutra-spec/` remain the design surface.

Status: **v1, 2026-05-17.** Grounded in the real implementation
(`sdk/sutra-compiler/sutra_compiler/lexer.py`, `parser.py`,
`ast_nodes.py`) — not an idealized grammar. Where a production is
parser-internal or recovery-only it is cited by source location
rather than over-specified. This is the PL-theory surface: lexical
grammar, syntactic grammar (EBNF), the desugaring pipeline as the
operational bridge, and the substrate denotational sketch. It
complements the prose specs in this folder; if this file and a
section spec disagree on a fact, that is a bug to resolve, not a
licensed drift.

Notation: EBNF. `X*` zero-or-more, `X+` one-or-more, `X?`
optional, `( … )` grouping, `|` alternation, `"x"` terminal,
`UPPER` lexical token class, `lower` nonterminal. Comments in
`(* … *)`.

---

## 1. Lexical grammar

Source is UTF-8. Whitespace and comments separate tokens and are
otherwise insignificant (no offside rule). Comments: `// … <eol>`
and `/* … */` (non-nesting).

```
IDENT      = (letter | "_") (letter | digit | "_")*
INT_LIT    = digit+
FLOAT_LIT  = digit+ "." digit+
IMAG_LIT   = (digit+ | digit+ "." digit+) "i"      (* 5i, 3.14i *)
STRING_LIT = '"' (char - '"' | '\' char)* '"'
CHAR_LIT   = "'" (char - "'" | '\' char) "'"
INTERP_STR = '$"' ( chunk | "{" expr "}" )* '"'      (* InterpolatedString *)
```

**Hard keywords** (lexer `KEYWORDS`, fixed positions):
`function method static public private var const return if else
while for foreach in do loop do_while while_loop iterative_loop
foreach_loop pass replace as try catch this operator new implicit
intrinsic class extends slot field true false unknown unk wait
async await`.

**Contextual keywords** (lex as `IDENT`, recognized by the parser
by lexeme + lookahead so user identifiers of the same spelling
keep working): `role`; the logical-connective words `and or not
nand xor xnor iff`.

**Primitive type names** (ordinary identifiers; treated as types
only in type position): `number` (canonical) and its deprecated
alias `scalar`, `int`, `float`, `complex`, `char`, `bool`,
`fuzzy`, `trit`, `vector`, `matrix`, `permutation`, `tuple`,
`string`, `map`, `void`, `Promise`. (`scalar` is retained only so
the frozen NeurIPS archive compiles — see
`planning/sutra-spec/types.md`.)

---

## 2. Syntactic grammar

### 2.1 Module and top-level

```
module      = top_level* ;
top_level   = function_decl
            | loop_function_decl
            | class_decl
            | var_decl
            | statement ;          (* bare statements are lowered as a stmt *)
```

### 2.2 Declarations

```
modifiers   = ( "public" | "private" | "static" )* ;
function_decl =
      "async"? modifiers "function" type IDENT
      "(" param_list? ")" block ;
param_list  = param ( "," param )* ;
param       = type IDENT ;

class_decl  = "class" IDENT "extends" IDENT
              "{" class_member* "}" ;
class_member = method_decl | field_decl | loop_function_decl ;
method_decl  = modifiers ( "method" | "intrinsic" "method" )
               type IDENT "(" param_list? ")" ( block | ";" ) ;
field_decl   = "field" type IDENT ( "=" expr )? ";" ;

var_decl =
      ( "const" | "var" | "role" | "slot"? type
      | "slot"? "var" ) IDENT ( ":" type )?
      ( "[" INT_LIT "]" )?
      ( "=" ( expr | "wait" ) )? ";" ;
(* concrete forms: `T x = e;`  `var x = e;`  `const x = e;`
   `T x;` (zero-init)  `var x : T;`  `var[N] x : T;`
   `role x = e;`  `slot T x = e;`  `T x = wait;`
   exact disambiguation: parser.py _parse_var_decl. *)
```

`intrinsic` method/function bodies are `;` (no block) — the
implementation is a substrate runtime method, not Sutra source.

### 2.3 Loop function declarations (the 2026-04-30 redesign)

```
loop_function_decl =
      ( "do_while" | "while_loop" | "iterative_loop"
      | "foreach_loop" ) IDENT
      "(" loop_ctrl ( "," loop_state_param )* ")" block ;
loop_ctrl        = expr ;     (* condition | count | array, per kind *)
loop_state_param = type IDENT ;
pass_stmt        = "pass" pass_item ( "," pass_item )* ";" ;
pass_item        = expr | "replace" ;
```

The body yields the next recurrent state via `pass`; `replace`
keeps a state slot at its loop-call-time value. See
`control-flow.md` §Loops for the substrate execution model
(fixed-T branchless RNN-cell unroll with a soft halt).

### 2.4 Statements

```
block      = "{" statement* "}" ;
statement  = var_decl
           | "return" expr? ";"
           | if_stmt
           | loop_stmt
           | loop_call_stmt
           | pass_stmt
           | foreach_stmt
           | try_stmt
           | block
           | expr ";" ;
if_stmt    = "if" "(" expr ")" block ( "else" ( if_stmt | block ) )? ;
loop_stmt  = "loop" "(" expr ( "as" IDENT )? ")" block ;
           (* count IntLiteral -> compile-time unroll;
              else -> implicit tail-recursive desugar, loop_desugar.py *)
loop_call_stmt = "loop" name "(" expr ( "," IDENT )* ")" ";" ;
name       = IDENT ( "." IDENT )? ;
foreach_stmt   = "foreach" "(" ( type | "var" ) IDENT "in" expr ")" block ;
try_stmt   = "try" block "catch" block ;
```

Retired surface still parsed for a clear error (no substrate
path): C-style `while (…) {}`, `for (…;…;…) {}`,
`do {} while (…);`. They lower to `CodegenNotSupported` pointing
at the loop-function forms.

### 2.5 Types

```
type   = IDENT type_args? ( "[" "]" )? ;
type_args = "<" type ( "," type )* ">" ;
(* e.g. number, vector, map<string, vector>, Promise<vector>,
   number[]  — see parser.py _parse_type *)
```

### 2.6 Expressions — precedence (lowest → highest)

Exactly as implemented by the precedence-climbing chain in
`parser.py` (`_parse_expr` → … → `_parse_primary`):

```
expr        = pipe_forward ;
pipe_forward = assignment ( "|>" assignment )* ;   (* "|>" parsed then
                                                      rejected, SUT0110 *)
assignment  = logical_or ( ( "=" | "+=" | "-=" | "*=" | "/=" )
                            assignment )? ;          (* right-assoc *)
logical_or  = logical_xor ( ( "||" | "or" ) logical_xor )* ;
logical_xor = logical_and ( ( "xor"|"xnor"|"iff"|"nand" ) logical_and )* ;
logical_and = equality ( ( "&&" | "and" ) equality )* ;
equality    = comparison ( ( "==" | "!=" ) comparison )* ;
comparison  = additive ( ( "<" | "<=" | ">" | ">=" ) additive )* ;
additive    = multiplicative ( ( "+" | "-" ) multiplicative )* ;
multiplicative = unary ( ( "*" | "/" | "%" ) unary )* ;
unary       = ( "!" | "-" | "+" | "not" | "await" ) unary
            | postfix ;
postfix     = primary ( "(" arg_list? ")"          (* call *)
                       | "." IDENT                  (* member access *)
                       | "[" expr "]"               (* subscript *)
                       | "++" | "--" )* ;
primary     = INT_LIT | FLOAT_LIT | IMAG_LIT | STRING_LIT
            | CHAR_LIT | INTERP_STR
            | "true" | "false" | "unknown" | "unk" | "this"
            | "new" IDENT "(" arg_list? ")"
            | IDENT
            | "(" expr ")"
            | array_literal | map_literal ;
array_literal = "[" ( expr ( "," expr )* )? "]" ;
map_literal   = "{" ( expr ":" expr ( "," expr ":" expr )* )? "}" ;
arg_list      = expr ( "," expr )* ;
```

`^` (exponentiation) is reduced at the parser/desugar level to
`Math.pow`; it is not a distinct AST binary node (see
`control-flow.md`/math notes). `|>` is intentionally a parse-then-
reject construct.

---

## 3. Static semantics (validation)

Sutra's design rule is **"no runtime errors by mechanism"**: type
mismatches produce semantically meaningless but mathematically
valid output; the validator + codegen are the line of defense.
Enforced statically (non-exhaustive; see `validator.py` and the
`SUTxxxx` diagnostic codes): `await` only inside an `async`
function; `pass` only inside a loop-function body; `wait` only in a
var-decl initializer with definite-assignment before use;
`loop NAME(…)` state args must be `slot` variables; primitive type
names are not user-class names (casing-drift check); `|>` is
rejected (SUT0110). Opinionated patterns warn but still compile;
escape hatches are explicit and grep-able.

---

## 4. Operational semantics — the desugaring pipeline

Sutra's dynamic semantics are defined by **lowering**, applied in
order before codegen (`translate_module` in both backends):

1. **promise desugar** (`promise_desugar.py`): `async`/`await` →
   explicit `Promise.*` construction; `await x` → `Promise.value`
   / `Promise.await_value`. JavaScript `.then()`-chain semantics
   (Promises/A+ vocabulary).
2. **implicit-loop desugar** (`loop_desugar.py`): `loop(expr){B}`
   with non-literal bound → a synthesized `iterative_loop`
   (integer bound) or `while_loop` (relational/logical bound)
   loop-function over the **implicit axon** = variables `B`
   mutates ∪ free variables of the bound (threaded invariant via
   `replace`); each such variable's declaration is rewritten to
   `slot`; the `loop` statement becomes a `loop`-call. Literal
   `loop[N]{B}` instead unrolls at compile time.
3. **stdlib inlining** (`inliner.py`): non-intrinsic stdlib
   method bodies (the literate `math.su` etc.) are inlined so the
   documented identity *is* the executed reduction.
4. **simplification** (`simplify.py`): algebraic constant folding,
   zero absorption.
5. **codegen** (`codegen_pytorch.py`, canonical; `codegen.py`
   numpy, deprecated): every Sutra operation emits substrate
   tensor ops.

A loop's reduction is the canonical example: `loop(c){B}` ≡ a
tail-recursive function `f(state) = if ¬c then state else
f(B⟦state⟧)`, executed as a fixed-T branchless RNN-cell unroll
with a soft-halt mux on the substrate. `await p` ≡ the terminal
read of that loop where the implicit axon is the single promise
slot and the halt is the two-channel arrival flag; with no
external producer it reduces exactly to `value(p)` (see
`planning/findings/2026-05-17-await-substrate-pure.md`).

---

## 5. Denotational sketch — the substrate

Every value denotes a vector in the extended state space
`ℝ^d = ℝ^semantic ⊕ ℝ^synthetic`. The synthetic block carries
designated axes: `AXIS_REAL`, `AXIS_IMAG` (a `number`/`complex` is
its value on these), `AXIS_TRUTH` (`bool`/`fuzzy`/`trit` ∈
[−1,+1]; `unknown` = 0), promise channels, slot block, string
codepoint block. There is no scalar primitive distinct from a
vector: a `number` is a vector with value on the number axis and
zeros elsewhere (`types.md`). Operations are tensor maps
ℝ^d → ℝ^d (matmul, elementwise, `tanh`/`exp`/`sqrt`/`abs`/`sign`,
crosstalk lookup). `is_true` is the defuzzification functional
ℝ^d → [−1,+1] that recursively sharpens along the truth axis
without binarizing. Fuzziness is the default denotation;
precision is the special case.

---

## 6. Known grammar caveats (accurate, not faked)

- The `var_decl` production above summarizes several concrete
  forms whose exact disambiguation is in `parser.py`
  `_parse_var_decl` (colon-form vs assignment-form vs slot-form
  lookahead). The EBNF is faithful in the set of accepted forms,
  approximate in factoring.
- Operator/`operator +` declarations and module imports are
  parsed-but-largely-deferred at codegen (V1 coverage —
  `planning/open-questions/codegen-v1-feature-coverage.md`).
- The implicit-loop kind selection (`iterative_loop` vs
  `while_loop`) is a syntactic heuristic on the bound's shape;
  equality/negation bounds inherit the fuzzy numeric-equality
  truth-axis semantics (`loop_desugar.py` `_loop_kind`).
- `^`, `|>` are surface constructs without their own AST nodes
  (reduced / rejected respectively).

This grammar is versioned with the implementation; update it in
the same spirit as the section specs when the surface changes.
```
