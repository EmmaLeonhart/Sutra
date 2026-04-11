package org.akasha.intellij

/**
 * Token type catalog. Only classifies enough to drive the highlighter and
 * the brace matcher — not a full grammar. When the real Kotlin parser lands
 * we will keep these as leaf token kinds and add composite element types
 * alongside them.
 */
object AkashaTokenTypes {
    // --- Trivia ---
    @JvmField val LINE_COMMENT   = AkashaTokenType("LINE_COMMENT")
    @JvmField val DOC_COMMENT    = AkashaTokenType("DOC_COMMENT")
    @JvmField val HASH_COMMENT   = AkashaTokenType("HASH_COMMENT")
    @JvmField val BLOCK_COMMENT  = AkashaTokenType("BLOCK_COMMENT")

    // --- Literals ---
    @JvmField val STRING          = AkashaTokenType("STRING")
    @JvmField val INTERP_STRING   = AkashaTokenType("INTERP_STRING")
    @JvmField val NUMBER          = AkashaTokenType("NUMBER")
    @JvmField val BOOLEAN_LITERAL = AkashaTokenType("BOOLEAN_LITERAL")

    // --- Identifiers ---
    @JvmField val KEYWORD        = AkashaTokenType("KEYWORD")
    @JvmField val PRIMITIVE_TYPE = AkashaTokenType("PRIMITIVE_TYPE")
    @JvmField val BUILTIN        = AkashaTokenType("BUILTIN")
    @JvmField val TYPE_NAME      = AkashaTokenType("TYPE_NAME")
    @JvmField val IDENTIFIER     = AkashaTokenType("IDENTIFIER")

    // --- Operators ---
    @JvmField val OPERATOR       = AkashaTokenType("OPERATOR")
    @JvmField val PIPE_FORWARD   = AkashaTokenType("PIPE_FORWARD") // illegal, highlighted as error

    // --- Punctuation / brackets ---
    @JvmField val LBRACE   = AkashaTokenType("LBRACE")
    @JvmField val RBRACE   = AkashaTokenType("RBRACE")
    @JvmField val LPAREN   = AkashaTokenType("LPAREN")
    @JvmField val RPAREN   = AkashaTokenType("RPAREN")
    @JvmField val LBRACKET = AkashaTokenType("LBRACKET")
    @JvmField val RBRACKET = AkashaTokenType("RBRACKET")
    @JvmField val COMMA    = AkashaTokenType("COMMA")
    @JvmField val SEMICOLON = AkashaTokenType("SEMICOLON")
    @JvmField val DOT      = AkashaTokenType("DOT")
}
