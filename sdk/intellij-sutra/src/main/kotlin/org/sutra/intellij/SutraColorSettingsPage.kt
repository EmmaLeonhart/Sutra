package org.sutra.intellij

import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighter
import com.intellij.openapi.options.colors.AttributesDescriptor
import com.intellij.openapi.options.colors.ColorDescriptor
import com.intellij.openapi.options.colors.ColorSettingsPage
import javax.swing.Icon

/**
 * Color settings page — Settings → Editor → Color Scheme → Sutra.
 *
 * The preview text is hand-written to exercise every highlight category
 * that [SutraSyntaxHighlighter] maps. If you add a new token kind, add
 * an example here so users can see and rebind it.
 */
class SutraColorSettingsPage : ColorSettingsPage {

    override fun getIcon(): Icon = SutraIcons.FILE
    override fun getHighlighter(): SyntaxHighlighter = SutraSyntaxHighlighter()
    override fun getDemoText(): String = DEMO
    override fun getAdditionalHighlightingTagToDescriptorMap(): Map<String, TextAttributesKey>? = null
    override fun getAttributeDescriptors(): Array<AttributesDescriptor> = DESCRIPTORS
    override fun getColorDescriptors(): Array<ColorDescriptor> = ColorDescriptor.EMPTY_ARRAY
    override fun getDisplayName(): String = "Sutra"

    companion object {
        private val DESCRIPTORS: Array<AttributesDescriptor> = arrayOf(
            AttributesDescriptor("Keywords//Control keyword", SutraSyntaxHighlighter.KEYWORD),
            AttributesDescriptor("Keywords//Primitive type", SutraSyntaxHighlighter.PRIMITIVE_TYPE),
            AttributesDescriptor("Keywords//Boolean literal", SutraSyntaxHighlighter.BOOLEAN_LITERAL),
            AttributesDescriptor("Keywords//Unknown literal", SutraSyntaxHighlighter.UNKNOWN_LITERAL),

            AttributesDescriptor("Identifiers//Type name", SutraSyntaxHighlighter.TYPE_NAME),
            AttributesDescriptor("Identifiers//Builtin function", SutraSyntaxHighlighter.BUILTIN),
            AttributesDescriptor("Identifiers//Plain identifier", SutraSyntaxHighlighter.IDENTIFIER),

            AttributesDescriptor("Literals//String", SutraSyntaxHighlighter.STRING),
            AttributesDescriptor("Literals//Interpolated string", SutraSyntaxHighlighter.INTERP_STRING),
            AttributesDescriptor("Literals//Char", SutraSyntaxHighlighter.CHAR_LITERAL),
            AttributesDescriptor("Literals//Number", SutraSyntaxHighlighter.NUMBER),
            AttributesDescriptor("Literals//Imaginary (5i)", SutraSyntaxHighlighter.IMAG_LITERAL),

            AttributesDescriptor("Comments//Line comment (//)", SutraSyntaxHighlighter.LINE_COMMENT),
            AttributesDescriptor("Comments//Doc comment (///)", SutraSyntaxHighlighter.DOC_COMMENT),
            AttributesDescriptor("Comments//Hash comment (#)", SutraSyntaxHighlighter.HASH_COMMENT),
            AttributesDescriptor("Comments//Block comment (/* */)", SutraSyntaxHighlighter.BLOCK_COMMENT),

            AttributesDescriptor("Operators//Operator", SutraSyntaxHighlighter.OPERATOR),
            AttributesDescriptor("Operators//Illegal pipe-forward (|>)", SutraSyntaxHighlighter.PIPE_FORWARD),

            AttributesDescriptor("Punctuation//Braces", SutraSyntaxHighlighter.BRACES),
            AttributesDescriptor("Punctuation//Parentheses", SutraSyntaxHighlighter.PARENTHESES),
            AttributesDescriptor("Punctuation//Brackets", SutraSyntaxHighlighter.BRACKETS),
            AttributesDescriptor("Punctuation//Comma", SutraSyntaxHighlighter.COMMA),
            AttributesDescriptor("Punctuation//Semicolon", SutraSyntaxHighlighter.SEMICOLON),
            AttributesDescriptor("Punctuation//Dot", SutraSyntaxHighlighter.DOT),

            AttributesDescriptor("Bad character", SutraSyntaxHighlighter.BAD_CHARACTER),
        )

        private val DEMO = """
            /// Example Sutra program — exercises every highlight category.
            // line comment
            # hash comment is also allowed
            /* block
               comment */

            function vector Classify(vector input) {
                const expected = embed("cat");
                fuzzy q = unsafeCast<fuzzy>(Cosine(input, expected));
                if (defuzzy(q)) {
                    return Bundle(input, expected);
                } else {
                    return Normalize(input);
                }
            }

            function string Main() {
                char letter = 'a';
                complex c = 5 + 5i;
                trit verdict = unknown;
                var greeting = ${'$'}"Hello, {Classify(embed("world"))}";
                return greeting;
            }

            function.Main();
        """.trimIndent()
    }
}
