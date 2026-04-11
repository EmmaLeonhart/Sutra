package org.akasha.intellij

import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Unit tests for [AkashaLexer]. These don't need a running IntelliJ test
 * application — the lexer is a pure string-in / token-out engine, so we
 * construct it directly and drive it over literal source buffers.
 *
 * Keeping these as plain JUnit 4 tests (no inheritance from
 * LightPlatformCodeInsightTestCase or similar) makes them fast and
 * dependency-light. When real PSI lands, we can add a parser-level test
 * base on top — these stay as the leaf-level token classification tests.
 */
class AkashaLexerTest {

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
        val lexer = AkashaLexer()
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
        val lexer = AkashaLexer()
        lexer.start("", 0, 0, 0)
        assertNull(lexer.tokenType)
    }

    @Test
    fun whitespaceOnlyProducesNoNonTriviaTokens() {
        assertEquals(emptyList<Tok>(), lex("   \n\t  "))
    }

    @Test
    fun lineCommentIsClassified() {
        assertSingleToken("// just a comment", AkashaTokenTypes.LINE_COMMENT)
    }

    @Test
    fun docCommentIsClassified() {
        assertSingleToken("/// a doc comment", AkashaTokenTypes.DOC_COMMENT)
    }

    @Test
    fun hashCommentIsClassified() {
        assertSingleToken("# a hash comment", AkashaTokenTypes.HASH_COMMENT)
    }

    @Test
    fun blockCommentIsClassified() {
        assertSingleToken("/* a\nblock\ncomment */", AkashaTokenTypes.BLOCK_COMMENT)
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
        assertSingleToken("\"hello\"", AkashaTokenTypes.STRING)
    }

    @Test
    fun interpolatedStringIsClassified() {
        assertSingleToken("\$\"hi {x}\"", AkashaTokenTypes.INTERP_STRING)
    }

    @Test
    fun integerNumberIsClassified() {
        assertSingleToken("42", AkashaTokenTypes.NUMBER)
    }

    @Test
    fun floatNumberIsClassified() {
        assertSingleToken("3.14", AkashaTokenTypes.NUMBER)
    }

    @Test
    fun trueAndFalseAreBooleanLiterals() {
        assertSingleToken("true", AkashaTokenTypes.BOOLEAN_LITERAL)
        assertSingleToken("false", AkashaTokenTypes.BOOLEAN_LITERAL)
    }

    // ------------------------------------------------------------------
    // Identifiers, keywords, builtins, primitive types
    // ------------------------------------------------------------------

    @Test
    fun functionKeywordIsClassified() {
        assertSingleToken("function", AkashaTokenTypes.KEYWORD)
    }

    @Test
    fun varAndConstAreKeywords() {
        assertSingleToken("var", AkashaTokenTypes.KEYWORD)
        assertSingleToken("const", AkashaTokenTypes.KEYWORD)
    }

    @Test
    fun controlFlowKeywordsAreClassified() {
        for (kw in listOf("if", "else", "while", "for", "foreach", "return")) {
            assertSingleToken(kw, AkashaTokenTypes.KEYWORD)
        }
    }

    @Test
    fun vectorAndPermutationArePrimitiveTypes() {
        assertSingleToken("vector", AkashaTokenTypes.PRIMITIVE_TYPE)
        assertSingleToken("permutation", AkashaTokenTypes.PRIMITIVE_TYPE)
    }

    @Test
    fun scalarFuzzyStringBoolVoidArePrimitiveTypes() {
        for (t in listOf("scalar", "fuzzy", "string", "bool", "void")) {
            assertSingleToken(t, AkashaTokenTypes.PRIMITIVE_TYPE)
        }
    }

    @Test
    fun snapAndBindAreBuiltins() {
        assertSingleToken("snap", AkashaTokenTypes.BUILTIN)
        assertSingleToken("bind", AkashaTokenTypes.BUILTIN)
    }

    @Test
    fun argmaxCosineAndIdentityPermutationAreBuiltins() {
        assertSingleToken("argmax_cosine", AkashaTokenTypes.BUILTIN)
        assertSingleToken("identity_permutation", AkashaTokenTypes.BUILTIN)
    }

    @Test
    fun plainIdentifierIsClassified() {
        assertSingleToken("myLocal", AkashaTokenTypes.IDENTIFIER)
    }

    // ------------------------------------------------------------------
    // Operators and punctuation
    // ------------------------------------------------------------------

    @Test
    fun pipeForwardIsClassifiedAsIllegalToken() {
        // Akasha explicitly does not support |>; the lexer surfaces it as
        // its own token category so the highlighter can paint it red.
        assertSingleToken("|>", AkashaTokenTypes.PIPE_FORWARD)
    }

    @Test
    fun bracketsAndPunctuationAreClassified() {
        val seq = "{}()[];,."
        val expected = listOf(
            AkashaTokenTypes.LBRACE,
            AkashaTokenTypes.RBRACE,
            AkashaTokenTypes.LPAREN,
            AkashaTokenTypes.RPAREN,
            AkashaTokenTypes.LBRACKET,
            AkashaTokenTypes.RBRACKET,
            AkashaTokenTypes.SEMICOLON,
            AkashaTokenTypes.COMMA,
            AkashaTokenTypes.DOT,
        )
        assertEquals(expected, types(seq))
    }

    @Test
    fun simpleArithmeticOperatorsAreOperators() {
        // The lexer classifies each operator glyph as OPERATOR.
        for (op in listOf("+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">=")) {
            val tokens = lex(op)
            assertEquals("`$op` should lex to one token", 1, tokens.size)
            assertEquals("`$op` should be OPERATOR", AkashaTokenTypes.OPERATOR, tokens[0].type)
        }
    }

    // ------------------------------------------------------------------
    // Integration: small realistic snippet
    // ------------------------------------------------------------------

    @Test
    fun smallFunctionSnippetClassifiesExpectedTokens() {
        val src = "function vector Bundle(vector a, vector b) { return a + b; }"
        val expected = listOf(
            AkashaTokenTypes.KEYWORD,        // function
            AkashaTokenTypes.PRIMITIVE_TYPE, // vector (return type)
            AkashaTokenTypes.IDENTIFIER,     // Bundle
            AkashaTokenTypes.LPAREN,
            AkashaTokenTypes.PRIMITIVE_TYPE, // vector
            AkashaTokenTypes.IDENTIFIER,     // a
            AkashaTokenTypes.COMMA,
            AkashaTokenTypes.PRIMITIVE_TYPE, // vector
            AkashaTokenTypes.IDENTIFIER,     // b
            AkashaTokenTypes.RPAREN,
            AkashaTokenTypes.LBRACE,
            AkashaTokenTypes.KEYWORD,        // return
            AkashaTokenTypes.IDENTIFIER,     // a
            AkashaTokenTypes.OPERATOR,       // +
            AkashaTokenTypes.IDENTIFIER,     // b
            AkashaTokenTypes.SEMICOLON,
            AkashaTokenTypes.RBRACE,
        )
        assertEquals(expected, types(src))
    }
}
