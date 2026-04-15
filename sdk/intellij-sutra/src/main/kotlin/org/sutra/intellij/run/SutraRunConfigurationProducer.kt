package org.sutra.intellij.run

import com.intellij.execution.actions.ConfigurationContext
import com.intellij.execution.actions.LazyRunConfigurationProducer
import com.intellij.openapi.util.Ref
import com.intellij.psi.PsiElement
import org.sutra.intellij.SutraFileType

/**
 * Right-click on a .su file or editor → "Run '<file>'" auto-creates a
 * SutraRunConfiguration pointed at that file. Same producer is reused by
 * [SutraRunLineMarkerContributor] to light up the gutter icon.
 */
class SutraRunConfigurationProducer
    : LazyRunConfigurationProducer<SutraRunConfiguration>() {

    override fun getConfigurationFactory() =
        SutraRunConfigurationType.getInstance().configurationFactories[0]

    override fun isConfigurationFromContext(
        configuration: SutraRunConfiguration,
        context: ConfigurationContext,
    ): Boolean {
        val file = context.location?.virtualFile ?: return false
        if (file.fileType != SutraFileType) return false
        return configuration.scriptPath == file.path
    }

    override fun setupConfigurationFromContext(
        configuration: SutraRunConfiguration,
        context: ConfigurationContext,
        sourceElement: Ref<PsiElement>,
    ): Boolean {
        val file = context.location?.virtualFile ?: return false
        if (file.fileType != SutraFileType) return false
        configuration.scriptPath = file.path
        configuration.setName(file.nameWithoutExtension)
        context.project.basePath?.let { configuration.workingDirectory = it }
        return true
    }
}
