package org.sutra.intellij

import com.intellij.extapi.psi.PsiFileBase
import com.intellij.openapi.fileTypes.FileType
import com.intellij.psi.FileViewProvider

/**
 * Root [PsiFile] for `.su` sources. The body is a flat run of tokens from
 * [SutraLexer] wrapped in a single marker by [SutraParserDefinition] —
 * there is no real PSI tree yet.
 */
class SutraFile(viewProvider: FileViewProvider) : PsiFileBase(viewProvider, SutraLanguage) {
    override fun getFileType(): FileType = SutraFileType
    override fun toString(): String = "Sutra File"
}
