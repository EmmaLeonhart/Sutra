package org.sutra.intellij

import com.intellij.openapi.fileTypes.LanguageFileType
import javax.swing.Icon

/**
 * File type for `.ak` source files. Registered through the `fileType`
 * extension in plugin.xml with `fieldName="INSTANCE"` so the IntelliJ
 * platform resolves this singleton reflectively.
 *
 * `object` declarations in Kotlin auto-generate a static `INSTANCE` field
 * of the enclosing type — that's the one the platform looks up, so no
 * explicit field is needed here.
 */
object SutraFileType : LanguageFileType(SutraLanguage) {
    override fun getName(): String = "Sutra"
    override fun getDescription(): String = "Sutra source file"
    override fun getDefaultExtension(): String = "ak"
    override fun getIcon(): Icon = SutraIcons.FILE
}
