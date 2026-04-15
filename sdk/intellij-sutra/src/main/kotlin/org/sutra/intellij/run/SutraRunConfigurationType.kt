package org.sutra.intellij.run

import com.intellij.execution.configurations.ConfigurationFactory
import com.intellij.execution.configurations.ConfigurationType
import com.intellij.execution.configurations.ConfigurationTypeUtil
import com.intellij.execution.configurations.RunConfiguration
import com.intellij.openapi.project.Project
import org.sutra.intellij.SutraIcons
import javax.swing.Icon

class SutraRunConfigurationType : ConfigurationType {
    override fun getDisplayName(): String = "Sutra"
    override fun getConfigurationTypeDescription(): String =
        "Run a Sutra (.su) program via the reference compiler (--run)."
    override fun getIcon(): Icon = SutraIcons.FILE
    override fun getId(): String = ID
    override fun getConfigurationFactories(): Array<ConfigurationFactory> =
        arrayOf(Factory(this))

    class Factory(type: ConfigurationType) : ConfigurationFactory(type) {
        override fun getId(): String = "SutraRunConfigurationFactory"
        override fun createTemplateConfiguration(project: Project): RunConfiguration =
            SutraRunConfiguration(project, this, "")
    }

    companion object {
        const val ID = "SutraRunConfigurationType"
        @JvmStatic
        fun getInstance(): SutraRunConfigurationType =
            ConfigurationTypeUtil.findConfigurationType(
                SutraRunConfigurationType::class.java
            )
    }
}
