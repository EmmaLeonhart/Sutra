package org.akasha.intellij

import com.intellij.extapi.psi.ASTWrapperPsiElement
import com.intellij.lang.ASTNode
import com.intellij.lang.ParserDefinition
import com.intellij.lang.PsiParser
import com.intellij.lexer.Lexer
import com.intellij.openapi.project.Project
import com.intellij.psi.FileViewProvider
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IFileElementType
import com.intellij.psi.tree.TokenSet

/**
 * Minimal parser definition — builds a flat PSI tree whose only composite
 * element is the file itself. This is enough to make the platform happy
 * about `.ak` files (file type, lexer, comment tokens, string tokens) while
 * deferring real parsing to [AkashaExternalAnnotator] + the Python reference
 * compiler.
 *
 * When we grow a proper Kotlin parser, the `createParser` body is the only
 * thing that has to change — everything else (token sets, factories) is
 * already wired.
 */
class AkashaParserDefinition : ParserDefinition {

    override fun createLexer(project: Project?): Lexer = AkashaLexer()

    override fun createParser(project: Project?): PsiParser = PsiParser { root, builder ->
        val marker = builder.mark()
        while (!builder.eof()) {
            builder.advanceLexer()
        }
        marker.done(root)
        builder.treeBuilt
    }

    override fun getFileNodeType(): IFileElementType = FILE

    override fun getCommentTokens(): TokenSet = COMMENTS

    override fun getStringLiteralElements(): TokenSet = STRING_LITERALS

    override fun createElement(node: ASTNode): PsiElement = ASTWrapperPsiElement(node)

    override fun createFile(viewProvider: FileViewProvider): PsiFile = AkashaFile(viewProvider)

    companion object {
        @JvmField
        val FILE: IFileElementType = IFileElementType(AkashaLanguage)

        @JvmField
        val COMMENTS: TokenSet = TokenSet.create(
            AkashaTokenTypes.LINE_COMMENT,
            AkashaTokenTypes.DOC_COMMENT,
            AkashaTokenTypes.HASH_COMMENT,
            AkashaTokenTypes.BLOCK_COMMENT,
        )

        @JvmField
        val STRING_LITERALS: TokenSet = TokenSet.create(
            AkashaTokenTypes.STRING,
            AkashaTokenTypes.INTERP_STRING,
        )
    }
}
