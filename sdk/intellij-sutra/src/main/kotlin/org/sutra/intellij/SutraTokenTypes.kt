package org.sutra.intellij

/**
 * Token type catalog. Only classifies enough to drive the highlighter and
 * the brace matcher — not a full grammar. When the real Kotlin parser lands
 * we will keep these as leaf token kinds and add composite element types
 * alongside them.
 */
object SutraTokenTypes {
    // --- Trivia ---
    @JvmField val LINE_COMMENT   = SutraTokenType("LINE_COMMENT")
    @JvmField val DOC_COMMENT    = SutraTokenType("DOC_COMMENT")
    @JvmField val HASH_COMMENT   = SutraTokenType("HASH_COMMENT")
    @JvmField val BLOCK_COMMENT  = SutraTokenType("BLOCK_COMMENT")

    // --- Literals ---
    @JvmField val STRING          = SutraTokenType("STRING")
    @JvmField val INTERP_STRING   = SutraTokenType("INTERP_STRING")
    @JvmField val CHAR_LITERAL    = SutraTokenType("CHAR_LITERAL")
    @JvmField val NUMBER          = SutraTokenType("NUMBER")
    @JvmField val IMAG_LITERAL    = SutraTokenType("IMAG_LITERAL")
    @JvmField val BOOLEAN_LITERAL = SutraTokenType("BOOLEAN_LITERAL")
    @JvmField val UNKNOWN_LITERAL = SutraTokenType("UNKNOWN_LITERAL")

    // --- Identifiers ---
    @JvmField val KEYWORD        = SutraTokenType("KEYWORD")
    @JvmField val PRIMITIVE_TYPE = SutraTokenType("PRIMITIVE_TYPE")
    @JvmField val BUILTIN        = SutraTokenType("BUILTIN")
    @JvmField val TYPE_NAME      = SutraTokenType("TYPE_NAME")
    @JvmField val IDENTIFIER     = SutraTokenType("IDENTIFIER")

    // --- Operators ---
    @JvmField val OPERATOR       = SutraTokenType("OPERATOR")
    @JvmField val PIPE_FORWARD   = SutraTokenType("PIPE_FORWARD") // illegal, highlighted as error

    // --- Punctuation / brackets ---
    @JvmField val LBRACE   = SutraTokenType("LBRACE")
    @JvmField val RBRACE   = SutraTokenType("RBRACE")
    @JvmField val LPAREN   = SutraTokenType("LPAREN")
    @JvmField val RPAREN   = SutraTokenType("RPAREN")
    @JvmField val LBRACKET = SutraTokenType("LBRACKET")
    @JvmField val RBRACKET = SutraTokenType("RBRACKET")
    @JvmField val COMMA    = SutraTokenType("COMMA")
    @JvmField val SEMICOLON = SutraTokenType("SEMICOLON")
    @JvmField val DOT      = SutraTokenType("DOT")
}
