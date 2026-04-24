package org.sutra.intellij

import com.intellij.lexer.Lexer
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors as Defaults
import com.intellij.openapi.editor.HighlighterColors
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.editor.colors.TextAttributesKey.createTextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighterBase
import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType

/**
 * Maps lexer tokens to highlight categories. Every category is exported as
 * a public [TextAttributesKey] so the color settings page can expose them
 * individually.
 */
class SutraSyntaxHighlighter : SyntaxHighlighterBase() {

    override fun getHighlightingLexer(): Lexer = SutraLexer()

    override fun getTokenHighlights(tokenType: IElementType): Array<TextAttributesKey> =
        when (tokenType) {
            SutraTokenTypes.LINE_COMMENT    -> LINE_COMMENT_KEYS
            SutraTokenTypes.DOC_COMMENT     -> DOC_COMMENT_KEYS
            SutraTokenTypes.HASH_COMMENT    -> HASH_COMMENT_KEYS
            SutraTokenTypes.BLOCK_COMMENT   -> BLOCK_COMMENT_KEYS

            SutraTokenTypes.STRING          -> STRING_KEYS
            SutraTokenTypes.INTERP_STRING   -> INTERP_STRING_KEYS
            SutraTokenTypes.CHAR_LITERAL    -> CHAR_LITERAL_KEYS
            SutraTokenTypes.NUMBER          -> NUMBER_KEYS
            SutraTokenTypes.IMAG_LITERAL    -> IMAG_LITERAL_KEYS
            SutraTokenTypes.BOOLEAN_LITERAL -> BOOLEAN_LITERAL_KEYS
            SutraTokenTypes.UNKNOWN_LITERAL -> UNKNOWN_LITERAL_KEYS

            SutraTokenTypes.KEYWORD         -> KEYWORD_KEYS
            SutraTokenTypes.PRIMITIVE_TYPE  -> PRIMITIVE_TYPE_KEYS
            SutraTokenTypes.BUILTIN         -> BUILTIN_KEYS
            SutraTokenTypes.TYPE_NAME       -> TYPE_NAME_KEYS
            SutraTokenTypes.IDENTIFIER      -> IDENTIFIER_KEYS

            SutraTokenTypes.OPERATOR        -> OPERATOR_KEYS
            SutraTokenTypes.PIPE_FORWARD    -> PIPE_FORWARD_KEYS

            SutraTokenTypes.LBRACE,
            SutraTokenTypes.RBRACE          -> BRACE_KEYS
            SutraTokenTypes.LPAREN,
            SutraTokenTypes.RPAREN          -> PAREN_KEYS
            SutraTokenTypes.LBRACKET,
            SutraTokenTypes.RBRACKET        -> BRACKET_KEYS

            SutraTokenTypes.COMMA           -> COMMA_KEYS
            SutraTokenTypes.SEMICOLON       -> SEMICOLON_KEYS
            SutraTokenTypes.DOT             -> DOT_KEYS

            TokenType.BAD_CHARACTER          -> BAD_CHAR_KEYS
            else                             -> EMPTY_KEYS
        }

    companion object {
        // --- Public attribute keys (exposed by the color settings page) ---
        // All four comment forms default to the same base color
        // (LINE_COMMENT — green in most themes) so //, ///, /* */, and #
        // render uniformly. They remain separate TextAttributesKey
        // instances so users can still rebind them individually in
        // Settings → Editor → Color Scheme → Sutra if they want
        // JavaDoc-style distinction later, but the out-of-the-box
        // experience is "a comment is a comment."
        val LINE_COMMENT     = createTextAttributesKey("SUTRA_LINE_COMMENT", Defaults.LINE_COMMENT)
        val DOC_COMMENT      = createTextAttributesKey("SUTRA_DOC_COMMENT", Defaults.LINE_COMMENT)
        val HASH_COMMENT     = createTextAttributesKey("SUTRA_HASH_COMMENT", Defaults.LINE_COMMENT)
        val BLOCK_COMMENT    = createTextAttributesKey("SUTRA_BLOCK_COMMENT", Defaults.LINE_COMMENT)

        val STRING           = createTextAttributesKey("SUTRA_STRING", Defaults.STRING)
        val INTERP_STRING    = createTextAttributesKey("SUTRA_INTERP_STRING", Defaults.STRING)
        val CHAR_LITERAL     = createTextAttributesKey("SUTRA_CHAR_LITERAL", Defaults.STRING)
        val NUMBER           = createTextAttributesKey("SUTRA_NUMBER", Defaults.NUMBER)
        val IMAG_LITERAL     = createTextAttributesKey("SUTRA_IMAG_LITERAL", Defaults.NUMBER)
        val BOOLEAN_LITERAL  = createTextAttributesKey("SUTRA_BOOLEAN_LITERAL", Defaults.KEYWORD)
        val UNKNOWN_LITERAL  = createTextAttributesKey("SUTRA_UNKNOWN_LITERAL", Defaults.KEYWORD)

        val KEYWORD          = createTextAttributesKey("SUTRA_KEYWORD", Defaults.KEYWORD)
        // Primitive types (vector, scalar, permutation, fuzzy, bool, …) are
        // visually *types*, not keywords. They used to inherit from
        // Defaults.KEYWORD, which made them the same color as `function` and
        // `return` — confusing because the user expects `vector` and a
        // user-defined `Cat` class to look alike. Inheriting from
        // Defaults.CLASS_NAME (same as TYPE_NAME below) makes `vector` and
        // `Cat` match out of the box.
        val PRIMITIVE_TYPE   = createTextAttributesKey("SUTRA_PRIMITIVE_TYPE", Defaults.CLASS_NAME)
        val BUILTIN          = createTextAttributesKey("SUTRA_BUILTIN", Defaults.STATIC_METHOD)
        val TYPE_NAME        = createTextAttributesKey("SUTRA_TYPE_NAME", Defaults.CLASS_NAME)
        val IDENTIFIER       = createTextAttributesKey("SUTRA_IDENTIFIER", Defaults.IDENTIFIER)

        val OPERATOR         = createTextAttributesKey("SUTRA_OPERATOR", Defaults.OPERATION_SIGN)
        val PIPE_FORWARD     = createTextAttributesKey("SUTRA_PIPE_FORWARD", HighlighterColors.BAD_CHARACTER)

        val BRACES           = createTextAttributesKey("SUTRA_BRACES", Defaults.BRACES)
        val PARENTHESES      = createTextAttributesKey("SUTRA_PARENTHESES", Defaults.PARENTHESES)
        val BRACKETS         = createTextAttributesKey("SUTRA_BRACKETS", Defaults.BRACKETS)

        val COMMA            = createTextAttributesKey("SUTRA_COMMA", Defaults.COMMA)
        val SEMICOLON        = createTextAttributesKey("SUTRA_SEMICOLON", Defaults.SEMICOLON)
        val DOT              = createTextAttributesKey("SUTRA_DOT", Defaults.DOT)

        val BAD_CHARACTER    = createTextAttributesKey("SUTRA_BAD_CHARACTER", HighlighterColors.BAD_CHARACTER)

        // --- Array wrappers for getTokenHighlights ---
        private val LINE_COMMENT_KEYS    = arrayOf(LINE_COMMENT)
        private val DOC_COMMENT_KEYS     = arrayOf(DOC_COMMENT)
        private val HASH_COMMENT_KEYS    = arrayOf(HASH_COMMENT)
        private val BLOCK_COMMENT_KEYS   = arrayOf(BLOCK_COMMENT)
        private val STRING_KEYS          = arrayOf(STRING)
        private val INTERP_STRING_KEYS   = arrayOf(INTERP_STRING)
        private val CHAR_LITERAL_KEYS    = arrayOf(CHAR_LITERAL)
        private val NUMBER_KEYS          = arrayOf(NUMBER)
        private val IMAG_LITERAL_KEYS    = arrayOf(IMAG_LITERAL)
        private val BOOLEAN_LITERAL_KEYS = arrayOf(BOOLEAN_LITERAL)
        private val UNKNOWN_LITERAL_KEYS = arrayOf(UNKNOWN_LITERAL)
        private val KEYWORD_KEYS         = arrayOf(KEYWORD)
        private val PRIMITIVE_TYPE_KEYS  = arrayOf(PRIMITIVE_TYPE)
        private val BUILTIN_KEYS         = arrayOf(BUILTIN)
        private val TYPE_NAME_KEYS       = arrayOf(TYPE_NAME)
        private val IDENTIFIER_KEYS      = arrayOf(IDENTIFIER)
        private val OPERATOR_KEYS        = arrayOf(OPERATOR)
        private val PIPE_FORWARD_KEYS    = arrayOf(PIPE_FORWARD)
        private val BRACE_KEYS           = arrayOf(BRACES)
        private val PAREN_KEYS           = arrayOf(PARENTHESES)
        private val BRACKET_KEYS         = arrayOf(BRACKETS)
        private val COMMA_KEYS           = arrayOf(COMMA)
        private val SEMICOLON_KEYS       = arrayOf(SEMICOLON)
        private val DOT_KEYS             = arrayOf(DOT)
        private val BAD_CHAR_KEYS        = arrayOf(BAD_CHARACTER)
        private val EMPTY_KEYS           = emptyArray<TextAttributesKey>()
    }
}
