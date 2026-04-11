package org.akasha.intellij

import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighter
import com.intellij.openapi.options.colors.AttributesDescriptor
import com.intellij.openapi.options.colors.ColorDescriptor
import com.intellij.openapi.options.colors.ColorSettingsPage
import javax.swing.Icon

/**
 * Color settings page — Settings → Editor → Color Scheme → Akasha.
 *
 * The preview text is hand-written to exercise every highlight category
 * that [AkashaSyntaxHighlighter] maps. If you add a new token kind, add
 * an example here so users can see and rebind it.
 */
class AkashaColorSettingsPage : ColorSettingsPage {

    override fun getIcon(): Icon = AkashaIcons.FILE
    override fun getHighlighter(): SyntaxHighlighter = AkashaSyntaxHighlighter()
    override fun getDemoText(): String = DEMO
    override fun getAdditionalHighlightingTagToDescriptorMap(): Map<String, TextAttributesKey>? = null
    override fun getAttributeDescriptors(): Array<AttributesDescriptor> = DESCRIPTORS
    override fun getColorDescriptors(): Array<ColorDescriptor> = ColorDescriptor.EMPTY_ARRAY
    override fun getDisplayName(): String = "Akasha"

    companion object {
        private val DESCRIPTORS: Array<AttributesDescriptor> = arrayOf(
            AttributesDescriptor("Keywords//Control keyword", AkashaSyntaxHighlighter.KEYWORD),
            AttributesDescriptor("Keywords//Primitive type", AkashaSyntaxHighlighter.PRIMITIVE_TYPE),
            AttributesDescriptor("Keywords//Boolean literal", AkashaSyntaxHighlighter.BOOLEAN_LITERAL),

            AttributesDescriptor("Identifiers//Type name", AkashaSyntaxHighlighter.TYPE_NAME),
            AttributesDescriptor("Identifiers//Builtin function", AkashaSyntaxHighlighter.BUILTIN),
            AttributesDescriptor("Identifiers//Plain identifier", AkashaSyntaxHighlighter.IDENTIFIER),

            AttributesDescriptor("Literals//String", AkashaSyntaxHighlighter.STRING),
            AttributesDescriptor("Literals//Interpolated string", AkashaSyntaxHighlighter.INTERP_STRING),
            AttributesDescriptor("Literals//Number", AkashaSyntaxHighlighter.NUMBER),

            AttributesDescriptor("Comments//Line comment (//)", AkashaSyntaxHighlighter.LINE_COMMENT),
            AttributesDescriptor("Comments//Doc comment (///)", AkashaSyntaxHighlighter.DOC_COMMENT),
            AttributesDescriptor("Comments//Hash comment (#)", AkashaSyntaxHighlighter.HASH_COMMENT),
            AttributesDescriptor("Comments//Block comment (/* */)", AkashaSyntaxHighlighter.BLOCK_COMMENT),

            AttributesDescriptor("Operators//Operator", AkashaSyntaxHighlighter.OPERATOR),
            AttributesDescriptor("Operators//Illegal pipe-forward (|>)", AkashaSyntaxHighlighter.PIPE_FORWARD),

            AttributesDescriptor("Punctuation//Braces", AkashaSyntaxHighlighter.BRACES),
            AttributesDescriptor("Punctuation//Parentheses", AkashaSyntaxHighlighter.PARENTHESES),
            AttributesDescriptor("Punctuation//Brackets", AkashaSyntaxHighlighter.BRACKETS),
            AttributesDescriptor("Punctuation//Comma", AkashaSyntaxHighlighter.COMMA),
            AttributesDescriptor("Punctuation//Semicolon", AkashaSyntaxHighlighter.SEMICOLON),
            AttributesDescriptor("Punctuation//Dot", AkashaSyntaxHighlighter.DOT),

            AttributesDescriptor("Bad character", AkashaSyntaxHighlighter.BAD_CHARACTER),
        )

        private val DEMO = """
            /// Example Akasha program — exercises every highlight category.
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
                var greeting = ${'$'}"Hello, {Classify(embed("world"))}";
                return greeting;
            }

            function.Main();
        """.trimIndent()
    }
}
