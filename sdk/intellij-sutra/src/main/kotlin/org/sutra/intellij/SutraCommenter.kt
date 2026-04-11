package org.sutra.intellij

import com.intellij.lang.Commenter

/**
 * Comment toggling — Ctrl+/ and Ctrl+Shift+/.
 *
 * Sutra supports four comment forms (`//`, `/* */`, `///`, `#`), but line
 * toggling always emits `//` because that's the canonical form. The `#`
 * and `///` forms are kept in the grammar for tolerance, not for the line
 * commenter to generate.
 */
class SutraCommenter : Commenter {
    override fun getLineCommentPrefix(): String = "//"
    override fun getBlockCommentPrefix(): String = "/*"
    override fun getBlockCommentSuffix(): String = "*/"
    override fun getCommentedBlockCommentPrefix(): String? = null
    override fun getCommentedBlockCommentSuffix(): String? = null
}
