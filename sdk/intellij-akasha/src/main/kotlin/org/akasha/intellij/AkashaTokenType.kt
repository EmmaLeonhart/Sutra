package org.akasha.intellij

import com.intellij.psi.tree.IElementType
import org.jetbrains.annotations.NonNls

/**
 * Marker [IElementType] for every token produced by [AkashaLexer]. We don't
 * yet have a real PSI tree (see [AkashaParserDefinition]), so these tokens
 * are consumed by the highlighter and commenter but never become first-class
 * PSI element types.
 */
class AkashaTokenType(@NonNls debugName: String) : IElementType(debugName, AkashaLanguage) {
    override fun toString(): String = "AkashaTokenType.${super.toString()}"
}
