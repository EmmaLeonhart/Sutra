package org.akasha.intellij

import com.intellij.lang.BracePair
import com.intellij.lang.PairedBraceMatcher
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IElementType

/**
 * Brace matcher wiring `{}`, `()`, and `[]` for Akasha. The platform uses
 * this for highlight-on-caret, auto-insertion, and the "go to matching
 * brace" action.
 *
 * Angle brackets (`<`, `>`) are deliberately not listed because Akasha
 * generics share the same tokens as comparison operators — matching them
 * needs real parser context.
 */
class AkashaBraceMatcher : PairedBraceMatcher {

    override fun getPairs(): Array<BracePair> = PAIRS

    override fun isPairedBracesAllowedBeforeType(lbraceType: IElementType, contextType: IElementType?): Boolean = true

    override fun getCodeConstructStart(file: PsiFile, openingBraceOffset: Int): Int = openingBraceOffset

    companion object {
        private val PAIRS: Array<BracePair> = arrayOf(
            BracePair(AkashaTokenTypes.LBRACE,   AkashaTokenTypes.RBRACE,   true),
            BracePair(AkashaTokenTypes.LPAREN,   AkashaTokenTypes.RPAREN,   false),
            BracePair(AkashaTokenTypes.LBRACKET, AkashaTokenTypes.RBRACKET, false),
        )
    }
}
