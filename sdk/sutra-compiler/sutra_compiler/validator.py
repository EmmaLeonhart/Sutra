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
- SUT0151: a call to a spec'd substrate builtin the canonical backend
  can't lower yet (`snap` / `make_rotation` / `compile_prototypes` /
  `geometric_loop`) — warning, not an error; the source is valid. For
  `snap` it steers to `argmax_cosine`; the rest say there is no
  implemented substitute yet.

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
from .symbol_table import (
    SymbolTable,
    _walk,
    arg_type_conflict,
    build_symbol_table,
    infer_type,
    local_names,
    local_type_env,
)


# Spec'd builtins the canonical (PyTorch) substrate can't lower yet: they
# parse + validate as structure but are rejected at codegen. This is
# `codegen.py` `Codegen._UNSUPPORTED_BUILTINS` MINUS the `array_*` ops, which
# the PyTorch backend (the canonical target) DOES implement. Surfacing them as
# a validator warning (SUT0151) gives an editor / `sutrac check` an early
# signal before codegen. `snap` is the one with newcomer exposure (tutorial 03)
# and a real implemented alternative (argmax_cosine); the rest are not taught
# and have no drop-in substitute, so the diagnostic says so plainly rather than
# invent one. Kept in sync with codegen by hand (four names; codegen is the
# actual enforcer).
_UNIMPLEMENTED_SUBSTRATE_BUILTINS = {
    "snap": "use `argmax_cosine(query, [a, b, c])` to clean a vector up against "
            "an explicit codebook (the cleanup primitive the demos use today); "
            "keep `snap` for when the substrate circuit lands",
    "make_rotation": None,
    "compile_prototypes": None,
    "geometric_loop": None,
}


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
        # The module's symbol table (v0.2 name resolution). Built in
        # visit_module before the item walk; consulted by the unknown-type
        # diagnostic (SUT0200) in _record_type_usage. None until built.
        self._symbols: Optional[SymbolTable] = None
        # Union of every function/method's local names (params + body var/const),
        # used by the unknown-FUNCTION diagnostic to skip first-class function
        # values called by name. Over-inclusive across decls, which is safe: it
        # only ever SUPPRESSES a typo warning, and the warning itself already
        # fires solely on near-misses of known builtins.
        self._all_local_names: Set[str] = set()
        # name -> declared type for the params/typed-locals of the ENCLOSING
        # function/method, set on entry to its body and restored on exit. Powers
        # `infer_type` of an Identifier arg for the wrong-arg-type diagnostic. Kept
        # per-decl (not a file-wide union) so an identifier never picks up a
        # same-named local's type from a different function and mis-fires.
        self._local_type_env: dict = {}

    # ---- module ----------------------------------------------------

    def visit_module(self, module: ast.Module) -> None:
        # Build the symbol table up front so type/name checks during the
        # walk can resolve declarations from anywhere in the file.
        self._symbols = build_symbol_table(module)
        for node in _walk(module):
            if isinstance(node, (ast.FunctionDecl, ast.MethodDecl)):
                self._all_local_names |= local_names(node)
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
        saved_env = self._local_type_env
        self._local_type_env = local_type_env(node)
        # SUT0205: the names legally referenceable as bare identifiers
        # inside THIS function's body (params + var/const + foreach
        # vars). Per-decl, not the file-wide union, so a typo of another
        # function's local still warns.
        saved_fn_locals = getattr(self, "_fn_local_names", None)
        self._fn_local_names = local_names(node)
        try:
            self.visit(node.body)
        finally:
            self._local_type_env = saved_env
            self._fn_local_names = saved_fn_locals
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
        saved_env = self._local_type_env
        self._local_type_env = local_type_env(node)
        # SUT0205 scope for the method body: params + body locals +
        # `this` (implicit receiver) + the enclosing class's field
        # names are all legitimately referenceable.
        saved_fn_locals = getattr(self, "_fn_local_names", None)
        self._fn_local_names = local_names(node) | {"this"}
        try:
            self.visit(node.body)
        finally:
            self._method_local_names = saved_method_scope
            self._local_type_env = saved_env
            self._fn_local_names = saved_fn_locals
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
                    hint="use a `number` for unbounded values, or clamp the "
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
        self._check_unknown_variable(node)
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

    def visit_MemberAccess(self, node: ast.MemberAccess) -> None:
        # SUT0205 suppression: a bare-identifier RECEIVER is a namespace
        # or object access (`Math.PI`, `Promise.resolve(x)`, `s.item`) —
        # receiver typos surface as unknown-member behaviour, not as an
        # unknown VARIABLE, and namespace anchors (Promise, Math) are
        # legitimately undeclared. (`Math` is 2 edits from `main`, so
        # without this the did-you-mean mis-fires.) SUT0144 still sees
        # the identifier via the normal visit below.
        if isinstance(node.obj, ast.Identifier):
            suppressed = getattr(self, "_sut0205_suppressed_ids", None)
            if suppressed is None:
                suppressed = self._sut0205_suppressed_ids = set()
            suppressed.add(id(node.obj))
        self.visit(node.obj)

    def visit_LoopFunctionDecl(self, node: ast.LoopFunctionDecl) -> None:
        # Loop-function bodies reference their state params plus the
        # contextual `iterator` / `element`; scope them for SUT0205 the
        # same way function bodies are.
        saved_fn_locals = getattr(self, "_fn_local_names", None)
        self._fn_local_names = (
            {p.name for p in node.state_params} | {"iterator", "element"})
        try:
            self.visit(node.condition)
            self.visit(node.body)
        finally:
            self._fn_local_names = saved_fn_locals

    #: Contextual keywords that lex as identifiers but are bound by the
    #: language, not by a declaration.
    _CONTEXTUAL_IDENT_KEYWORDS = frozenset({
        "iterator",   # current tick inside loop-function bodies
        "element",    # current element inside foreach_loop bodies
        "this",       # method receiver
        "_",          # discard convention
    })

    def _check_unknown_variable(self, node: ast.Identifier) -> None:
        """SUT0205 (round-18 audit): a bare identifier EXPRESSION that
        resolves to nothing. Before this, `return totl + 1;` (typo of a
        local `total`) validated CLEAN and died at runtime as a raw
        Python NameError — variables were the one name class without a
        diagnostic (functions SUT0201, types SUT0200, arity SUT0202).
        Warning, not error (source is still valid v0.1 Sutra); callee
        positions are owned by SUT0201/0204 and suppressed here."""
        if self._symbols is None:
            return
        # Only inside a function/method body whose local set we track;
        # loop-function bodies and top-level initializers are out of
        # scope for v1 (conservative — never a false positive there).
        fn_locals = getattr(self, "_fn_local_names", None)
        if fn_locals is None:
            return
        if id(node) in getattr(self, "_sut0205_suppressed_ids", ()):
            return
        name = node.name
        if (name in fn_locals
                or name in self._file_scope_names
                or name in self._CONTEXTUAL_IDENT_KEYWORDS
                or name in self._symbols.classes
                or name in self._symbols.type_params
                or self._symbols.is_known_function(name)):
            return
        from .symbol_table import python_builtin_names, variable_typo_suggestion
        if name in python_builtin_names():
            # A bare (non-called) Python-builtin reference — rare; the
            # called form is SUT0204's. Stay silent to hold the
            # zero-false-positive bar.
            return
        # NEAR-MISS ONLY, mirroring SUT0201. The corpus is explicit that
        # undeclared free identifiers are LEGITIMATE Sutra ("the
        # `behaviors` value is whatever the runtime binds" —
        # 23_subscript_access.su), so a plain unresolved→warn rule is
        # wrong by design, not just noisy. Only the typo signal is safe:
        # a name within 2 edits of a DECLARED local/file-scope name.
        suggestion = variable_typo_suggestion(
            name, fn_locals | self._file_scope_names)
        if suggestion is None:
            return
        self.diagnostics.warning(
            f"unknown variable `{name}` — did you mean `{suggestion}`?",
            node.span,
            code="SUT0205",
            hint=f"`{name}` is not declared in this function or at "
                 f"file scope — the closest declared name is "
                 f"`{suggestion}`. An undeclared name reaches the "
                 "generated code as a bare Python name and fails at "
                 "runtime",
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
        # SUT0151: `snap` is a spec'd cleanup primitive whose attractor
        # circuit the substrate doesn't implement yet, so a program that
        # calls it parses + validates as a structure but is rejected at
        # codegen. Surface that early (a warning, not an error — the
        # source is valid Sutra) and point the newcomer at the cleanup
        # primitive the demos use today. Mirrors the codegen rejection in
        # codegen.py (Codegen._UNSUPPORTED_BUILTINS / tutorial 03).
        callee = node.callee
        if (isinstance(callee, ast.Identifier)
                and callee.name in _UNIMPLEMENTED_SUBSTRATE_BUILTINS):
            hint = _UNIMPLEMENTED_SUBSTRATE_BUILTINS[callee.name]
            self.diagnostics.warning(
                f"`{callee.name}` is not yet supported on the PyTorch substrate "
                "(the canonical compile target) — it is a spec'd primitive with "
                "no runtime lowering yet, so a program using it is rejected at "
                "codegen",
                node.span,
                code="SUT0151",
                hint=hint or ("no implemented substitute yet — it is a "
                              "forward-looking spec primitive, not a callable "
                              "operation on the current substrate"),
            )
        # SUT0201 (v0.2 name resolution): a bare call whose name is an unresolved
        # LIKELY TYPO of a known function. `unknown_function_suggestion` returns a
        # suggestion only when the name resolves nowhere (file-scope, builtins,
        # stdlib, first-class function locals, classes) AND is a near-miss of a
        # known lowercase function — so legitimate undeclared cross-file methods
        # (`Cosine`) and external producers (`network_lookup`) never warn. Warning,
        # not error: the source is still valid v0.1 Sutra.
        if isinstance(callee, ast.Identifier) and self._symbols is not None:
            # SUT0204 takes priority over the SUT0201 typo guess: a call to a
            # CALLABLE PYTHON BUILTIN that is not a Sutra name lowers to a bare
            # Python call and runs on the host (`print`, `str(len(...))`) — the
            # accidental escape hatch against the no-mid-computation-I/O identity.
            # Naming it plainly beats "did you mean <near Sutra fn>?". Warning (the
            # source still compiles); measured 0 valid-corpus false positives.
            if self._symbols.is_python_builtin_escape(callee.name, self._all_local_names):
                self.diagnostics.warning(
                    f"`{callee.name}` is a Python builtin, not a Sutra function — "
                    "calling it lowers to a host call, which Sutra does not allow "
                    "(no host execution mid-computation)",
                    callee.span,
                    code="SUT0204",
                    hint=f"there is no Sutra `{callee.name}`; use the Sutra "
                         "operation for what you need (see the stdlib), not the "
                         "host builtin",
                )
            else:
                suggestion = self._symbols.unknown_function_suggestion(
                    callee.name, self._all_local_names
                )
                if suggestion is not None:
                    self.diagnostics.warning(
                        f"unknown function `{callee.name}` — did you mean "
                        f"`{suggestion}`?",
                        callee.span,
                        code="SUT0201",
                        hint=f"`{callee.name}` resolves to no function, builtin, "
                             "stdlib call, or local — the closest known name is "
                             f"`{suggestion}`",
                    )
            # SUT0202 (v0.2 name resolution): arity check on a call to a
            # file-declared function. Sutra params are fixed-arity (no defaults
            # or varargs), so an arg-count mismatch is a real error surfaced as a
            # warning (source is still valid v0.1 Sutra). Only plain functions —
            # methods thread the implicit `this` separately; see `function_arity`.
            arity = self._symbols.function_arity(callee.name)
            if arity is not None and len(node.args) != arity:
                plural = "argument" if arity == 1 else "arguments"
                self.diagnostics.warning(
                    f"function `{callee.name}` expects {arity} {plural} but "
                    f"got {len(node.args)}",
                    callee.span,
                    code="SUT0202",
                    hint="check the call against the function's parameter list — "
                         "Sutra functions take a fixed number of arguments",
                )
            # SUT0203 (v0.2 name resolution): a definitively-wrong argument type.
            # Only the text-vs-concrete-non-text conflict fires (see
            # `arg_type_conflict`) — e.g. `similarity("cat","dog")` passing a raw
            # string where an embedding vector is required. Inference is
            # conservative (None = unknown = never a conflict), so this stays at 0
            # corpus false positives. Warning, not error.
            param_types = self._symbols.param_types_of(callee.name)
            if param_types:
                for i, arg in enumerate(node.args):
                    if i >= len(param_types):
                        break
                    pt = param_types[i]
                    at = infer_type(arg, self._symbols, self._local_type_env)
                    if arg_type_conflict(pt, at):
                        self.diagnostics.warning(
                            f"argument {i + 1} of `{callee.name}` has type "
                            f"`{at}` but a `{pt}` is expected",
                            getattr(arg, "span", callee.span),
                            code="SUT0203",
                            hint=(f"`{callee.name}` expects a `{pt}` here — if you "
                                  "meant to use text as a value, embed it first "
                                  "(`embed(\"...\")`) to get a vector"
                                  if pt == "vector" and at == "string"
                                  else f"convert the value to `{pt}` before the call"),
                        )
        for t in node.type_args:
            self._record_type_usage(t)
        # SUT0205 suppression: the callee position is owned by the
        # unknown-FUNCTION diagnostics (SUT0201/0204) — a bare-identifier
        # callee must not double-report as an unknown VARIABLE.
        if isinstance(node.callee, ast.Identifier):
            suppressed = getattr(self, "_sut0205_suppressed_ids", None)
            if suppressed is None:
                suppressed = self._sut0205_suppressed_ids = set()
            suppressed.add(id(node.callee))
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
            # `number` canonical (the `scalar` alias was removed 2026-06-23).
            "number",
            "vector", "matrix", "tuple", "string",
            "bool", "fuzzy", "void", "permutation", "map",
        }
        if type_ref.name not in PRIMITIVES:
            self._class_name_usages.add(type_ref.name)
        # SUT0200 (v0.2 name resolution): warn on a type name that cannot
        # resolve. Open-world scoped — `is_reportable_unknown_type` only
        # fires on a LOWERCASE unresolved name (a primitive/container typo
        # such as `vec`→`vector`), never on a PascalCase one (which may be a
        # sibling `.su` object file the single-file compile can't see). This
        # keeps the intentionally-open corpus files clean; the gate test
        # `test_full_valid_corpus_zero_reportable_false_positives` proves 0
        # false positives across the whole corpus.
        if self._symbols is not None and self._symbols.is_reportable_unknown_type(type_ref.name):
            self.diagnostics.warning(
                f"unknown type `{type_ref.name}` — it is not a primitive, a "
                "container, a declared class, or a known stdlib type",
                type_ref.span,
                code="SUT0200",
                hint="check the spelling against the built-in types (e.g. "
                     "`vector`, `number`, `string`, `fuzzy`), or declare the "
                     "type before using it",
            )
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
