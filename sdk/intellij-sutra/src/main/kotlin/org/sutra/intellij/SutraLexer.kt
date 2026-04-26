package org.sutra.intellij

import com.intellij.lexer.LexerBase
import com.intellij.psi.TokenType
import com.intellij.psi.tree.IElementType

/**
 * Hand-written lexer for Sutra. v0.1 scope: produces enough token
 * classification for syntax highlighting, brace matching, and the
 * `commentTokens`/`stringLiteralElements` hooks used by the platform.
 *
 * This is intentionally not a full parser — Sutra's real grammar lives
 * in `sdk/sutra-compiler/sutra_compiler/parser.py` and is reached via
 * [SutraExternalAnnotator]. A future Kotlin port (or a JFlex-based
 * regeneration from the Python reference) will replace this.
 *
 * Keep the keyword / primitive / builtin sets in sync with:
 *   - `sdk/sutra-compiler/sutra_compiler/lexer.py`
 *   - `sdk/vscode-sutra/syntaxes/sutra.tmLanguage.json`
 *   - `sdk/vscode-sutra/src/extension.ts`
 *   - `planning/sutra-spec/21-builtins.md`
 */
class SutraLexer : LexerBase() {

    private var buffer: CharSequence = ""
    private var bufferEnd: Int = 0
    private var tokenStart: Int = 0
    private var tokenEnd: Int = 0
    private var tokenType: IElementType? = null
    private var stateValue: Int = 0

    override fun start(buffer: CharSequence, startOffset: Int, endOffset: Int, initialState: Int) {
        this.buffer = buffer
        this.bufferEnd = endOffset
        this.tokenStart = startOffset
        this.tokenEnd = startOffset
        this.stateValue = initialState
        advance()
    }

    override fun getState(): Int = stateValue
    override fun getTokenType(): IElementType? = tokenType
    override fun getTokenStart(): Int = tokenStart
    override fun getTokenEnd(): Int = tokenEnd
    override fun getBufferSequence(): CharSequence = buffer
    override fun getBufferEnd(): Int = bufferEnd

    override fun advance() {
        tokenStart = tokenEnd
        if (tokenStart >= bufferEnd) {
            tokenType = null
            return
        }

        val c = buffer[tokenStart]

        // --- Whitespace ---
        if (c.isWhitespace()) {
            var i = tokenStart + 1
            while (i < bufferEnd && buffer[i].isWhitespace()) i++
            tokenEnd = i
            tokenType = TokenType.WHITE_SPACE
            return
        }

        // --- `//` line / `///` doc / `/* */` block comments ---
        if (c == '/' && tokenStart + 1 < bufferEnd) {
            val next = buffer[tokenStart + 1]
            if (next == '/') {
                val isDoc = tokenStart + 2 < bufferEnd && buffer[tokenStart + 2] == '/'
                var i = tokenStart + 2
                while (i < bufferEnd && buffer[i] != '\n') i++
                tokenEnd = i
                tokenType = if (isDoc) SutraTokenTypes.DOC_COMMENT else SutraTokenTypes.LINE_COMMENT
                return
            }
            if (next == '*') {
                var i = tokenStart + 2
                while (i + 1 < bufferEnd && !(buffer[i] == '*' && buffer[i + 1] == '/')) i++
                tokenEnd = if (i + 1 < bufferEnd) i + 2 else bufferEnd
                tokenType = SutraTokenTypes.BLOCK_COMMENT
                return
            }
        }

        // --- `#` hash comment ---
        if (c == '#') {
            var i = tokenStart + 1
            while (i < bufferEnd && buffer[i] != '\n') i++
            tokenEnd = i
            tokenType = SutraTokenTypes.HASH_COMMENT
            return
        }

        // --- Interpolated string `$"..."` ---
        if (c == '$' && tokenStart + 1 < bufferEnd && buffer[tokenStart + 1] == '"') {
            tokenEnd = scanStringBody(tokenStart + 2)
            tokenType = SutraTokenTypes.INTERP_STRING
            return
        }

        // --- Plain string `"..."` ---
        if (c == '"') {
            tokenEnd = scanStringBody(tokenStart + 1)
            tokenType = SutraTokenTypes.STRING
            return
        }

        // --- Char literal `'a'`, `'\n'`, `'\\''` ---
        // Matches the Python lexer's CHAR_LIT handling. Backslash
        // escapes consume two source chars; the closing quote is
        // expected to appear on the same line.
        if (c == '\'') {
            tokenEnd = scanCharBody(tokenStart + 1)
            tokenType = SutraTokenTypes.CHAR_LITERAL
            return
        }

        // --- Numeric literal (with optional imaginary-unit suffix) ---
        // `5`, `3.14` are NUMBER; `5i`, `3.14i` are IMAG_LITERAL.
        // An `i` right after the digits only counts as the imaginary
        // suffix — if the next char after `i` is an identifier char
        // (e.g. `5index`) the `i` belongs to the following identifier.
        if (c.isDigit()) {
            var i = tokenStart + 1
            while (i < bufferEnd && buffer[i].isDigit()) i++
            if (i + 1 < bufferEnd && buffer[i] == '.' && buffer[i + 1].isDigit()) {
                i += 2
                while (i < bufferEnd && buffer[i].isDigit()) i++
            }
            if (i < bufferEnd && buffer[i] == 'i' &&
                (i + 1 >= bufferEnd || !(buffer[i + 1].isLetterOrDigit() || buffer[i + 1] == '_'))
            ) {
                tokenEnd = i + 1
                tokenType = SutraTokenTypes.IMAG_LITERAL
                return
            }
            tokenEnd = i
            tokenType = SutraTokenTypes.NUMBER
            return
        }

        // --- Identifier / keyword / primitive type / builtin / type-name ---
        if (c.isLetter() || c == '_') {
            var i = tokenStart + 1
            while (i < bufferEnd) {
                val ch = buffer[i]
                if (!ch.isLetterOrDigit() && ch != '_') break
                i++
            }
            tokenEnd = i
            val word = buffer.subSequence(tokenStart, i).toString()
            tokenType = classifyWord(word)
            return
        }

        // --- Illegal pipe-forward `|>` (SUT0110) ---
        if (c == '|' && tokenStart + 1 < bufferEnd && buffer[tokenStart + 1] == '>') {
            tokenEnd = tokenStart + 2
            tokenType = SutraTokenTypes.PIPE_FORWARD
            return
        }

        // --- Two-character operators ---
        if (tokenStart + 1 < bufferEnd) {
            val pair = "${c}${buffer[tokenStart + 1]}"
            if (pair in TWO_CHAR_OPERATORS) {
                tokenEnd = tokenStart + 2
                tokenType = SutraTokenTypes.OPERATOR
                return
            }
        }

        // --- Bracket / delimiter / single-char operators / unknown ---
        tokenEnd = tokenStart + 1
        tokenType = when (c) {
            '{' -> SutraTokenTypes.LBRACE
            '}' -> SutraTokenTypes.RBRACE
            '(' -> SutraTokenTypes.LPAREN
            ')' -> SutraTokenTypes.RPAREN
            '[' -> SutraTokenTypes.LBRACKET
            ']' -> SutraTokenTypes.RBRACKET
            ',' -> SutraTokenTypes.COMMA
            ';' -> SutraTokenTypes.SEMICOLON
            '.' -> SutraTokenTypes.DOT
            in SINGLE_CHAR_OPERATORS -> SutraTokenTypes.OPERATOR
            else -> TokenType.BAD_CHARACTER
        }
    }

    /**
     * Scan the body of a char literal starting at [bodyStart] (just past
     * the opening single quote). Returns the offset immediately after the
     * closing quote — or the end of the line / buffer if unterminated, so
     * an unterminated literal still produces a single token rather than
     * cascading bad-character tokens.
     */
    private fun scanCharBody(bodyStart: Int): Int {
        var i = bodyStart
        while (i < bufferEnd) {
            val ch = buffer[i]
            if (ch == '\\' && i + 1 < bufferEnd) {
                i += 2
                continue
            }
            if (ch == '\n') return i
            if (ch == '\'') return i + 1
            i++
        }
        return bufferEnd
    }

    /**
     * Scan the body of a string literal starting at [bodyStart] (just past
     * the opening quote). Returns the offset immediately after the closing
     * quote — or [bufferEnd] if the string is unterminated.
     */
    private fun scanStringBody(bodyStart: Int): Int {
        var i = bodyStart
        while (i < bufferEnd) {
            val ch = buffer[i]
            if (ch == '\\' && i + 1 < bufferEnd) {
                i += 2
                continue
            }
            if (ch == '\n') return i      // unterminated on this line
            if (ch == '"') return i + 1   // consume closing quote
            i++
        }
        return bufferEnd
    }

    private fun classifyWord(word: String): IElementType = when {
        word in KEYWORDS -> SutraTokenTypes.KEYWORD
        word in PRIMITIVE_TYPES -> SutraTokenTypes.PRIMITIVE_TYPE
        word in BUILTINS -> SutraTokenTypes.BUILTIN
        word in BOOLEAN_LITERALS -> SutraTokenTypes.BOOLEAN_LITERAL
        word in UNKNOWN_LITERALS -> SutraTokenTypes.UNKNOWN_LITERAL
        word.isNotEmpty() && word[0].isUpperCase() -> SutraTokenTypes.TYPE_NAME
        else -> SutraTokenTypes.IDENTIFIER
    }

    companion object {
        private val KEYWORDS: Set<String> = setOf(
            "function", "method", "operator",
            "public", "private", "static", "implicit",
            "var", "const", "new",
            "return", "if", "else", "while", "for", "foreach", "in", "do",
            "loop", "as",
            "try", "catch", "break", "continue", "this",
            // Explicit deferred-init marker. Only legal as a var-decl
            // initializer (`int i = wait;`). Highlighted as a keyword
            // because it's a reserved word, even though it occupies an
            // expression position grammatically.
            "wait",
            // User-defined ontology classes — `class Name extends
            // Parent { }`. MVP scope is empty bodies + single
            // inheritance bottoming out at a primitive type.
            "class", "extends",
        )

        private val PRIMITIVE_TYPES: Set<String> = setOf(
            "scalar", "vector", "matrix", "tuple",
            "string", "bool", "fuzzy", "void",
            "permutation", "map",
            // Numeric + truth-family primitives added alongside char
            // literal / imaginary-unit support. Kept in sync with
            // `PRIMITIVE_TYPE_NAMES` in sutra_compiler/lexer.py.
            "char", "int", "float", "complex", "trit",
        )

        private val BUILTINS: Set<String> = setOf(
            // v0.1 high-level builtins (documented in the VS Code extension)
            "embed", "defuzzy", "unsafeCast", "unsafeOverride",
            "snap", "similarity", "Cosine",
            "Bundle", "Bind", "Blend", "Normalize",
            // VSA builtin signatures from planning/sutra-spec/21-builtins.md
            "bind", "unbind", "bundle", "permute", "compose",
            "basis_vector", "permutation_key", "identity_permutation",
            "argmax_cosine", "select",
        )

        private val BOOLEAN_LITERALS: Set<String> = setOf("true", "false")

        // The neutral point on the truth axis — the three-valued-logic
        // `?`. Both spellings hit `TokenKind.KW_UNKNOWN` in the Python
        // lexer; the IDE highlights them as a literal, not a keyword,
        // to match how `true` / `false` are styled.
        private val UNKNOWN_LITERALS: Set<String> = setOf("unknown", "unk")

        private val TWO_CHAR_OPERATORS: Set<String> = setOf(
            "==", "!=", "<=", ">=", "&&", "||",
            "++", "--", "+=", "-=", "*=", "/=",
        )

        private const val SINGLE_CHAR_OPERATORS: String = "+-*/%<>=!&|^~?:"
    }
}
