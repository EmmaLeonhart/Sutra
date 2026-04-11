package org.sutra.intellij.solution

import com.intellij.openapi.fileTypes.LanguageFileType
import com.intellij.openapi.fileTypes.PlainTextLanguage
import javax.swing.Icon

/**
 * File type registration for `.akproj` (Sutra Project) files.
 *
 * Same motivation as [SutraSolutionFileType] — plain-text file type
 * whose main purpose is recognizability by the Sutra solution tool
 * window and by other plugin components, rather than dedicated
 * syntax highlighting. See [SutraSolutionFileType]'s docstring for
 * the full rationale.
 */
class SutraProjectFileType : LanguageFileType(PlainTextLanguage.INSTANCE) {
    override fun getName(): String = "Sutra Project"
    override fun getDescription(): String =
        "Sutra project file (TOML; describes one project within a solution)"
    override fun getDefaultExtension(): String = "akproj"
    override fun getIcon(): Icon? = null

    companion object {
        @JvmField
        val INSTANCE = SutraProjectFileType()
    }
}
