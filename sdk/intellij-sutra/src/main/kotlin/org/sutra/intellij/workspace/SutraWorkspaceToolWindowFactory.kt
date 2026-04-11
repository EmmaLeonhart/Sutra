package org.sutra.intellij.workspace

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import java.awt.Dimension
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import java.nio.file.Path
import javax.swing.BorderFactory
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.JTree
import javax.swing.SwingUtilities
import javax.swing.tree.DefaultMutableTreeNode
import javax.swing.tree.DefaultTreeModel
import javax.swing.tree.TreePath
import javax.swing.tree.TreeSelectionModel

/**
 * Registers the **Sutra Workspace** tool window — the v1 home for the
 * workspace/project tree described in `planning/sutra-spec/22-workspaces.md`.
 *
 * On creation, the tool window scans the project root for the first
 * `atman.toml` file (bounded depth, so it finishes fast even on large
 * repositories), loads the workspace by shelling out to the Python
 * reference parser at `sutra_compiler.workspace`, and renders the
 * resulting structure as a `JTree` of:
 *
 *     workspace (name, version, substrate)
 *     ├── project (name, substrate, dependency summary)
 *     │   ├── source file 1
 *     │   ├── source file 2
 *     │   └── ...
 *     └── project ...
 *
 * Double-clicking any node opens the corresponding file in the
 * editor. A project node opens its own `atman.toml`, the workspace
 * root node opens the root `atman.toml`, a source node opens the
 * `.su` file.
 *
 * Out of scope for v1 (explicit v1.1 follow-ups named in the spec):
 * `ProjectOpenProcessor` auto-detect on folder open, source-root
 * configuration via `ModuleRootModificationUtil`, run configurations
 * that wrap `sutrac --emit-flybrain` / similar, and the MCP tool
 * surface for querying the workspace from an agent.
 */
class SutraWorkspaceToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createEmptyBorder(6, 6, 6, 6)

        val statusLabel = JLabel(" ")
        statusLabel.border = BorderFactory.createEmptyBorder(0, 0, 6, 0)
        panel.add(statusLabel, BorderLayout.NORTH)

        val treeRoot = DefaultMutableTreeNode("Sutra Workspace")
        val treeModel = DefaultTreeModel(treeRoot)
        val tree = JTree(treeModel)
        tree.selectionModel.selectionMode = TreeSelectionModel.SINGLE_TREE_SELECTION
        tree.rootVisible = true
        tree.showsRootHandles = true

        tree.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount != 2) return
                val path: TreePath = tree.getPathForLocation(e.x, e.y) ?: return
                val node = path.lastPathComponent as? DefaultMutableTreeNode ?: return
                val userObject = node.userObject
                if (userObject is NodePayload) {
                    openFile(project, userObject.filePath)
                }
            }
        })

        val scroll = JScrollPane(tree)
        scroll.preferredSize = Dimension(280, 400)
        panel.add(scroll, BorderLayout.CENTER)

        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)

        // Populate in the background so tool window creation is fast.
        ApplicationManager.getApplication().executeOnPooledThread {
            val basePath = project.basePath?.let { Path.of(it) }
            if (basePath == null) {
                SwingUtilities.invokeLater {
                    statusLabel.text = "Project has no base path — cannot scan for workspace"
                }
                return@executeOnPooledThread
            }
            val atmanFile = SutraWorkspaceLoader.findWorkspaceFile(basePath)
            if (atmanFile == null) {
                SwingUtilities.invokeLater {
                    statusLabel.text = "<html>No <code>atman.toml</code> file found in this project. " +
                        "Create one at the project root and click the refresh icon on the tool " +
                        "window toolbar (coming in v1.1) to reload.</html>"
                }
                return@executeOnPooledThread
            }
            when (val result = SutraWorkspaceLoader.loadWorkspace(atmanFile)) {
                is SutraWorkspaceLoadResult.Failure -> {
                    SwingUtilities.invokeLater {
                        statusLabel.text =
                            "<html>Failed to load ${atmanFile.fileName}: " +
                            "<code>${escapeHtml(result.message)}</code></html>"
                    }
                }
                is SutraWorkspaceLoadResult.Success -> {
                    SwingUtilities.invokeLater {
                        statusLabel.text =
                            "<html><b>${escapeHtml(result.workspace.name)}</b> " +
                            "&middot; v${escapeHtml(result.workspace.sutraVersion)} " +
                            "&middot; substrate " +
                            "<code>${escapeHtml(result.workspace.defaultSubstrate)}</code></html>"
                        populateTree(treeRoot, treeModel, result.workspace)
                        tree.expandRow(0)
                        for (i in 0 until tree.rowCount) tree.expandRow(i)
                    }
                }
            }
        }
    }

    private fun populateTree(
        root: DefaultMutableTreeNode,
        model: DefaultTreeModel,
        workspace: SutraWorkspaceModel,
    ) {
        root.removeAllChildren()
        root.userObject = NodePayload(
            display = "📦 ${workspace.name}",
            filePath = workspace.atmanFile,
        )
        for (project in workspace.projects) {
            val depSummary = if (project.dependencies.isEmpty()) {
                ""
            } else {
                " (depends on: " + project.dependencies.joinToString(", ") { it.name } + ")"
            }
            // Every project's atman.toml is at a fixed relative path
            // from the project directory — no discovery needed.
            val projectAtman = project.path.resolve("atman.toml")
            val projectNode = DefaultMutableTreeNode(
                NodePayload(
                    display = "📁 ${project.name} [${project.substrate}]$depSummary",
                    filePath = projectAtman,
                )
            )
            for (src in project.sources) {
                val rel = try {
                    project.path.relativize(src).toString()
                } catch (e: IllegalArgumentException) {
                    src.fileName.toString()
                }
                projectNode.add(
                    DefaultMutableTreeNode(
                        NodePayload(
                            display = "📄 $rel",
                            filePath = src,
                        )
                    )
                )
            }
            root.add(projectNode)
        }
        model.reload(root)
    }

    private fun openFile(project: Project, path: Path) {
        val vfile = LocalFileSystem.getInstance().findFileByNioFile(path)
        if (vfile == null) {
            LOG.warn("Cannot open file (not found in VFS): $path")
            return
        }
        FileEditorManager.getInstance(project).openFile(vfile, true)
    }

    private fun escapeHtml(s: String): String =
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    /**
     * Payload attached to every tree node so mouse clicks can find
     * the file to open without storing state on the JTree itself.
     */
    private data class NodePayload(
        val display: String,
        val filePath: Path,
    ) {
        override fun toString(): String = display
    }

    companion object {
        private val LOG = Logger.getInstance(SutraWorkspaceToolWindowFactory::class.java)
    }
}
