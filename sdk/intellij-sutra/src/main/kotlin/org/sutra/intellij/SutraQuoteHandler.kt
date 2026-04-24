package org.sutra.intellij

import com.intellij.codeInsight.editorActions.SimpleTokenSetQuoteHandler

/**
 * Quote handler — tells the platform that Sutra's quoted tokens are
 * `STRING` (`"..."`), `INTERP_STRING` (`$"..."`), and `CHAR_LITERAL`
 * (`'a'`). Enables quote auto-insertion, string-continuation awareness,
 * and the "typing inside a string" detection used by other subsystems.
 */
class SutraQuoteHandler : SimpleTokenSetQuoteHandler(
    SutraTokenTypes.STRING,
    SutraTokenTypes.INTERP_STRING,
    SutraTokenTypes.CHAR_LITERAL,
)
