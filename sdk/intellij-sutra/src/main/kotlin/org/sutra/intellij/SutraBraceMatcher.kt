package org.sutra.intellij

import com.intellij.lang.BracePair
import com.intellij.lang.PairedBraceMatcher
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IElementType

/**
 * Brace matcher wiring `{}`, `()`, and `[]` for Sutra. The platform uses
 * this for highlight-on-caret, auto-insertion, and the "go to matching
 * brace" action.
 *
 * Angle brackets (`<`, `>`) are deliberately not listed because Sutra
 * generics share the same tokens as comparison operators — matching them
 * needs real parser context.
 */
class SutraBraceMatcher : PairedBraceMatcher {

    override fun getPairs(): Array<BracePair> = PAIRS

    override fun isPairedBracesAllowedBeforeType(lbraceType: IElementType, contextType: IElementType?): Boolean = true

    override fun getCodeConstructStart(file: PsiFile, openingBraceOffset: Int): Int = openingBraceOffset

    companion object {
        private val PAIRS: Array<BracePair> = arrayOf(
            BracePair(SutraTokenTypes.LBRACE,   SutraTokenTypes.RBRACE,   true),
            BracePair(SutraTokenTypes.LPAREN,   SutraTokenTypes.RPAREN,   false),
            BracePair(SutraTokenTypes.LBRACKET, SutraTokenTypes.RBRACKET, false),
        )
    }
}
