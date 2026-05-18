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
        # User-declared classes — name → parent_name. Populated by
        # visit_ClassDecl. Used to walk inheritance chains and to
        # check that user-defined types in type positions actually
        # resolve to a declared class.
        self._class_decls: dict = {}
        # `wait`-declared variables in the *current* function scope.
        # Maps name → declaration span, populated when a `var x = wait;`
        # is seen. Cleared on function entry so wait-tracking is
        # function-local. When the function body finishes, any name
        # still in this dict has never been assigned and gets a
        # SUT0130 error.
        self._wait_declared: dict = {}
        # Names declared at file scope (top-level FunctionDecl,
        # MethodDecl, VarDecl, ClassDecl, LoopFunctionDecl). Populated
        # in visit_module before the per-item walk. Used by the object-
        # encapsulation rule (SUT0144): object methods cannot read
        # file-scope names — see planning/open-questions/
        # function-taxonomy-and-closure.md.
        self._file_scope_names: Set[str] = set()
        # When inside a method body, the set of names locally in
        # scope (params + body var decls). None when not in a method.
        # The encapsulation rule fires on any Identifier whose name is
        # in _file_scope_names AND not in _method_local_names while
        # _method_local_names is non-None.
        self._method_local_names: Optional[Set[str]] = None

    # ---- module ----------------------------------------------------

    def visit_module(self, module: ast.Module) -> None:
        # Pre-pass: collect every top-level declaration's name into the
        # file-scope set, EXCEPT class names. Class names are
        # namespace anchors — `Math.log(x)` from inside a method is
        # legitimate access through the class boundary, not a
        # file-scope read. The encapsulation rule (SUT0144) fires on
        # bare references to file-scope free functions, top-level vars,
        # top-level methods, and top-level loop functions.
        for item in module.items:
            if isinstance(item, ast.ClassDecl):
                continue
            name = getattr(item, "name", None)
            if isinstance(name, str) and name:
                self._file_scope_names.add(name)
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

    def visit_ClassDecl(self, node: ast.ClassDecl) -> None:
        # Detect duplicate class declarations.
        if node.name in self._class_decls:
            self.diagnostics.error(
                f"class `{node.name}` is already declared in this module",
                node.span,
                code="SUT0141",
            )
            # Still walk methods so any in-method diagnostics fire.
            for m in node.methods:
                self.visit(m)
            return

        # Walk the would-be inheritance chain to verify it bottoms
        # out at a primitive. The parent must be either a primitive
        # type name or a previously-declared user class. Forward
        # references aren't supported in MVP — declarations are
        # expected to be in dependency order.
        from .lexer import PRIMITIVE_TYPE_NAMES

        parent = node.parent_name
        if parent in PRIMITIVE_TYPE_NAMES:
            self._class_decls[node.name] = parent
        elif parent not in self._class_decls:
            self.diagnostics.error(
                f"class `{node.name}` extends `{parent}`, which is not a "
                "primitive type and has not been declared earlier in this "
                "module. The MVP class system requires the extends-chain "
                "to bottom out at a primitive (vector / int / float / "
                "fuzzy / etc.) and does not support forward references",
                node.span,
                code="SUT0142",
                hint=f"declare `class {parent} extends <something> {{ }}` "
                     "before this declaration, or change `extends` to a "
                     "primitive type name",
            )
            # Still register the class so downstream references don't
            # double-error. Mark with a sentinel so we know the chain
            # is broken.
            self._class_decls[node.name] = parent
        else:
            # Walk transitively to confirm the chain ultimately reaches
            # a primitive (it should, by induction, but a malformed
            # earlier decl can poison the chain — we already errored on
            # it, so just treat this one as OK for downstream usage).
            self._class_decls[node.name] = parent

        # Walk methods declared inside the class body. Each is
        # validator-visited via the existing visit_MethodDecl, which
        # enforces the encapsulation rule (SUT0144) on the body.
        for m in node.methods:
            self.visit(m)
        # Walk loop function declarations declared inside the class
        # body (object loops). Same visitor path as top-level loop
        # function decls.
        for lf in node.loop_functions:
            self.visit(lf)
        # Walk field declarations. Each field's type position is
        # recorded for type-usage tracking; duplicate field names within
        # the same class are flagged.
        seen_fields: set[str] = set()
        for fd in node.fields:
            self._record_type_usage(fd.type_ref)
            if fd.name in seen_fields:
                self.diagnostics.error(
                    f"duplicate field `{fd.name}` in class `{node.name}` — "
                    "each field name in a class body must be unique",
                    fd.span,
                    code="SUT0145",
                    hint="rename the duplicate field, or remove the "
                         "redundant declaration",
                )
            seen_fields.add(fd.name)

    def visit_FunctionDecl(self, node: ast.FunctionDecl) -> None:
        self._check_modifier_conflict(node.modifiers, node.span)
        self._record_type_usage(node.return_type)
        for p in node.params:
            self._record_type_usage(p.type_ref)
        self._enter_function_scope()
        self.visit(node.body)
        self._exit_function_scope()

    def visit_MethodDecl(self, node: ast.MethodDecl) -> None:
        self._check_modifier_conflict(node.modifiers, node.span)
        self._record_type_usage(node.return_type)
        for p in node.params:
            self._record_type_usage(p.type_ref)
        self._enter_function_scope()
        # Encapsulation rule (SUT0144): walking the method body, any
        # bare Identifier whose name is in _file_scope_names but not in
        # _method_local_names is forbidden. Seed the local set with the
        # method's params; visit_VarDecl extends it as `var x = ...;`
        # decls are seen inside the body.
        saved_method_scope = self._method_local_names
        self._method_local_names = {p.name for p in node.params}
        try:
            self.visit(node.body)
        finally:
            self._method_local_names = saved_method_scope
        self._exit_function_scope()

    def visit_VarDecl(self, node: ast.VarDecl) -> None:
        if node.type_ref is not None:
            self._record_type_usage(node.type_ref)
        # `wait`-initialized declarations: register the name as a
        # pending wait (assigned-later promise) and do NOT descend into
        # the initializer — `WaitLiteral` is legal here, illegal
        # everywhere else, and the position check below catches the
        # everywhere-else case.
        if isinstance(node.initializer, ast.WaitLiteral):
            if self._method_local_names is not None:
                self._method_local_names.add(node.name)
            # Top-level `wait` has no enclosing function body to
            # assign in — reject it. Use the wait stack as the
            # in-function indicator (it's pushed by _enter_function_scope).
            if not getattr(self, "_wait_stack", []):
                self.diagnostics.error(
                    "`wait` is only valid inside a function or method "
                    "body — top-level declarations don't have a later "
                    "execution flow to assign in",
                    node.span,
                    code="SUT0133",
                    hint="move the declaration into a function body, "
                         "or initialize it with a concrete value at the "
                         "top level",
                )
                return
            if node.type_ref is None:
                # `var x = wait;` (inferred) has no type to default the
                # zero-of-type emission to. Require an explicit type.
                self.diagnostics.error(
                    "`var x = wait;` (inferred) is not allowed — "
                    "`wait` requires an explicit type so the compiler "
                    "knows the zero-of-type to allocate at the "
                    "declaration site",
                    node.span,
                    code="SUT0131",
                    hint="write `int x = wait;` (or another concrete type) "
                         "instead, or use `var x : TYPE;` for the same "
                         "uninitialized-slot semantics without the explicit "
                         "deferred-init signal",
                )
            else:
                self._wait_declared[node.name] = node.span
            return
        if node.initializer is not None:
            self.visit(node.initializer)
        # After the initializer is checked (so `var x = file_scope_name;`
        # inside a method body still flags the file-scope read), register
        # x as method-local so subsequent references inside the body
        # don't trip the encapsulation rule.
        if self._method_local_names is not None:
            self._method_local_names.add(node.name)
        # Fuzzy / trit literals live on the truth axis which the
        # spec defines over [-1, +1]. A literal outside that range is
        # almost always a mistake; warn (not error) so existing programs
        # don't break while the rule beds in.
        if (node.type_ref is not None
                and node.type_ref.name in ("fuzzy", "trit")
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

    def visit_Identifier(self, node: ast.Identifier) -> None:
        # Object-encapsulation rule (SUT0144): when we are inside a
        # method body (`_method_local_names` is non-None), any bare
        # identifier whose name is declared at file scope but is not
        # locally bound (param or var decl in the body) is forbidden.
        # Object methods are encapsulated within the class boundary —
        # static methods see the class as namespace; non-static
        # methods see `this` only. File-scope visibility is for free
        # functions only.
        # See planning/open-questions/function-taxonomy-and-closure.md.
        if self._method_local_names is None:
            return
        if node.name in self._method_local_names:
            return
        if node.name in self._file_scope_names:
            self.diagnostics.error(
                f"object methods cannot read file-scope name `{node.name}` — "
                "object methods are encapsulated within the class boundary "
                "(static methods see the class as namespace; non-static "
                "methods see `this` only). File-scope visibility is for "
                "free functions only.",
                node.span,
                code="SUT0144",
                hint=(
                    f"if `{node.name}` should be accessible to this method, "
                    "either make this a free function (`function` instead of "
                    f"`method`), or move `{node.name}` onto a class so the "
                    "method can reach it through `this.` or the class as a "
                    "namespace."
                ),
            )

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

    def visit_WaitLiteral(self, node: ast.WaitLiteral) -> None:
        # The only place `wait` is legal is the RHS of a var-decl
        # initializer, which `visit_VarDecl` handles by short-circuiting
        # before descending. If we reach the literal through any other
        # path, it's a position error.
        self.diagnostics.error(
            "`wait` is only valid as a var-decl initializer "
            "(`int i = wait;`); it cannot appear in other expression "
            "positions",
            node.span,
            code="SUT0130",
            hint="if you want a placeholder value, use a typed zero "
                 "(`0`, `unknown`, the zero vector); if you want explicit "
                 "deferred initialization, move `wait` to a declaration",
        )

    def visit_Assignment(self, node: ast.Assignment) -> None:
        # If this assigns to a wait-declared name, mark the wait as
        # satisfied. Single-name targets only — assignments to fields
        # / subscripts don't satisfy a wait on the variable itself.
        if (isinstance(node.target, ast.Identifier)
                and node.target.name in self._wait_declared):
            del self._wait_declared[node.target.name]
        self.visit(node.value)

    # ---- helpers ---------------------------------------------------

    def _enter_function_scope(self) -> None:
        # Save the outer wait-tracking state and start a fresh scope.
        # Function definitions can be nested (a method inside a class
        # inside another method-bearing decl, for instance), so we
        # need to restore on exit rather than just clearing.
        self._wait_stack = getattr(self, "_wait_stack", [])
        self._wait_stack.append(self._wait_declared)
        self._wait_declared = {}

    def _exit_function_scope(self) -> None:
        # Any wait-declared name still pending at function exit was
        # never assigned. Per the wait spec ("if it's not declared at
        # all, it throws an error"), that's an error.
        for name, span in self._wait_declared.items():
            self.diagnostics.error(
                f"variable `{name}` was declared with `wait` but never "
                "assigned in the function body — `wait` is a promise "
                "that an assignment will follow before the value is read",
                span,
                code="SUT0132",
                hint=f"add `{name} = <value>;` somewhere in this function, "
                     "or remove the `wait` initializer if you intended "
                     "the zero-of-type as the final value",
            )
        self._wait_declared = self._wait_stack.pop() if self._wait_stack else {}

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
            # `number` canonical; `scalar` deprecated alias.
            "number",
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
