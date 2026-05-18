"""Lexer for the Sutra language.

Produces a flat list of tokens from source text. The lexer is
intentionally forgiving: unknown characters become `TokenKind.UNKNOWN`
with a diagnostic attached rather than aborting, so the parser still
sees a usable stream.

Language features handled:

- Comment forms: `//` line, `/* */` block, `///` doc line, `#` line.
  Block comments are NOT nested (matches C).
- String literals: regular `"..."` and interpolated `$"... {expr} ..."`.
  Interpolated strings become a flat sequence:
      STRING_INTERP_START  STRING_LIT_CHUNK  INTERP_OPEN
      ...tokens for expr...
      INTERP_CLOSE  STRING_LIT_CHUNK  STRING_INTERP_END
  That lets the parser walk inside `{...}` with the full expression
  grammar and still know we're inside a string.
- Numeric literals: integer and decimal; no hex/exponent yet.
- Identifiers and keywords.
- Multi-character operators: `==`, `!=`, `<=`, `>=`, `&&`, `||`,
  `++`, `--`, `+=`, `-=`, `*=`, `/=`, `=>`, `->`, `::`, `|>`.
  (`|>` is lexed so we can flag it explicitly; the spec forbids it.)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from .diagnostics import (
    DiagnosticBag,
    SourcePosition,
    SourceSpan,
)


class TokenKind(Enum):
    # ---- structural ----
    LBRACE = auto()          # {
    RBRACE = auto()          # }
    LPAREN = auto()          # (
    RPAREN = auto()          # )
    LBRACKET = auto()        # [
    RBRACKET = auto()        # ]
    SEMICOLON = auto()       # ;
    COMMA = auto()            # ,
    DOT = auto()              # .
    COLON = auto()            # :

    # ---- operators ----
    PLUS = auto()             # +
    MINUS = auto()            # -
    STAR = auto()             # *
    SLASH = auto()            # /
    PERCENT = auto()          # %
    BANG = auto()             # !
    TILDE = auto()            # ~ (alternative NOT)
    QUESTION = auto()         # ?
    ASSIGN = auto()           # =
    EQ = auto()               # ==
    NEQ = auto()              # !=
    LT = auto()               # <
    GT = auto()               # >
    LE = auto()               # <=
    GE = auto()               # >=
    AND = auto()              # &&
    OR = auto()               # ||
    BIT_AND = auto()          # &
    BIT_OR = auto()           # |
    BIT_XOR = auto()          # ^
    PLUS_PLUS = auto()        # ++
    MINUS_MINUS = auto()      # --
    PLUS_ASSIGN = auto()      # +=
    MINUS_ASSIGN = auto()     # -=
    STAR_ASSIGN = auto()      # *=
    SLASH_ASSIGN = auto()     # /=
    ARROW = auto()            # ->
    FAT_ARROW = auto()        # =>
    PIPE_FORWARD = auto()     # |>  (spec says: not supported)
    DOUBLE_COLON = auto()     # ::

    # ---- literals ----
    INT_LIT = auto()
    FLOAT_LIT = auto()
    IMAG_LIT = auto()            # imaginary-unit suffix: 5i, 3.14i
    CHAR_LIT = auto()            # single-quoted char literal 'a'
    STRING_LIT = auto()          # plain "..." literal
    STRING_INTERP_START = auto()  # opening $" of interpolated string
    STRING_INTERP_END = auto()    # closing " of interpolated string
    STRING_LIT_CHUNK = auto()     # literal text chunk inside interp string
    INTERP_OPEN = auto()          # { inside interpolated string
    INTERP_CLOSE = auto()         # } inside interpolated string
    TRUE = auto()
    FALSE = auto()
    KW_UNKNOWN = auto()         # the `unknown` literal — truth-axis neutral
    KW_WAIT = auto()            # the `wait` literal — explicit deferred init

    # ---- identifiers / keywords ----
    IDENT = auto()
    KW_FUNCTION = auto()
    KW_METHOD = auto()
    KW_STATIC = auto()
    KW_PUBLIC = auto()
    KW_PRIVATE = auto()
    KW_VAR = auto()
    KW_CONST = auto()
    KW_ROLE = auto()
    KW_RETURN = auto()
    KW_IF = auto()
    KW_ELSE = auto()
    KW_WHILE = auto()
    KW_FOR = auto()
    KW_FOREACH = auto()
    KW_IN = auto()
    KW_DO = auto()
    KW_LOOP = auto()
    KW_DO_WHILE = auto()
    KW_WHILE_LOOP = auto()
    KW_ITERATIVE_LOOP = auto()
    KW_FOREACH_LOOP = auto()
    # `pass <exprs>;` — tail-recursive yield in a loop body. Required to
    # provide one expression per state parameter; the condition is
    # re-evaluated automatically against the new state. The `replace`
    # keyword takes the place of an expression to mean "keep this
    # parameter's input value across the recurrence."
    KW_PASS = auto()
    KW_REPLACE = auto()
    # Note: `element` (the foreach_loop's current-array-value reference)
    # and `iterator` (the iterative_loop's tick number) are CONTEXTUAL
    # — they parse as plain IDENT tokens and the codegen recognizes
    # them specially in the identifier translation path. They are not
    # hard keywords so they don't break unrelated `element` / `iterator`
    # variable names elsewhere in user code.
    KW_AS = auto()
    KW_TRY = auto()
    KW_CATCH = auto()
    KW_THIS = auto()
    KW_OPERATOR = auto()
    KW_NEW = auto()
    KW_IMPLICIT = auto()
    # `intrinsic` — declares a function whose body lives in the runtime
    # (no Sutra-level body). Used by stdlib files for leaf primitives
    # like `dot`, `sqrt`, `tanh`, `make_truth`, `embed` that can't be
    # expressed in Sutra arithmetic. Calls compile to `_VSA.<name>(...)`.
    KW_INTRINSIC = auto()
    # Logical-connective keyword operators. Spelled case-insensitively
    # (the lexer lowercases lexemes before matching, only for these).
    # Map to the same stdlib functions the symbolic forms (`!`, `&&`,
    # `||`, etc.) lower to:
    #   not / NOT  -> logical_not    (symbolic: ! ~)
    #   and / AND  -> logical_and    (symbolic: && &)
    #   nand       -> logical_nand
    #   or  / OR   -> logical_or     (symbolic: || |)
    #   xor        -> logical_xor
    #   xnor / iff -> logical_xnor
    KW_LOGICAL_NOT = auto()
    KW_LOGICAL_AND = auto()
    KW_LOGICAL_OR = auto()
    KW_LOGICAL_NAND = auto()
    KW_LOGICAL_XOR = auto()
    KW_LOGICAL_XNOR = auto()
    # `class Name extends Parent { ... }` — user-defined ontology
    # class. MVP scope is empty bodies + single inheritance; the
    # extends-chain must bottom out at a primitive class. See
    # docs/ontology.md.
    KW_CLASS = auto()
    KW_EXTENDS = auto()
    KW_SLOT = auto()
    # `field T name;` — declares a named tag-along variable on a class
    # instance. At runtime the field is stored via the same axon
    # rotation-binding machinery that backs `Axon.add` / `Axon.item`;
    # the field declaration is the schema. See docs/ontology.md.
    KW_FIELD = auto()
    # `async function ...` and `await expr` — surface vocabulary for
    # promises and await/async. Both are syntactic sugar over the
    # tail-recursive loop machinery (`while_loop`, `do_while`); see
    # planning/sutra-spec/promises.md for the lowering. `async` is a
    # function-decl modifier; `await` is an expression operator.
    # `Promise<T>` is a parameterised type-ref name, listed in
    # PRIMITIVE_TYPE_NAMES below — not a hard keyword.
    KW_ASYNC = auto()
    KW_AWAIT = auto()

    # ---- special ----
    EOF = auto()
    UNKNOWN = auto()


# Keywords that have a dedicated TokenKind.
KEYWORDS = {
    "function": TokenKind.KW_FUNCTION,
    "method": TokenKind.KW_METHOD,
    "static": TokenKind.KW_STATIC,
    "public": TokenKind.KW_PUBLIC,
    "private": TokenKind.KW_PRIVATE,
    "var": TokenKind.KW_VAR,
    "const": TokenKind.KW_CONST,
    # "role" is a CONTEXTUAL keyword — not in the lexer's hard-keyword
    # map so `vector role` parameters and `role` identifiers keep
    # parsing. The parser recognizes `role X = ...;` at statement-start
    # by checking the IDENT lexeme + lookahead. See parser.py.
    "return": TokenKind.KW_RETURN,
    "if": TokenKind.KW_IF,
    "else": TokenKind.KW_ELSE,
    "while": TokenKind.KW_WHILE,
    "for": TokenKind.KW_FOR,
    "foreach": TokenKind.KW_FOREACH,
    "in": TokenKind.KW_IN,
    "do": TokenKind.KW_DO,
    "loop": TokenKind.KW_LOOP,
    "do_while": TokenKind.KW_DO_WHILE,
    "while_loop": TokenKind.KW_WHILE_LOOP,
    "iterative_loop": TokenKind.KW_ITERATIVE_LOOP,
    "foreach_loop": TokenKind.KW_FOREACH_LOOP,
    "pass": TokenKind.KW_PASS,
    "replace": TokenKind.KW_REPLACE,
    "as": TokenKind.KW_AS,
    "try": TokenKind.KW_TRY,
    "catch": TokenKind.KW_CATCH,
    "this": TokenKind.KW_THIS,
    "operator": TokenKind.KW_OPERATOR,
    "new": TokenKind.KW_NEW,
    "implicit": TokenKind.KW_IMPLICIT,
    "intrinsic": TokenKind.KW_INTRINSIC,
    "class": TokenKind.KW_CLASS,
    "extends": TokenKind.KW_EXTENDS,
    "slot": TokenKind.KW_SLOT,
    "field": TokenKind.KW_FIELD,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    # `unknown` — the neutral point on the truth axis (0.0 between
    # true and false). The first-class three-valued value, and a
    # readability win over `trit t = 0`. `unk` is a short alias
    # that gets the same token — both forms are fine to write.
    "unknown": TokenKind.KW_UNKNOWN,
    "unk": TokenKind.KW_UNKNOWN,
    # `wait` — explicit deferred-initializer marker. Only legal in a
    # var-decl initializer position (`int i = wait;`). Tells the
    # compiler "I'm declaring this name now, an assignment will
    # follow before any read." The validator enforces definite
    # assignment; the codegen emits zero-of-type at the declaration
    # site and the later assignment overrides it.
    "wait": TokenKind.KW_WAIT,
    # `async` / `await` — promise vocabulary. Hard keywords because
    # `async function` is a function-decl modifier and `await expr` is
    # an expression operator; both must be recognised at fixed lex
    # positions, not contextually. See planning/sutra-spec/promises.md.
    "async": TokenKind.KW_ASYNC,
    "await": TokenKind.KW_AWAIT,
}

# Primitive type names. They are ordinary identifiers at the lexer
# level - the parser treats them as types in type positions.
#
# `permutation` is a vector at the substrate level (a fixed ±1
# mask) but it's a distinct compile-time type: the operations on
# it (compose, invert, act on a vector) are different from the
# operations on a plain vector.
#
# `map` is a built-in generic collection type, written as
# `map<K, V>` in type position. It's listed here so the validator
# doesn't flag it as a user-defined class name subject to
# casing-drift checks, and so that the spec treats it as a primitive
# container alongside `tuple`.
PRIMITIVE_TYPE_NAMES = {
    # `number` is the canonical name for a value on the number axis
    # (real / imaginary components of a d-dim vector). `scalar` is a
    # DEPRECATED ALIAS kept only so the frozen NeurIPS archive
    # (paper/neurips/**, which cannot be edited) keeps compiling — a
    # `scalar` is a 0-d tensor, which is conceptually NOT what a Sutra
    # number is, so the name misleads. New code uses `number`.
    "number",
    "scalar",
    "vector",
    "matrix",
    "tuple",
    "string",
    "bool",
    "fuzzy",
    "void",
    "permutation",
    "map",
    "char",
    "int",
    # Three-valued primitive class. Same truth-axis storage as
    # `fuzzy`; the difference is compile-time tagging + the
    # three-way polarizer in defuzzification, which preserves the
    # neutral point instead of collapsing it.
    "trit",
    # Complex numbers — real+imaginary pair on synthetic[AXIS_REAL]
    # and synthetic[AXIS_IMAG]. Every numeric value is implicitly
    # on the complex plane; the `complex` type tag is compile-time
    # metadata for type-hygiene purposes. `5i` / `5 + 5i` literals
    # already emit make_complex calls; the type lets the programmer
    # declare the intent at the slot level.
    "complex",
    # `Promise<T>` — parameterised promise type. Returned by `async
    # function`s; awaited via `await expr`. Lives here (not in the
    # KEYWORDS map) so that it's a contextual type name like
    # `vector` / `dict`, not a hard keyword that would block users
    # from naming a class `Promise`. See planning/sutra-spec/promises.md.
    "Promise",
}

# Logical-connective keywords. CONTEXTUAL — these names lex as
# IDENT so user identifiers like `Iff`, `Nand`, `XorTable` keep
# parsing. The parser checks IDENT lexemes against this map (after
# lowercasing) only in expression positions, where they then become
# operators. Maps lowercased lexeme -> the logical-op string the
# inliner lowers to. Symbolic equivalents (`!`, `~`, `&&`, `&`,
# `||`, `|`) come through dedicated tokens, not this map.
_LOGIC_KEYWORD_NAMES = {
    "not":  "!",       # unary
    "and":  "&&",      # binary
    "or":   "||",      # binary
    "nand": "nand",    # binary
    "xor":  "xor",     # binary
    "xnor": "xnor",    # binary
    "iff":  "xnor",    # binary, alias for xnor
}

# Contextual keywords: identifiers with special meaning in expressions
# but which are still legal bareword identifiers in other positions.
CONTEXTUAL_KEYWORDS = {
    "defuzzy",
    "embed",
    "unsafeCast",
    "unsafeOverride",
}


@dataclass
class Token:
    kind: TokenKind
    lexeme: str
    span: SourceSpan
    # For literals: the interpreted value. `value` is a Python object
    # for ease of later lowering; for now the parser only cares about
    # it for strings.
    value: object = None

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Token({self.kind.name}, {self.lexeme!r}, {self.span.start})"


class Lexer:
    """Tokenize Sutra source into a flat list.

    Call `tokenize()` and then consume `tokens` and `diagnostics`.
    """

    def __init__(self, source: str, *, file: Optional[str] = None) -> None:
        self.source = source
        self.file = file
        self.diagnostics = DiagnosticBag(file=file)
        self.tokens: List[Token] = []
        self._pos = 0
        self._line = 1
        self._col = 1
        # Stack of open interpolated-string states. Each entry stores
        # (start_pos, brace_depth_at_interp_open). When we are inside
        # an interpolation's `{...}`, we count braces so we only return
        # to string mode on the matching `}`.
        self._interp_stack: List[int] = []

    # ---- public API -------------------------------------------------------

    def tokenize(self) -> List[Token]:
        while not self._at_end():
            if self._interp_stack and self._interp_stack[-1] == 0:
                # We are inside the literal part of an interpolated
                # string (not within `{...}`). Continue scanning the
                # string body.
                self._scan_interp_body()
                continue
            self._scan_token()
        self._emit(TokenKind.EOF, "", self._pos, self._pos)
        return self.tokens

    # ---- position bookkeeping --------------------------------------------

    def _at_end(self) -> bool:
        return self._pos >= len(self.source)

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        if idx >= len(self.source):
            return ""
        return self.source[idx]

    def _advance(self) -> str:
        ch = self.source[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _position_at(self, offset: int) -> SourcePosition:
        # Walk from 0 to offset to get accurate line/col. Only called
        # for token starts/ends on the main path, so we use a cheap
        # incremental tracker instead: line/col are maintained by
        # `_advance`. For span starts we snapshot before scanning.
        raise NotImplementedError("Use _snapshot / _make_span instead")

    def _snapshot(self) -> SourcePosition:
        return SourcePosition(line=self._line, column=self._col, offset=self._pos)

    def _span(self, start: SourcePosition) -> SourceSpan:
        return SourceSpan(start=start, end=self._snapshot())

    # ---- token emission ---------------------------------------------------

    def _emit(
        self,
        kind: TokenKind,
        lexeme: str,
        start_offset: int,
        end_offset: int,
        *,
        value: object = None,
    ) -> None:
        # Compute accurate positions from offsets by re-scanning the
        # known lexeme boundaries using the maintained _line/_col. In
        # practice the caller already has a SourcePosition snapshot so
        # we accept that via `_emit_with_span` instead. This helper is
        # kept for the EOF sentinel only.
        pos = SourcePosition(line=self._line, column=self._col, offset=end_offset)
        span = SourceSpan(start=pos, end=pos)
        self.tokens.append(Token(kind=kind, lexeme=lexeme, span=span, value=value))

    def _emit_tok(
        self,
        kind: TokenKind,
        lexeme: str,
        start: SourcePosition,
        *,
        value: object = None,
    ) -> None:
        span = self._span(start)
        self.tokens.append(Token(kind=kind, lexeme=lexeme, span=span, value=value))

    # ---- main scanner -----------------------------------------------------

    def _scan_token(self) -> None:
        # Skip whitespace (but not newlines inside counts)
        while not self._at_end() and self._peek() in " \t\r\n":
            self._advance()
        if self._at_end():
            return

        start = self._snapshot()
        ch = self._peek()

        # Comments --------------------------------------------------------
        if ch == "/" and self._peek(1) == "/":
            self._scan_line_comment()
            return
        if ch == "/" and self._peek(1) == "*":
            self._scan_block_comment(start)
            return
        if ch == "#":
            self._scan_line_comment()
            return

        # Strings ----------------------------------------------------------
        if ch == '"':
            self._scan_plain_string(start)
            return
        if ch == "$" and self._peek(1) == '"':
            self._scan_interp_string_open(start)
            return
        if ch == "'":
            self._scan_char(start)
            return

        # Numbers ----------------------------------------------------------
        if ch.isdigit():
            self._scan_number(start)
            return

        # Identifiers / keywords ------------------------------------------
        if ch == "_" or ch.isalpha():
            self._scan_ident(start)
            return

        # Operators & punctuation -----------------------------------------
        self._scan_operator(start)

    # ---- comments ---------------------------------------------------------

    def _scan_line_comment(self) -> None:
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    def _scan_block_comment(self, start: SourcePosition) -> None:
        # Consume "/*"
        self._advance()
        self._advance()
        while not self._at_end():
            if self._peek() == "*" and self._peek(1) == "/":
                self._advance()
                self._advance()
                return
            self._advance()
        # Unterminated
        self.diagnostics.error(
            "unterminated block comment",
            self._span(start),
            code="SUT0001",
            hint="add `*/` to close the comment",
        )

    # ---- strings ----------------------------------------------------------

    def _scan_plain_string(self, start: SourcePosition) -> None:
        self._advance()  # opening "
        buf: List[str] = []
        while not self._at_end() and self._peek() != '"':
            ch = self._advance()
            if ch == "\\":
                if self._at_end():
                    break
                esc = self._advance()
                buf.append(self._interpret_escape(esc))
            elif ch == "\n":
                self.diagnostics.error(
                    "unterminated string literal (newline before closing quote)",
                    self._span(start),
                    code="SUT0002",
                )
                break
            else:
                buf.append(ch)
        if not self._at_end() and self._peek() == '"':
            self._advance()
        else:
            self.diagnostics.error(
                "unterminated string literal",
                self._span(start),
                code="SUT0002",
            )
        lexeme = self.source[start.offset:self._pos]
        self._emit_tok(
            TokenKind.STRING_LIT, lexeme, start, value="".join(buf)
        )

    def _scan_interp_string_open(self, start: SourcePosition) -> None:
        # `$"` opens an interpolated string. We emit a STRING_INTERP_START
        # token and then push a state entry. The main loop will call
        # `_scan_interp_body` until the string is closed.
        self._advance()  # $
        self._advance()  # "
        self._emit_tok(TokenKind.STRING_INTERP_START, "$\"", start)
        self._interp_stack.append(0)

    def _scan_interp_body(self) -> None:
        """Scan inside an interpolated string, outside `{...}` regions."""
        buf_start = self._snapshot()
        buf: List[str] = []
        while not self._at_end():
            ch = self._peek()
            if ch == '"':
                # End of the interpolated string.
                if buf:
                    lexeme = self.source[buf_start.offset:self._pos]
                    self._emit_tok(
                        TokenKind.STRING_LIT_CHUNK, lexeme, buf_start,
                        value="".join(buf),
                    )
                close_start = self._snapshot()
                self._advance()
                self._emit_tok(TokenKind.STRING_INTERP_END, "\"", close_start)
                self._interp_stack.pop()
                return
            if ch == "{":
                # Emit any pending chunk, then enter interpolation mode.
                if buf:
                    lexeme = self.source[buf_start.offset:self._pos]
                    self._emit_tok(
                        TokenKind.STRING_LIT_CHUNK, lexeme, buf_start,
                        value="".join(buf),
                    )
                open_start = self._snapshot()
                self._advance()
                self._emit_tok(TokenKind.INTERP_OPEN, "{", open_start)
                # Mark that we are now tracking a nested brace.
                self._interp_stack[-1] = 1
                return
            if ch == "\\":
                self._advance()
                if self._at_end():
                    break
                esc = self._advance()
                buf.append(self._interpret_escape(esc))
                continue
            if ch == "\n":
                self.diagnostics.error(
                    "unterminated interpolated string literal",
                    self._span(buf_start),
                    code="SUT0002",
                )
                break
            self._advance()
            buf.append(ch)
        # EOF without closing quote.
        self.diagnostics.error(
            "unterminated interpolated string literal",
            self._span(buf_start),
            code="SUT0002",
        )
        # Pop so we don't loop.
        if self._interp_stack:
            self._interp_stack.pop()

    def _scan_char(self, start: SourcePosition) -> None:
        """Scan a single-quoted character literal: `'a'`, `'\\n'`, `'\\''`.

        Runs after the dispatcher sees a leading `'`. Recognises the
        same escape sequences as string literals (see
        `_interpret_escape`). Empty literal `''` and unterminated
        literal both produce diagnostics and emit CHAR_LIT with value
        0 so the parser keeps making progress.
        """
        self._advance()  # opening '
        value = 0
        if self._at_end() or self._peek() == "'":
            self.diagnostics.error(
                "empty character literal",
                self._span(start),
                code="SUT0003",
                hint="a character literal must contain exactly one character",
            )
            if not self._at_end() and self._peek() == "'":
                self._advance()
            lexeme = self.source[start.offset:self._pos]
            self._emit_tok(TokenKind.CHAR_LIT, lexeme, start, value=value)
            return

        ch = self._advance()
        if ch == "\\":
            if self._at_end():
                self.diagnostics.error(
                    "unterminated character literal",
                    self._span(start),
                    code="SUT0003",
                )
                lexeme = self.source[start.offset:self._pos]
                self._emit_tok(TokenKind.CHAR_LIT, lexeme, start, value=value)
                return
            esc = self._advance()
            decoded = self._interpret_escape(esc)
            value = ord(decoded)
        elif ch == "\n":
            self.diagnostics.error(
                "unterminated character literal (newline before closing quote)",
                self._span(start),
                code="SUT0003",
            )
            lexeme = self.source[start.offset:self._pos]
            self._emit_tok(TokenKind.CHAR_LIT, lexeme, start, value=value)
            return
        else:
            value = ord(ch)

        if not self._at_end() and self._peek() == "'":
            self._advance()
        else:
            self.diagnostics.error(
                "unterminated character literal (expected closing `'`)",
                self._span(start),
                code="SUT0003",
            )
        lexeme = self.source[start.offset:self._pos]
        self._emit_tok(TokenKind.CHAR_LIT, lexeme, start, value=value)

    def _interpret_escape(self, ch: str) -> str:
        mapping = {
            "n": "\n",
            "t": "\t",
            "r": "\r",
            "\\": "\\",
            "\"": "\"",
            "'": "'",
            "0": "\0",
            "{": "{",
            "}": "}",
            "$": "$",
        }
        return mapping.get(ch, ch)

    # ---- numbers ----------------------------------------------------------

    def _scan_number(self, start: SourcePosition) -> None:
        is_float = False
        while not self._at_end() and self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while not self._at_end() and self._peek().isdigit():
                self._advance()
        # Imaginary-unit suffix: `5i`, `3.14i`. Only binds when the
        # character AFTER the `i` is not an identifier continuation —
        # so `5i` → IMAG_LIT(5) but `5index` → INT_LIT(5) + IDENT("index")
        # and the bare variable name `i` still lexes as IDENT. Same
        # disambiguation pattern as numeric suffixes in Rust / C#.
        if self._peek() == "i":
            nxt = self._peek(1)
            if nxt == "" or not (nxt.isalnum() or nxt == "_"):
                self._advance()  # consume the `i`
                lexeme = self.source[start.offset:self._pos]
                # Magnitude is the numeric part without the trailing `i`.
                magnitude = float(lexeme[:-1])
                self._emit_tok(
                    TokenKind.IMAG_LIT, lexeme, start, value=magnitude
                )
                return
        lexeme = self.source[start.offset:self._pos]
        if is_float:
            self._emit_tok(TokenKind.FLOAT_LIT, lexeme, start, value=float(lexeme))
        else:
            self._emit_tok(TokenKind.INT_LIT, lexeme, start, value=int(lexeme))

    # ---- identifiers ------------------------------------------------------

    def _scan_ident(self, start: SourcePosition) -> None:
        while not self._at_end():
            ch = self._peek()
            if ch == "_" or ch.isalnum():
                self._advance()
            else:
                break
        lexeme = self.source[start.offset:self._pos]
        kind = KEYWORDS.get(lexeme, TokenKind.IDENT)
        # The logical-connective keywords (`not`, `and`, `or`, `nand`,
        # `xor`, `xnor`, `iff`) are CONTEXTUAL — they emit as IDENT so
        # they don't shadow user identifiers like `Iff` or `Nand`.
        # The parser recognizes them as operators in expression
        # positions by checking the IDENT lexeme (case-insensitively).
        # See _LOGIC_KEYWORD_NAMES below.
        self._emit_tok(kind, lexeme, start)

    # ---- operators --------------------------------------------------------

    def _scan_operator(self, start: SourcePosition) -> None:
        ch = self._advance()
        nxt = self._peek()

        # Two-character operators first.
        two: Optional[TokenKind] = None
        if ch == "=" and nxt == "=":
            two = TokenKind.EQ
        elif ch == "!" and nxt == "=":
            two = TokenKind.NEQ
        elif ch == "<" and nxt == "=":
            two = TokenKind.LE
        elif ch == ">" and nxt == "=":
            two = TokenKind.GE
        elif ch == "&" and nxt == "&":
            two = TokenKind.AND
        elif ch == "|" and nxt == "|":
            two = TokenKind.OR
        elif ch == "+" and nxt == "+":
            two = TokenKind.PLUS_PLUS
        elif ch == "-" and nxt == "-":
            two = TokenKind.MINUS_MINUS
        elif ch == "+" and nxt == "=":
            two = TokenKind.PLUS_ASSIGN
        elif ch == "-" and nxt == "=":
            two = TokenKind.MINUS_ASSIGN
        elif ch == "*" and nxt == "=":
            two = TokenKind.STAR_ASSIGN
        elif ch == "/" and nxt == "=":
            two = TokenKind.SLASH_ASSIGN
        elif ch == "-" and nxt == ">":
            two = TokenKind.ARROW
        elif ch == "=" and nxt == ">":
            two = TokenKind.FAT_ARROW
        elif ch == "|" and nxt == ">":
            two = TokenKind.PIPE_FORWARD
        elif ch == ":" and nxt == ":":
            two = TokenKind.DOUBLE_COLON

        if two is not None:
            self._advance()
            lex = self.source[start.offset:self._pos]
            self._emit_tok(two, lex, start)
            return

        # Single-character operators / punctuation.
        single = {
            "{": TokenKind.LBRACE,
            "}": TokenKind.RBRACE,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            ";": TokenKind.SEMICOLON,
            ",": TokenKind.COMMA,
            ".": TokenKind.DOT,
            ":": TokenKind.COLON,
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "!": TokenKind.BANG,
            "?": TokenKind.QUESTION,
            "=": TokenKind.ASSIGN,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
            "~": TokenKind.TILDE,
            # Single `&` and `|` are logical, not bitwise — Sutra has
            # no bits to flip. They lex to the same kinds as `&&` and
            # `||` so the parser and inliner treat them uniformly.
            "&": TokenKind.AND,
            "|": TokenKind.OR,
            "^": TokenKind.BIT_XOR,
        }
        kind = single.get(ch)
        if kind is None:
            self.diagnostics.error(
                f"unexpected character {ch!r}",
                self._span(start),
                code="SUT0003",
            )
            self._emit_tok(TokenKind.UNKNOWN, ch, start)
            return
        self._emit_tok(kind, ch, start)

        # Brace counting inside interpolated strings. When we see `{`
        # or `}` inside a `{ expr }` region of an interpolated string,
        # we adjust the depth counter. A matching close returns control
        # to the string body.
        if self._interp_stack and self._interp_stack[-1] > 0:
            if kind is TokenKind.LBRACE:
                self._interp_stack[-1] += 1
            elif kind is TokenKind.RBRACE:
                self._interp_stack[-1] -= 1
                if self._interp_stack[-1] == 0:
                    # Replace the last-emitted RBRACE with INTERP_CLOSE
                    # so the parser knows we're back in string mode.
                    closing = self.tokens.pop()
                    self.tokens.append(
                        Token(
                            kind=TokenKind.INTERP_CLOSE,
                            lexeme=closing.lexeme,
                            span=closing.span,
                        )
                    )
