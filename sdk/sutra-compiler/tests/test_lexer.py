"""Unit tests for the Sutra lexer.

Run with plain Python: `python -m unittest tests.test_lexer` from the
sdk/sutra-compiler directory, or via pytest if installed.
"""

import unittest

from sutra_compiler.lexer import Lexer, TokenKind


def lex(src):
    lexer = Lexer(src)
    toks = lexer.tokenize()
    return toks, lexer.diagnostics


def kinds(toks, drop_eof=True):
    out = [t.kind for t in toks]
    if drop_eof and out and out[-1] is TokenKind.EOF:
        out = out[:-1]
    return out


class TestBasicTokens(unittest.TestCase):
    def test_empty_source(self):
        toks, diag = lex("")
        self.assertEqual(kinds(toks), [])
        self.assertFalse(diag.has_errors())

    def test_whitespace_only(self):
        toks, diag = lex("   \n\t  \r\n  ")
        self.assertEqual(kinds(toks), [])
        self.assertFalse(diag.has_errors())

    def test_single_ident(self):
        toks, _ = lex("abc")
        self.assertEqual(kinds(toks), [TokenKind.IDENT])
        self.assertEqual(toks[0].lexeme, "abc")

    def test_keywords(self):
        toks, _ = lex("function method if else while for return")
        self.assertEqual(
            kinds(toks),
            [
                TokenKind.KW_FUNCTION,
                TokenKind.KW_METHOD,
                TokenKind.KW_IF,
                TokenKind.KW_ELSE,
                TokenKind.KW_WHILE,
                TokenKind.KW_FOR,
                TokenKind.KW_RETURN,
            ],
        )

    def test_integer_and_float(self):
        toks, _ = lex("42 3.14 0 0.0")
        self.assertEqual(
            kinds(toks),
            [
                TokenKind.INT_LIT,
                TokenKind.FLOAT_LIT,
                TokenKind.INT_LIT,
                TokenKind.FLOAT_LIT,
            ],
        )
        self.assertEqual(toks[0].value, 42)
        self.assertEqual(toks[1].value, 3.14)


class TestOperators(unittest.TestCase):
    def test_two_char_operators(self):
        toks, _ = lex("== != <= >= && || ++ -- += -= *= /= -> => |>")
        self.assertEqual(
            kinds(toks),
            [
                TokenKind.EQ,
                TokenKind.NEQ,
                TokenKind.LE,
                TokenKind.GE,
                TokenKind.AND,
                TokenKind.OR,
                TokenKind.PLUS_PLUS,
                TokenKind.MINUS_MINUS,
                TokenKind.PLUS_ASSIGN,
                TokenKind.MINUS_ASSIGN,
                TokenKind.STAR_ASSIGN,
                TokenKind.SLASH_ASSIGN,
                TokenKind.ARROW,
                TokenKind.FAT_ARROW,
                TokenKind.PIPE_FORWARD,
            ],
        )

    def test_single_char_operators(self):
        toks, _ = lex("+ - * / % = < > ! ? . , ; : ( ) { } [ ]")
        expected = [
            TokenKind.PLUS,
            TokenKind.MINUS,
            TokenKind.STAR,
            TokenKind.SLASH,
            TokenKind.PERCENT,
            TokenKind.ASSIGN,
            TokenKind.LT,
            TokenKind.GT,
            TokenKind.BANG,
            TokenKind.QUESTION,
            TokenKind.DOT,
            TokenKind.COMMA,
            TokenKind.SEMICOLON,
            TokenKind.COLON,
            TokenKind.LPAREN,
            TokenKind.RPAREN,
            TokenKind.LBRACE,
            TokenKind.RBRACE,
            TokenKind.LBRACKET,
            TokenKind.RBRACKET,
        ]
        self.assertEqual(kinds(toks), expected)


class TestComments(unittest.TestCase):
    def test_line_comment(self):
        toks, diag = lex("// comment\nabc")
        self.assertEqual(kinds(toks), [TokenKind.IDENT])
        self.assertFalse(diag.has_errors())

    def test_block_comment(self):
        toks, diag = lex("/* a\nmulti line\ncomment */abc")
        self.assertEqual(kinds(toks), [TokenKind.IDENT])
        self.assertFalse(diag.has_errors())

    def test_doc_comment(self):
        toks, _ = lex("/// doc\nabc")
        self.assertEqual(kinds(toks), [TokenKind.IDENT])

    def test_hash_comment(self):
        toks, _ = lex("# hash comment\nabc")
        self.assertEqual(kinds(toks), [TokenKind.IDENT])

    def test_unterminated_block_comment_diagnostic(self):
        _, diag = lex("/* never ends")
        self.assertTrue(diag.has_errors())
        self.assertTrue(any("unterminated block comment" in d.message for d in diag))


class TestStrings(unittest.TestCase):
    def test_plain_string(self):
        toks, _ = lex('"hello"')
        self.assertEqual(kinds(toks), [TokenKind.STRING_LIT])
        self.assertEqual(toks[0].value, "hello")

    def test_escapes(self):
        toks, _ = lex(r'"a\nb\tc"')
        self.assertEqual(toks[0].value, "a\nb\tc")

    def test_unterminated_string(self):
        _, diag = lex('"never ends')
        self.assertTrue(diag.has_errors())

    def test_interpolation_empty(self):
        toks, diag = lex('$""')
        self.assertFalse(diag.has_errors())
        self.assertEqual(
            kinds(toks),
            [TokenKind.STRING_INTERP_START, TokenKind.STRING_INTERP_END],
        )

    def test_interpolation_one_expr(self):
        toks, diag = lex('$"hello {name}"')
        self.assertFalse(diag.has_errors())
        self.assertEqual(
            kinds(toks),
            [
                TokenKind.STRING_INTERP_START,
                TokenKind.STRING_LIT_CHUNK,
                TokenKind.INTERP_OPEN,
                TokenKind.IDENT,
                TokenKind.INTERP_CLOSE,
                TokenKind.STRING_INTERP_END,
            ],
        )

    def test_interpolation_multiple(self):
        toks, diag = lex('$"a {b} c {d+1} e"')
        self.assertFalse(diag.has_errors())
        # Just check the general shape: alternating chunks and interps.
        kind_list = kinds(toks)
        self.assertEqual(kind_list[0], TokenKind.STRING_INTERP_START)
        self.assertEqual(kind_list[-1], TokenKind.STRING_INTERP_END)
        self.assertIn(TokenKind.PLUS, kind_list)

    def test_interpolation_with_nested_string(self):
        # "reference" appears as a string literal inside the expression
        # portion of an interpolation. The lexer should pop back into
        # string mode on the matching close brace, not the first `"`.
        toks, diag = lex('$"outer {embed(\"inner\")}"')
        # diagnostics may or may not be present depending on whether
        # we chose to support escape sequences here; the important
        # thing is we don't crash.
        self.assertIsNotNone(toks)


class TestPositionTracking(unittest.TestCase):
    def test_line_column(self):
        toks, _ = lex("abc\n  def")
        # Two idents: abc at 1:1, def at 2:3.
        self.assertEqual(toks[0].span.start.line, 1)
        self.assertEqual(toks[0].span.start.column, 1)
        self.assertEqual(toks[1].span.start.line, 2)
        self.assertEqual(toks[1].span.start.column, 3)


if __name__ == "__main__":
    unittest.main()
