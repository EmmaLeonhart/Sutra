package org.sutra.intellij.run

import com.intellij.openapi.fileChooser.FileChooserDescriptorFactory
import com.intellij.openapi.options.SettingsEditor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.util.ui.FormBuilder
import javax.swing.JComponent
import javax.swing.JPanel

class SutraRunConfigurationEditor(
    private val project: Project,
) : SettingsEditor<SutraRunConfiguration>() {

    private val scriptField = TextFieldWithBrowseButton().apply {
        addBrowseFolderListener(
            "Sutra File",
            "Select a .su source file to run.",
            project,
            FileChooserDescriptorFactory.createSingleFileDescriptor("su"),
        )
    }

    private val workDirField = TextFieldWithBrowseButton().apply {
        addBrowseFolderListener(
            "Working Directory",
            "Directory to run the compiler from.",
            project,
            FileChooserDescriptorFactory.createSingleFolderDescriptor(),
        )
    }

    override fun resetEditorFrom(s: SutraRunConfiguration) {
        scriptField.text = s.scriptPath
        workDirField.text = s.workingDirectory
    }

    override fun applyEditorTo(s: SutraRunConfiguration) {
        s.scriptPath = scriptField.text.trim()
        s.workingDirectory = workDirField.text.trim()
    }

    override fun createEditor(): JComponent {
        val panel: JPanel = FormBuilder.createFormBuilder()
            .addLabeledComponent("Sutra file:", scriptField)
            .addLabeledComponent("Working directory:", workDirField)
            .panel
        return panel
    }
}
