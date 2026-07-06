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
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Set

from . import ast_nodes as ast
from .lexer import PRIMITIVE_TYPE_NAMES

# Built-in generic container type names (the H1 finding's allowlist ∪ the
# primitive `map`/`tuple`, which are already primitives but named here too for
# clarity). These are types a program can name without declaring.
CONTAINER_TYPE_NAMES: Set[str] = {"list", "dict", "set", "array"}


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

    def is_known_type(self, name: str) -> bool:
        """Whether `name` resolves to a type this table can see. NOT yet
        diagnostic-grade (stdlib/cross-file types are added in a later rung)."""
        if not name:
            return False
        # Numeric type-args (e.g. the `512` in `BigInt<512>`) are values, not
        # unknown type names — never flag them.
        if name.isdigit():
            return True
        return (
            name in PRIMITIVE_TYPE_NAMES
            or name in CONTAINER_TYPE_NAMES
            or name in self.classes
            or name in self.type_params
        )

    def is_known_function(self, name: str) -> bool:
        """Whether `name` resolves to a file-scope function or method. NOT yet
        diagnostic-grade (builtins/intrinsics/first-class locals come later)."""
        return name in self.functions or name in self.methods


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
