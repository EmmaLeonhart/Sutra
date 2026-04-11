package org.sutra.intellij

import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Unit tests for [SutraLexer]. These don't need a running IntelliJ test
 * application — the lexer is a pure string-in / token-out engine, so we
 * construct it directly and drive it over literal source buffers.
 *
 * Keeping these as plain JUnit 4 tests (no inheritance from
 * LightPlatformCodeInsightTestCase or similar) makes them fast and
 * dependency-light. When real PSI lands, we can add a parser-level test
 * base on top — these stay as the leaf-level token classification tests.
 */
class SutraLexerTest {

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private data class Tok(val type: IElementType?, val text: String)

    /**
     * Drive the lexer over [source] and return every produced token,
     * skipping only [TokenType.WHITE_SPACE] so assertions focus on
     * classified content.
     */
    private fun lex(source: String): List<Tok> {
        val lexer = SutraLexer()
        lexer.start(source, 0, source.length, 0)
        val out = mutableListOf<Tok>()
        while (lexer.tokenType != null) {
            val type = lexer.tokenType
            if (type != TokenType.WHITE_SPACE) {
                out.add(
                    Tok(
                        type,
                        source.substring(lexer.tokenStart, lexer.tokenEnd),
                    )
                )
            }
            lexer.advance()
        }
        return out
    }

    /** Convenience: return only the token *types*, in order. */
    private fun types(source: String): List<IElementType?> = lex(source).map { it.type }

    private fun assertSingleToken(source: String, expected: IElementType) {
        val tokens = lex(source)
        assertEquals("expected exactly one non-whitespace token in `$source`", 1, tokens.size)
        assertEquals(expected, tokens[0].type)
        assertEquals(source, tokens[0].text)
    }

    // ------------------------------------------------------------------
    // Trivia
    // ------------------------------------------------------------------

    @Test
    fun emptyInputProducesNoTokens() {
        val lexer = SutraLexer()
        lexer.start("", 0, 0, 0)
        assertNull(lexer.tokenType)
    }

    @Test
    fun whitespaceOnlyProducesNoNonTriviaTokens() {
        assertEquals(emptyList<Tok>(), lex("   \n\t  "))
    }

    @Test
    fun lineCommentIsClassified() {
        assertSingleToken("// just a comment", SutraTokenTypes.LINE_COMMENT)
    }

    @Test
    fun docCommentIsClassified() {
        assertSingleToken("/// a doc comment", SutraTokenTypes.DOC_COMMENT)
    }

    @Test
    fun hashCommentIsClassified() {
        assertSingleToken("# a hash comment", SutraTokenTypes.HASH_COMMENT)
    }

    @Test
    fun blockCommentIsClassified() {
        assertSingleToken("/* a\nblock\ncomment */", SutraTokenTypes.BLOCK_COMMENT)
    }

    @Test
    fun unterminatedBlockCommentDoesNotHang() {
        // Whatever the recovery policy is, the lexer must terminate and
        // produce *some* token for the dangling `/*`.
        val tokens = lex("/* no closer")
        assertNotNull(tokens.firstOrNull()?.type)
    }

    // ------------------------------------------------------------------
    // Literals
    // ------------------------------------------------------------------

    @Test
    fun plainStringIsClassified() {
        assertSingleToken("\"hello\"", SutraTokenTypes.STRING)
    }

    @Test
    fun interpolatedStringIsClassified() {
        assertSingleToken("\$\"hi {x}\"", SutraTokenTypes.INTERP_STRING)
    }

    @Test
    fun integerNumberIsClassified() {
        assertSingleToken("42", SutraTokenTypes.NUMBER)
    }

    @Test
    fun floatNumberIsClassified() {
        assertSingleToken("3.14", SutraTokenTypes.NUMBER)
    }

    @Test
    fun trueAndFalseAreBooleanLiterals() {
        assertSingleToken("true", SutraTokenTypes.BOOLEAN_LITERAL)
        assertSingleToken("false", SutraTokenTypes.BOOLEAN_LITERAL)
    }

    // ------------------------------------------------------------------
    // Identifiers, keywords, builtins, primitive types
    // ------------------------------------------------------------------

    @Test
    fun functionKeywordIsClassified() {
        assertSingleToken("function", SutraTokenTypes.KEYWORD)
    }

    @Test
    fun varAndConstAreKeywords() {
        assertSingleToken("var", SutraTokenTypes.KEYWORD)
        assertSingleToken("const", SutraTokenTypes.KEYWORD)
    }

    @Test
    fun controlFlowKeywordsAreClassified() {
        for (kw in listOf("if", "else", "while", "for", "foreach", "return")) {
            assertSingleToken(kw, SutraTokenTypes.KEYWORD)
        }
    }

    @Test
    fun vectorAndPermutationArePrimitiveTypes() {
        assertSingleToken("vector", SutraTokenTypes.PRIMITIVE_TYPE)
        assertSingleToken("permutation", SutraTokenTypes.PRIMITIVE_TYPE)
    }

    @Test
    fun scalarFuzzyStringBoolVoidArePrimitiveTypes() {
        for (t in listOf("scalar", "fuzzy", "string", "bool", "void")) {
            assertSingleToken(t, SutraTokenTypes.PRIMITIVE_TYPE)
        }
    }

    @Test
    fun snapAndBindAreBuiltins() {
        assertSingleToken("snap", SutraTokenTypes.BUILTIN)
        assertSingleToken("bind", SutraTokenTypes.BUILTIN)
    }

    @Test
    fun argmaxCosineAndIdentityPermutationAreBuiltins() {
        assertSingleToken("argmax_cosine", SutraTokenTypes.BUILTIN)
        assertSingleToken("identity_permutation", SutraTokenTypes.BUILTIN)
    }

    @Test
    fun plainIdentifierIsClassified() {
        assertSingleToken("myLocal", SutraTokenTypes.IDENTIFIER)
    }

    // ------------------------------------------------------------------
    // Operators and punctuation
    // ------------------------------------------------------------------

    @Test
    fun pipeForwardIsClassifiedAsIllegalToken() {
        // Sutra explicitly does not support |>; the lexer surfaces it as
        // its own token category so the highlighter can paint it red.
        assertSingleToken("|>", SutraTokenTypes.PIPE_FORWARD)
    }

    @Test
    fun bracketsAndPunctuationAreClassified() {
        val seq = "{}()[];,."
        val expected = listOf(
            SutraTokenTypes.LBRACE,
            SutraTokenTypes.RBRACE,
            SutraTokenTypes.LPAREN,
            SutraTokenTypes.RPAREN,
            SutraTokenTypes.LBRACKET,
            SutraTokenTypes.RBRACKET,
            SutraTokenTypes.SEMICOLON,
            SutraTokenTypes.COMMA,
            SutraTokenTypes.DOT,
        )
        assertEquals(expected, types(seq))
    }

    @Test
    fun simpleArithmeticOperatorsAreOperators() {
        // The lexer classifies each operator glyph as OPERATOR.
        for (op in listOf("+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">=")) {
            val tokens = lex(op)
            assertEquals("`$op` should lex to one token", 1, tokens.size)
            assertEquals("`$op` should be OPERATOR", SutraTokenTypes.OPERATOR, tokens[0].type)
        }
    }

    // ------------------------------------------------------------------
    // Integration: small realistic snippet
    // ------------------------------------------------------------------

    @Test
    fun smallFunctionSnippetClassifiesExpectedTokens() {
        val src = "function vector Bundle(vector a, vector b) { return a + b; }"
        val expected = listOf(
            SutraTokenTypes.KEYWORD,        // function
            SutraTokenTypes.PRIMITIVE_TYPE, // vector (return type)
            SutraTokenTypes.IDENTIFIER,     // Bundle
            SutraTokenTypes.LPAREN,
            SutraTokenTypes.PRIMITIVE_TYPE, // vector
            SutraTokenTypes.IDENTIFIER,     // a
            SutraTokenTypes.COMMA,
            SutraTokenTypes.PRIMITIVE_TYPE, // vector
            SutraTokenTypes.IDENTIFIER,     // b
            SutraTokenTypes.RPAREN,
            SutraTokenTypes.LBRACE,
            SutraTokenTypes.KEYWORD,        // return
            SutraTokenTypes.IDENTIFIER,     // a
            SutraTokenTypes.OPERATOR,       // +
            SutraTokenTypes.IDENTIFIER,     // b
            SutraTokenTypes.SEMICOLON,
            SutraTokenTypes.RBRACE,
        )
        assertEquals(expected, types(src))
    }
}
