"""Loader for the Sutra standard library.

Walks `sutra_compiler/stdlib/*.su` at compiler init, parses each file,
and returns a symbol table mapping function names to their parsed
`FunctionDecl` AST nodes. The inliner pass consumes this table: when
it sees a `Call(Identifier(name), args)` whose name is in the table,
it beta-reduces the function body into the caller's AST.

This is the first stage in the stdlib lowering pipeline. Subsequent
stages (the inliner pass itself, unroll propagation, runtime-method
deletion, intrinsic mechanism, fusion pass) build on the symbol
table this module produces.

The loader is deliberately simple:
  - No caching across processes. The parse is fast (7 files, ~600
    lines total today) and runs once per compiler instantiation.
  - No transitive resolution. If stdlib function A calls stdlib
    function B, the inliner handles the nesting by inlining A first
    and then running the pass again (or in one fixpoint pass) — this
    module just returns the raw declarations.
  - Duplicate names across files are a hard error. A function should
    live in exactly one .su file; see stdlib/README.md's category
    split.
  - Parse diagnostics from stdlib files are fatal — the stdlib is the
    compiler's own code, not user input. A broken stdlib is a compiler
    bug.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from . import ast_nodes as ast
from .lexer import Lexer
from .parser import Parser


STDLIB_DIR = os.path.join(os.path.dirname(__file__), "stdlib")


class StdlibLoadError(Exception):
    """Raised when the stdlib fails to load. Always a compiler bug —
    never a user error. Carries the file path and underlying reason
    so the stacktrace points at the real problem."""


def load_stdlib(stdlib_dir: str = STDLIB_DIR) -> Dict[str, ast.FunctionDecl]:
    """Return `{function_name → FunctionDecl}` for every function
    declaration in every `*.su` file under the stdlib directory.

    Both shapes are picked up:
      1. Top-level `function ...` and `intrinsic function ...;` —
         the original stdlib form. Goes into the table by its bare
         name (`log`, `bind`, etc.).
      2. Class-body static methods on stdlib classes (`class Math {
         static intrinsic method scalar log(scalar x); ... }`) — the
         post-2026-05-01 namespaced form. Goes into the table under
         BOTH the bare name (`log`) and the namespaced name
         (`Math.log`). The bare-name entry preserves backward
         compatibility for user code that still calls `log(x)`; the
         namespaced entry supports the future call shape
         `Math.log(x)`. Class-bodied static methods are repackaged
         as `FunctionDecl` so callers don't have to know which
         shape they came from.

    Method declarations on instances (non-static), top-level
    statements, and class bodies that aren't static-method bearing
    are ignored — the stdlib is callable-namespace-only by design.
    """
    table: Dict[str, ast.FunctionDecl] = {}

    def _add(name: str, decl: ast.FunctionDecl, path: str) -> None:
        if name in table:
            existing = table[name]
            raise StdlibLoadError(
                f"duplicate stdlib function {name!r}: "
                f"declared at {path}:{decl.span.start.line} and "
                f"previously at {existing.span.start.line} in an "
                f"earlier file. Each function should live in one "
                f"stdlib file; see stdlib/README.md for the "
                f"category split."
            )
        table[name] = decl

    for fname in sorted(os.listdir(stdlib_dir)):
        if not fname.endswith(".su"):
            continue
        path = os.path.join(stdlib_dir, fname)
        module = _parse_stdlib_file(path)
        for item in module.items:
            if isinstance(item, ast.FunctionDecl):
                _add(item.name, item, path)
            elif isinstance(item, ast.ClassDecl):
                for m in item.methods:
                    if (m.modifiers.is_static
                            and not m.is_operator
                            and not m.type_params):
                        # Repackage as a FunctionDecl so callers don't
                        # need to special-case class-bodied entries.
                        repackaged = ast.FunctionDecl(
                            modifiers=m.modifiers,
                            return_type=m.return_type,
                            name=m.name,
                            type_params=m.type_params,
                            params=m.params,
                            body=m.body,
                            is_operator=False,
                            is_intrinsic=m.is_intrinsic,
                            span=m.span,
                        )
                        # Bare-name entry (backward compat).
                        _add(m.name, repackaged, path)
                        # Namespaced entry (`Math.log`) — duplicates
                        # the AST node, which is fine because lookups
                        # don't mutate it.
                        _add(f"{item.name}.{m.name}", repackaged, path)

    return table


def _parse_stdlib_file(path: str) -> ast.Module:
    """Lex + parse one stdlib .su file. Fatal on any diagnostic."""
    with open(path, encoding="utf-8") as fp:
        src = fp.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    if lexer.diagnostics.has_errors():
        raise StdlibLoadError(
            f"{path}: stdlib lex errors — compiler bug:\n"
            + "\n".join(d.format() for d in lexer.diagnostics)
        )
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        raise StdlibLoadError(
            f"{path}: stdlib parse errors — compiler bug:\n"
            + "\n".join(d.format() for d in lexer.diagnostics)
        )
    return module


def stdlib_function_names(stdlib_dir: str = STDLIB_DIR) -> List[str]:
    """Names of every function declaration the stdlib contributes.

    Convenience wrapper around `load_stdlib` — returns just the names,
    sorted, for diagnostics and documentation. A runtime-methods
    removal pass can use this as the authoritative list of "stdlib
    callers exist; this runtime method is a candidate for deletion
    once the inliner is wired."
    """
    return sorted(load_stdlib(stdlib_dir).keys())


# Module-level cache of the intrinsic names — names declared via
# `intrinsic function ...;` in any stdlib file. The codegen uses this
# to route `Call(Identifier(name), args)` to `_VSA.<name>(args)`
# when name is an intrinsic (the runtime class implements it).
# Populated lazily on first access; safe because stdlib source is
# frozen for a given process.
_INTRINSIC_NAMES_CACHE: Optional[frozenset] = None


def intrinsic_names(stdlib_dir: str = STDLIB_DIR) -> frozenset:
    """Return the frozenset of intrinsic function names declared in
    the stdlib — the leaves the runtime must implement.

    Includes both bare-name and namespaced (`Math.log`) entries since
    the dual-registration pattern (load_stdlib) puts both into the
    table. Callers that need only one form can filter with `.`."""
    global _INTRINSIC_NAMES_CACHE
    if _INTRINSIC_NAMES_CACHE is None:
        table = load_stdlib(stdlib_dir)
        _INTRINSIC_NAMES_CACHE = frozenset(
            name for name, decl in table.items()
            if getattr(decl, "is_intrinsic", False)
        )
    return _INTRINSIC_NAMES_CACHE


# Per-class intrinsic-method registry, populated lazily. Maps
# `class_name -> frozenset of intrinsic method names`. Used by the
# codegen to dispatch `Tensor.MatrixMul(a, b)` to `_VSA.MatrixMul(a, b)`
# when the class is declared in stdlib (and therefore not in the
# user's module AST).
_STDLIB_CLASS_INTRINSICS_CACHE: Optional[Dict[str, frozenset]] = None


def stdlib_class_intrinsic_methods(
    stdlib_dir: str = STDLIB_DIR,
) -> Dict[str, frozenset]:
    """Return `{class_name: frozenset(method_names)}` for every
    static-intrinsic method declared inside a stdlib class body.

    Lets the codegen dispatch namespaced stdlib calls
    (`Tensor.MatrixMul(a, b)`) to the runtime alongside its existing
    user-class dispatch path.
    """
    global _STDLIB_CLASS_INTRINSICS_CACHE
    if _STDLIB_CLASS_INTRINSICS_CACHE is None:
        result: Dict[str, set] = {}
        for fname in sorted(os.listdir(stdlib_dir)):
            if not fname.endswith(".su"):
                continue
            path = os.path.join(stdlib_dir, fname)
            module = _parse_stdlib_file(path)
            for item in module.items:
                if not isinstance(item, ast.ClassDecl):
                    continue
                for m in item.methods:
                    if (m.is_intrinsic
                            and m.modifiers.is_static
                            and not m.is_operator
                            and not m.type_params):
                        result.setdefault(item.name, set()).add(m.name)
        _STDLIB_CLASS_INTRINSICS_CACHE = {
            cls: frozenset(names) for cls, names in result.items()
        }
    return _STDLIB_CLASS_INTRINSICS_CACHE


# Stdlib-class parent + operator-method registries — populated by
# the same single-walk pattern. Used by the codegen's binary-op
# dispatch to find class-bodied operator overloads defined inside
# stdlib classes (e.g. `String + String → string_concat`).
_STDLIB_CLASS_PARENTS_CACHE: Optional[Dict[str, str]] = None
_STDLIB_CLASS_OPERATORS_CACHE: Optional[Dict[str, Dict[str, ast.MethodDecl]]] = None


def _populate_class_meta(stdlib_dir: str) -> None:
    """Single pass that fills both _STDLIB_CLASS_PARENTS_CACHE and
    _STDLIB_CLASS_OPERATORS_CACHE. Cheaper than two walks of the
    stdlib tree."""
    global _STDLIB_CLASS_PARENTS_CACHE, _STDLIB_CLASS_OPERATORS_CACHE
    parents: Dict[str, str] = {}
    operators: Dict[str, Dict[str, ast.MethodDecl]] = {}
    for fname in sorted(os.listdir(stdlib_dir)):
        if not fname.endswith(".su"):
            continue
        path = os.path.join(stdlib_dir, fname)
        module = _parse_stdlib_file(path)
        for item in module.items:
            if not isinstance(item, ast.ClassDecl):
                continue
            if item.parent_name is not None:
                parents[item.name] = item.parent_name
            for m in item.methods:
                if m.is_operator and not m.type_params and not m.is_intrinsic:
                    # m.name is `operator+`, `operator==`, etc. (per
                    # the parser's `f"operator{op_name}"` convention).
                    op_sym = m.name[len("operator"):]
                    operators.setdefault(item.name, {})[op_sym] = m
    _STDLIB_CLASS_PARENTS_CACHE = parents
    _STDLIB_CLASS_OPERATORS_CACHE = operators


def stdlib_class_parents(stdlib_dir: str = STDLIB_DIR) -> Dict[str, str]:
    """Return `{class_name: parent_class_name}` for every stdlib
    class. Used by the codegen so an inheritance walk on a stdlib-
    declared class (e.g. `String → vector`) resolves correctly when
    the operator dispatch climbs the chain looking for overloads.
    """
    if _STDLIB_CLASS_PARENTS_CACHE is None:
        _populate_class_meta(stdlib_dir)
    return _STDLIB_CLASS_PARENTS_CACHE or {}


def stdlib_class_operators(
    stdlib_dir: str = STDLIB_DIR,
) -> Dict[str, Dict[str, ast.MethodDecl]]:
    """Return `{class_name: {op_symbol: MethodDecl}}` for every
    operator overload declared on a stdlib class. The codegen
    emits each one as a top-level Python function during prelude
    emission, and dispatches `a OP b` to it when either operand's
    type chain hits the class.
    """
    if _STDLIB_CLASS_OPERATORS_CACHE is None:
        _populate_class_meta(stdlib_dir)
    return _STDLIB_CLASS_OPERATORS_CACHE or {}
