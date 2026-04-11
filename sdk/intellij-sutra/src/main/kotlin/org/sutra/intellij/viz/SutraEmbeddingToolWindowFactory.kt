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
 * Registers the **Sutra Embedding Space** tool window — the v0.2
 * first-cut visualizer from
 * `planning/sutra-spec/20-ide-architecture.md` §"Embedding-Space
 * Visualizer as a Core Pane".
 *
 * What it shows right now:
 *   A 2D scatter of ~100 toy points projected onto two composite
 *   basis vectors, rendered in pure Canvas 2D inside a JCEF browser.
 *   The default projection mode is 2D per the resolved open question
 *   in the spec; 3D is planned as an opt-in mode alongside UMAP/t-SNE
 *   in the projection dropdown but not implemented in v1.
 *
 * What it does NOT do yet (named design targets, coming in later
 * revisions):
 *   - Hook to the runtime MCP server for live embedding data — it
 *     only renders seeded pseudo-random points today.
 *   - User-chosen composite basis vectors as Sutra expressions.
 *     The current demo hard-codes two directions just so the pane
 *     has something visible the moment you open it.
 *   - Projection mode switching (UMAP/t-SNE/3D).
 *   - Bidirectional selection sync with the editor (hover a point,
 *     jump to the source that created it).
 *
 * Why JCEF and not native Swing:
 *   - Web 2D/3D ecosystem reuse (three.js, d3, WebGL) is available
 *     behind the same JCEF layer once we start needing it.
 *   - The JS↔Kotlin bridge JCEF exposes gives us a clean path to
 *     wire the visualizer into the MCP tool surface without building
 *     a custom serialization layer.
 *   - JCEF ships with most IntelliJ Platform distributions; the
 *     small number of distributions where it isn't available fall
 *     back to a static placeholder panel so the tool window still
 *     renders without crashing.
 *
 * See companion [SutraFlyBrainToolWindowFactory] for the fly-brain
 * topological view, which uses the same pattern.
 */
class SutraEmbeddingToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())

        if (!JBCefApp.isSupported()) {
            panel.add(buildJcefUnavailablePlaceholder(), BorderLayout.CENTER)
        } else {
            try {
                val browser = JBCefBrowser()
                val html = loadHtmlResource("/viz/embedding-space.html")
                browser.loadHTML(html, "about:blank")
                panel.add(browser.component, BorderLayout.CENTER)
            } catch (t: Throwable) {
                LOG.warn("Failed to initialize JCEF for Sutra embedding visualizer", t)
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
                "<h3>Sutra Embedding Space</h3>" +
                "<p>JCEF (JetBrains Chromium Embedded Framework) is not " +
                "available in this IntelliJ Platform distribution, so the " +
                "embedding-space visualizer cannot render here.</p>" +
                "<p>The Swing fallback renderer mentioned in " +
                "<code>planning/sutra-spec/20-ide-architecture.md</code> " +
                "§\"Renderer: JCEF + three.js\" is not yet implemented. " +
                "This pane will remain blank until either JCEF becomes " +
                "available or the Swing fallback lands.</p>" +
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
                "<h3>Sutra Embedding Space — initialization failed</h3>" +
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
        "<html><body><h3>Sutra Embedding Space</h3><p>${escapeHtml(message)}</p></body></html>"

    private fun escapeHtml(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")

    companion object {
        private val LOG = Logger.getInstance(SutraEmbeddingToolWindowFactory::class.java)
    }
}
