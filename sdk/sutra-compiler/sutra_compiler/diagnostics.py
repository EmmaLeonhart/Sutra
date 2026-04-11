"""Diagnostics for the Sutra compiler.

A `Diagnostic` is a single error/warning/info message with enough
position information that editors (and humans) can point straight at
the offending character. Line and column are 1-based in the output,
like every other compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DiagnosticLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class SourcePosition:
    """A position in a source file. Line and column are 1-based."""

    line: int
    column: int
    offset: int  # absolute byte offset, 0-based

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class SourceSpan:
    """A half-open range [start, end) in a source file."""

    start: SourcePosition
    end: SourcePosition

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


@dataclass
class Diagnostic:
    """A single compiler diagnostic."""

    level: DiagnosticLevel
    message: str
    span: SourceSpan
    file: Optional[str] = None
    code: Optional[str] = None  # e.g. "SUT0001"
    hint: Optional[str] = None

    def format(self, *, color: bool = False) -> str:
        """Human-readable one-line form: path:line:col: level: message."""
        file = self.file or "<input>"
        pos = self.span.start
        level = self.level.value
        code = f" [{self.code}]" if self.code else ""
        out = f"{file}:{pos.line}:{pos.column}: {level}: {self.message}{code}"
        if self.hint:
            out += f"\n  hint: {self.hint}"
        return out


class DiagnosticBag:
    """Collects diagnostics produced during a compilation.

    The bag never raises; the compiler keeps going after errors so that
    a single bad token doesn't hide the rest of the file from the
    validator. Callers decide at the end whether any errors were
    reported.
    """

    def __init__(self, file: Optional[str] = None) -> None:
        self.file = file
        self._items: List[Diagnostic] = []

    # ---- basic operations -------------------------------------------------

    def add(self, diag: Diagnostic) -> None:
        if diag.file is None:
            diag.file = self.file
        self._items.append(diag)

    def error(
        self,
        message: str,
        span: SourceSpan,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
    ) -> None:
        self.add(
            Diagnostic(
                level=DiagnosticLevel.ERROR,
                message=message,
                span=span,
                code=code,
                hint=hint,
            )
        )

    def warning(
        self,
        message: str,
        span: SourceSpan,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
    ) -> None:
        self.add(
            Diagnostic(
                level=DiagnosticLevel.WARNING,
                message=message,
                span=span,
                code=code,
                hint=hint,
            )
        )

    # ---- queries ----------------------------------------------------------

    @property
    def items(self) -> List[Diagnostic]:
        return list(self._items)

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self._items if d.level is DiagnosticLevel.ERROR]

    @property
    def warnings(self) -> List[Diagnostic]:
        return [d for d in self._items if d.level is DiagnosticLevel.WARNING]

    def has_errors(self) -> bool:
        return any(d.level is DiagnosticLevel.ERROR for d in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)
