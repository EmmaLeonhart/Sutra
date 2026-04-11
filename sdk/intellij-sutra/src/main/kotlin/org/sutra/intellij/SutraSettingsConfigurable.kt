package org.sutra.intellij

import com.intellij.openapi.options.Configurable
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBTextField
import com.intellij.util.ui.FormBuilder
import com.intellij.util.ui.JBUI
import javax.swing.JComponent
import javax.swing.JPanel

/**
 * Settings UI for the Sutra plugin, shown under
 * **Settings → Tools → Sutra**.
 *
 * Currently exposes the two knobs the external annotator needs: the
 * compiler executable and the args before the `--json <file>` tail.
 * Future Sutra IDE work (visualizer basis defaults, runtime MCP server
 * address, bundled-stack roots) will join this Configurable as
 * additional fields or grouped sub-configurables rather than spawning
 * new top-level pages.
 *
 * The fields are *intentionally* blank-by-default: a blank field means
 * "use the fallback chain in [SutraSettings]" (env var → hardcoded
 * default). This preserves the v0.1 env-var behavior for users who
 * installed the scaffold before v0.2 and don't want to migrate.
 */
class SutraSettingsConfigurable : Configurable {

    private var panel: JPanel? = null
    private lateinit var compilerField: JBTextField
    private lateinit var argsField: JBTextField

    override fun getDisplayName(): String = "Sutra"

    /**
     * `null` help topic is fine — IntelliJ doesn't enforce this.
     * A real docs page would hang off here if/when the plugin ships
     * bundled help.
     */
    override fun getHelpTopic(): String? = null

    override fun createComponent(): JComponent {
        compilerField = JBTextField().apply {
            toolTipText = "Executable to invoke. Leave blank to use \$SUTRA_COMPILER or \"python\"."
        }
        argsField = JBTextField().apply {
            toolTipText = "Args before `--json <file>`. Leave blank to use \$SUTRA_COMPILER_ARGS or \"-m sutra_compiler\"."
        }
        val compilerLabel = JBLabel("Compiler executable:")
        val argsLabel = JBLabel("Compiler arguments:")
        val hint = JBLabel(
            "<html>Blank fields fall back to <code>\$SUTRA_COMPILER</code> / " +
                    "<code>\$SUTRA_COMPILER_ARGS</code>, then to " +
                    "<code>${SutraSettings.DEFAULT_COMPILER}</code> / " +
                    "<code>${SutraSettings.DEFAULT_COMPILER_ARGS}</code>.</html>"
        ).apply {
            border = JBUI.Borders.emptyTop(8)
        }

        val built = FormBuilder.createFormBuilder()
            .addLabeledComponent(compilerLabel, compilerField, 1, false)
            .addLabeledComponent(argsLabel, argsField, 1, false)
            .addComponent(hint)
            .addComponentFillVertically(JPanel(), 0)
            .panel
        panel = built
        reset()
        return built
    }

    override fun isModified(): Boolean {
        val state = SutraSettings.getInstance().state
        return compilerField.text != state.compilerPath
                || argsField.text != state.compilerArgs
    }

    override fun apply() {
        val settings = SutraSettings.getInstance()
        settings.state.compilerPath = compilerField.text.trim()
        settings.state.compilerArgs = argsField.text.trim()
    }

    override fun reset() {
        val state = SutraSettings.getInstance().state
        compilerField.text = state.compilerPath
        argsField.text = state.compilerArgs
    }

    override fun disposeUIResources() {
        panel = null
    }
}
