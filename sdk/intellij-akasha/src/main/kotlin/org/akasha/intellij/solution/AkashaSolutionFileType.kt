package org.akasha.intellij.solution

import com.intellij.openapi.fileTypes.LanguageFileType
import com.intellij.openapi.fileTypes.PlainTextLanguage
import javax.swing.Icon

/**
 * File type registration for `.aksln` (Akasha Solution) files.
 *
 * These files are TOML documents per `planning/akasha-spec/22-solutions.md`.
 * We register them as a plain-text file type here rather than declaring
 * them as a dedicated Akasha Solution language because:
 *
 *   1. We do not want to write our own TOML lexer/parser.
 *   2. Depending on the IntelliJ TOML plugin as a hard plugin-xml
 *      dependency would complicate the build and require users to have
 *      that plugin enabled. It is bundled with IDEA Community 2024.1
 *      but not with every distribution.
 *
 * Users who want full TOML syntax highlighting can add the `.aksln`
 * extension to their TOML file type association in
 * Settings → Editor → File Types → TOML → + → `*.aksln`. That is a
 * one-click workaround that preserves our zero-dependency design.
 *
 * The file type exists primarily so the Akasha Solution tool window
 * can recognize these files when scanning the project tree and so
 * that double-clicking a solution node in the tool window opens the
 * correct editor view.
 */
class AkashaSolutionFileType : LanguageFileType(PlainTextLanguage.INSTANCE) {
    override fun getName(): String = "Akasha Solution"
    override fun getDescription(): String =
        "Akasha solution file (TOML; enumerates the projects in a solution)"
    override fun getDefaultExtension(): String = "aksln"
    override fun getIcon(): Icon? = null  // future: bundle an icon

    companion object {
        @JvmField
        val INSTANCE = AkashaSolutionFileType()
    }
}
