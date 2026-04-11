package org.sutra.intellij

import com.intellij.psi.tree.IElementType
import org.jetbrains.annotations.NonNls

/**
 * Marker [IElementType] for every token produced by [SutraLexer]. We don't
 * yet have a real PSI tree (see [SutraParserDefinition]), so these tokens
 * are consumed by the highlighter and commenter but never become first-class
 * PSI element types.
 */
class SutraTokenType(@NonNls debugName: String) : IElementType(debugName, SutraLanguage) {
    override fun toString(): String = "SutraTokenType.${super.toString()}"
}
