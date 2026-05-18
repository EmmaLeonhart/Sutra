"""Recursive-descent parser for the Sutra language.

The parser consumes a token stream produced by `Lexer` and builds the
AST nodes from `ast_nodes`. It does NOT throw on parse errors — it
records a diagnostic, tries a recovery strategy (usually "skip to the
next `;` or `}`"), and keeps going, so a single bad token doesn't hide
the rest of the file from the validator.

Grammar covered (v0.1):

    module          = { top_level_item }
    top_level_item  = function_decl | method_decl | var_decl | statement

    function_decl   = modifiers? "function" modifiers? type ident
                      ("<" type_params ">")? "(" params? ")" block
                    | modifiers? "function" modifiers? "operator" op_token
                      "(" params? ")" block
    method_decl     = modifiers? "method" type ident
                      ("<" type_params ">")? "(" params? ")" block
    modifiers       = ("public" | "private" | "static")+

    type            = ident ("<" type_args ">")?
    params          = param ("," param)*
    param           = type ident

    block           = "{" { statement } "}"
    statement       = if_stmt | while_stmt | for_stmt | foreach_stmt
                    | do_while_stmt | try_stmt | return_stmt
                    | var_decl | block | expr_stmt

    var_decl        = ("var" | "const") ident ["=" expr] ";"
                    | "const" type ident ["=" expr] ";"
                    | type ident ["=" expr] ";"

    if_stmt         = "if" "(" expr ")" block [ "else" (if_stmt | block) ]
    while_stmt      = "while" "(" expr ")" block
    for_stmt        = "for" "(" [for_init] ";" [expr] ";" [expr] ")" block
    for_init        = var_decl_no_semi | expr
    foreach_stmt    = "foreach" "(" ("var" | type) ident "in" expr ")" block
    do_while_stmt   = "do" block "while" "(" expr ")" ";"
    try_stmt        = "try" block "catch" block
    return_stmt     = "return" [expr] ";"
    expr_stmt       = expr ";"

    expr            = assignment
    assignment      = logical_or (assign_op assignment)?
    logical_or      = logical_and ("||" logical_and)*
    logical_and     = equality ("&&" equality)*
    equality        = comparison (("==" | "!=") comparison)*
    comparison      = additive (("<" | ">" | "<=" | ">=") additive)*
    additive        = multiplicative (("+" | "-") multiplicative)*
    multiplicative  = unary (("*" | "/" | "%") unary)*
    unary           = ("!" | "-" | "+") unary | postfix
    postfix         = primary { call_or_member }
    call_or_member  = "." ident | "(" args? ")" | "<" type_args ">" "(" args?")"
    primary         = literal | interp_string | ident | "this"
                    | paren_or_cast | special_call

    paren_or_cast   = "(" ( type ")" unary  |  expr ")" )
    special_call    = "unsafeCast" "<" type ">" "(" expr ")"
                    | "unsafeOverride" "(" expr ")"
                    | "defuzzy" "(" expr ")"
                    | "embed" "(" expr ")"

Ambiguities handled:

- `(Type) expr` (cast) vs `(expr)` (group): we save the position, try
  to parse a bare type followed by `)`, and if the next token can
  start a unary expression, commit to cast; otherwise rewind.
- `Ident < ... > (...)` (generic call) vs `a < b` (comparison): in
  postfix position we look ahead for a balanced `<...>` followed by
  `(`. If the pattern matches, it's a generic call.
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

from . import ast_nodes as ast
from .diagnostics import (
    DiagnosticBag,
    SourcePosition,
    SourceSpan,
)
from .lexer import Token, TokenKind


# Tokens that can start a unary/primary expression. Used by the cast
# disambiguation to decide whether `(X)` is a cast or a group.
_EXPR_START_TOKENS = {
    TokenKind.INT_LIT,
    TokenKind.FLOAT_LIT,
    TokenKind.IMAG_LIT,
    TokenKind.CHAR_LIT,
    TokenKind.STRING_LIT,
    TokenKind.STRING_INTERP_START,
    TokenKind.TRUE,
    TokenKind.FALSE,
    TokenKind.KW_UNKNOWN,
    TokenKind.KW_WAIT,
    TokenKind.IDENT,
    TokenKind.KW_THIS,
    TokenKind.LPAREN,
    TokenKind.LBRACKET,
    TokenKind.BANG,
    TokenKind.MINUS,
    TokenKind.PLUS,
}

# Primitive type names. The parser treats these like any other type
# identifier but keeps the set around for nicer error messages.
_PRIMITIVE_TYPES = {
    # `number` canonical; `scalar` deprecated alias (see lexer.py
    # PRIMITIVE_TYPE_NAMES — kept for the frozen NeurIPS archive).
    "number",
    "scalar", "vector", "matrix", "tuple", "string",
    "bool", "fuzzy", "void", "permutation", "map",
    "char", "int",
    # trit = three-valued fuzzy (three-way polarizer in defuzz).
    "trit",
    # complex — real/imag pair on synthetic axes 0, 1.
    "complex",
}

# Keywords that can act as a "special function" in expression position.
_SPECIAL_CALL_NAMES = {"unsafeCast", "unsafeOverride", "defuzzy", "embed"}


class Parser:
    def __init__(
        self,
        tokens: List[Token],
        *,
        file: Optional[str] = None,
        diagnostics: Optional[DiagnosticBag] = None,
    ) -> None:
        self.tokens = tokens
        self.file = file
        self.diagnostics = diagnostics if diagnostics is not None else DiagnosticBag(file=file)
        self._pos = 0

    # ================================================================
    # Public entry points
    # ================================================================

    def parse_module(self) -> ast.Module:
        start = self._current_span()
        items: List[ast.TopLevel] = []
        while not self._at_end():
            item = self._parse_top_level()
            if item is not None:
                items.append(item)
        end = self._current_span()
        module_span = SourceSpan(start=start.start, end=end.end)
        return ast.Module(items=items, span=module_span)

    # ================================================================
    # Token stream helpers
    # ================================================================

    def _at_end(self) -> bool:
        return self._peek().kind is TokenKind.EOF

    def _peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _current_span(self) -> SourceSpan:
        return self._peek().span

    def _advance(self) -> Token:
        tok = self.tokens[self._pos]
        if tok.kind is not TokenKind.EOF:
            self._pos += 1
        return tok

    def _check(self, kind: TokenKind) -> bool:
        return self._peek().kind is kind

    def _check_any(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _match(self, *kinds: TokenKind) -> Optional[Token]:
        if self._peek().kind in kinds:
            return self._advance()
        return None

    def _expect(self, kind: TokenKind, what: str) -> Optional[Token]:
        if self._check(kind):
            return self._advance()
        tok = self._peek()
        self.diagnostics.error(
            f"expected {what}, got {self._describe(tok)}",
            tok.span,
            code="SUT0100",
        )
        return None

    def _describe(self, tok: Token) -> str:
        if tok.kind is TokenKind.EOF:
            return "end of file"
        return f"`{tok.lexeme}`"

    def _synchronize_to(self, *kinds: TokenKind) -> None:
        """Skip tokens until we hit one of `kinds` (inclusive of those
        kinds) or EOF. Used for error recovery after a parse failure.
        """
        while not self._at_end() and self._peek().kind not in kinds:
            self._advance()

    def _skip_to_statement_boundary(self) -> None:
        # Skip to the next `;` or `}` and consume the `;` if present.
        depth = 0
        while not self._at_end():
            kind = self._peek().kind
            if kind is TokenKind.LBRACE or kind is TokenKind.LPAREN:
                depth += 1
            elif kind is TokenKind.RBRACE or kind is TokenKind.RPAREN:
                if depth == 0:
                    return
                depth -= 1
            elif kind is TokenKind.SEMICOLON and depth == 0:
                self._advance()
                return
            self._advance()

    # ================================================================
    # Top-level
    # ================================================================

    def _parse_top_level(self) -> Optional[ast.TopLevel]:
        # Peek modifiers + keyword to decide which production to take.
        save = self._pos
        mods = self._parse_modifiers()
        tok = self._peek()

        if tok.kind is TokenKind.KW_FUNCTION:
            return self._parse_function_decl(mods)
        if tok.kind is TokenKind.KW_ASYNC and self._peek(1).kind is TokenKind.KW_FUNCTION:
            # `async function ...` — promise-producing function.
            # Consume the `async` modifier; _parse_function_decl picks
            # up at `function`. See planning/sutra-spec/promises.md.
            self._advance()
            return self._parse_function_decl(mods, is_async=True)
        if tok.kind in (TokenKind.KW_DO_WHILE,
                        TokenKind.KW_WHILE_LOOP,
                        TokenKind.KW_ITERATIVE_LOOP,
                        TokenKind.KW_FOREACH_LOOP):
            if mods.is_public or mods.is_private or mods.is_static:
                self.diagnostics.error(
                    "modifiers (`public`/`private`/`static`) are not yet "
                    "supported on loop function declarations",
                    tok.span,
                    code="SUT0101",
                )
            return self._parse_loop_function_decl()
        if tok.kind is TokenKind.KW_INTRINSIC and self._peek(1).kind is TokenKind.KW_FUNCTION:
            # `intrinsic function <ret> <name>(<params>);` — signature
            # only, body lives in the runtime. Used by stdlib files for
            # leaf primitives.
            self._advance()  # consume `intrinsic`
            return self._parse_function_decl(mods, is_intrinsic=True)
        if tok.kind is TokenKind.KW_METHOD:
            return self._parse_method_decl(mods)
        if tok.kind is TokenKind.KW_STATIC and self._peek(1).kind is TokenKind.KW_METHOD:
            mods.is_static = True
            return self._parse_method_decl(mods)
        if tok.kind is TokenKind.KW_CLASS:
            # Modifiers don't apply to class declarations in the MVP
            # surface — surface them as an error if any were saved.
            if mods.is_public or mods.is_private or mods.is_static:
                self.diagnostics.error(
                    "modifiers (`public`/`private`/`static`) are not yet "
                    "supported on class declarations",
                    tok.span,
                    code="SUT0101",
                )
            return self._parse_class_decl()
        if tok.kind is TokenKind.KW_SLOT:
            # `slot TYPE name = expr;` — only legal at function scope
            # in the MVP, but the parser doesn't enforce that today.
            # Modifiers aren't supported on slot decls.
            if mods.is_public or mods.is_private or mods.is_static:
                self.diagnostics.error(
                    "modifiers (`public`/`private`/`static`) are not "
                    "supported on slot declarations",
                    tok.span,
                    code="SUT0101",
                )
            return self._parse_slot_decl()

        # No function/method. Modifiers only make sense on those, so if
        # we saw any, that's an error; rewind and try as a statement.
        if mods.is_public or mods.is_private or mods.is_static:
            self.diagnostics.error(
                "modifiers (`public`/`private`/`static`) only apply to function and method declarations",
                tok.span,
                code="SUT0101",
            )
            self._pos = save  # rewind so the next pass sees the same tokens

        stmt = self._parse_statement()
        return stmt

    def _parse_modifiers(self) -> ast.Modifiers:
        mods = ast.Modifiers()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.KW_PUBLIC:
                mods.is_public = True
                self._advance()
            elif tok.kind is TokenKind.KW_PRIVATE:
                mods.is_private = True
                self._advance()
            elif tok.kind is TokenKind.KW_STATIC:
                # `static` can appear before `method`. Only consume here
                # if what follows is `function` — `method` handles its
                # own `static` check via _parse_top_level.
                if self._peek(1).kind is TokenKind.KW_FUNCTION:
                    mods.is_static = True
                    self._advance()
                else:
                    break
            else:
                break
        return mods

    # ----------------------------------------------------------------
    # Function / method declarations
    # ----------------------------------------------------------------

    def _parse_function_decl(
        self, mods: ast.Modifiers, *, is_intrinsic: bool = False,
        is_async: bool = False,
    ) -> Optional[ast.FunctionDecl]:
        start_span = self._current_span()
        self._expect(TokenKind.KW_FUNCTION, "`function`")

        # More modifiers may legally appear after `function` in the
        # full internal form: `function public static vector Foo(...)`.
        inner_mods = self._parse_modifiers()
        if inner_mods.is_public:
            mods.is_public = True
        if inner_mods.is_private:
            mods.is_private = True
        if inner_mods.is_static:
            mods.is_static = True

        # Operator overload? `function operator + (...)`
        if self._check(TokenKind.KW_OPERATOR):
            return self._parse_operator_decl(mods, start_span, is_method=False)

        return_type = self._parse_type()
        if return_type is None:
            self._skip_to_statement_boundary()
            return None

        name_tok = self._expect(TokenKind.IDENT, "function name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        type_params = self._parse_type_params()
        params = self._parse_param_list()
        if is_intrinsic:
            # Signature only; semicolon in place of body. Fabricate an
            # empty Block so downstream code that assumes .body is a
            # Block doesn't need a special-case.
            semi = self._expect(TokenKind.SEMICOLON, "`;` to close intrinsic declaration")
            end = semi.span.end if semi is not None else self._current_span().end
            body = ast.Block(statements=[], span=SourceSpan(start=end, end=end))
            return ast.FunctionDecl(
                modifiers=mods,
                return_type=return_type,
                name=name_tok.lexeme,
                type_params=type_params,
                params=params,
                body=body,
                is_operator=False,
                is_intrinsic=True,
                is_async=is_async,
                span=SourceSpan(start=start_span.start, end=end),
            )
        body = self._parse_block()
        if body is None:
            return None

        end_span = body.span
        return ast.FunctionDecl(
            modifiers=mods,
            return_type=return_type,
            name=name_tok.lexeme,
            type_params=type_params,
            params=params,
            body=body,
            is_operator=False,
            is_async=is_async,
            span=SourceSpan(start=start_span.start, end=end_span.end),
        )


    _LOOP_KIND_TOKEN = {
        TokenKind.KW_DO_WHILE: "do_while",
        TokenKind.KW_WHILE_LOOP: "while_loop",
        TokenKind.KW_ITERATIVE_LOOP: "iterative_loop",
        TokenKind.KW_FOREACH_LOOP: "foreach_loop",
    }

    def _parse_loop_function_decl(self) -> Optional[ast.LoopFunctionDecl]:
        """Parse `<kind> name(condition, type name (= default)?, ...) { body }`.

        The first item in the paren-list is an expression (the condition for
        while/do_while; the count for iterative; the array for foreach).
        Remaining items are state-parameter declarations with optional
        defaults. State params can be referenced by the condition expression.
        """
        start_span = self._current_span()
        kind_tok = self._advance()
        kind = self._LOOP_KIND_TOKEN[kind_tok.kind]

        name_tok = self._expect(TokenKind.IDENT, f"loop function name after `{kind}`")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        if self._expect(TokenKind.LPAREN, "`(` after loop function name") is None:
            self._skip_to_statement_boundary()
            return None

        # First item: the condition expression.
        condition = self._parse_expr()
        if condition is None:
            self._skip_to_statement_boundary()
            return None

        # Remaining items: state parameters (TYPE name (= default)?).
        state_params: List[ast.LoopStateParam] = []
        while self._match(TokenKind.COMMA):
            param_start = self._current_span()
            type_ref = self._parse_type()
            if type_ref is None:
                self._skip_to_statement_boundary()
                return None
            param_name_tok = self._expect(TokenKind.IDENT, "state parameter name")
            if param_name_tok is None:
                self._skip_to_statement_boundary()
                return None
            default_expr: Optional[ast.Expr] = None
            if self._match(TokenKind.ASSIGN):
                default_expr = self._parse_expr()
                if default_expr is None:
                    self._skip_to_statement_boundary()
                    return None
            param_end = self._current_span().end
            state_params.append(
                ast.LoopStateParam(
                    type_ref=type_ref,
                    name=param_name_tok.lexeme,
                    default=default_expr,
                    span=SourceSpan(start=param_start.start, end=param_end),
                )
            )

        if self._expect(TokenKind.RPAREN, "`)` to close loop parameter list") is None:
            self._skip_to_statement_boundary()
            return None

        body = self._parse_block()
        if body is None:
            return None

        end_span = body.span
        return ast.LoopFunctionDecl(
            kind=kind,
            name=name_tok.lexeme,
            condition=condition,
            state_params=state_params,
            body=body,
            span=SourceSpan(start=start_span.start, end=end_span.end),
        )

    def _parse_method_decl(
        self, mods: ast.Modifiers, *, is_intrinsic: bool = False
    ) -> Optional[ast.MethodDecl]:
        start_span = self._current_span()
        # Consume `static` if we got here via static-method detection.
        self._match(TokenKind.KW_STATIC)
        # Consume `intrinsic` if it precedes `method` (handled by the
        # caller normally, but tolerate it here for top-level entry).
        if self._check(TokenKind.KW_INTRINSIC):
            self._advance()
            is_intrinsic = True
        self._expect(TokenKind.KW_METHOD, "`method`")

        if self._check(TokenKind.KW_OPERATOR):
            if is_intrinsic:
                self.diagnostics.error(
                    "operator methods cannot be declared `intrinsic`",
                    self._current_span(),
                    code="SUT0145",
                )
            fn = self._parse_operator_decl(mods, start_span, is_method=True)
            if fn is None:
                return None
            return ast.MethodDecl(
                modifiers=mods,
                return_type=fn.return_type,
                name=fn.name,
                type_params=fn.type_params,
                params=fn.params,
                body=fn.body,
                is_operator=True,
                span=fn.span,
            )

        return_type = self._parse_type()
        if return_type is None:
            self._skip_to_statement_boundary()
            return None

        name_tok = self._expect(TokenKind.IDENT, "method name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        type_params = self._parse_type_params()
        params = self._parse_param_list()
        if is_intrinsic:
            # Signature-only declaration; semicolon in place of body.
            semi = self._expect(TokenKind.SEMICOLON,
                                "`;` to close intrinsic method declaration")
            end = semi.span.end if semi is not None else self._current_span().end
            body = ast.Block(statements=[], span=SourceSpan(start=end, end=end))
            return ast.MethodDecl(
                modifiers=mods,
                return_type=return_type,
                name=name_tok.lexeme,
                type_params=type_params,
                params=params,
                body=body,
                is_operator=False,
                is_intrinsic=True,
                span=SourceSpan(start=start_span.start, end=end),
            )

        body = self._parse_block()
        if body is None:
            return None

        end_span = body.span
        return ast.MethodDecl(
            modifiers=mods,
            return_type=return_type,
            name=name_tok.lexeme,
            type_params=type_params,
            params=params,
            body=body,
            is_operator=False,
            span=SourceSpan(start=start_span.start, end=end_span.end),
        )

    def _parse_class_decl(self) -> Optional[ast.ClassDecl]:
        """Parse `class Name extends Parent { ... }`.

        MVP scope: empty body required, single `extends` parent
        required (no implicit object root yet), no modifiers, no
        type parameters, no member declarations inside the braces.
        Any non-empty body is an error directing the user to file
        an issue / wait for the ontology work to land.
        """
        start_span = self._current_span()
        self._expect(TokenKind.KW_CLASS, "`class`")

        name_tok = self._expect(TokenKind.IDENT, "class name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        # `extends Parent` — required in MVP. We could default to
        # `vector` if omitted, but making it explicit is closer to
        # how the user described the design ("inherits from vector").
        extends_tok = self._expect(TokenKind.KW_EXTENDS,
                                   "`extends ParentName` (required in MVP)")
        if extends_tok is None:
            self._skip_to_statement_boundary()
            return None
        parent_tok = self._expect(TokenKind.IDENT, "parent class name")
        if parent_tok is None:
            self._skip_to_statement_boundary()
            return None

        self._expect(TokenKind.LBRACE, "`{` to open class body")
        methods: List[ast.MethodDecl] = []
        loop_functions: List[ast.LoopFunctionDecl] = []
        fields: List[ast.FieldDecl] = []
        loop_kw_set = (
            TokenKind.KW_DO_WHILE,
            TokenKind.KW_WHILE_LOOP,
            TokenKind.KW_ITERATIVE_LOOP,
            TokenKind.KW_FOREACH_LOOP,
        )
        while not self._check(TokenKind.RBRACE) and self._peek().kind is not TokenKind.EOF:
            tok0 = self._peek()
            tok1 = self._peek(1)
            tok2 = self._peek(2)
            # Detect the four method shapes plus loop function decls.
            is_method_start = False
            is_static = False
            is_intrinsic = False
            if tok0.kind is TokenKind.KW_METHOD:
                is_method_start = True
            elif (tok0.kind is TokenKind.KW_STATIC
                  and tok1.kind is TokenKind.KW_METHOD):
                is_method_start = True
                is_static = True
            elif (tok0.kind is TokenKind.KW_INTRINSIC
                  and tok1.kind is TokenKind.KW_METHOD):
                is_method_start = True
                is_intrinsic = True
                self._advance()
            elif (tok0.kind is TokenKind.KW_STATIC
                  and tok1.kind is TokenKind.KW_INTRINSIC
                  and tok2.kind is TokenKind.KW_METHOD):
                is_method_start = True
                is_static = True
                is_intrinsic = True
                self._advance()  # static
                self._advance()  # intrinsic
            if is_method_start:
                mods = ast.Modifiers()
                if is_static:
                    mods.is_static = True
                m = self._parse_method_decl(mods, is_intrinsic=is_intrinsic)
                if m is not None:
                    methods.append(m)
            elif tok0.kind in loop_kw_set:
                # Object loop: a loop function declared inside a class
                # body. Same shape as a top-level loop function decl;
                # the codegen emits it with a class-mangled name and
                # routes `loop Class.name(...)` calls to it. Non-static
                # by default — `this` threads as an implicit state.
                lf = self._parse_loop_function_decl()
                if lf is not None:
                    loop_functions.append(lf)
            elif (tok0.kind is TokenKind.KW_STATIC
                  and tok1.kind in loop_kw_set):
                # Static class-bodied loop: explicit `static` keyword.
                # Same as a top-level loop function — no `this`
                # threading. Called via `loop Class.name(args)`.
                self._advance()  # consume `static`
                lf = self._parse_loop_function_decl()
                if lf is not None:
                    lf.is_static = True
                    loop_functions.append(lf)
            elif tok0.kind is TokenKind.KW_FIELD:
                fd = self._parse_field_decl()
                if fd is not None:
                    fields.append(fd)
            else:
                self.diagnostics.error(
                    "class bodies accept method, loop-function, and "
                    "field declarations only. Operator implementations "
                    "are deferred",
                    self._current_span(),
                    code="SUT0140",
                    hint="declare the body member as `method <ret> "
                         "<name>(...) { ... }`, a loop function "
                         "(`do_while`, `while_loop`, `iterative_loop`, "
                         "`foreach_loop`), `field <type> <name>;`, or "
                         "remove it",
                )
                # Skip forward to a closing brace so the rest of the
                # file still parses.
                depth = 1
                while depth > 0 and self._peek().kind is not TokenKind.EOF:
                    nxt = self._advance()
                    if nxt.kind is TokenKind.LBRACE:
                        depth += 1
                    elif nxt.kind is TokenKind.RBRACE:
                        depth -= 1
                # We've consumed the closing brace; bail out.
                end_span = self._current_span()
                return ast.ClassDecl(
                    name=name_tok.lexeme,
                    parent_name=parent_tok.lexeme,
                    methods=methods,
                    loop_functions=loop_functions,
                    fields=fields,
                    span=SourceSpan(start=start_span.start, end=end_span.end),
                )
        close = self._expect(TokenKind.RBRACE, "`}` to close class body")
        if close is None:
            return None
        end_span = self._current_span()

        return ast.ClassDecl(
            name=name_tok.lexeme,
            parent_name=parent_tok.lexeme,
            methods=methods,
            loop_functions=loop_functions,
            fields=fields,
            span=SourceSpan(start=start_span.start, end=end_span.end),
        )

    def _parse_field_decl(self) -> Optional[ast.FieldDecl]:
        """Parse `field <type> <name>;` inside a class body. Per the
        2026-05-08 class-field design, fields are tag-along variables
        whose runtime storage is the same axon rotation-binding
        machinery; the declaration is the schema."""
        kw_tok = self._expect(TokenKind.KW_FIELD, "`field`")
        if kw_tok is None:
            return None
        type_ref = self._parse_type()
        if type_ref is None:
            self._skip_to_statement_boundary()
            return None
        name_tok = self._expect(TokenKind.IDENT, "field name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None
        end = self._expect(TokenKind.SEMICOLON, "`;` to terminate field declaration")
        if end is None:
            return None
        return ast.FieldDecl(
            name=name_tok.lexeme,
            type_ref=type_ref,
            span=SourceSpan(start=kw_tok.span.start, end=end.span.end),
        )

    def _parse_slot_decl(self) -> Optional[ast.VarDecl]:
        """Parse `slot TYPE name [= expr];` — rotation-bound storage
        in the synthetic subspace.

        The runtime primitives (slot_store / slot_load / rotate_slot)
        are wired in `_VSA`; the codegen integration that threads slot
        state through function scopes is deferred. The parser accepts
        the form; codegen rejects with SUT0150.
        """
        start_span = self._current_span()
        self._expect(TokenKind.KW_SLOT, "`slot`")

        # `slot TYPE name = expr;` — TYPE is required (slot decls
        # always carry an explicit type because the synthetic-subspace
        # plane allocation is per-type-shape).
        type_ref = self._parse_type()
        if type_ref is None:
            self._skip_to_statement_boundary()
            return None
        name_tok = self._expect(TokenKind.IDENT, "slot variable name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        init: Optional[ast.Expr] = None
        if self._match(TokenKind.ASSIGN):
            init = self._parse_expr()

        end = self._expect(TokenKind.SEMICOLON, "`;` after slot declaration")
        end_span = end.span if end else self._current_span()
        return ast.VarDecl(
            is_const=False,
            is_var_inferred=False,
            type_ref=type_ref,
            name=name_tok.lexeme,
            initializer=init,
            span=SourceSpan(start=start_span.start, end=end_span.end),
            is_slot=True,
        )

    def _parse_operator_decl(
        self,
        mods: ast.Modifiers,
        start_span: SourceSpan,
        *,
        is_method: bool,
    ) -> Optional[ast.FunctionDecl]:
        """Handle `operator <op>` in function/method declarations.

        Returns a FunctionDecl for uniform handling by the caller; the
        caller can wrap in a MethodDecl if `is_method=True`.
        """
        self._expect(TokenKind.KW_OPERATOR, "`operator`")

        # The return type can come BEFORE `operator` in the short form
        # or AFTER it in the form `function operator +(...)` — the spec
        # shows both shapes. We already consumed `operator`, so whatever
        # follows is the return type if it's an identifier, or the op
        # token itself if the return type was implicit.
        #
        # Looking at the spec examples:
        #   function operator +(vector a, vector b) { ... }
        #   function public static scalar operator +(scalar a, scalar b) { ... }
        #
        # In the second form, the return type precedes `operator`, which
        # means we never reach this branch — the type-then-`operator`
        # sequence would have been consumed by _parse_function_decl
        # before we got here. So: at this point the next token is the
        # operator itself.

        op_tok = self._advance()
        op_name = op_tok.lexeme
        if op_tok.kind not in {
            TokenKind.PLUS, TokenKind.MINUS, TokenKind.STAR, TokenKind.SLASH,
            TokenKind.PERCENT, TokenKind.EQ, TokenKind.NEQ, TokenKind.LT,
            TokenKind.GT, TokenKind.LE, TokenKind.GE, TokenKind.BANG,
        }:
            self.diagnostics.error(
                f"`{op_name}` is not an overloadable operator",
                op_tok.span,
                code="SUT0102",
            )

        params = self._parse_param_list()
        body = self._parse_block()
        if body is None:
            return None

        # Operator overloads implicitly return the same type as the
        # first parameter in our AST placeholder; the validator can
        # tighten this later.
        implicit_type = ast.TypeRef(name="vector", type_args=[], span=op_tok.span)
        return ast.FunctionDecl(
            modifiers=mods,
            return_type=implicit_type,
            name=f"operator{op_name}",
            type_params=[],
            params=params,
            body=body,
            is_operator=True,
            span=SourceSpan(start=start_span.start, end=body.span.end),
        )

    def _parse_type_params(self) -> List[str]:
        """Parse `<T, U>` if present, return list of names."""
        if not self._check(TokenKind.LT):
            return []
        # Check look-ahead: we only consume `<` if we see a balanced
        # close before a newline-ish structure. For type params on a
        # declaration this is almost always unambiguous because the
        # surrounding context is clear.
        save = self._pos
        self._advance()
        names: List[str] = []
        while True:
            tok = self._expect(TokenKind.IDENT, "type parameter name")
            if tok is None:
                self._pos = save
                return []
            names.append(tok.lexeme)
            if self._match(TokenKind.COMMA):
                continue
            break
        if not self._expect(TokenKind.GT, "`>` to close type parameter list"):
            self._pos = save
            return []
        return names

    def _parse_param_list(self) -> List[ast.Param]:
        params: List[ast.Param] = []
        if not self._expect(TokenKind.LPAREN, "`(`"):
            return params
        if self._match(TokenKind.RPAREN):
            return params
        while True:
            start = self._current_span()
            type_ref = self._parse_type()
            if type_ref is None:
                self._synchronize_to(TokenKind.COMMA, TokenKind.RPAREN)
                if self._match(TokenKind.COMMA):
                    continue
                break
            name_tok = self._expect(TokenKind.IDENT, "parameter name")
            if name_tok is None:
                self._synchronize_to(TokenKind.COMMA, TokenKind.RPAREN)
                if self._match(TokenKind.COMMA):
                    continue
                break
            params.append(
                ast.Param(
                    type_ref=type_ref,
                    name=name_tok.lexeme,
                    span=SourceSpan(start=start.start, end=name_tok.span.end),
                )
            )
            if self._match(TokenKind.COMMA):
                continue
            break
        self._expect(TokenKind.RPAREN, "`)` to close parameter list")
        return params

    def _parse_type(self) -> Optional[ast.TypeRef]:
        name_tok = self._peek()
        # Accept `function` as a type name in addition to plain idents.
        # This makes function-typed parameters work — e.g.
        # `function int call(function f, int v) { return f(v); }`.
        # The KW_FUNCTION token is otherwise the function-decl
        # keyword, but in type position it's the function-value type.
        if name_tok.kind is TokenKind.KW_FUNCTION:
            self._advance()
            end_pos = self.tokens[self._pos - 1].span.end
            return ast.TypeRef(
                name="function",
                type_args=[],
                span=SourceSpan(start=name_tok.span.start, end=end_pos),
            )
        if name_tok.kind is not TokenKind.IDENT:
            return None
        self._advance()
        type_args: List[ast.TypeRef] = []
        if self._check(TokenKind.LT):
            save = self._pos
            self._advance()
            args_ok = True
            while True:
                inner = self._parse_type()
                if inner is None:
                    args_ok = False
                    break
                type_args.append(inner)
                if self._match(TokenKind.COMMA):
                    continue
                break
            if not args_ok or not self._match(TokenKind.GT):
                # Not actually a generic — rewind.
                self._pos = save
                type_args = []
        end_pos = self.tokens[self._pos - 1].span.end
        return ast.TypeRef(
            name=name_tok.lexeme,
            type_args=type_args,
            span=SourceSpan(start=name_tok.span.start, end=end_pos),
        )

    # ================================================================
    # Statements
    # ================================================================

    def _parse_block(self) -> Optional[ast.Block]:
        start = self._current_span()
        if not self._expect(TokenKind.LBRACE, "`{`"):
            return None
        stmts: List[ast.Stmt] = []
        while not self._at_end() and not self._check(TokenKind.RBRACE):
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        end_tok = self._expect(TokenKind.RBRACE, "`}` to close block")
        end_span = end_tok.span if end_tok else self._current_span()
        return ast.Block(
            statements=stmts,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_statement(self) -> Optional[ast.Stmt]:
        tok = self._peek()

        if tok.kind is TokenKind.LBRACE:
            return self._parse_block()
        if tok.kind is TokenKind.KW_IF:
            return self._parse_if()
        if tok.kind is TokenKind.KW_WHILE:
            return self._parse_while()
        if tok.kind is TokenKind.KW_FOR:
            return self._parse_for()
        if tok.kind is TokenKind.KW_FOREACH:
            return self._parse_foreach()
        if tok.kind is TokenKind.KW_DO:
            return self._parse_do_while()
        if tok.kind is TokenKind.KW_LOOP:
            return self._parse_loop()
        if tok.kind is TokenKind.KW_TRY:
            return self._parse_try()
        if tok.kind is TokenKind.KW_RETURN:
            return self._parse_return()
        if tok.kind is TokenKind.KW_PASS:
            return self._parse_pass()
        if tok.kind in (TokenKind.KW_VAR, TokenKind.KW_CONST):
            return self._parse_var_or_const()
        if tok.kind is TokenKind.KW_SLOT:
            return self._parse_slot_decl()
        # Contextual `role` keyword: at statement-start, `role IDENT = ...`
        # is a role declaration; elsewhere `role` is a normal identifier.
        # We look for IDENT("role") IDENT ASSIGN to disambiguate.
        if (tok.kind is TokenKind.IDENT and tok.lexeme == "role"
                and self._peek(1).kind is TokenKind.IDENT
                and self._peek(2).kind is TokenKind.ASSIGN):
            return self._parse_var_or_const()
        # Nested function/method declarations aren't explicitly
        # forbidden; delegate to top-level handling if encountered.
        if tok.kind is TokenKind.KW_FUNCTION:
            return self._parse_function_decl(ast.Modifiers())
        if tok.kind is TokenKind.KW_METHOD:
            return self._parse_method_decl(ast.Modifiers())

        # Could be a typed declaration (`vector x = ...;`) or an
        # expression statement. We distinguish by look-ahead:
        # IDENT IDENT is a declaration, IDENT<...> IDENT is a generic
        # declaration, anything else is an expression.
        if self._looks_like_typed_decl():
            return self._parse_typed_var_decl()

        return self._parse_expr_stmt()

    def _looks_like_typed_decl(self) -> bool:
        if self._peek().kind is not TokenKind.IDENT:
            return False
        # Skip type args <...> if present
        offset = 1
        if self._peek(offset).kind is TokenKind.LT:
            depth = 1
            offset += 1
            while offset < len(self.tokens) and depth > 0:
                k = self._peek(offset).kind
                if k is TokenKind.LT:
                    depth += 1
                elif k is TokenKind.GT:
                    depth -= 1
                elif k in (TokenKind.SEMICOLON, TokenKind.LBRACE, TokenKind.RBRACE):
                    return False
                offset += 1
        # After the type, we need another IDENT then `=` or `;` or `,`.
        if self._peek(offset).kind is TokenKind.IDENT:
            nxt = self._peek(offset + 1).kind
            if nxt in (TokenKind.ASSIGN, TokenKind.SEMICOLON):
                return True
        return False

    def _parse_typed_var_decl(self) -> Optional[ast.VarDecl]:
        start = self._current_span()
        type_ref = self._parse_type()
        if type_ref is None:
            self._skip_to_statement_boundary()
            return None
        name_tok = self._expect(TokenKind.IDENT, "variable name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None
        init: Optional[ast.Expr] = None
        if self._match(TokenKind.ASSIGN):
            init = self._parse_expr()
        end = self._expect(TokenKind.SEMICOLON, "`;` after declaration")
        end_span = end.span if end else self._current_span()
        return ast.VarDecl(
            is_const=False,
            is_var_inferred=False,
            type_ref=type_ref,
            name=name_tok.lexeme,
            initializer=init,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_var_or_const(self) -> Optional[ast.VarDecl]:
        start = self._current_span()
        keyword = self._advance()  # var, const, or IDENT("role")
        is_const = keyword.kind is TokenKind.KW_CONST
        # `role` is a contextual keyword — the lexer emits IDENT for it,
        # and the parser dispatched us here when it saw IDENT("role")
        # followed by IDENT + ASSIGN (a role declaration pattern).
        is_role = (keyword.kind is TokenKind.IDENT
                   and keyword.lexeme == "role")
        is_var = keyword.kind is TokenKind.KW_VAR

        array_size: Optional[int] = None
        if is_var and self._check(TokenKind.LBRACKET):
            self._advance()  # [
            size_tok = self._expect(TokenKind.INT_LIT, "array size (integer literal)")
            if size_tok is not None:
                try:
                    array_size = int(size_tok.lexeme)
                except ValueError:
                    array_size = None
            self._expect(TokenKind.RBRACKET, "`]` after array size")

        # `const TYPE x = ...` is legal. `var TYPE x` is explicitly
        # forbidden; we still parse it and emit an error so the rest of
        # the file can be validated.
        type_ref: Optional[ast.TypeRef] = None
        is_var_inferred = is_var  # `var` is inferred unless colon-typed
        if is_const and self._peek().kind is TokenKind.IDENT and self._peek(1).kind is TokenKind.IDENT:
            type_ref = self._parse_type()
        elif is_var and self._peek().kind is TokenKind.IDENT and self._peek(1).kind is TokenKind.IDENT:
            # `var TYPE x` — illegal per the syntax-decisions doc.
            # Note: `var x : TYPE` is legal (handled below after the
            # name); this branch catches the no-colon form only.
            bad_type = self._parse_type()
            self.diagnostics.error(
                "`var` cannot be combined with a space-separated type; "
                "use colon syntax instead (`var x : TYPE`)",
                SourceSpan(start=keyword.span.start, end=bad_type.span.end if bad_type else keyword.span.end),
                code="SUT0103",
                hint="write either `var x = ...;` (inferred), "
                     "`var x : TYPE;` (explicit slot), or "
                     "`TYPE x = ...;` (classic typed declaration)",
            )
            type_ref = bad_type
            is_var_inferred = False

        name_tok = self._expect(TokenKind.IDENT, "variable name")
        if name_tok is None:
            self._skip_to_statement_boundary()
            return None

        # `var x : TYPE` — the rotation-bound colon syntax from Candidate B.
        # Only valid on var (not const, not role). role is always inferred
        # from the RHS for now; the learned_from/semantic-role side of the
        # type system comes with the deferred learned-matrix work.
        is_var_colon = False
        if is_var and self._match(TokenKind.COLON):
            parsed_type = self._parse_type()
            if parsed_type is not None:
                type_ref = parsed_type
                is_var_colon = True
                is_var_inferred = False

        init: Optional[ast.Expr] = None
        if self._match(TokenKind.ASSIGN):
            init = self._parse_expr()

        # `role x` always needs an initializer — a role without a
        # binding source is semantically empty (unlike `var x : T`
        # which allocates a zero slot).
        if is_role and init is None:
            self.diagnostics.error(
                "`role` declaration needs an initializer (e.g. "
                "`role capital_of = learned_from(...)`). "
                "Uninitialized roles are not meaningful in Sutra — use "
                "`var x : TYPE;` for an empty slot instead.",
                SourceSpan(start=keyword.span.start, end=self._current_span().end),
                code="SUT0104",
                hint="add `= <expr>` to the role declaration",
            )

        end = self._expect(TokenKind.SEMICOLON, "`;` after declaration")
        end_span = end.span if end else self._current_span()
        return ast.VarDecl(
            is_const=is_const,
            is_var_inferred=is_var_inferred and type_ref is None,
            type_ref=type_ref,
            name=name_tok.lexeme,
            initializer=init,
            span=SourceSpan(start=start.start, end=end_span.end),
            is_role=is_role,
            is_var_colon=is_var_colon,
            array_size=array_size,
        )

    def _parse_if(self) -> Optional[ast.IfStmt]:
        start = self._current_span()
        self._advance()  # if
        self._expect(TokenKind.LPAREN, "`(` after `if`")
        cond = self._parse_expr()
        self._expect(TokenKind.RPAREN, "`)` to close `if` condition")
        then_branch = self._parse_block()
        if then_branch is None:
            return None
        else_branch: Optional[Union[ast.IfStmt, ast.Block]] = None
        if self._match(TokenKind.KW_ELSE):
            if self._check(TokenKind.KW_IF):
                else_branch = self._parse_if()
            else:
                else_branch = self._parse_block()
        end_span = else_branch.span if else_branch else then_branch.span
        return ast.IfStmt(
            condition=cond,
            then_branch=then_branch,
            else_branch=else_branch,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_while(self) -> Optional[ast.WhileStmt]:
        start = self._current_span()
        self._advance()  # while
        self._expect(TokenKind.LPAREN, "`(` after `while`")
        cond = self._parse_expr()
        self._expect(TokenKind.RPAREN, "`)` to close `while` condition")
        body = self._parse_block()
        if body is None:
            return None
        return ast.WhileStmt(
            condition=cond,
            body=body,
            span=SourceSpan(start=start.start, end=body.span.end),
        )

    def _parse_for(self) -> Optional[ast.ForStmt]:
        start = self._current_span()
        self._advance()  # for
        self._expect(TokenKind.LPAREN, "`(` after `for`")

        init: Optional[ast.Stmt] = None
        if not self._check(TokenKind.SEMICOLON):
            # Init is either a var/const decl (with trailing `;`) or an
            # expression statement.
            if self._check_any(TokenKind.KW_VAR, TokenKind.KW_CONST):
                init = self._parse_var_or_const()
            elif self._looks_like_typed_decl():
                init = self._parse_typed_var_decl()
            else:
                init = self._parse_expr_stmt()
            # var/expr statements consume their trailing `;` already.
        else:
            self._advance()  # consume the empty-init `;`

        cond: Optional[ast.Expr] = None
        if not self._check(TokenKind.SEMICOLON):
            cond = self._parse_expr()
        self._expect(TokenKind.SEMICOLON, "`;` between `for` clauses")

        step: Optional[ast.Expr] = None
        if not self._check(TokenKind.RPAREN):
            step = self._parse_expr()
        self._expect(TokenKind.RPAREN, "`)` to close `for` header")

        body = self._parse_block()
        if body is None:
            return None
        return ast.ForStmt(
            init=init,
            condition=cond,
            step=step,
            body=body,
            span=SourceSpan(start=start.start, end=body.span.end),
        )

    def _parse_foreach(self) -> Optional[ast.ForeachStmt]:
        start = self._current_span()
        self._advance()  # foreach
        self._expect(TokenKind.LPAREN, "`(` after `foreach`")

        var_type: Optional[ast.TypeRef] = None
        if self._match(TokenKind.KW_VAR):
            pass  # inferred
        else:
            var_type = self._parse_type()

        name_tok = self._expect(TokenKind.IDENT, "loop variable name")
        name = name_tok.lexeme if name_tok else ""
        self._expect(TokenKind.KW_IN, "`in`")
        iterable = self._parse_expr()
        self._expect(TokenKind.RPAREN, "`)` to close `foreach` header")
        body = self._parse_block()
        if body is None:
            return None
        return ast.ForeachStmt(
            var_type=var_type,
            var_name=name,
            iterable=iterable,
            body=body,
            span=SourceSpan(start=start.start, end=body.span.end),
        )

    def _parse_do_while(self) -> Optional[ast.DoWhileStmt]:
        start = self._current_span()
        self._advance()  # do
        body = self._parse_block()
        if body is None:
            return None
        self._expect(TokenKind.KW_WHILE, "`while` after `do` block")
        self._expect(TokenKind.LPAREN, "`(`")
        cond = self._parse_expr()
        self._expect(TokenKind.RPAREN, "`)`")
        end = self._expect(TokenKind.SEMICOLON, "`;` after do-while")
        end_span = end.span if end else self._current_span()
        return ast.DoWhileStmt(
            body=body,
            condition=cond,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_loop(self):
        """Parse a `loop` statement.

        Forms:
          loop (10) { ... }            bounded, unrolls at compile time
          loop (10 as i) { ... }       bounded with index variable
          loop (expr) { ... }          condition-based (tail-recursive cell)
          loop NAME(cond, args, ...);  invoke a loop function
                                       (2026-04-30 redesign — see
                                       _parse_loop_function_decl)

        Disambiguation by what follows `loop`:
          IDENT → loop call (new function-decl form)
          LPAREN → existing bounded / condition-based forms
        """
        start = self._current_span()
        self._advance()  # loop

        if self._check(TokenKind.IDENT):
            name_tok = self._advance()
            full_name = name_tok.lexeme
            if self._match(TokenKind.DOT):
                method_tok = self._expect(TokenKind.IDENT,
                                          "method name after `.` in loop call")
                if method_tok is None:
                    self._skip_to_statement_boundary()
                    return None
                full_name = f"{name_tok.lexeme}.{method_tok.lexeme}"
            if self._expect(TokenKind.LPAREN, "`(` after loop function name") is None:
                self._skip_to_statement_boundary()
                return None
            condition_arg = self._parse_expr()
            if condition_arg is None:
                self._skip_to_statement_boundary()
                return None
            state_arg_names: List[str] = []
            while self._match(TokenKind.COMMA):
                arg_tok = self._expect(
                    TokenKind.IDENT,
                    "state argument must be an identifier (slot variable name)",
                )
                if arg_tok is None:
                    self._skip_to_statement_boundary()
                    return None
                state_arg_names.append(arg_tok.lexeme)
            self._expect(TokenKind.RPAREN, "`)` to close loop call argument list")
            end = self._expect(TokenKind.SEMICOLON, "`;` after loop call")
            end_span = end.span if end else self._current_span()
            return ast.LoopCallStmt(
                name=full_name,
                condition_arg=condition_arg,
                state_arg_names=state_arg_names,
                span=SourceSpan(start=start.start, end=end_span.end),
            )

        # Existing forms.
        self._expect(TokenKind.LPAREN, "`(` after `loop`")

        # Try to determine if this is a bounded loop (integer literal)
        # or a condition-based loop (any other expression).
        count: Optional[ast.Expr] = None
        index_var: Optional[str] = None
        condition: Optional[ast.Expr] = None

        expr = self._parse_expr()

        # Check if this is a bounded loop: the expression is an integer
        # literal, possibly followed by `as identifier`.
        if isinstance(expr, ast.IntLiteral):
            count = expr
            if self._match(TokenKind.KW_AS):
                name_tok = self._expect(TokenKind.IDENT, "index variable name after `as`")
                index_var = name_tok.lexeme if name_tok else "_i"
        else:
            # Condition-based (tail-recursive cell) loop.
            condition = expr

        self._expect(TokenKind.RPAREN, "`)` to close `loop` header")
        body = self._parse_block()
        if body is None:
            return None
        return ast.LoopStmt(
            count=count,
            index_var=index_var,
            condition=condition,
            body=body,
            span=SourceSpan(start=start.start, end=body.span.end),
        )

    def _parse_try(self) -> Optional[ast.TryStmt]:
        start = self._current_span()
        self._advance()  # try
        try_body = self._parse_block()
        if try_body is None:
            return None
        self._expect(TokenKind.KW_CATCH, "`catch` after `try` block")
        catch_body = self._parse_block()
        if catch_body is None:
            return None
        return ast.TryStmt(
            try_body=try_body,
            catch_body=catch_body,
            span=SourceSpan(start=start.start, end=catch_body.span.end),
        )

    def _parse_pass(self):
        """Parse `pass <expr_or_replace>, ...;` — tail-recursive yield in
        a loop function body. Each item is either an expression or the
        `replace` keyword (carries the input value through). The number
        of items must match the enclosing loop's state-param count;
        validation happens at codegen.
        """
        start = self._current_span()
        self._advance()  # pass
        values: List = []
        # `pass;` with zero items would be unusual but parser accepts it
        # (codegen will catch it if the loop has state params).
        if not self._check(TokenKind.SEMICOLON):
            values.append(self._parse_pass_value())
            while self._match(TokenKind.COMMA):
                values.append(self._parse_pass_value())
        end = self._expect(TokenKind.SEMICOLON, "`;` after `pass`")
        end_span = end.span if end else self._current_span()
        return ast.PassStmt(
            values=values,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_pass_value(self):
        """One item in a pass list: either `replace` or a regular expression."""
        tok = self._peek()
        if tok.kind is TokenKind.KW_REPLACE:
            self._advance()
            return ast.ReplaceMarker(span=tok.span)
        return self._parse_expr()

    def _parse_return(self) -> Optional[ast.ReturnStmt]:
        start = self._current_span()
        self._advance()  # return
        value: Optional[ast.Expr] = None
        if not self._check(TokenKind.SEMICOLON):
            value = self._parse_expr()
        end = self._expect(TokenKind.SEMICOLON, "`;` after `return`")
        end_span = end.span if end else self._current_span()
        return ast.ReturnStmt(
            value=value,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    def _parse_expr_stmt(self) -> Optional[ast.ExprStmt]:
        start = self._current_span()
        expr = self._parse_expr()
        if expr is None:
            self._skip_to_statement_boundary()
            return None
        end = self._expect(TokenKind.SEMICOLON, "`;` after expression")
        end_span = end.span if end else self._current_span()
        return ast.ExprStmt(
            expr=expr,
            span=SourceSpan(start=start.start, end=end_span.end),
        )

    # ================================================================
    # Expressions (Pratt-style via cascaded precedence methods)
    # ================================================================

    def _parse_expr(self) -> ast.Expr:
        return self._parse_pipe_forward()

    def _parse_pipe_forward(self) -> ast.Expr:
        # The `|>` operator is explicitly forbidden by the spec. The
        # validator emits SUT0110 for every occurrence via a token
        # walk. We still parse it here as a low-precedence left-assoc
        # binary operator so the rest of the expression parses cleanly
        # and the user only sees the root-cause diagnostic, not a
        # cascade of "expected `;`" recoveries.
        left = self._parse_assignment()
        while self._match(TokenKind.PIPE_FORWARD):
            right = self._parse_assignment()
            left = ast.BinaryOp(
                op="|>", left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    def _parse_assignment(self) -> ast.Expr:
        left = self._parse_logical_or()
        assign_kinds = {
            TokenKind.ASSIGN: "=",
            TokenKind.PLUS_ASSIGN: "+=",
            TokenKind.MINUS_ASSIGN: "-=",
            TokenKind.STAR_ASSIGN: "*=",
            TokenKind.SLASH_ASSIGN: "/=",
        }
        if self._peek().kind in assign_kinds:
            op_tok = self._advance()
            op = assign_kinds[op_tok.kind]
            value = self._parse_assignment()
            return ast.Assignment(
                op=op,
                target=left,
                value=value,
                span=SourceSpan(start=left.span.start, end=value.span.end),
            )
        return left

    # Logical operator precedence (lowest to highest):
    #   ||  or                  (parse_logical_or)
    #   xor xnor iff nand       (parse_logical_xor)
    #   &&  and                 (parse_logical_and)
    #   ==  !=                  (parse_equality)
    #   <   <=  >  >=           (parse_comparison)
    # Symbolic and keyword forms produce the same op-string in the
    # AST so the inliner can lower uniformly. The keyword forms
    # (`and`, `or`, `nand`, `xor`, `xnor`, `iff`, `not`) are
    # CONTEXTUAL — they lex as IDENT and the parser checks their
    # lowercased lexeme here so user identifiers with the same
    # spelling (e.g. `Iff`, `Nand`) keep working.
    _LOGICAL_OR_KW = {"or"}             # binary, op="||"
    _LOGICAL_XOR_KW = {                  # binary, op as named
        "xor":  "xor",
        "xnor": "xnor",
        "iff":  "xnor",
        "nand": "nand",
    }
    _LOGICAL_AND_KW = {"and"}            # binary, op="&&"
    _LOGICAL_NOT_KW = {"not"}            # unary, op="!"

    def _ident_lex_lower(self) -> Optional[str]:
        """Return the lowercased lexeme of the current token if it's
        an IDENT, else None. Used by the logical-keyword check."""
        tok = self._peek()
        if tok.kind is TokenKind.IDENT:
            return tok.lexeme.lower()
        return None

    def _parse_logical_or(self) -> ast.Expr:
        left = self._parse_logical_xor()
        while True:
            tok = self._peek()
            ident_lower = self._ident_lex_lower()
            if tok.kind is TokenKind.OR:
                self._advance()
                op = "||"
            elif ident_lower in self._LOGICAL_OR_KW:
                self._advance()
                op = "||"
            else:
                break
            right = self._parse_logical_xor()
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    def _parse_logical_xor(self) -> ast.Expr:
        left = self._parse_logical_and()
        while True:
            ident_lower = self._ident_lex_lower()
            if ident_lower in self._LOGICAL_XOR_KW:
                op = self._LOGICAL_XOR_KW[ident_lower]
                self._advance()
            else:
                break
            right = self._parse_logical_and()
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    def _parse_logical_and(self) -> ast.Expr:
        left = self._parse_equality()
        while True:
            tok = self._peek()
            ident_lower = self._ident_lex_lower()
            if tok.kind is TokenKind.AND:
                self._advance()
                op = "&&"
            elif ident_lower in self._LOGICAL_AND_KW:
                self._advance()
                op = "&&"
            else:
                break
            right = self._parse_equality()
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    _CHAIN_COMPARISON_TOKENS = frozenset({
        TokenKind.EQ, TokenKind.NEQ,
        TokenKind.LT, TokenKind.GT, TokenKind.LE, TokenKind.GE,
    })

    def _parse_equality(self) -> ast.Expr:
        # Equality + comparison are merged into one chain-aware parser.
        # Python's chained-comparison semantics with Sutra-specific
        # reductions for transitive same-op chains.
        return self._parse_chained_comparison()

    def _parse_comparison(self) -> ast.Expr:
        # Kept as a separate level for additive-precedence callers
        # that don't want chain detection. Today only _parse_equality
        # is the entry; this method is here so subclassing parsers
        # that want plain non-chained comparison can override.
        return self._parse_chained_comparison()

    def _parse_chained_comparison(self) -> ast.Expr:
        first = self._parse_additive()
        # Collect a chain of (op_string, operand) pairs.
        ops: List[str] = []
        operands: List[ast.Expr] = [first]
        while self._peek().kind in self._CHAIN_COMPARISON_TOKENS:
            op_tok = self._advance()
            op = op_tok.lexeme
            # Token lexeme differs from canonical op string for !=
            if op_tok.kind is TokenKind.NEQ:
                op = "!="
            elif op_tok.kind is TokenKind.EQ:
                op = "=="
            right = self._parse_additive()
            ops.append(op)
            operands.append(right)
        if not ops:
            return first
        if len(ops) == 1:
            # Single comparison: emit BinaryOp as before.
            return ast.BinaryOp(
                op=ops[0],
                left=operands[0],
                right=operands[1],
                span=SourceSpan(
                    start=operands[0].span.start,
                    end=operands[1].span.end,
                ),
            )
        span = SourceSpan(
            start=operands[0].span.start,
            end=operands[-1].span.end,
        )
        op_set = set(ops)
        # Uniform `==` chain.
        if op_set == {"=="}:
            return ast.Call(
                callee=ast.Identifier(name="Equals", span=span),
                type_args=[],
                args=operands,
                span=span,
            )
        # Uniform strict-ordering chain.
        if op_set == {"<"}:
            return ast.Call(
                callee=ast.Identifier(name="hasOrder", span=span),
                type_args=[],
                args=operands,
                span=span,
            )
        if op_set == {">"}:
            return ast.Call(
                callee=ast.Identifier(name="hasOrder", span=span),
                type_args=[],
                args=list(reversed(operands)),
                span=span,
            )
        if op_set == {"<="}:
            return ast.Call(
                callee=ast.Identifier(name="hasOrderOrEqual", span=span),
                type_args=[],
                args=operands,
                span=span,
            )
        if op_set == {">="}:
            return ast.Call(
                callee=ast.Identifier(name="hasOrderOrEqual", span=span),
                type_args=[],
                args=list(reversed(operands)),
                span=span,
            )
        # Mixed `==` + uniform-direction ordering — group adjacent
        # `==` operands and pass the groups as args to hasOrder /
        # hasOrderOrEqual. Each group is either a bare operand or a
        # `Call(Equals, [members])` (multi-element). Args always in
        # ascending order — descending source has its group list
        # reversed before the Call is built.
        ordering_ops_set = {"<", "<=", ">", ">="}
        if "!=" not in op_set and op_set.issubset({"=="} | ordering_ops_set):
            ascending_set = {"<", "<="}
            descending_set = {">", ">="}
            present_ordering = op_set & ordering_ops_set
            is_ascending = bool(present_ordering) and present_ordering.issubset(ascending_set)
            is_descending = bool(present_ordering) and present_ordering.issubset(descending_set)
            if is_ascending or is_descending:
                # Walk left-to-right, gathering adjacent == operands
                # into one group and starting a new group at every
                # ordering op.
                groups: List[List[ast.Expr]] = []
                current = [operands[0]]
                for i, op_i in enumerate(ops):
                    nxt = operands[i + 1]
                    if op_i == "==":
                        current.append(nxt)
                    else:
                        groups.append(current)
                        current = [nxt]
                groups.append(current)
                # Single-element groups stay flat; multi-element
                # groups wrap in Equals(...).
                group_args: List[ast.Expr] = []
                for g in groups:
                    if len(g) == 1:
                        group_args.append(g[0])
                    else:
                        gspan = SourceSpan(
                            start=g[0].span.start, end=g[-1].span.end,
                        )
                        group_args.append(ast.Call(
                            callee=ast.Identifier(name="Equals", span=gspan),
                            type_args=[],
                            args=g,
                            span=gspan,
                        ))
                if is_descending:
                    group_args = list(reversed(group_args))
                # Any non-strict ordering op present -> hasOrderOrEqual.
                non_strict = bool(present_ordering & {"<=", ">="})
                callee_name = "hasOrderOrEqual" if non_strict else "hasOrder"
                return ast.Call(
                    callee=ast.Identifier(name=callee_name, span=span),
                    type_args=[],
                    args=group_args,
                    span=span,
                )
        # Fallback: AND-chain expansion of pairwise BinaryOps. Each
        # pair goes through the inliner's normal comparison-lowering
        # pipeline (`<` -> `lt(a, b)` -> `b > a`, etc.), so the final
        # emitted form is the polynomial chain.
        and_chain: ast.Expr = ast.BinaryOp(
            op=ops[0],
            left=operands[0],
            right=operands[1],
            span=SourceSpan(
                start=operands[0].span.start, end=operands[1].span.end,
            ),
        )
        for i, op in enumerate(ops[1:], start=1):
            pair = ast.BinaryOp(
                op=op,
                left=operands[i],
                right=operands[i + 1],
                span=SourceSpan(
                    start=operands[i].span.start,
                    end=operands[i + 1].span.end,
                ),
            )
            and_chain = ast.BinaryOp(
                op="&&",
                left=and_chain,
                right=pair,
                span=SourceSpan(
                    start=and_chain.span.start, end=pair.span.end,
                ),
            )
        return and_chain

    def _parse_additive(self) -> ast.Expr:
        left = self._parse_multiplicative()
        while self._peek().kind in (TokenKind.PLUS, TokenKind.MINUS):
            op_tok = self._advance()
            right = self._parse_multiplicative()
            op = op_tok.lexeme
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    def _parse_multiplicative(self) -> ast.Expr:
        left = self._parse_unary()
        while self._peek().kind in (
            TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT
        ):
            op_tok = self._advance()
            right = self._parse_unary()
            op = op_tok.lexeme
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                span=SourceSpan(start=left.span.start, end=right.span.end),
            )
        return left

    def _parse_unary(self) -> ast.Expr:
        # `!`, `~`, and the `not` keyword (case-insensitive, contextual
        # — lexes as IDENT) all produce the same UnaryOp("!") AST so
        # the inliner lowers them uniformly to logical_not. `+` and
        # `-` stay as arithmetic unary operators.
        kind = self._peek().kind
        ident_lower = self._ident_lex_lower()
        is_logical_not = (
            kind in (TokenKind.BANG, TokenKind.TILDE)
            or ident_lower in self._LOGICAL_NOT_KW
        )
        if is_logical_not:
            op_tok = self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp(
                op="!",
                operand=operand,
                span=SourceSpan(start=op_tok.span.start, end=operand.span.end),
            )
        if kind in (TokenKind.MINUS, TokenKind.PLUS):
            op_tok = self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp(
                op=op_tok.lexeme,
                operand=operand,
                span=SourceSpan(start=op_tok.span.start, end=operand.span.end),
            )
        if kind is TokenKind.KW_AWAIT:
            # `await expr` — gate on the input axon backing `expr`'s
            # promise. Only legal inside an `async function` body; the
            # codegen/validator enforces that. See planning/sutra-spec/
            # promises.md §"Lowering".
            op_tok = self._advance()
            operand = self._parse_unary()
            return ast.AwaitExpr(
                operand=operand,
                span=SourceSpan(start=op_tok.span.start, end=operand.span.end),
            )
        return self._parse_postfix()

    def _parse_postfix(self) -> ast.Expr:
        expr = self._parse_primary()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.DOT:
                self._advance()
                member_tok = self._expect(TokenKind.IDENT, "member name")
                if member_tok is None:
                    return expr
                expr = ast.MemberAccess(
                    obj=expr,
                    member=member_tok.lexeme,
                    span=SourceSpan(start=expr.span.start, end=member_tok.span.end),
                )
                continue
            if tok.kind is TokenKind.LPAREN:
                args, end_pos = self._parse_arg_list()
                expr = ast.Call(
                    callee=expr,
                    type_args=[],
                    args=args,
                    span=SourceSpan(start=expr.span.start, end=end_pos),
                )
                continue
            if tok.kind is TokenKind.LT and self._looks_like_generic_call():
                type_args = self._parse_type_arg_list()
                args, end_pos = self._parse_arg_list()
                expr = ast.Call(
                    callee=expr,
                    type_args=type_args,
                    args=args,
                    span=SourceSpan(start=expr.span.start, end=end_pos),
                )
                continue
            if tok.kind is TokenKind.LBRACKET:
                # Postfix subscript: `target[index]`. Used for map
                # lookups and (future) array indexing.
                self._advance()
                index = self._parse_expr()
                close = self._expect(
                    TokenKind.RBRACKET, "`]` to close subscript"
                )
                end = close.span.end if close else self._current_span().end
                expr = ast.Subscript(
                    target=expr,
                    index=index,
                    span=SourceSpan(start=expr.span.start, end=end),
                )
                continue
            if tok.kind in (TokenKind.PLUS_PLUS, TokenKind.MINUS_MINUS):
                self._advance()
                expr = ast.PostfixOp(
                    op=tok.lexeme,
                    operand=expr,
                    span=SourceSpan(start=expr.span.start, end=tok.span.end),
                )
                continue
            break
        return expr

    def _looks_like_generic_call(self) -> bool:
        """Peek ahead to decide if `<` opens a generic call.

        Pattern: `< type (, type)* > (`
        We require the closing `>` to appear before any token that
        wouldn't fit in a type list, and we require a `(` immediately
        after the `>`.
        """
        assert self._peek().kind is TokenKind.LT
        offset = 1
        depth = 1
        while self._pos + offset < len(self.tokens):
            k = self._peek(offset).kind
            if k is TokenKind.LT:
                depth += 1
            elif k is TokenKind.GT:
                depth -= 1
                if depth == 0:
                    return self._peek(offset + 1).kind is TokenKind.LPAREN
            elif k in (
                TokenKind.IDENT,
                TokenKind.COMMA,
                TokenKind.DOT,
            ):
                pass
            else:
                return False
            offset += 1
        return False

    def _parse_type_arg_list(self) -> List[ast.TypeRef]:
        self._expect(TokenKind.LT, "`<`")
        args: List[ast.TypeRef] = []
        while True:
            t = self._parse_type()
            if t is None:
                break
            args.append(t)
            if self._match(TokenKind.COMMA):
                continue
            break
        self._expect(TokenKind.GT, "`>`")
        return args

    def _parse_arg_list(self) -> Tuple[List[ast.Expr], SourcePosition]:
        self._expect(TokenKind.LPAREN, "`(`")
        args: List[ast.Expr] = []
        if self._check(TokenKind.RPAREN):
            close = self._advance()
            return args, close.span.end
        while True:
            expr = self._parse_expr()
            args.append(expr)
            if self._match(TokenKind.COMMA):
                continue
            break
        close = self._expect(TokenKind.RPAREN, "`)` to close argument list")
        end = close.span.end if close else self._current_span().end
        return args, end

    # ----------------------------------------------------------------
    # Primary expressions
    # ----------------------------------------------------------------

    def _parse_primary(self) -> ast.Expr:
        tok = self._peek()

        if tok.kind is TokenKind.INT_LIT:
            self._advance()
            return ast.IntLiteral(value=int(tok.value) if tok.value is not None else 0, span=tok.span)
        if tok.kind is TokenKind.FLOAT_LIT:
            self._advance()
            return ast.FloatLiteral(value=float(tok.value) if tok.value is not None else 0.0, span=tok.span)
        if tok.kind is TokenKind.IMAG_LIT:
            self._advance()
            return ast.ImaginaryLiteral(
                value=float(tok.value) if tok.value is not None else 0.0,
                span=tok.span,
            )
        if tok.kind is TokenKind.STRING_LIT:
            self._advance()
            return ast.StringLiteral(value=str(tok.value) if tok.value is not None else "", span=tok.span)
        if tok.kind is TokenKind.CHAR_LIT:
            self._advance()
            return ast.CharLiteral(value=int(tok.value) if tok.value is not None else 0, span=tok.span)
        if tok.kind is TokenKind.STRING_INTERP_START:
            return self._parse_interp_string()
        if tok.kind is TokenKind.TRUE:
            self._advance()
            return ast.BoolLiteral(value=True, span=tok.span)
        if tok.kind is TokenKind.FALSE:
            self._advance()
            return ast.BoolLiteral(value=False, span=tok.span)
        if tok.kind is TokenKind.KW_UNKNOWN:
            self._advance()
            return ast.UnknownLiteral(span=tok.span)
        if tok.kind is TokenKind.KW_WAIT:
            # `wait` parses as a primary expression so the rest of the
            # declaration grammar (`int i = wait;`) works. Position
            # restriction (only as a var-decl initializer) is enforced
            # by the validator, not the parser — same approach used
            # for other context-sensitive constructs.
            self._advance()
            return ast.WaitLiteral(span=tok.span)
        if tok.kind is TokenKind.KW_THIS:
            self._advance()
            return ast.ThisExpr(span=tok.span)
        if tok.kind is TokenKind.KW_NEW:
            return self._parse_new_expr()
        if tok.kind is TokenKind.IDENT:
            # Handle special built-in calls syntactically.
            if tok.lexeme in _SPECIAL_CALL_NAMES:
                return self._parse_special_call(tok)
            self._advance()
            return ast.Identifier(name=tok.lexeme, span=tok.span)
        if tok.kind is TokenKind.KW_FUNCTION and self._peek(1).kind is TokenKind.DOT:
            # The `function.` disambiguation prefix: documented in
            # examples/02-functions-vs-methods.su. Resolves an ambiguous
            # bareword call to the free-function namespace. We treat
            # the literal `function` keyword as an identifier in this
            # position so the rest of the postfix chain parses normally.
            self._advance()
            return ast.Identifier(name="function", span=tok.span)
        if tok.kind is TokenKind.LPAREN:
            return self._parse_paren_or_cast()
        if tok.kind is TokenKind.LBRACKET:
            return self._parse_array_literal()
        if tok.kind is TokenKind.LBRACE:
            return self._parse_map_literal()

        # Unknown — emit error and return a placeholder identifier so
        # higher-level code keeps making progress.
        self.diagnostics.error(
            f"expected expression, got {self._describe(tok)}",
            tok.span,
            code="SUT0104",
        )
        self._advance()
        return ast.Identifier(name="<error>", span=tok.span)

    def _parse_new_expr(self) -> ast.Expr:
        """Parse `new ClassName(args)` — auto-constructor sugar that
        the codegen lowers to a `<Class>_new(args)` factory call.
        Per the user's 2026-05-08 design, args are positional and
        match the field declarations in source order."""
        new_tok = self._expect(TokenKind.KW_NEW, "`new`")
        if new_tok is None:
            return ast.Identifier(name="<error>", span=self._current_span())
        name_tok = self._expect(TokenKind.IDENT, "class name after `new`")
        if name_tok is None:
            return ast.Identifier(name="<error>", span=self._current_span())
        self._expect(TokenKind.LPAREN, "`(` to open constructor args")
        args: List[ast.Expr] = []
        if not self._check(TokenKind.RPAREN):
            args.append(self._parse_expr())
            while self._check(TokenKind.COMMA):
                self._advance()
                args.append(self._parse_expr())
        end = self._expect(TokenKind.RPAREN, "`)` to close constructor args")
        end_pos = end.span.end if end is not None else self._current_span().end
        return ast.NewExpr(
            class_name=name_tok.lexeme,
            args=args,
            span=SourceSpan(start=new_tok.span.start, end=end_pos),
        )

    def _parse_interp_string(self) -> ast.InterpolatedString:
        start_tok = self._advance()  # STRING_INTERP_START
        parts: List[Union[str, ast.Expr]] = []
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.STRING_INTERP_END:
                end = self._advance()
                return ast.InterpolatedString(
                    parts=parts,
                    span=SourceSpan(start=start_tok.span.start, end=end.span.end),
                )
            if tok.kind is TokenKind.STRING_LIT_CHUNK:
                self._advance()
                parts.append(str(tok.value) if tok.value is not None else tok.lexeme)
                continue
            if tok.kind is TokenKind.INTERP_OPEN:
                self._advance()
                expr = self._parse_expr()
                self._expect(TokenKind.INTERP_CLOSE, "`}` to close interpolation")
                parts.append(expr)
                continue
            # Anything else inside an interpolated string is a lexer
            # bug (or EOF after unterminated literal). Bail.
            self.diagnostics.error(
                "unterminated interpolated string literal",
                tok.span,
                code="SUT0002",
            )
            return ast.InterpolatedString(
                parts=parts,
                span=SourceSpan(start=start_tok.span.start, end=tok.span.end),
            )

    def _parse_map_literal(self) -> ast.Expr:
        """Parse `{k1: v1, k2: v2, ...}` — an inline map literal.

        Only called from `_parse_primary`, so we're guaranteed to be
        in expression position. Block statements are handled by
        `_parse_statement` before any expression parsing begins, so
        the only way to reach this helper is from inside an
        expression context (after `=`, `return`, as a call argument,
        etc.). An empty map literal `{}` is legal; trailing commas
        are not, to match the rest of the grammar.
        """
        lbrace = self._advance()  # consume {
        keys: List[ast.Expr] = []
        values: List[ast.Expr] = []
        if self._check(TokenKind.RBRACE):
            close = self._advance()
            return ast.MapLiteral(
                keys=keys,
                values=values,
                span=SourceSpan(start=lbrace.span.start, end=close.span.end),
            )
        while True:
            key = self._parse_expr()
            self._expect(TokenKind.COLON, "`:` between map key and value")
            value = self._parse_expr()
            keys.append(key)
            values.append(value)
            if self._match(TokenKind.COMMA):
                continue
            break
        close = self._expect(TokenKind.RBRACE, "`}` to close map literal")
        end = close.span.end if close else self._current_span().end
        return ast.MapLiteral(
            keys=keys,
            values=values,
            span=SourceSpan(start=lbrace.span.start, end=end),
        )

    def _parse_array_literal(self) -> ast.Expr:
        """Parse `[elem, elem, ...]` — an inline array literal.

        Called from `_parse_primary` when the current token is `[`.
        An empty array literal `[]` is legal; trailing commas are not
        permitted (matches the rest of the expression grammar).
        """
        lbracket = self._advance()  # consume [
        elements: List[ast.Expr] = []
        if self._check(TokenKind.RBRACKET):
            close = self._advance()
            return ast.ArrayLiteral(
                elements=elements,
                span=SourceSpan(start=lbracket.span.start, end=close.span.end),
            )
        while True:
            elements.append(self._parse_expr())
            if self._match(TokenKind.COMMA):
                continue
            break
        close = self._expect(TokenKind.RBRACKET, "`]` to close array literal")
        end = close.span.end if close else self._current_span().end
        return ast.ArrayLiteral(
            elements=elements,
            span=SourceSpan(start=lbracket.span.start, end=end),
        )

    def _parse_paren_or_cast(self) -> ast.Expr:
        # Save state so we can rewind if the cast attempt fails.
        save = self._pos
        lparen = self._advance()  # (

        # Try to read a type followed by `)` followed by a token that
        # starts a unary expression. If that succeeds, it's a cast.
        type_ref = self._try_parse_type_for_cast()
        if (
            type_ref is not None
            and self._check(TokenKind.RPAREN)
            and self._peek(1).kind in _EXPR_START_TOKENS
            and self._peek(1).kind is not TokenKind.LPAREN  # avoid ambiguity with call
        ):
            self._advance()  # )
            operand = self._parse_unary()
            return ast.CastExpr(
                target_type=type_ref,
                expr=operand,
                span=SourceSpan(start=lparen.span.start, end=operand.span.end),
            )

        # Not a cast — rewind and parse as a parenthesized expression.
        self._pos = save
        self._advance()  # (
        inner = self._parse_expr()
        close = self._expect(TokenKind.RPAREN, "`)` to close parenthesized expression")
        end = close.span.end if close else inner.span.end
        return ast.Parenthesized(
            inner=inner,
            span=SourceSpan(start=lparen.span.start, end=end),
        )

    def _try_parse_type_for_cast(self) -> Optional[ast.TypeRef]:
        """Attempt to parse a type without committing to it.

        Returns None on failure and rewinds its own position. The
        caller is responsible for deciding whether to commit based on
        what follows.
        """
        save = self._pos
        tok = self._peek()
        if tok.kind is not TokenKind.IDENT:
            return None
        t = self._parse_type()
        if t is None:
            self._pos = save
            return None
        return t

    def _parse_special_call(self, name_tok: Token) -> ast.Expr:
        name = name_tok.lexeme
        self._advance()  # name
        type_args: List[ast.TypeRef] = []
        if self._check(TokenKind.LT):
            type_args = self._parse_type_arg_list()
        if not self._expect(TokenKind.LPAREN, f"`(` after `{name}`"):
            return ast.Identifier(name=name, span=name_tok.span)
        inner = self._parse_expr()
        close = self._expect(TokenKind.RPAREN, f"`)` to close `{name}` call")
        end = close.span.end if close else inner.span.end
        full_span = SourceSpan(start=name_tok.span.start, end=end)

        if name == "unsafeCast":
            if not type_args:
                self.diagnostics.error(
                    "`unsafeCast` requires a type argument: `unsafeCast<Type>(value)`",
                    full_span,
                    code="SUT0105",
                )
                return ast.UnsafeCastExpr(
                    target_type=ast.TypeRef(name="<missing>", type_args=[], span=full_span),
                    expr=inner,
                    span=full_span,
                )
            return ast.UnsafeCastExpr(
                target_type=type_args[0], expr=inner, span=full_span
            )
        if name == "unsafeOverride":
            return ast.UnsafeOverrideExpr(expr=inner, span=full_span)
        if name == "defuzzy":
            return ast.DefuzzyExpr(expr=inner, span=full_span)
        if name == "embed":
            return ast.EmbedExpr(expr=inner, span=full_span)

        # Shouldn't get here because we checked _SPECIAL_CALL_NAMES.
        return ast.Call(
            callee=ast.Identifier(name=name, span=name_tok.span),
            type_args=type_args,
            args=[inner],
            span=full_span,
        )
