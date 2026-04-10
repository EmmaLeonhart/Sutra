"""Akasha language compiler / validator.

This package implements the first pass of the Akasha SDK: a lexer,
parser, and syntactic validator for `.ak` source files.

Scope (v0.1):
    - Full tokenization of Akasha source (all comment forms, string
      interpolation, numeric literals, identifiers, operators).
    - Recursive-descent parser that recognizes the declaration and
      statement grammar described in planning/akasha-spec and
      akasha-syntax-decisions.md.
    - Structural validation: balanced brackets, semicolons where the
      grammar requires them, well-formed declarations and control flow.
    - A small set of rule checks that the syntax-decisions doc makes
      explicit (e.g. `var TYPE x` is forbidden, `if (...)` requires
      parentheses, a bare identifier cannot be used as a condition).

Out of scope for v0.1:
    - Type checking
    - Name resolution across files
    - Code generation / runtime lowering
    - Cross-file solution analysis

The compiler is intentionally liberal where the spec is still open
(anonymous functions, pipe operator, etc.) - it accepts the documented
forms and flags the clearly-forbidden ones.
"""

__version__ = "0.1.0"

from .diagnostics import Diagnostic, DiagnosticLevel, DiagnosticBag
from .lexer import Lexer, Token, TokenKind
from .parser import Parser
from .validator import validate_source, validate_file

__all__ = [
    "Diagnostic",
    "DiagnosticLevel",
    "DiagnosticBag",
    "Lexer",
    "Token",
    "TokenKind",
    "Parser",
    "validate_source",
    "validate_file",
    "__version__",
]
