package org.sutra.intellij.solution

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.openapi.diagnostic.Logger
import org.sutra.intellij.SutraSettings
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import kotlin.io.path.isDirectory
import kotlin.io.path.isRegularFile
import kotlin.io.path.walk
import kotlin.streams.toList

/**
 * In-memory representation of an Sutra solution, mirroring the
 * Python data classes in `sdk/sutra-compiler/sutra_compiler/solution.py`.
 *
 * Loading is done by shelling out to the reference Python parser
 * via `python -m sutra_compiler.solution --json <path>` and
 * deserializing the JSON output. This is the same
 * shell-out-to-Python pattern [SutraExternalAnnotator] already
 * uses for compiler diagnostics, so it reuses the same interpreter
 * configuration from [SutraSettings] and does not introduce a new
 * dependency.
 *
 * Why shell out instead of reimplementing the TOML parser in Kotlin:
 *
 *   - Single source of truth for the solution/project schema. If
 *     the Python parser ever learns a new field or tightens a
 *     validation rule, the Kotlin side picks it up for free on
 *     the next call.
 *   - The Python parser's error messages (AKA2000-AKA2099 codes)
 *     are already the spec's reference error set. Reproducing them
 *     in Kotlin would be duplication.
 *   - TOML parsing in Kotlin would require either pulling in a
 *     third-party library (tomlj, ktoml) as a plugin dependency or
 *     writing our own, both of which we can avoid.
 */
data class SutraSolutionModel(
    val name: String,
    val sutraVersion: String,
    val description: String,
    val defaultSubstrate: String,
    val compilerArgs: List<String>,
    val aksFile: Path,
    val projects: List<SutraProjectModel>,
) {
    val projectsByName: Map<String, SutraProjectModel>
        get() = projects.associateBy { it.name }
}

data class SutraProjectModel(
    val name: String,
    val path: Path,
    val entry: Path,
    val substrate: String,
    val description: String,
    val compilerArgs: List<String>,
    val sources: List<Path>,
    val dependencies: List<SutraProjectDependency>,
)

data class SutraProjectDependency(
    val name: String,
    val path: Path,
)

/**
 * Either [Success] with a parsed [SutraSolutionModel] or [Failure]
 * with a diagnostic string (typically the first line of the Python
 * parser's stderr, which carries the `AKA####` code).
 */
sealed class SutraSolutionLoadResult {
    data class Success(val solution: SutraSolutionModel) : SutraSolutionLoadResult()
    data class Failure(val message: String) : SutraSolutionLoadResult()
}


/**
 * Top-level utility for loading a solution file and for scanning a
 * directory to discover one.
 */
object SutraSolutionLoader {

    private val LOG = Logger.getInstance(SutraSolutionLoader::class.java)

    /**
     * Walk `root` looking for the first `.aksln` file and return its
     * path, or `null` if none was found.
     *
     * Only traverses up to a bounded depth so that huge repositories do
     * not cause slow tool-window startup. Three levels is enough to
     * find a solution file at the root of a typical project layout.
     */
    @OptIn(kotlin.io.path.ExperimentalPathApi::class)
    fun findSolutionFile(root: Path, maxDepth: Int = 3): Path? {
        if (!root.isDirectory()) return null
        val candidates = root.walk(kotlin.io.path.PathWalkOption.FOLLOW_LINKS)
            .filter { it.isRegularFile() && it.fileName.toString().endsWith(".aksln") }
            .take(1)
            .toList()
        return candidates.firstOrNull()
    }

    /**
     * Shell out to the Python reference parser and return a Kotlin
     * data model of the solution, or a [Failure] carrying the first
     * diagnostic line from the parser.
     *
     * Timeout is 15 seconds by default — solution parsing is pure
     * filesystem + TOML, no network, no heavy computation, so even
     * a large solution should finish well under that.
     */
    fun loadSolution(aksFile: Path, timeoutSeconds: Long = 15): SutraSolutionLoadResult {
        val settings = SutraSettings.getInstance()
        val exe = settings.effectiveCompiler()
        val rawArgs = settings.effectiveCompilerArgs().trim()
        val argv = mutableListOf(exe)
        if (rawArgs.isNotEmpty()) {
            // `--no-json` mode does not exist; instead we replace the
            // module-invocation target so `sutra_compiler.solution` is
            // the script, not the top-level `sutra_compiler` entry.
            // The rawArgs from settings is typically `-m sutra_compiler`;
            // we substitute `-m sutra_compiler.solution` to invoke the
            // solution-specific CLI.
            val substituted = rawArgs.replace(
                Regex("(^|\\s)-m\\s+sutra_compiler(\\b)"),
                "$1-m sutra_compiler.solution$2",
            )
            argv.addAll(substituted.split(Regex("\\s+")))
        }
        argv.add("--json")
        argv.add(aksFile.toString())

        return try {
            val process = ProcessBuilder(argv)
                .redirectErrorStream(false)
                .start()
            val stdout = BufferedReader(InputStreamReader(process.inputStream, Charsets.UTF_8))
                .readText()
            val stderr = BufferedReader(InputStreamReader(process.errorStream, Charsets.UTF_8))
                .readText()
            val finished = process.waitFor(timeoutSeconds, TimeUnit.SECONDS)
            if (!finished) {
                process.destroyForcibly()
                return SutraSolutionLoadResult.Failure(
                    "solution parser timed out after ${timeoutSeconds}s"
                )
            }
            if (process.exitValue() != 0) {
                val firstErrLine = stderr.lineSequence().firstOrNull() ?: "unknown error"
                return SutraSolutionLoadResult.Failure(firstErrLine.trim())
            }
            SutraSolutionLoadResult.Success(parseJson(stdout, aksFile))
        } catch (e: Exception) {
            LOG.warn("Failed to invoke solution parser for $aksFile", e)
            SutraSolutionLoadResult.Failure("failed to invoke solution parser: ${e.message}")
        }
    }

    private fun parseJson(json: String, aksFile: Path): SutraSolutionModel {
        val root = JsonParser.parseString(json).asJsonObject
        val projects = root.getAsJsonArray("projects").map { elem ->
            val obj = elem.asJsonObject
            SutraProjectModel(
                name = obj.get("name").asString,
                path = Path.of(obj.get("path").asString),
                entry = Path.of(obj.get("entry").asString),
                substrate = obj.get("substrate").asString,
                description = obj.optStringOrEmpty("description"),
                compilerArgs = obj.getAsJsonArray("compiler_args").map { it.asString },
                sources = obj.getAsJsonArray("sources").map { Path.of(it.asString) },
                dependencies = obj.getAsJsonArray("dependencies").map { d ->
                    val dobj = d.asJsonObject
                    SutraProjectDependency(
                        name = dobj.get("name").asString,
                        path = Path.of(dobj.get("path").asString),
                    )
                },
            )
        }
        return SutraSolutionModel(
            name = root.get("name").asString,
            sutraVersion = root.get("sutra_version").asString,
            description = root.optStringOrEmpty("description"),
            defaultSubstrate = root.get("default_substrate").asString,
            compilerArgs = root.getAsJsonArray("compiler_args").map { it.asString },
            aksFile = aksFile,
            projects = projects,
        )
    }

    private fun JsonObject.optStringOrEmpty(key: String): String =
        if (has(key) && !get(key).isJsonNull) get(key).asString else ""
}
