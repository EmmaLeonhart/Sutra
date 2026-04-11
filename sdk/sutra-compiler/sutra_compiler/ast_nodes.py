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
class StringLiteral(Expr):
    value: str


@dataclass
class BoolLiteral(Expr):
    value: bool


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
class DoWhileStmt(Stmt):
    body: Block
    condition: Expr


@dataclass
class TryStmt(Stmt):
    try_body: Block
    catch_body: Block


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
    """`var x = ...;`, `const x = ...;`, or `TYPE x = ...;`"""

    is_const: bool
    is_var_inferred: bool       # true if declared with `var`
    type_ref: Optional[TypeRef]  # None only if is_var_inferred is True
    name: str
    initializer: Optional[Expr]


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


@dataclass
class MethodDecl(Node):
    modifiers: Modifiers
    return_type: TypeRef
    name: str
    type_params: List[str]
    params: List[Param]
    body: Block
    is_operator: bool = False


# ============================================================
# Module
# ============================================================


TopLevel = Union[FunctionDecl, MethodDecl, VarDecl, Stmt]


@dataclass
class Module:
    items: List[TopLevel]
    span: SourceSpan
