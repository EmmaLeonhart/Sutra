package org.sutra.intellij.viz

import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.jcef.JBCefApp
import com.intellij.ui.jcef.JBCefBrowser
import java.awt.BorderLayout
import javax.swing.BorderFactory
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.SwingConstants

/**
 * Registers the **Sutra Fly Brain** tool window — the v0.3 fly-brain
 * topological visualizer from
 * `planning/fly-brain-visualizer.md` §"v0.3 — fly-brain topological
 * view (option a)".
 *
 * What it shows right now:
 *   A static topology view of the reference mushroom-body circuit —
 *   50 projection neurons in a column on the left, a sampled blob of
 *   Kenyon cells in the middle (2000 is too many to render one-by-one
 *   in a tiny tool window, so the sampled subset is ~200), 1 anterior
 *   paired lateral neuron as a shared inhibitory sink, and 20 mushroom
 *   body output neurons on the right. KC sparsity (~5% active) is
 *   rendered by highlighting a random 5% of the sampled KCs as
 *   "currently firing" on every repaint, so the pane looks alive even
 *   without a running Brian2 simulation behind it.
 *
 * What it does NOT do yet (named in the planning doc as later
 * deliverables, explicitly out of scope for v0.3 first cut):
 *   - Live spike feed from a Brian2 run (v0.3 full scope)
 *   - Source-to-circuit mapping (hover a KC, highlight the `.ak` line)
 *   - Time-scrubbing along a recorded simulation run
 *   - Anatomical view with hemibrain/FlyWire mesh data (v0.4+, research
 *     blocked on the Sutra-unit ↔ hemibrain-neuron-ID mapping)
 *   - MCP surface for agent querying (flybrain.topology, flybrain.spikes
 *     etc.)
 *
 * Same JCEF-first pattern as [SutraEmbeddingToolWindowFactory]:
 * degrades gracefully to a plain Swing placeholder panel on
 * distributions where JCEF is unavailable or fails to initialize.
 * The reason for keeping JCEF in both panes is that the eventual
 * MCP-bridge wiring (bidirectional queries between the pane and the
 * Sutra runtime) slots in cleanly through the JS ↔ Kotlin bridge
 * JCEF already provides.
 */
class SutraFlyBrainToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())

        if (!JBCefApp.isSupported()) {
            panel.add(buildJcefUnavailablePlaceholder(), BorderLayout.CENTER)
        } else {
            try {
                val browser = JBCefBrowser()
                val html = loadHtmlResource("/viz/fly-brain.html")
                browser.loadHTML(html, "about:blank")
                panel.add(browser.component, BorderLayout.CENTER)
            } catch (t: Throwable) {
                LOG.warn("Failed to initialize JCEF for Sutra fly-brain visualizer", t)
                panel.add(buildJcefErrorPlaceholder(t), BorderLayout.CENTER)
            }
        }

        val contentFactory = ContentFactory.getInstance()
        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }

    private fun loadHtmlResource(path: String): String {
        val stream = javaClass.getResourceAsStream(path)
            ?: return buildFallbackHtml("resource not found: $path")
        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    private fun buildJcefUnavailablePlaceholder(): JPanel {
        val p = JPanel(BorderLayout())
        p.border = BorderFactory.createEmptyBorder(24, 24, 24, 24)
        val label = JLabel(
            "<html><body style='width:480px'>" +
                "<h3>Sutra Fly Brain</h3>" +
                "<p>JCEF (JetBrains Chromium Embedded Framework) is not " +
                "available in this IntelliJ Platform distribution, so the " +
                "fly-brain topological visualizer cannot render here.</p>" +
                "<p>The Swing fallback renderer mentioned in " +
                "<code>planning/fly-brain-visualizer.md</code> is not yet " +
                "implemented. Either install a JCEF-capable IntelliJ " +
                "distribution or wait for the Swing fallback to land.</p>" +
                "</body></html>",
            SwingConstants.LEFT,
        )
        p.add(label, BorderLayout.CENTER)
        return p
    }

    private fun buildJcefErrorPlaceholder(t: Throwable): JPanel {
        val p = JPanel(BorderLayout())
        p.border = BorderFactory.createEmptyBorder(24, 24, 24, 24)
        val label = JLabel(
            "<html><body style='width:480px'>" +
                "<h3>Sutra Fly Brain — initialization failed</h3>" +
                "<p>JCEF is supported but the browser failed to " +
                "initialize. Error:</p>" +
                "<pre>${escapeHtml(t.toString())}</pre>" +
                "</body></html>",
            SwingConstants.LEFT,
        )
        p.add(label, BorderLayout.CENTER)
        return p
    }

    private fun buildFallbackHtml(message: String): String =
        "<html><body><h3>Sutra Fly Brain</h3><p>${escapeHtml(message)}</p></body></html>"

    private fun escapeHtml(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")

    companion object {
        private val LOG = Logger.getInstance(SutraFlyBrainToolWindowFactory::class.java)
    }
}
