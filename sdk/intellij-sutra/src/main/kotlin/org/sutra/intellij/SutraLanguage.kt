package org.sutra.intellij

import com.intellij.lang.Language

/**
 * The Sutra [Language] singleton. Registered via plugin.xml and referenced
 * by every language-scoped extension point (parser definition, highlighter,
 * completion contributor, external annotator, etc.).
 */
object SutraLanguage : Language("Sutra")
