package org.akasha.intellij

import com.intellij.codeInsight.template.TemplateActionContext
import com.intellij.codeInsight.template.TemplateContextType

/**
 * Live template context — makes the templates in
 * `resources/liveTemplates/Akasha.xml` available inside `.ak` files.
 *
 * The contextId `"AKASHA"` is referenced by every `<context>` entry in
 * the XML bundle and by the `liveTemplateContext` registration in
 * plugin.xml.
 */
class AkashaLiveTemplateContext : TemplateContextType("Akasha") {
    override fun isInContext(templateActionContext: TemplateActionContext): Boolean {
        val file = templateActionContext.file
        return file.language.`is`(AkashaLanguage)
    }
}
