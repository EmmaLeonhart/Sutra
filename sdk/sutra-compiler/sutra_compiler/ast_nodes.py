"""AST node definitions for the Sutra compiler.

These are intentionally lean dataclasses. The parser builds them, the
validator walks them. A more elaborate visitor framework can come later
when we start lowering to IR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from .diagnostics import SourceSpan


# ============================================================
# Base
# ============================================================


@dataclass
class Node:
    span: SourceSpan


# ============================================================
# Types
# ============================================================


@dataclass
class TypeRef(Node):
    """A type appearing in a declaration or expression.

    `name` is the base type name. `type_args` is populated for generic
    instantiations like `List<vector>` or `Identity<Cat>`.
    """

    name: str
    type_args: List["TypeRef"] = field(default_factory=list)


# ============================================================
# Expressions
# ============================================================


@dataclass
class Expr(Node):
    pass


@dataclass
class IntLiteral(Expr):
    value: int


@dataclass
class FloatLiteral(Expr):
    value: float


@dataclass
class ImaginaryLiteral(Expr):
    # `5i`, `3.14i` — a number literal with an `i` suffix. Represents
    # a pure-imaginary value; runtime allocation places the scalar on
    # synthetic[AXIS_IMAG] with zero on the real axis. The `i` suffix
    # only binds when the following character is not an identifier
    # continuation, so the bare variable name `i` remains available
    # (`5 * i` stays a multiplication; `5i` is one token).
    value: float


@dataclass
class ComplexLiteral(Expr):
    # Folded form produced by the simplifier when it sees `Number ± Nij`
    # (an int/float plus or minus an imaginary literal). Codegen lowers
    # this to a single `_VSA.make_complex(re, im)` call so the emitted
    # source is one allocation instead of a vector-add. No user-facing
    # syntax produces this directly — always a fold.
    re: float
    im: float


@dataclass
class StringLiteral(Expr):
    value: str


@dataclass
class CharLiteral(Expr):
    # The Unicode code point. Runtime representation is a number-axis
    # scalar (synthetic[AXIS_REAL] = code point) plus a char-flag bit
    # on synthetic[AXIS_CHAR_FLAG] distinguishing chars from plain ints.
    value: int


@dataclass
class BoolLiteral(Expr):
    value: bool


@dataclass
class UnknownLiteral(Expr):
    # The `unknown` keyword — the neutral point on the truth axis,
    # 0.0 between false (-1) and true (+1). First-class value for
    # three-valued logic (see `trit` primitive class). Carries no
    # payload — the value is implicit in the literal kind.
    pass


@dataclass
class WaitLiteral(Expr):
    # The `wait` keyword — explicit deferred-initializer marker.
    # Legal only as the RHS of a var-decl (`int i = wait;`). Means
    # "I'm declaring this name now, an assignment will follow before
    # any read." The validator enforces definite assignment; codegen
    # emits zero-of-type at the declaration site and the later
    # assignment overrides it. Using `wait` anywhere else is a
    # parse-time error. Resolves the no-null deferred-init candidate
    # D from planning/open-questions/no-null.md.
    pass


@dataclass
class InterpolatedString(Expr):
    """$"foo {x} bar" — alternating literal chunks and expressions.

    `parts` is a list where each item is either a `str` literal chunk
    or an `Expr` interpolation.
    """

    parts: List[Union[str, Expr]]


@dataclass
class Identifier(Expr):
    name: str


@dataclass
class ThisExpr(Expr):
    pass


@dataclass
class MemberAccess(Expr):
    obj: Expr
    member: str


@dataclass
class Call(Expr):
    callee: Expr
    type_args: List[TypeRef]
    args: List[Expr]


@dataclass
class NewExpr(Expr):
    """`new ClassName(args)` — auto-constructor for a class with field
    declarations.

    Per the user's 2026-05-08 class-field design, a constructor is "a
    function that returns something that is in the class." `new` is
    sugar over that: the codegen emits a `<Class>_new(args)` factory
    that starts from a fresh vector and adds each field via axon_add
    in declaration order. Args are positional and must match the
    field count.
    """

    class_name: str
    args: List[Expr]


@dataclass
class CastExpr(Expr):
    """`(Type) expr` — safe cast."""

    target_type: TypeRef
    expr: Expr


@dataclass
class UnsafeCastExpr(Expr):
    """`unsafeCast<Type>(expr)`."""

    target_type: TypeRef
    expr: Expr


@dataclass
class UnsafeOverrideExpr(Expr):
    expr: Expr


@dataclass
class DefuzzyExpr(Expr):
    expr: Expr


@dataclass
class EmbedExpr(Expr):
    expr: Expr


@dataclass
class BinaryOp(Expr):
    op: str  # "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "&&", "||"
    left: Expr
    right: Expr


@dataclass
class UnaryOp(Expr):
    op: str  # "!", "-", "+"
    operand: Expr


@dataclass
class AwaitExpr(Expr):
    """`await expr` — gate on the input axon backing `expr`'s promise.

    Only legal inside an async function body (validated downstream).
    Lowers to a gated while_loop that waits for `expr`'s output axon
    to fire; see planning/sutra-spec/promises.md §"Lowering".
    """
    operand: Expr


@dataclass
class PostfixOp(Expr):
    op: str  # "++", "--"
    operand: Expr


@dataclass
class Assignment(Expr):
    op: str  # "=", "+=", "-=", "*=", "/="
    target: Expr
    value: Expr


@dataclass
class Parenthesized(Expr):
    inner: Expr


@dataclass
class ArrayLiteral(Expr):
    """`[a, b, c]` — an inline sequence of expressions.

    Used for argmax-cosine calls and similar list-of-vectors operands.
    The element type is inferred at use — the AST node just carries
    the raw element expressions.
    """

    elements: List[Expr] = field(default_factory=list)


@dataclass
class Subscript(Expr):
    """`target[index]` — postfix subscript access.

    Used for map lookups (`BEHAVIOR_OF[winner]`) and future array
    indexing. Whether the lookup is exact-match, cosine-nearest, or
    integer indexing is a runtime concern of the target type.
    """

    target: Expr
    index: Expr


@dataclass
class MapLiteral(Expr):
    """`{k1: v1, k2: v2, ...}` — an inline map literal.

    Keys and values are stored as parallel lists so the generic
    AST walker in the validator visits every child expression. An
    empty map literal `{}` has both lists empty.

    Map literals only appear in expression position (after `=`,
    `return`, as a function argument, etc.). A bare `{...}` at
    statement position is always a block — writing a map literal
    there requires wrapping it in a declaration or call.
    """

    keys: List[Expr] = field(default_factory=list)
    values: List[Expr] = field(default_factory=list)


# ============================================================
# Statements
# ============================================================


@dataclass
class Stmt(Node):
    pass


@dataclass
class Block(Stmt):
    statements: List[Stmt]


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr]


@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_branch: Block
    else_branch: Optional[Union["IfStmt", Block]]


@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: Block


@dataclass
class ForStmt(Stmt):
    init: Optional[Stmt]        # var decl, expr stmt, or None
    condition: Optional[Expr]
    step: Optional[Expr]
    body: Block


@dataclass
class ForeachStmt(Stmt):
    var_type: Optional[TypeRef]  # None means `var`
    var_name: str
    iterable: Expr
    body: Block


@dataclass
class LoopStmt(Stmt):
    """Sutra's unified loop construct.

    Three forms:
      loop (10) { ... }            → bounded, count is IntLiteral, no index
      loop (10 as i) { ... }       → bounded with index variable
      loop (condition) { ... }     → eigenrotation (convergence-based)

    The compiler distinguishes by checking whether `count` is set:
      - count is not None → bounded loop, unrolls at compile time
      - count is None → condition-based, compiles to geometric rotation
    """
    count: Optional[Expr]           # integer expression for bounded loops, None for while-style
    index_var: Optional[str]        # 'as i' variable name, None if not used
    condition: Optional[Expr]       # boolean expression for while-style loops, None for bounded
    body: Block


@dataclass
class DoWhileStmt(Stmt):
    body: Block
    condition: Expr


@dataclass
class TryStmt(Stmt):
    try_body: Block
    catch_body: Block




@dataclass
class LoopStateParam(Node):
    """One state parameter of a loop function declaration.

    Like Param but with an optional default initializer for use when
    the loop is called without specifying that parameter (common for
    accumulator state — running max, sum, count, etc.).
    """
    type_ref: TypeRef
    name: str
    default: Optional[Expr]


@dataclass
class LoopFunctionDecl(Node):
    """A loop function declaration of one of the four kinds.

    Surface syntax (kind keyword + name + paren-list + body):
        do_while addNumber(x < 11, int x) { pass x + 1; }
        while_loop ... (cond, ...state) { ... }
        iterative_loop ... (count, ...state) { ... }
        foreach_loop ... (array, ...state) { ... }

    For do_while/while_loop, `condition` is a boolean expression that
    references the state params; the loop iterates until it becomes
    false. For iterative_loop, `condition` is an integer expression
    giving the cap on tick count; the body uses the `iterator` keyword
    for the current tick. For foreach_loop, `condition` is an array
    expression; one element per tick (binding details TBD).

    The body uses `pass <exprs>;` (PassStmt) for the tail-recursive yield.
    """
    kind: str  # "do_while" | "while_loop" | "iterative_loop" | "foreach_loop"
    name: str
    condition: Expr        # first paren-list item; semantic depends on kind
    state_params: List[LoopStateParam]
    body: Block
    # Class-bodied loops only: when False (the default for class
    # loops), the loop is non-static and `this` threads as an implicit
    # first state parameter. When True, the loop is static and is
    # called via `loop Class.name(args)` without an instance. Top-level
    # loop functions (no enclosing class) ignore this field — they're
    # always effectively static.
    is_static: bool = False


@dataclass
class ReplaceMarker(Node):
    """Placeholder for the `replace` keyword in a `pass` argument list.

    `pass <expr>, replace, <expr>;` means: update first state param to
    expr, keep second state param at its input value, update third.
    Used when the body only updates some of the state params per tick.
    """


@dataclass
class PassStmt(Stmt):
    """`pass expr1, expr2, ...;` — tail-recursive yield in a loop body.

    Required to provide one value per state parameter (in declaration
    order). Each value is either an expression (the new value for that
    state param) or a ReplaceMarker (keep the param's input value).

    Triggers the next iteration of the enclosing loop function.
    Forbidden outside a loop function declaration body.
    """
    values: List[Union[Expr, ReplaceMarker]]


@dataclass
class LoopCallStmt(Stmt):
    """`loop name(cond_arg, state_arg, ...);` — invoke a loop function.

    The condition_arg is evaluated once before the first tick (and
    re-evaluated against the new state each subsequent tick).
    The state_args MUST be identifiers (slot variable names in the
    caller scope); on loop completion, the loop's final state values
    are written back into those caller variables (by-reference).
    """
    name: str
    condition_arg: Expr
    state_arg_names: List[str]


# ============================================================
# Declarations
# ============================================================


@dataclass
class Modifiers:
    is_public: bool = False
    is_private: bool = False
    is_static: bool = False


@dataclass
class Param(Node):
    type_ref: TypeRef
    name: str


@dataclass
class VarDecl(Stmt):
    """`var x = ...;`, `const x = ...;`, `TYPE x = ...;`, `var x : TYPE;`,
    `var[N] x : TYPE;`, or `role x = ...;`.

    The 2026-04-22 extensions (colon-syntax, array-slot form, role-
    declaration form) all ride on the same node type with additional
    flags:

    - `is_role`: this is a semantic role binding. `role X = expr;`
      produces a value that semantically should be treated as a
      learned matrix operator; today it behaves identically to
      `vector X = expr;` because learned-matrix binding is deferred.
      When learned-matrix binding lands, the is_role flag is what
      tells the codegen to emit the matrix-fit path.
    - `is_var_colon`: declared via `var X : TYPE` (the new
      rotation-bound form, with optional initializer). Uninitialized
      form allocates a zero value of the given type — this is the
      "var as storage slot" semantics from the surface-syntax decision.
    - `array_size`: if non-None, this is a `var[N] X : TYPE` array
      declaration allocating N slots. Semantics still pending; today
      the codegen just treats it as a Python list of N zero-values.
    """

    is_const: bool
    is_var_inferred: bool       # true if declared with `var` (inferred)
    type_ref: Optional[TypeRef]  # None only if is_var_inferred is True
    name: str
    initializer: Optional[Expr]
    is_role: bool = False
    is_var_colon: bool = False
    array_size: Optional[int] = None
    is_slot: bool = False


@dataclass
class FunctionDecl(Node):
    modifiers: Modifiers
    return_type: TypeRef
    name: str                    # operator name like "+" when is_operator
    type_params: List[str]
    params: List[Param]
    body: Block
    is_operator: bool = False
    is_implicit_conversion: bool = False
    # `intrinsic` declarations: signature only, semicolon-terminated,
    # no Sutra body. `body` is an empty Block in that case. Used by
    # stdlib files for leaf primitives whose implementation lives in
    # the runtime class (`_VSA.<name>(...)`).
    is_intrinsic: bool = False
    # `async function ...` — promise-producing function. Body may use
    # `await expr` to gate on incoming axons. Lowering is spec'd in
    # planning/sutra-spec/promises.md; codegen lowering is pending.
    is_async: bool = False


@dataclass
class MethodDecl(Node):
    modifiers: Modifiers
    return_type: TypeRef
    name: str
    type_params: List[str]
    params: List[Param]
    body: Block
    is_operator: bool = False
    # `static intrinsic method ...;` — signature only, semicolon-
    # terminated, no Sutra body. Used by stdlib class-as-namespace
    # bodies for leaf primitives whose implementation lives in the
    # runtime class (`_VSA.<name>(...)`). Mirrors FunctionDecl's
    # is_intrinsic for the class-method shape.
    is_intrinsic: bool = False


@dataclass
class FieldDecl(Node):
    """`field T name;` — a tag-along named variable on a class instance.

    Per the user's class-field design (2026-05-08): a class is an axon
    with a declared schema. Fields are not embedded substrate state;
    they're tag-along variables that travel with the `this` vector. At
    runtime, field reads and writes go through the same rotation-
    binding machinery that backs `Axon.add` / `Axon.item`. The class
    declaration provides the field-name schema; it does not allocate
    fixed slots in the vector.
    """
    name: str
    type_ref: TypeRef


@dataclass
class ClassDecl(Node):
    """`class Name extends Parent { ... }` — user-defined ontology
    class.

    Body content: method declarations, loop function declarations, and
    (since 2026-05-08) field declarations are accepted inside the body.
    Operator implementations remain deferred.

    Methods declared inside a class body land on this node's
    `methods` list. Field declarations land on `fields`. Loop function
    declarations land on `loop_functions`.

    At runtime an instance of a user class is a vector with optional
    rotation-bound field entries (the axon machinery). The declaration
    is compile-time metadata: the validator registers the class name
    and the field schema; the codegen lowers field reads and writes
    through the existing axon runtime methods.
    """
    name: str
    parent_name: str  # the `extends` target — required in MVP
    methods: List["MethodDecl"] = field(default_factory=list)
    loop_functions: List["LoopFunctionDecl"] = field(default_factory=list)
    fields: List["FieldDecl"] = field(default_factory=list)


# ============================================================
# Module
# ============================================================


TopLevel = Union[FunctionDecl, MethodDecl, VarDecl, Stmt, ClassDecl]


@dataclass
class Module:
    items: List[TopLevel]
    span: SourceSpan
