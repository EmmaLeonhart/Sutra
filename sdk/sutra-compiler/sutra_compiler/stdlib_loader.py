"""Loader for the Sutra standard library.

Walks `sutra_compiler/stdlib/*.su` at compiler init, parses each file,
and returns a symbol table mapping function names to their parsed
`FunctionDecl` AST nodes. The inliner pass consumes this table — when
it sees a `Call(Identifier(name), args)` whose name is in the table,
it beta-reduces the function body into the caller's AST.

This is step 1 of the six-step pipeline in `stdlib/README.md` / STATUS.md.
Steps 2+ (inliner, unroll propagation, runtime-method deletion,
intrinsic mechanism, fusion pass) build on top of what this module
exposes.

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
from typing import Dict, List

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

    Methods (`method ...`) and top-level statements are ignored — the
    stdlib is function declarations only by design. A function whose
    body is commented out (the intrinsic-blocked stubs in the .su
    files) simply isn't present as a `FunctionDecl` and so doesn't
    appear in the returned table.
    """
    table: Dict[str, ast.FunctionDecl] = {}

    for fname in sorted(os.listdir(stdlib_dir)):
        if not fname.endswith(".su"):
            continue
        path = os.path.join(stdlib_dir, fname)
        module = _parse_stdlib_file(path)
        for item in module.items:
            if not isinstance(item, ast.FunctionDecl):
                continue
            if item.name in table:
                # Duplicate across files. Point at both sources so the
                # cleanup is obvious.
                existing = table[item.name]
                raise StdlibLoadError(
                    f"duplicate stdlib function {item.name!r}: "
                    f"declared at {path}:{item.span.start.line} and "
                    f"previously at {existing.span.start.line} in an "
                    f"earlier file. Each function should live in one "
                    f"stdlib file; see stdlib/README.md for the "
                    f"category split."
                )
            table[item.name] = item

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
