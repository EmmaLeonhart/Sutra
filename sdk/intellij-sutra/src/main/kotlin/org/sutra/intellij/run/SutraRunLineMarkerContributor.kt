package org.sutra.intellij.run

import com.intellij.execution.lineMarker.ExecutorAction
import com.intellij.execution.lineMarker.RunLineMarkerContributor
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiWhiteSpace
import com.intellij.psi.util.elementType
import org.sutra.intellij.SutraTokenTypes

/**
 * Puts a gutter ▶ icon next to `function ... main(...)` declarations so
 * one click runs the current .su file via [SutraRunConfigurationProducer].
 * Matches a leaf IDENTIFIER with text "main" whose nearest preceding
 * non-trivia keyword is `function`.
 */
class SutraRunLineMarkerContributor : RunLineMarkerContributor() {
    override fun getInfo(element: PsiElement): Info? {
        if (element.firstChild != null) return null
        if (element.elementType != SutraTokenTypes.IDENTIFIER) return null
        if (element.text != "main") return null
        if (!precededByFunctionKeyword(element)) return null
        val actions = ExecutorAction.getActions(0)
        return Info(
            com.intellij.icons.AllIcons.RunConfigurations.TestState.Run,
            actions,
        ) { "Run '${element.containingFile?.name ?: "Sutra"}'" }
    }

    private fun precededByFunctionKeyword(leaf: PsiElement): Boolean {
        var prev: PsiElement? = leaf.prevSibling ?: leaf.parent?.prevSibling
        var hops = 0
        while (prev != null && hops < 8) {
            if (prev is PsiWhiteSpace || prev.elementType == SutraTokenTypes.LINE_COMMENT ||
                prev.elementType == SutraTokenTypes.BLOCK_COMMENT ||
                prev.elementType == SutraTokenTypes.DOC_COMMENT ||
                prev.elementType == SutraTokenTypes.HASH_COMMENT) {
                prev = prev.prevSibling
                continue
            }
            if (prev.elementType == SutraTokenTypes.KEYWORD && prev.text == "function") return true
            prev = prev.prevSibling
            hops++
        }
        return false
    }
}
