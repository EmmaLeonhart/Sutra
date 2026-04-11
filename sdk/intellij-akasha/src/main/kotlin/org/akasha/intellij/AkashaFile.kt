package org.akasha.intellij

import com.intellij.extapi.psi.PsiFileBase
import com.intellij.openapi.fileTypes.FileType
import com.intellij.psi.FileViewProvider

/**
 * Root [PsiFile] for `.ak` sources. The body is a flat run of tokens from
 * [AkashaLexer] wrapped in a single marker by [AkashaParserDefinition] —
 * there is no real PSI tree yet.
 */
class AkashaFile(viewProvider: FileViewProvider) : PsiFileBase(viewProvider, AkashaLanguage) {
    override fun getFileType(): FileType = AkashaFileType
    override fun toString(): String = "Akasha File"
}
