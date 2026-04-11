package org.sutra.intellij

import com.intellij.codeInsight.template.TemplateActionContext
import com.intellij.codeInsight.template.TemplateContextType

/**
 * Live template context — makes the templates in
 * `resources/liveTemplates/Sutra.xml` available inside `.su` files.
 *
 * The contextId `"SUTRA"` is referenced by every `<context>` entry in
 * the XML bundle and by the `liveTemplateContext` registration in
 * plugin.xml.
 */
class SutraLiveTemplateContext : TemplateContextType("Sutra") {
    override fun isInContext(templateActionContext: TemplateActionContext): Boolean {
        val file = templateActionContext.file
        return file.language.`is`(SutraLanguage)
    }
}
