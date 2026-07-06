"""Symbol table for Sutra name resolution — the v0.2 milestone (H1).

v0.1's validator deliberately skips name resolution, cross-declaration type
checking, and arity checking (see the `validator.py` docstring: those "land in
v0.2+ once we have a symbol table and cross-module resolution"). This module is
the FOUNDATION for that pass: it walks a parsed `Module` and collects the
file-scope declarations — user classes (with their methods/fields), top-level
functions, and top-level methods (a Sutra file acts as an object declaration, so
`MethodDecl` appears at module scope) — into a queryable `SymbolTable`.

Scope of THIS rung: COLLECTION ONLY. It emits no diagnostics and changes no
runtime behavior. Later rungs add local-scope tracking, cross-file / stdlib
resolution, and the unknown-type / unknown-function / arity diagnostics that
consult this table.

Deliberate non-wiring: `is_known_type` / `is_known_function` currently consult
only the primitive/container type names plus symbols collected from THIS module.
Stdlib builtins, intrinsics, and cross-file types are folded in when the
diagnostics turn on (a later rung). Until then a `False` result is NOT a
"definitely unknown" verdict — do not wire these into a diagnostic yet. In
particular `03_methods.su` legitimately references `Animal`/`Cat` types declared
in no file; resolving those without a false positive is a later rung's job.
"""
from __future__ import annotations

import dataclasses
import functools
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set

from . import ast_nodes as ast
from .lexer import PRIMITIVE_TYPE_NAMES

# Built-in generic container type names (the H1 finding's allowlist ∪ the
# primitive `map`/`tuple`, which are already primitives but named here too for
# clarity). These are types a program can name without declaring. Matched
# case-INSENSITIVELY: the corpus uses both `list<T>` and the PascalCase generic
# spelling `List<T>` / `Array<int,10>`, and the diagnostic must not false-positive
# on either (which spelling is canonical is a separate style/deprecation call —
# this only keeps the unknown-type diagnostic from lying).
CONTAINER_TYPE_NAMES: Set[str] = {"list", "dict", "set", "array"}

# First-class function-value types: a callable passed as a value is annotated
# `function` (e.g. `function int apply(function f, int v)` in 14_arrow_functions.su
# / higher_order_functions.su). MEASURED CORRECTION to rung 3's note: `function` is
# not ONLY the declaration keyword — it also appears in TYPE position as the type of
# a first-class function value, so it is a real known type. Spec:
# planning/open-questions/function-taxonomy-and-closure.md.
FIRST_CLASS_TYPE_NAMES: Set[str] = {"function"}


@functools.lru_cache(maxsize=1)
def extern_function_names() -> frozenset:
    """Global callable names the diagnostics must treat as known: substrate
    BUILTINS, stdlib functions, and intrinsics — in BOTH qualified
    (`Embedding.embed`) and bare (`embed`) forms. Over-inclusive on purpose: the
    v0.2 bar is ZERO false positives, so any name the compiler can actually resolve
    must never be flagged as unknown; typo detection (rung 5) is tuned separately.
    Cached — the stdlib load reads files once."""
    from .codegen_base import BUILTINS
    from .stdlib_loader import intrinsic_names, stdlib_function_names

    names: Set[str] = set(BUILTINS.keys())
    for n in list(stdlib_function_names()) + list(intrinsic_names()):
        names.add(n)
        if "." in n:
            names.add(n.rsplit(".", 1)[1])  # bare last component
    return frozenset(names)


@functools.lru_cache(maxsize=1)
def extern_signatures() -> dict:
    """`name -> (return_type, param_types)` for stdlib functions / intrinsics that
    carry real type annotations, under BOTH bare (`similarity`, `embed`) and
    qualified (`Embedding.embed`) names. Substrate BUILTINS that have no stdlib
    declaration (`bind`, `bundle`, `argmax_cosine`) are absent — their argument
    and result types are genuinely unknown, so callers must treat a missing entry
    as "cannot check", never as a conflict. Cached; the stdlib load reads files
    once. (`_type_name` is defined further down but resolved at call time.)"""
    from .stdlib_loader import load_stdlib

    sigs: dict = {}
    for name, decl in load_stdlib().items():
        rt = _type_name(getattr(decl, "return_type", None))
        pts = [_type_name(getattr(p, "type_ref", None))
               for p in getattr(decl, "params", []) or []]
        sigs[name] = (rt, pts)
    return sigs


@functools.lru_cache(maxsize=1)
def _known_bare_lowercase_functions() -> frozenset:
    """Known callable names in the function convention (lowercase, unqualified) —
    the candidate set the unknown-FUNCTION typo detector suggests from. PascalCase
    method names and qualified `Class.method` forms are excluded on purpose: they
    are the METHOD convention, and an unresolved PascalCase call may be a cross-file
    sibling method (open world), not a typo of a lowercase builtin."""
    return frozenset(n for n in extern_function_names()
                     if "." not in n and n[:1].islower())


def _levenshtein(a: str, b: str, cap: int) -> int:
    """Edit distance, short-circuiting once it provably exceeds `cap` (returns
    cap+1). Cheap: the corpus names are short and the cap is 2."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        best = cur[0]
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (a[i - 1] != b[j - 1]))
            best = min(best, cur[j])
        if best > cap:
            return cap + 1
        prev = cur
    return prev[len(b)]


def function_typo_suggestion(name: str, max_distance: int = 2):
    """If `name` is a likely misspelling of a known lowercase function, return that
    function name; else None. Only LOWERCASE names are considered — an unresolved
    PascalCase call is a method-convention name (possibly a cross-file sibling
    method), not a builtin typo. Measured 2026-07-06: real typos sit 1-2 edits from
    their target (`argmaxcosine`→`argmax_cosine`=1, `bundel`→`bundle`=2) while
    legitimately-undeclared externals sit far away (`matrix_rows`=7, `network_lookup`
    =9), so a max_distance of 2 separates the two with a wide margin."""
    if not name or not name[:1].islower():
        return None
    best, best_d = None, max_distance + 1
    for cand in _known_bare_lowercase_functions():
        d = _levenshtein(name, cand, max_distance)
        if d < best_d and d > 0:
            best, best_d = cand, d
    return best


@functools.lru_cache(maxsize=1)
def extern_type_names() -> frozenset:
    """Global type names the diagnostics must treat as known: stdlib class names
    plus measured primitive-type gaps. `float` is added here because it is a real
    first-class type (the parent of `JavaScriptFloat` in `stdlib_class_parents`) —
    but into THIS allowlist, NOT `lexer.PRIMITIVE_TYPE_NAMES`, leaving the canonical
    primitive set untouched (CLAUDE.md alias-hygiene). `function` is deliberately
    NOT added: the corpus scan (2026-07-06) shows it is the `function` keyword, not
    a type annotation — deferred until it is measured as a real type."""
    from .stdlib_loader import stdlib_class_parents

    names: Set[str] = set(stdlib_class_parents().keys())
    names.add("float")
    return frozenset(names)


@dataclass
class FunctionSig:
    """A callable's signature. `arity` is the declared parameter count (used by
    the later arity-checking rung). Top-level methods carry an implicit `this`
    that is NOT counted in `arity` — the desugared call threads it separately."""

    name: str
    arity: int
    type_params: List[str] = field(default_factory=list)
    is_intrinsic: bool = False
    is_operator: bool = False
    is_method: bool = False
    # Declared return-type name (the base name of the return TypeRef), or None
    # when not known. Consumed by expression type inference (a call's result type
    # is its callee's return_type) — see `infer_type`.
    return_type: Optional[str] = None
    # Declared parameter type names, positionally (base names; None for a param
    # with no resolvable type). Consumed by the wrong-arg-type diagnostic.
    param_types: List[Optional[str]] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    parent_name: str
    method_names: Set[str] = field(default_factory=set)
    field_names: Set[str] = field(default_factory=set)


@dataclass
class SymbolTable:
    """File-scope declarations collected from one `Module`."""

    functions: Dict[str, FunctionSig] = field(default_factory=dict)
    methods: Dict[str, FunctionSig] = field(default_factory=dict)
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    # Generic type parameters declared on file-scope functions/methods, in scope
    # for their signatures (e.g. the `T` in `function T id<T>(T x)`).
    type_params: Set[str] = field(default_factory=set)
    # Whether the queries also consult the global stdlib/builtins name sets
    # (rung 3). True makes `is_known_*` diagnostic-grade; set False for tests that
    # want to inspect only what THIS module declared.
    include_extern: bool = True
    # Resolution mode for the unknown-type diagnostic (rung "cross-file / external
    # types"). False = OPEN world (single-file compile): an unresolved PascalCase
    # name may be a not-yet-seen sibling class/file, so it is NOT reportable. True =
    # CLOSED world (the whole project's modules were unioned in via
    # `build_project_symbol_table`), so any unresolved name is genuinely unknown.
    closed_world: bool = False

    def is_known_type(self, name: str) -> bool:
        """Whether `name` resolves to a type: a primitive, container (case-
        insensitive), first-class `function`, a class declared in this module (or,
        closed-world, a sibling module), an in-scope generic param, or (rung 3) a
        stdlib class / measured primitive-type gap."""
        if not name:
            return False
        # Numeric type-args (e.g. the `512` in `BigInt<512>`) are values, not
        # unknown type names — never flag them.
        if name.isdigit():
            return True
        return (
            name in PRIMITIVE_TYPE_NAMES
            or name.lower() in CONTAINER_TYPE_NAMES
            or name in FIRST_CLASS_TYPE_NAMES
            or name in self.classes
            or name in self.type_params
            or (self.include_extern and name in extern_type_names())
        )

    def is_reportable_unknown_type(self, name: str) -> bool:
        """Whether the unknown-type diagnostic (rung 4) should FLAG `name`. A known
        type is never reported. For an UNRESOLVED name the answer depends on the
        world model, which rests on Sutra's naming convention (measured 2026-07-06:
        every primitive/container is lowercase — bar `Promise`, itself a stdlib
        class — and every declarable class is PascalCase):

        - Open world (single-file): only a LOWERCASE unresolved name is reportable —
          it can only be a typo of a primitive/container/stdlib type (`vec`→`vector`,
          the removed `scalar`), the exact H1 typo surface. A PascalCase unresolved
          name (`Animal`, `Cat` in 03_methods.su) may be an external sibling
          class/file and is deliberately NOT reported — this is what keeps the
          intentionally-open corpus files clean.
        - Closed world (full project unioned in): any unresolved name is genuinely
          unknown, so PascalCase names become reportable too."""
        if self.is_known_type(name) or not name or name.isdigit():
            return False
        if self.closed_world:
            return True
        return name[:1].islower()

    def is_known_function(self, name: str) -> bool:
        """Whether `name` resolves to a file-scope function/method or (rung 3) a
        substrate builtin, stdlib function, or intrinsic. Local first-class
        function values are checked separately via `local_names` (rung 2)."""
        return (
            name in self.functions
            or name in self.methods
            or (self.include_extern and name in extern_function_names())
        )

    def call_return_type(self, name: str) -> Optional[str]:
        """The result type of a call to `name`: a file-scope function/method's
        declared return type, else (extern) a stdlib function/intrinsic's return
        type. None when unknown — including for untyped builtins. Used by
        `infer_type` for `Call` nodes."""
        sig = self.functions.get(name) or self.methods.get(name)
        if sig is not None and sig.return_type:
            return sig.return_type
        if self.include_extern:
            entry = extern_signatures().get(name)
            if entry is not None:
                return entry[0]
        return None

    def param_types_of(self, name: str) -> Optional[List[Optional[str]]]:
        """Declared parameter types of `name` (positionally), or None when the
        callee is unknown or carries no type info (e.g. the untyped builtins
        `bind`/`bundle`/`argmax_cosine`). Used by the wrong-arg-type diagnostic —
        a None result means "cannot check", never "conflict"."""
        sig = self.functions.get(name) or self.methods.get(name)
        if sig is not None and sig.param_types:
            return sig.param_types
        if self.include_extern:
            entry = extern_signatures().get(name)
            if entry is not None:
                return entry[1]
        return None

    def function_arity(self, name: str):
        """The declared parameter count of a file-scope plain FUNCTION `name`, or
        None if `name` is not a file-declared function. Restricted to functions on
        purpose: Sutra params are fixed-arity (no defaults/varargs — checked against
        the AST), so `len(args) == arity` is exact for a function. METHODS are
        excluded here because their bare/desugared call forms thread the implicit
        `this` separately, which the pre-desugar AST does not make unambiguous;
        builtins/stdlib are excluded because the table does not carry their arity."""
        sig = self.functions.get(name)
        return sig.arity if sig is not None else None

    def unknown_function_suggestion(self, name: str, locals_in_scope=frozenset()):
        """For the unknown-FUNCTION diagnostic (rung 5): if a bare call to `name`
        is an unresolved LIKELY TYPO, return the suggested known function; else None.

        A call is left alone (returns None) when `name` resolves to a file-scope
        function/method, a substrate builtin / stdlib fn / intrinsic, a first-class
        function value in local scope (`local_names`), a class (constructor-style),
        or a generic type param. Only what remains is tested — and even then a
        warning is raised ONLY if the name is a near-miss of a known lowercase
        function (see `function_typo_suggestion`). This is deliberately NOT a
        plain unresolved→warn rule: the corpus is full of legitimate undeclared
        cross-file method calls (`Cosine`, `Bind`) and external producers
        (`network_lookup`, `matrix_rows`), so only the typo signal is safe at the
        zero-false-positive bar."""
        if (self.is_known_function(name)
                or name in locals_in_scope
                or name in self.classes
                or name in self.type_params):
            return None
        return function_typo_suggestion(name)


def _walk(node: ast.Node) -> Iterator[ast.Node]:
    """Yield `node` and every descendant ast Node (generic dataclass traversal).
    The AST is a tree (no cycles); non-Node fields — spans, strings, enums like
    `Modifiers` — are skipped."""
    yield node
    for f in dataclasses.fields(node):
        val = getattr(node, f.name, None)
        if isinstance(val, ast.Node):
            yield from _walk(val)
        elif isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, ast.Node):
                    yield from _walk(item)


def local_names(decl) -> Set[str]:
    """The local names in scope inside a function's/method's body: its parameter
    names plus every `var`/`const` declared anywhere in the body (nested blocks
    included). These are legitimately referenceable — and, if function-valued
    (an arrow desugared to a hoisted function held in a local), legitimately
    CALLABLE — so the later unknown-name / unknown-function diagnostics must treat
    them as known. This is the local half of name resolution (rung 2); it does not
    yet model shadowing or block-level lifetime, which the diagnostics don't need
    to avoid false positives (a name in scope anywhere in the body is not unknown)."""
    names: Set[str] = set()
    for p in getattr(decl, "params", []) or []:
        names.add(p.name)
    body = getattr(decl, "body", None)
    if isinstance(body, ast.Node):
        for n in _walk(body):
            if isinstance(n, ast.VarDecl):
                names.add(n.name)
    return names


def _type_name(type_ref) -> Optional[str]:
    """The base name of a TypeRef, or None if absent (e.g. a void/omitted type)."""
    return getattr(type_ref, "name", None) if type_ref is not None else None


def local_type_env(decl) -> Dict[str, str]:
    """name -> declared type for the params and explicitly-typed var/const decls in
    a function/method body. The type half of `local_names`: it powers `infer_type`
    of an `Identifier`. CONSERVATIVE — only names with an explicit type annotation
    are recorded; a `var x = <expr>` with no annotation is omitted (its type would
    need initializer inference, which we do not do here) so inference returns None
    for it rather than guessing."""
    env: Dict[str, str] = {}
    for p in getattr(decl, "params", []) or []:
        t = _type_name(getattr(p, "type_ref", None))
        if t:
            env[p.name] = t
    body = getattr(decl, "body", None)
    if isinstance(body, ast.Node):
        for n in _walk(body):
            if isinstance(n, ast.VarDecl):
                t = _type_name(getattr(n, "type_ref", None)) or _type_name(getattr(n, "var_type", None))
                if t:
                    env[n.name] = t
    return env


# Literal AST node -> Sutra type name. Only the unambiguous literals; anything
# needing context (ArrayLiteral element type, operator result type) is left to the
# caller / returns None, keeping inference conservative.
_LITERAL_TYPES = {
    "StringLiteral": "string",
    "InterpolatedString": "string",
    "CharLiteral": "char",
    "BoolLiteral": "bool",
    "IntLiteral": "int",
    "FloatLiteral": "number",
    "ComplexLiteral": "complex",
    "ImaginaryLiteral": "complex",
}


def infer_type(expr, symbols: "SymbolTable", local_types: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Best-effort, CONSERVATIVE type of an expression: the Sutra type name, or
    None when it cannot be determined. None is always safe — the diagnostics only
    act on a definitively-inferred type, never on None — so unknown constructs
    (operators, array literals, member access, un-annotated locals) return None
    rather than a guess. Handled precisely: every unambiguous literal, `embed(...)`
    (→vector), a cast (→its target type), a parenthesised inner expr, an identifier
    (→its declared local/param type), and a call (→its callee's return type)."""
    local_types = local_types or {}
    kind = type(expr).__name__
    if kind in _LITERAL_TYPES:
        return _LITERAL_TYPES[kind]
    if isinstance(expr, ast.EmbedExpr):
        return "vector"
    if isinstance(expr, (ast.CastExpr, ast.UnsafeCastExpr)):
        return _type_name(getattr(expr, "target_type", None))
    if isinstance(expr, ast.Parenthesized):
        return infer_type(expr.inner, symbols, local_types)
    if isinstance(expr, ast.Identifier):
        return local_types.get(expr.name)
    if isinstance(expr, ast.Call):
        callee = expr.callee
        if isinstance(callee, ast.Identifier):
            return symbols.call_return_type(callee.name)
        if isinstance(callee, ast.MemberAccess):
            base = callee.obj
            if isinstance(base, ast.Identifier):
                return (symbols.call_return_type(f"{base.name}.{callee.member}")
                        or symbols.call_return_type(callee.member))
            return symbols.call_return_type(callee.member)
    return None


def build_symbol_table(module: ast.Module) -> SymbolTable:
    """Collect file-scope declarations from a parsed module. Pure; no diagnostics."""
    table = SymbolTable()
    for item in module.items:
        if isinstance(item, ast.FunctionDecl):
            table.functions[item.name] = FunctionSig(
                name=item.name,
                arity=len(item.params),
                type_params=list(item.type_params),
                is_intrinsic=item.is_intrinsic,
                is_operator=item.is_operator,
                return_type=_type_name(item.return_type),
                param_types=[_type_name(p.type_ref) for p in item.params],
            )
            table.type_params.update(item.type_params)
        elif isinstance(item, ast.MethodDecl):
            table.methods[item.name] = FunctionSig(
                name=item.name,
                arity=len(item.params),
                type_params=list(item.type_params),
                is_intrinsic=item.is_intrinsic,
                is_operator=item.is_operator,
                is_method=True,
                return_type=_type_name(item.return_type),
                param_types=[_type_name(p.type_ref) for p in item.params],
            )
            table.type_params.update(item.type_params)
        elif isinstance(item, ast.ClassDecl):
            info = ClassInfo(name=item.name, parent_name=item.parent_name)
            for m in item.methods:
                info.method_names.add(m.name)
            for fld in item.fields:
                info.field_names.add(fld.name)
            table.classes[item.name] = info
    return table


def build_project_symbol_table(modules, file_type_names=None) -> SymbolTable:
    """Union the file-scope declarations of several modules into one CLOSED-world
    table — the cross-file half of external-type handling. A Sutra file acts as an
    object declaration, so besides each module's declared classes/functions/methods
    the caller may pass `file_type_names` (e.g. the sibling `.su` basenames) which
    become known class types too: that is how a reference like `Cat` resolves to a
    sibling `Cat.su` when the whole project is present. The result has
    `closed_world=True`, so `is_reportable_unknown_type` will flag any name that
    still does not resolve — including PascalCase typos an open single-file compile
    cannot safely judge."""
    table = SymbolTable(closed_world=True)
    for m in modules:
        sub = build_symbol_table(m)
        table.functions.update(sub.functions)
        table.methods.update(sub.methods)
        table.classes.update(sub.classes)
        table.type_params.update(sub.type_params)
    for fname in file_type_names or []:
        table.classes.setdefault(fname, ClassInfo(name=fname, parent_name=""))
    return table
