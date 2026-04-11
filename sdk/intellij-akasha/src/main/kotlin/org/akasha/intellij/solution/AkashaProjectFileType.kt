package org.akasha.intellij.solution

import com.intellij.openapi.fileTypes.LanguageFileType
import com.intellij.openapi.fileTypes.PlainTextLanguage
import javax.swing.Icon

/**
 * File type registration for `.akproj` (Akasha Project) files.
 *
 * Same motivation as [AkashaSolutionFileType] — plain-text file type
 * whose main purpose is recognizability by the Akasha solution tool
 * window and by other plugin components, rather than dedicated
 * syntax highlighting. See [AkashaSolutionFileType]'s docstring for
 * the full rationale.
 */
class AkashaProjectFileType : LanguageFileType(PlainTextLanguage.INSTANCE) {
    override fun getName(): String = "Akasha Project"
    override fun getDescription(): String =
        "Akasha project file (TOML; describes one project within a solution)"
    override fun getDefaultExtension(): String = "akproj"
    override fun getIcon(): Icon? = null

    companion object {
        @JvmField
        val INSTANCE = AkashaProjectFileType()
    }
}
