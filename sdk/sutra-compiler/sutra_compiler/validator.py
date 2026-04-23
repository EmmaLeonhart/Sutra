"""High-level validator for Sutra source.

The validator runs after the parser. It walks the AST and emits
diagnostics for rules that the syntax-decisions document calls out as
errors but that aren't enforced by the pure parser.

Rules implemented in v0.1:

- SUT0103: `var TYPE x` — `var` combined with an explicit type. (The
  parser already emits this; the validator doesn't need to re-check.)
- SUT0110: `|>` pipe-forward operator is not supported in Sutra.
- SUT0111: `(vector) "string"` (or any primitive-cast applied to a
  string literal) — per the spec, string→vector must go through
  `embed(...)`, not a cast.
- SUT0112: modifiers combined in disallowed ways (e.g. both `public`
  and `private`).
- SUT0113: naming drift — the file uses class names in inconsistent
  casing (a warning, not an error, because both are currently
  accepted in the example code).

v0.1 deliberately does NOT do:

- Type checking across declarations
- Name resolution (unknown identifiers)
- Arity checking on calls
- Return-statement coverage

Those land in v0.2+ once we have a symbol table and cross-module
resolution.
"""

from __future__ import annotations

from typing import List, Optional, Set

from . import ast_nodes as ast
from .diagnostics import (
    DiagnosticBag,
    DiagnosticLevel,
    SourcePosition,
    SourceSpan,
)
from .lexer import Lexer, TokenKind
from .parser import Parser


def _fuzzy_literal_constant(expr: ast.Expr) -> Optional[float]:
    """Fold a literal (possibly with unary +/-) to a single scalar.

    Returns None for anything needing runtime evaluation. Used to
    range-check fuzzy-typed literal initializers.
    """
    if isinstance(expr, ast.FloatLiteral):
        return float(expr.value)
    if isinstance(expr, ast.IntLiteral):
        return float(expr.value)
    if isinstance(expr, ast.BoolLiteral):
        return 1.0 if expr.value else -1.0
    if isinstance(expr, ast.UnknownLiteral):
        return 0.0
    if isinstance(expr, ast.UnaryOp) and expr.op in ("-", "+"):
        inner = _fuzzy_literal_constant(expr.operand)
        if inner is None:
            return None
        return -inner if expr.op == "-" else inner
    if isinstance(expr, ast.Parenthesized):
        return _fuzzy_literal_constant(expr.inner)
    return None


# ============================================================
# Public entry points
# ============================================================


def validate_source(
    source: str,
    *,
    file: Optional[str] = None,
) -> DiagnosticBag:
    """Lex, parse, and validate a string of Sutra source."""
    lexer = Lexer(source, file=file)
    tokens = lexer.tokenize()
    bag = lexer.diagnostics
    parser = Parser(tokens, file=file, diagnostics=bag)
    module = parser.parse_module()
    _check_pipe_forward(tokens, bag)
    _Walker(bag).visit_module(module)
    return bag


def validate_file(path: str) -> DiagnosticBag:
    """Validate a file on disk."""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    return validate_source(source, file=path)


# ============================================================
# Token-level checks (before AST walk)
# ============================================================


def _check_pipe_forward(tokens, bag: DiagnosticBag) -> None:
    """Flag any `|>` pipe-forward tokens.

    The spec is explicit: Sutra does not have a pipe operator; use
    nested calls or method chaining instead.
    """
    for tok in tokens:
        if tok.kind is TokenKind.PIPE_FORWARD:
            bag.error(
                "the `|>` pipe-forward operator is not supported in Sutra",
                tok.span,
                code="SUT0110",
                hint="use nested calls (`Normalize(Blend(a, b))`) or method chaining (`a.Blend(b).Normalize()`)",
            )


# ============================================================
# AST walker
# ============================================================


class _Walker:
    """AST walker that runs validator rules.

    Each visit_X method handles one node type. Unhandled nodes fall
    back to a generic child-walk so we always reach every expression.
    """

    def __init__(self, diagnostics: DiagnosticBag) -> None:
        self.diagnostics = diagnostics
        self._class_name_usages: Set[str] = set()

    # ---- module ----------------------------------------------------

    def visit_module(self, module: ast.Module) -> None:
        for item in module.items:
            self.visit(item)
        self._check_class_casing_drift()

    # ---- dispatch --------------------------------------------------

    def visit(self, node) -> None:
        method_name = f"visit_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is not None:
            method(node)
        else:
            self._walk_children(node)

    def _walk_children(self, node) -> None:
        # Generic walk: visit every field that's an AST node or a list
        # of AST nodes. This is enough for the v0.1 validator; richer
        # traversal can come later.
        for attr in vars(node).values():
            if isinstance(attr, (ast.Node, ast.Module)):
                self.visit(attr)
            elif isinstance(attr, list):
                for item in attr:
                    if isinstance(item, ast.Node):
                        self.visit(item)

    # ---- declarations ----------------------------------------------

    def visit_FunctionDecl(self, node: ast.FunctionDecl) -> None:
        self._check_modifier_conflict(node.modifiers, node.span)
        self._record_type_usage(node.return_type)
        for p in node.params:
            self._record_type_usage(p.type_ref)
        self.visit(node.body)

    def visit_MethodDecl(self, node: ast.MethodDecl) -> None:
        self._check_modifier_conflict(node.modifiers, node.span)
        self._record_type_usage(node.return_type)
        for p in node.params:
            self._record_type_usage(p.type_ref)
        self.visit(node.body)

    def visit_VarDecl(self, node: ast.VarDecl) -> None:
        if node.type_ref is not None:
            self._record_type_usage(node.type_ref)
        if node.initializer is not None:
            self.visit(node.initializer)
        # Fuzzy / trit / luk literals live on the truth axis which the
        # spec defines over [-1, +1]. A literal outside that range is
        # almost always a mistake; warn (not error) so existing programs
        # don't break while the rule beds in.
        if (node.type_ref is not None
                and node.type_ref.name in ("fuzzy", "trit", "luk")
                and node.initializer is not None):
            value = _fuzzy_literal_constant(node.initializer)
            if value is not None and (value < -1.0 or value > 1.0):
                self.diagnostics.warning(
                    f"{node.type_ref.name} literal {value!r} is outside "
                    "[-1, +1] — the truth axis saturates at ±1. "
                    "Did you mean a different type?",
                    node.span,
                    code="SUT0120",
                    hint="use a `scalar` for unbounded values, or clamp the "
                         "literal into [-1, +1]",
                )

    def visit_Param(self, node: ast.Param) -> None:
        self._record_type_usage(node.type_ref)

    # ---- statements ------------------------------------------------

    def visit_Block(self, node: ast.Block) -> None:
        for s in node.statements:
            self.visit(s)

    def visit_IfStmt(self, node: ast.IfStmt) -> None:
        self.visit(node.condition)
        self.visit(node.then_branch)
        if node.else_branch is not None:
            self.visit(node.else_branch)

    def visit_ForStmt(self, node: ast.ForStmt) -> None:
        if node.init is not None:
            self.visit(node.init)
        if node.condition is not None:
            self.visit(node.condition)
        if node.step is not None:
            self.visit(node.step)
        self.visit(node.body)

    def visit_ForeachStmt(self, node: ast.ForeachStmt) -> None:
        if node.var_type is not None:
            self._record_type_usage(node.var_type)
        self.visit(node.iterable)
        self.visit(node.body)

    # ---- expressions -----------------------------------------------

    def visit_CastExpr(self, node: ast.CastExpr) -> None:
        # SUT0111: (TYPE) "string literal" is not allowed. String ->
        # vector must go through embed(), per the spec.
        if isinstance(node.expr, ast.StringLiteral):
            self.diagnostics.error(
                f"cannot cast a string literal to `{node.target_type.name}`; "
                "use `embed(...)` to convert a string into a vector",
                node.span,
                code="SUT0111",
                hint="write `embed(\"...\")` instead of `({}) \"...\"`".format(
                    node.target_type.name
                ),
            )
        self._record_type_usage(node.target_type)
        self.visit(node.expr)

    def visit_UnsafeCastExpr(self, node: ast.UnsafeCastExpr) -> None:
        self._record_type_usage(node.target_type)
        self.visit(node.expr)

    def visit_Call(self, node: ast.Call) -> None:
        for t in node.type_args:
            self._record_type_usage(t)
        self.visit(node.callee)
        for a in node.args:
            self.visit(a)

    # ---- helpers ---------------------------------------------------

    def _check_modifier_conflict(
        self, mods: ast.Modifiers, span: SourceSpan
    ) -> None:
        if mods.is_public and mods.is_private:
            self.diagnostics.error(
                "a declaration cannot be both `public` and `private`",
                span,
                code="SUT0112",
            )

    def _record_type_usage(self, type_ref: Optional[ast.TypeRef]) -> None:
        if type_ref is None:
            return
        # Only track user-defined types (not primitives) so we can
        # detect casing drift on the same logical name.
        PRIMITIVES = {
            "scalar", "vector", "matrix", "tuple", "string",
            "bool", "fuzzy", "void", "permutation", "map",
        }
        if type_ref.name not in PRIMITIVES:
            self._class_name_usages.add(type_ref.name)
        for arg in type_ref.type_args:
            self._record_type_usage(arg)

    def _check_class_casing_drift(self) -> None:
        # Detect when the same class name appears in multiple casings
        # within a single file. e.g. `animal` and `Animal`. We don't
        # know which is canonical, so we emit a single warning listing
        # both variants.
        by_lower: dict = {}
        for name in self._class_name_usages:
            by_lower.setdefault(name.lower(), set()).add(name)
        for variants in by_lower.values():
            if len(variants) > 1:
                sorted_variants = sorted(variants)
                joined = ", ".join(f"`{v}`" for v in sorted_variants)
                # Use a zero-length span at position 1,1 since this is
                # a file-level concern. The SUT0113 code makes it
                # editor-filterable.
                pos = SourcePosition(line=1, column=1, offset=0)
                self.diagnostics.warning(
                    f"class name appears in multiple casings in the same file: {joined}",
                    SourceSpan(start=pos, end=pos),
                    code="SUT0113",
                    hint="pick one casing and use it consistently — the spec "
                         "follows C# naming (PascalCase for class names)",
                )
