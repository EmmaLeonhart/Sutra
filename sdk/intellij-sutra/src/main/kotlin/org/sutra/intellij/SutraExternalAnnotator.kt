package org.sutra.intellij

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.editor.Document
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

/**
 * Runs the Sutra reference compiler (`python -m sutra_compiler --json`)
 * over the current file and surfaces its diagnostics as editor annotations.
 *
 * Mirrors the behavior of `sdk/vscode-sutra/src/extension.ts` — the same
 * JSON shape, the same 1-based → 0-based column conversion, the same AKA####
 * code display.
 *
 * Configuration is resolved by [SutraSettings], which implements a
 * three-step fallback chain:
 *
 *   1. Values set in Settings → Tools → Sutra (persistent state)
 *   2. Environment variables SUTRA_COMPILER / SUTRA_COMPILER_ARGS
 *   3. Hardcoded defaults: `python` and `-m sutra_compiler`
 *
 * v0.1 users who only set env vars keep working unchanged.
 */
class SutraExternalAnnotator : ExternalAnnotator<SutraExternalAnnotator.Info, SutraExternalAnnotator.Result>() {

    /** Snapshot of the file + command line needed to run the compiler off-thread. */
    data class Info(
        val filePath: String,
        val command: List<String>,
    )

    /** Parsed compiler output, ready to apply. */
    data class Result(val diagnostics: List<SutraDiagnostic>)

    data class SutraDiagnostic(
        val line: Int,
        val column: Int,
        val endLine: Int,
        val endColumn: Int,
        val level: String,
        val code: String?,
        val message: String,
        val hint: String?,
    )

    override fun collectInformation(file: PsiFile): Info? {
        val virtualFile = file.virtualFile ?: return null
        if (!virtualFile.isInLocalFileSystem) return null
        return Info(
            filePath = virtualFile.path,
            command = buildCommand(virtualFile.path),
        )
    }

    override fun doAnnotate(collectedInfo: Info?): Result? {
        val info = collectedInfo ?: return null
        return try {
            val process = ProcessBuilder(info.command)
                .redirectErrorStream(false)
                .start()
            val stdout = BufferedReader(InputStreamReader(process.inputStream)).readText()
            val finished = process.waitFor(15, TimeUnit.SECONDS)
            if (!finished) {
                process.destroyForcibly()
                LOG.warn("sutrac timed out for ${info.filePath}")
                return Result(emptyList())
            }
            Result(parseCompilerJson(stdout))
        } catch (e: Exception) {
            // Most common cause: python isn't on PATH. Log once, don't spam.
            LOG.warn("sutrac invocation failed for ${info.filePath}: ${e.message}")
            Result(emptyList())
        }
    }

    override fun apply(file: PsiFile, annotationResult: Result?, holder: AnnotationHolder) {
        val result = annotationResult ?: return
        val virtualFile = file.virtualFile ?: return
        val document = FileDocumentManager.getInstance().getDocument(virtualFile) ?: return
        for (diag in result.diagnostics) {
            val range = toTextRange(document, diag) ?: continue
            val severity = when (diag.level) {
                "error"   -> HighlightSeverity.ERROR
                "warning" -> HighlightSeverity.WARNING
                else      -> HighlightSeverity.WEAK_WARNING
            }
            val message = buildString {
                append(diag.message)
                if (!diag.hint.isNullOrBlank()) {
                    append("\n  hint: ")
                    append(diag.hint)
                }
                if (!diag.code.isNullOrBlank()) {
                    append("  [")
                    append(diag.code)
                    append("]")
                }
            }
            holder.newAnnotation(severity, message).range(range).create()
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private fun buildCommand(filePath: String): List<String> {
        val settings = SutraSettings.getInstance()
        val exe = settings.effectiveCompiler()
        val rawArgs = settings.effectiveCompilerArgs()
        val argv = mutableListOf(exe)
        argv.addAll(rawArgs.trim().split(Regex("\\s+")))
        argv.add("--json")
        argv.add(filePath)
        return argv
    }

    private fun parseCompilerJson(json: String): List<SutraDiagnostic> {
        if (json.isBlank()) return emptyList()
        return try {
            val root = JsonParser.parseString(json).asJsonObject
            val files = root.getAsJsonArray("files") ?: return emptyList()
            val out = mutableListOf<SutraDiagnostic>()
            files.forEach { fileElement ->
                if (!fileElement.isJsonObject) return@forEach
                val diagArray = fileElement.asJsonObject.getAsJsonArray("diagnostics") ?: return@forEach
                diagArray.forEach { d ->
                    if (!d.isJsonObject) return@forEach
                    out.add(jsonToDiagnostic(d.asJsonObject))
                }
            }
            out
        } catch (e: Exception) {
            LOG.warn("sutrac JSON parse failed: ${e.message}")
            emptyList()
        }
    }

    private fun jsonToDiagnostic(obj: JsonObject): SutraDiagnostic {
        val line = obj.optInt("line", 1)
        val column = obj.optInt("column", 1)
        return SutraDiagnostic(
            line = line,
            column = column,
            endLine = obj.optInt("end_line", line),
            endColumn = obj.optInt("end_column", column + 1),
            level = obj.optString("level", "error"),
            code = obj.optNullableString("code"),
            message = obj.optString("message", ""),
            hint = obj.optNullableString("hint"),
        )
    }

    private fun JsonObject.optInt(key: String, default: Int): Int =
        if (has(key) && !get(key).isJsonNull) get(key).asInt else default

    private fun JsonObject.optString(key: String, default: String): String =
        if (has(key) && !get(key).isJsonNull) get(key).asString else default

    private fun JsonObject.optNullableString(key: String): String? =
        if (has(key) && !get(key).isJsonNull) get(key).asString else null

    /**
     * Convert a 1-based (line, column) pair from the compiler into a
     * 0-based [TextRange] the annotation holder can consume. Clamped to
     * document bounds so malformed diagnostics never throw.
     */
    private fun toTextRange(document: Document, diag: SutraDiagnostic): TextRange? {
        val lineCount = document.lineCount
        if (lineCount == 0) return null
        val startLine = (diag.line - 1).coerceIn(0, lineCount - 1)
        val endLineIdx = (diag.endLine - 1).coerceIn(0, lineCount - 1)
        val startLineStart = document.getLineStartOffset(startLine)
        val startLineEnd = document.getLineEndOffset(startLine)
        val startOffset = (startLineStart + (diag.column - 1))
            .coerceIn(startLineStart, startLineEnd)
        val endLineStart = document.getLineStartOffset(endLineIdx)
        val endLineEnd = document.getLineEndOffset(endLineIdx)
        var endOffset = (endLineStart + (diag.endColumn - 1))
            .coerceIn(endLineStart, endLineEnd)
        if (endOffset <= startOffset) {
            endOffset = (startOffset + 1).coerceAtMost(document.textLength)
        }
        return TextRange(startOffset, endOffset)
    }

    companion object {
        private val LOG = Logger.getInstance(SutraExternalAnnotator::class.java)
    }
}
