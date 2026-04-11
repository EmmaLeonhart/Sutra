package org.akasha.intellij

import com.intellij.lang.Language

/**
 * The Akasha [Language] singleton. Registered via plugin.xml and referenced
 * by every language-scoped extension point (parser definition, highlighter,
 * completion contributor, external annotator, etc.).
 */
object AkashaLanguage : Language("Akasha")
