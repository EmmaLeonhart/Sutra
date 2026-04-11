package org.akasha.intellij.solution

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
 * Registers the **Akasha Solution** tool window — the v1 home for the
 * solution/project tree described in `planning/akasha-spec/22-solutions.md`.
 *
 * On creation, the tool window scans the project root for the first
 * `.aksln` file (bounded depth, so it finishes fast even on large
 * repositories), loads the solution by shelling out to the Python
 * reference parser at `akasha_compiler.solution`, and renders the
 * resulting structure as a `JTree` of:
 *
 *     solution (name, version, substrate)
 *     ├── project (name, substrate, dependency summary)
 *     │   ├── source file 1
 *     │   ├── source file 2
 *     │   └── ...
 *     └── project ...
 *
 * Double-clicking any node opens the corresponding file in the
 * editor. A project node opens its `.akproj`, a solution node
 * opens its `.aksln`, a source node opens the `.ak` file.
 *
 * Out of scope for v1 (explicit v1.1 follow-ups named in the spec):
 * `ProjectOpenProcessor` auto-detect on folder open, source-root
 * configuration via `ModuleRootModificationUtil`, run configurations
 * that wrap `akashac --emit-flybrain` / similar, and the MCP tool
 * surface for querying the solution from an agent.
 */
class AkashaSolutionToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createEmptyBorder(6, 6, 6, 6)

        val statusLabel = JLabel(" ")
        statusLabel.border = BorderFactory.createEmptyBorder(0, 0, 6, 0)
        panel.add(statusLabel, BorderLayout.NORTH)

        val treeRoot = DefaultMutableTreeNode("Akasha Solution")
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
                    statusLabel.text = "Project has no base path — cannot scan for solution"
                }
                return@executeOnPooledThread
            }
            val aksFile = AkashaSolutionLoader.findSolutionFile(basePath)
            if (aksFile == null) {
                SwingUtilities.invokeLater {
                    statusLabel.text = "<html>No <code>.aksln</code> file found in this project. " +
                        "Create one and click the refresh icon on the tool window toolbar " +
                        "(coming in v1.1) to reload.</html>"
                }
                return@executeOnPooledThread
            }
            when (val result = AkashaSolutionLoader.loadSolution(aksFile)) {
                is AkashaSolutionLoadResult.Failure -> {
                    SwingUtilities.invokeLater {
                        statusLabel.text =
                            "<html>Failed to load ${aksFile.fileName}: " +
                            "<code>${escapeHtml(result.message)}</code></html>"
                    }
                }
                is AkashaSolutionLoadResult.Success -> {
                    SwingUtilities.invokeLater {
                        statusLabel.text =
                            "<html><b>${escapeHtml(result.solution.name)}</b> " +
                            "&middot; v${escapeHtml(result.solution.akashaVersion)} " +
                            "&middot; substrate " +
                            "<code>${escapeHtml(result.solution.defaultSubstrate)}</code></html>"
                        populateTree(treeRoot, treeModel, result.solution)
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
        solution: AkashaSolutionModel,
    ) {
        root.removeAllChildren()
        root.userObject = NodePayload(
            display = "📦 ${solution.name}",
            filePath = solution.aksFile,
        )
        for (project in solution.projects) {
            val depSummary = if (project.dependencies.isEmpty()) {
                ""
            } else {
                " (depends on: " + project.dependencies.joinToString(", ") { it.name } + ")"
            }
            val projectNode = DefaultMutableTreeNode(
                NodePayload(
                    display = "📁 ${project.name} [${project.substrate}]$depSummary",
                    filePath = project.path.resolve(project.name + ".akproj")
                        .let { candidate ->
                            // Fall back to the first .akproj in the directory if
                            // the naming convention `{name}.akproj` does not hold
                            // (the solution file's `akproj = "..."` override can
                            // point at an arbitrary filename).
                            if (candidate.toFile().isFile) candidate
                            else project.path.toFile().listFiles { f ->
                                f.isFile && f.name.endsWith(".akproj")
                            }?.firstOrNull()?.toPath() ?: project.path
                        },
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
        private val LOG = Logger.getInstance(AkashaSolutionToolWindowFactory::class.java)
    }
}
