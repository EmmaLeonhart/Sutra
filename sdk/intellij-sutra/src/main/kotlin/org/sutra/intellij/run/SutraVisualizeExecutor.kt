package org.sutra.intellij.run

import com.intellij.execution.Executor
import com.intellij.icons.AllIcons
import com.intellij.openapi.util.IconLoader
import com.intellij.openapi.wm.ToolWindowId
import javax.swing.Icon

/**
 * Custom executor that gives "Run with 3D Visualization" its own gutter
 * icon and toolbar button, distinct from the standard Run executor.
 *
 * In the gutter next to `function string main()` there will be two
 * actions: the standard ▶ Run and this ▶ Visualize. Each creates the
 * same [SutraRunConfiguration] but the runner dispatches on which
 * executor was used.
 */
class SutraVisualizeExecutor : Executor() {
    companion object {
        const val EXECUTOR_ID = "SutraVisualize"
    }

    override fun getToolWindowId(): String = ToolWindowId.RUN
    override fun getToolWindowIcon(): Icon = AllIcons.Toolwindows.ToolWindowRun
    override fun getIcon(): Icon = AllIcons.Actions.Execute
    override fun getDisabledIcon(): Icon = IconLoader.getDisabledIcon(icon)
    override fun getDescription(): String = "Run Sutra program with 3D vector space visualization"
    override fun getActionName(): String = "Visualize"
    override fun getId(): String = EXECUTOR_ID
    override fun getStartActionText(): String = "Run with 3D Visualization"
    override fun getContextActionId(): String = "SutraRunVisualize"
}
