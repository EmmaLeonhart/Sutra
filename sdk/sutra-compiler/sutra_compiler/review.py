"""Review mode — step-by-step trace of compilation stages.

Exposes `review_file(path)` which compiles a .su file and prints each
stage of the pipeline in human-readable form:

  1. Source                   (the .su input)
  2. Parsed AST               (pseudo-Sutra pretty-print of the AST)
  3. After stdlib inlining    (inliner expansion)
  4. During simplification    (each rewrite rule that fired + what it
                               turned the expression into)
  5. Simplified AST           (final form after all rewrites)
  6. Emitted Python           (what the codegen produced)

Intended use:

    python -m sutra_compiler --review examples/analogy.su

Works as a teaching and debugging aid. If a program is doing something
unexpected at runtime, the review output shows exactly which source-
level expression became what pre-runtime form, and which rewrites
contributed along the way.
"""
from __future__ import annotations

import os
import sys
from typing import List, Tuple

from . import ast_nodes as ast
from .lexer import Lexer
from .parser import Parser
from .simplify import set_trace_callback, simplify_module
from .inliner import inline_stdlib_calls


# ---------------------------------------------------------------------
# Pretty-printer — emit a pseudo-Sutra-source form of the AST
# ---------------------------------------------------------------------


def pretty_expr(node) -> str:
    """Render an expression AST node as Sutra-looking source text.

    Not a full source round-trip (spans / types are lost) but readable
    enough for the review-mode trace. Literals render as their values;
    calls render as `name(arg, arg)`; binary ops render as `lhs op rhs`.
    """
    if node is None:
        return "<none>"
    if isinstance(node, ast.Identifier):
        return node.name
    if isinstance(node, ast.IntLiteral):
        return str(node.value)
    if isinstance(node, ast.FloatLiteral):
        return f"{node.value!r}"
    if isinstance(node, ast.BoolLiteral):
        return "true" if node.value else "false"
    if isinstance(node, ast.StringLiteral):
        return f'"{node.value}"'
    if isinstance(node, ast.CharLiteral):
        return f"'{chr(node.value)}'"
    if isinstance(node, ast.ImaginaryLiteral):
        return f"{node.value}i"
    if isinstance(node, ast.ComplexLiteral):
        return f"({node.re} + {node.im}i)"
    if hasattr(ast, "UnknownLiteral") and isinstance(node, ast.UnknownLiteral):
        return "unknown"
    if isinstance(node, ast.Parenthesized):
        return f"({pretty_expr(node.inner)})"
    if isinstance(node, ast.UnaryOp):
        return f"{node.op}{pretty_expr(node.operand)}"
    if isinstance(node, ast.BinaryOp):
        return f"{pretty_expr(node.left)} {node.op} {pretty_expr(node.right)}"
    if isinstance(node, ast.Call):
        callee = pretty_expr(node.callee) if not isinstance(node.callee, ast.Identifier) else node.callee.name
        args = ", ".join(pretty_expr(a) for a in node.args)
        return f"{callee}({args})"
    if isinstance(node, ast.ArrayLiteral):
        return "[" + ", ".join(pretty_expr(e) for e in node.elements) + "]"
    if isinstance(node, ast.Subscript):
        return f"{pretty_expr(node.target)}[{pretty_expr(node.index)}]"
    if isinstance(node, ast.MemberAccess):
        return f"{pretty_expr(node.obj)}.{node.member}"
    if isinstance(node, ast.EmbedExpr):
        return f"embed({pretty_expr(node.expr)})"
    if isinstance(node, ast.DefuzzyExpr):
        return f"defuzzy({pretty_expr(node.expr)})"
    # Fallback: the raw dataclass repr.
    return f"<{type(node).__name__}>"


def pretty_stmt(stmt, indent: int = 0) -> List[str]:
    """Render a statement as a list of lines."""
    pad = "  " * indent
    if isinstance(stmt, ast.VarDecl):
        type_str = f"{stmt.type_ref.name} " if stmt.type_ref else "var "
        init = f" = {pretty_expr(stmt.initializer)}" if stmt.initializer else ""
        return [f"{pad}{type_str}{stmt.name}{init};"]
    if isinstance(stmt, ast.ReturnStmt):
        return [f"{pad}return {pretty_expr(stmt.value)};"]
    if isinstance(stmt, ast.ExprStmt):
        return [f"{pad}{pretty_expr(stmt.expr)};"]
    if isinstance(stmt, ast.FunctionDecl):
        ret = stmt.return_type.name if stmt.return_type else "void"
        params = ", ".join(
            f"{p.type_ref.name if p.type_ref else 'var'} {p.name}"
            for p in (stmt.params or [])
        )
        lines = [f"{pad}function {ret} {stmt.name}({params}) {{"]
        for s in stmt.body.statements:
            lines.extend(pretty_stmt(s, indent + 1))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(stmt, ast.IfStmt):
        lines = [f"{pad}if ({pretty_expr(stmt.condition)}) {{"]
        for s in stmt.then_branch.statements:
            lines.extend(pretty_stmt(s, indent + 1))
        lines.append(f"{pad}}}")
        return lines
    return [f"{pad}<{type(stmt).__name__}>"]


def pretty_module(module: ast.Module) -> str:
    """Render an entire module as a string."""
    lines: List[str] = []
    for item in module.items:
        lines.extend(pretty_stmt(item))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Trace collector — attach to simplify.set_trace_callback
# ---------------------------------------------------------------------


class _TraceCollector:
    def __init__(self):
        self.events: List[Tuple[str, str, str]] = []

    def __call__(self, rule: str, before, after) -> None:
        self.events.append(
            (rule, pretty_expr(before), pretty_expr(after))
        )


# ---------------------------------------------------------------------
# Review entry point
# ---------------------------------------------------------------------


RULE_BAR = "=" * 72
SUB_BAR = "-" * 72


def _heading(title: str) -> str:
    return f"\n{RULE_BAR}\n{title}\n{RULE_BAR}"


def review_file(path: str) -> int:
    """Compile `path` through the pipeline, printing each stage.

    Returns 0 on success, 1 if any stage raised.
    """
    if not os.path.exists(path):
        print(f"{path}: error: file not found", file=sys.stderr)
        return 1

    with open(path, encoding="utf-8") as f:
        src = f.read()

    # --- 1. Source ---
    print(_heading(f"1. Source  ({path})"))
    print(src)

    # --- 2. Parse ---
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.errors:
        print("\nParse errors:")
        for d in lexer.diagnostics.errors:
            print(f"  {d.format()}")
        return 1

    print(_heading("2. Parsed AST  (pseudo-Sutra pretty-print)"))
    print(pretty_module(module))

    # --- 3. Inline stdlib ---
    try:
        inline_stdlib_calls(module)
    except Exception as e:
        print(f"\nInliner error: {type(e).__name__}: {e}")
        return 1

    print(_heading("3. After stdlib inlining"))
    print(pretty_module(module))

    # --- 4 + 5. Simplification with per-rule trace ---
    collector = _TraceCollector()
    set_trace_callback(collector)
    try:
        simplify_module(module)
    finally:
        set_trace_callback(None)

    print(_heading("4. Simplification trace  (rewrites that fired)"))
    if not collector.events:
        print("  (no rewrites fired)")
    else:
        print(f"  {len(collector.events)} rewrite(s) fired:\n")
        for i, (rule, before, after) in enumerate(collector.events, 1):
            print(f"  [{i:2}] {rule}")
            print(f"       before: {before}")
            print(f"       after:  {after}")
            print()

    print(_heading("5. Simplified AST"))
    print(pretty_module(module))

    # --- 6. Emitted Python ---
    try:
        from .codegen import translate_module
    except ImportError as e:
        print(f"\nCodegen import failed: {e}")
        return 1
    try:
        py_src = translate_module(module)
    except Exception as e:
        print(f"\nCodegen error: {type(e).__name__}: {e}")
        return 1

    print(_heading("6. Emitted Python  (first 80 lines)"))
    lines = py_src.splitlines()
    for line in lines[:80]:
        print(line)
    if len(lines) > 80:
        print(f"... ({len(lines) - 80} more lines omitted)")

    print(_heading("Review complete"))
    print(f"  source:          {len(src)} chars")
    print(f"  parsed items:    {len(module.items)}")
    print(f"  rewrites fired:  {len(collector.events)}")
    print(f"  emitted Python:  {len(lines)} lines")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m sutra_compiler.review FILE.su", file=sys.stderr)
        sys.exit(2)
    sys.exit(review_file(sys.argv[1]))
