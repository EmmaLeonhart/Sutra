package org.akasha.intellij

import com.intellij.codeInsight.editorActions.SimpleTokenSetQuoteHandler

/**
 * Quote handler — tells the platform that Akasha's string tokens are both
 * `STRING` (`"..."`) and `INTERP_STRING` (`$"..."`). Enables quote
 * auto-insertion, string-continuation awareness, and the "typing inside a
 * string" detection used by other subsystems.
 */
class AkashaQuoteHandler : SimpleTokenSetQuoteHandler(
    AkashaTokenTypes.STRING,
    AkashaTokenTypes.INTERP_STRING,
)
