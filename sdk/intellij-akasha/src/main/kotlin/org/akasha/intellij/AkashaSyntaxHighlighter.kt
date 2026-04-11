package org.akasha.intellij

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
class AkashaSyntaxHighlighter : SyntaxHighlighterBase() {

    override fun getHighlightingLexer(): Lexer = AkashaLexer()

    override fun getTokenHighlights(tokenType: IElementType): Array<TextAttributesKey> =
        when (tokenType) {
            AkashaTokenTypes.LINE_COMMENT    -> LINE_COMMENT_KEYS
            AkashaTokenTypes.DOC_COMMENT     -> DOC_COMMENT_KEYS
            AkashaTokenTypes.HASH_COMMENT    -> HASH_COMMENT_KEYS
            AkashaTokenTypes.BLOCK_COMMENT   -> BLOCK_COMMENT_KEYS

            AkashaTokenTypes.STRING          -> STRING_KEYS
            AkashaTokenTypes.INTERP_STRING   -> INTERP_STRING_KEYS
            AkashaTokenTypes.NUMBER          -> NUMBER_KEYS
            AkashaTokenTypes.BOOLEAN_LITERAL -> BOOLEAN_LITERAL_KEYS

            AkashaTokenTypes.KEYWORD         -> KEYWORD_KEYS
            AkashaTokenTypes.PRIMITIVE_TYPE  -> PRIMITIVE_TYPE_KEYS
            AkashaTokenTypes.BUILTIN         -> BUILTIN_KEYS
            AkashaTokenTypes.TYPE_NAME       -> TYPE_NAME_KEYS
            AkashaTokenTypes.IDENTIFIER      -> IDENTIFIER_KEYS

            AkashaTokenTypes.OPERATOR        -> OPERATOR_KEYS
            AkashaTokenTypes.PIPE_FORWARD    -> PIPE_FORWARD_KEYS

            AkashaTokenTypes.LBRACE,
            AkashaTokenTypes.RBRACE          -> BRACE_KEYS
            AkashaTokenTypes.LPAREN,
            AkashaTokenTypes.RPAREN          -> PAREN_KEYS
            AkashaTokenTypes.LBRACKET,
            AkashaTokenTypes.RBRACKET        -> BRACKET_KEYS

            AkashaTokenTypes.COMMA           -> COMMA_KEYS
            AkashaTokenTypes.SEMICOLON       -> SEMICOLON_KEYS
            AkashaTokenTypes.DOT             -> DOT_KEYS

            TokenType.BAD_CHARACTER          -> BAD_CHAR_KEYS
            else                             -> EMPTY_KEYS
        }

    companion object {
        // --- Public attribute keys (exposed by the color settings page) ---
        val LINE_COMMENT     = createTextAttributesKey("AKASHA_LINE_COMMENT", Defaults.LINE_COMMENT)
        val DOC_COMMENT      = createTextAttributesKey("AKASHA_DOC_COMMENT", Defaults.DOC_COMMENT)
        val HASH_COMMENT     = createTextAttributesKey("AKASHA_HASH_COMMENT", Defaults.LINE_COMMENT)
        val BLOCK_COMMENT    = createTextAttributesKey("AKASHA_BLOCK_COMMENT", Defaults.BLOCK_COMMENT)

        val STRING           = createTextAttributesKey("AKASHA_STRING", Defaults.STRING)
        val INTERP_STRING    = createTextAttributesKey("AKASHA_INTERP_STRING", Defaults.STRING)
        val NUMBER           = createTextAttributesKey("AKASHA_NUMBER", Defaults.NUMBER)
        val BOOLEAN_LITERAL  = createTextAttributesKey("AKASHA_BOOLEAN_LITERAL", Defaults.KEYWORD)

        val KEYWORD          = createTextAttributesKey("AKASHA_KEYWORD", Defaults.KEYWORD)
        val PRIMITIVE_TYPE   = createTextAttributesKey("AKASHA_PRIMITIVE_TYPE", Defaults.KEYWORD)
        val BUILTIN          = createTextAttributesKey("AKASHA_BUILTIN", Defaults.STATIC_METHOD)
        val TYPE_NAME        = createTextAttributesKey("AKASHA_TYPE_NAME", Defaults.CLASS_NAME)
        val IDENTIFIER       = createTextAttributesKey("AKASHA_IDENTIFIER", Defaults.IDENTIFIER)

        val OPERATOR         = createTextAttributesKey("AKASHA_OPERATOR", Defaults.OPERATION_SIGN)
        val PIPE_FORWARD     = createTextAttributesKey("AKASHA_PIPE_FORWARD", HighlighterColors.BAD_CHARACTER)

        val BRACES           = createTextAttributesKey("AKASHA_BRACES", Defaults.BRACES)
        val PARENTHESES      = createTextAttributesKey("AKASHA_PARENTHESES", Defaults.PARENTHESES)
        val BRACKETS         = createTextAttributesKey("AKASHA_BRACKETS", Defaults.BRACKETS)

        val COMMA            = createTextAttributesKey("AKASHA_COMMA", Defaults.COMMA)
        val SEMICOLON        = createTextAttributesKey("AKASHA_SEMICOLON", Defaults.SEMICOLON)
        val DOT              = createTextAttributesKey("AKASHA_DOT", Defaults.DOT)

        val BAD_CHARACTER    = createTextAttributesKey("AKASHA_BAD_CHARACTER", HighlighterColors.BAD_CHARACTER)

        // --- Array wrappers for getTokenHighlights ---
        private val LINE_COMMENT_KEYS    = arrayOf(LINE_COMMENT)
        private val DOC_COMMENT_KEYS     = arrayOf(DOC_COMMENT)
        private val HASH_COMMENT_KEYS    = arrayOf(HASH_COMMENT)
        private val BLOCK_COMMENT_KEYS   = arrayOf(BLOCK_COMMENT)
        private val STRING_KEYS          = arrayOf(STRING)
        private val INTERP_STRING_KEYS   = arrayOf(INTERP_STRING)
        private val NUMBER_KEYS          = arrayOf(NUMBER)
        private val BOOLEAN_LITERAL_KEYS = arrayOf(BOOLEAN_LITERAL)
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
