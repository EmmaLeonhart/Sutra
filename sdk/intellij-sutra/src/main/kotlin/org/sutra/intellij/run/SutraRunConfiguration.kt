package org.sutra.intellij.run

import com.intellij.execution.Executor
import com.intellij.execution.configurations.CommandLineState
import com.intellij.execution.configurations.ConfigurationFactory
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.configurations.LocatableConfigurationBase
import com.intellij.execution.configurations.RunConfigurationWithSuppressedDefaultDebugAction
import com.intellij.execution.configurations.RunProfileState
import com.intellij.execution.process.KillableColoredProcessHandler
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.process.ProcessTerminatedListener
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.openapi.options.SettingsEditor
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.JDOMExternalizerUtil
import org.jdom.Element
import org.sutra.intellij.SutraSettings
import java.io.File

/**
 * Run configuration for a single Sutra source file. Shells out to the
 * reference compiler with `--run`, which compiles via the numpy backend
 * and executes a `main()` if present. All output flows into IDEA's Run
 * tool window.
 */
class SutraRunConfiguration(
    project: Project,
    factory: ConfigurationFactory,
    name: String,
) : LocatableConfigurationBase<RunProfileState>(project, factory, name),
    RunConfigurationWithSuppressedDefaultDebugAction {

    var scriptPath: String = ""
    var workingDirectory: String = ""

    override fun getConfigurationEditor(): SettingsEditor<out SutraRunConfiguration> =
        SutraRunConfigurationEditor(project)

    override fun getState(executor: Executor, env: ExecutionEnvironment): RunProfileState {
        val script = scriptPath
        val settings = SutraSettings.getInstance()
        val exe = settings.effectiveCompiler()
        val baseArgs = splitArgs(settings.effectiveCompilerArgs())
        val cwd = workingDirectory.ifBlank { project.basePath ?: File(script).parent ?: "." }

        return object : CommandLineState(env) {
            override fun startProcess(): ProcessHandler {
                val cmd = GeneralCommandLine(exe)
                    .withParameters(baseArgs)
                    .withParameters("--run", script)
                    .withWorkDirectory(cwd)
                    .withCharset(Charsets.UTF_8)
                    .withEnvironment("PYTHONIOENCODING", "utf-8")
                val handler = KillableColoredProcessHandler(cmd)
                ProcessTerminatedListener.attach(handler)
                return handler
            }
        }
    }

    override fun checkConfiguration() {
        if (scriptPath.isBlank()) {
            throw com.intellij.execution.configurations.RuntimeConfigurationError(
                "No Sutra file specified."
            )
        }
        if (!File(scriptPath).isFile) {
            throw com.intellij.execution.configurations.RuntimeConfigurationError(
                "Sutra file not found: $scriptPath"
            )
        }
    }

    override fun suggestedName(): String? =
        if (scriptPath.isNotBlank()) File(scriptPath).name else null

    override fun writeExternal(element: Element) {
        super.writeExternal(element)
        JDOMExternalizerUtil.writeField(element, "SCRIPT_PATH", scriptPath)
        JDOMExternalizerUtil.writeField(element, "WORKING_DIRECTORY", workingDirectory)
    }

    override fun readExternal(element: Element) {
        super.readExternal(element)
        scriptPath = JDOMExternalizerUtil.readField(element, "SCRIPT_PATH", "")
        workingDirectory = JDOMExternalizerUtil.readField(element, "WORKING_DIRECTORY", "")
    }

    private fun splitArgs(s: String): List<String> {
        if (s.isBlank()) return emptyList()
        val out = mutableListOf<String>()
        val cur = StringBuilder()
        var quote: Char? = null
        for (c in s) {
            when {
                quote != null -> if (c == quote) { quote = null } else cur.append(c)
                c == '"' || c == '\'' -> quote = c
                c.isWhitespace() -> if (cur.isNotEmpty()) { out.add(cur.toString()); cur.setLength(0) }
                else -> cur.append(c)
            }
        }
        if (cur.isNotEmpty()) out.add(cur.toString())
        return out
    }
}
