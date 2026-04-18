package org.sutra.intellij.run

import com.intellij.execution.configurations.RunProfile
import com.intellij.execution.configurations.RunProfileState
import com.intellij.execution.configurations.RunnerSettings
import com.intellij.execution.configurations.CommandLineState
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.process.KillableColoredProcessHandler
import com.intellij.execution.process.ProcessAdapter
import com.intellij.execution.process.ProcessEvent
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.process.ProcessTerminatedListener
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.execution.runners.GenericProgramRunner
import com.intellij.execution.ui.RunContentDescriptor
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.jcef.JBCefApp
import com.intellij.ui.jcef.JBCefBrowser
import org.sutra.intellij.SutraSettings
import java.awt.BorderLayout
import java.io.File
import javax.swing.JPanel

/**
 * Program runner for the Visualize executor. When the user clicks
 * "Run with 3D Visualization", this runner:
 *
 * 1. Shells `python -m sutra_compiler --run-viz <file>` (same as the
 *    normal run but with `--run-viz` instead of `--run`).
 * 2. After the process exits, reads the `*_trace.json` file the
 *    compiler produced.
 * 3. Loads the Three.js visualizer HTML into the "Sutra Embedding Space"
 *    JCEF tool window with the trace data injected.
 *
 * The program output still appears in the normal Run console.
 */
class SutraVisualizeRunner : GenericProgramRunner<RunnerSettings>() {

    companion object {
        private val LOG = Logger.getInstance(SutraVisualizeRunner::class.java)
    }

    override fun getRunnerId(): String = "SutraVisualizeRunner"

    override fun canRun(executorId: String, profile: RunProfile): Boolean =
        executorId == SutraVisualizeExecutor.EXECUTOR_ID && profile is SutraRunConfiguration

    override fun doExecute(state: RunProfileState, env: ExecutionEnvironment): RunContentDescriptor? {
        val config = env.runProfile as? SutraRunConfiguration ?: return null
        val script = config.scriptPath
        val settings = SutraSettings.getInstance()
        val exe = settings.effectiveCompiler()
        val baseArgs = splitArgs(settings.effectiveCompilerArgs())
        val cwd = config.workingDirectory.ifBlank {
            env.project.basePath ?: File(script).parent ?: "."
        }

        val projectRoot = env.project.basePath ?: cwd
        val compilerSrc = File(projectRoot, "sdk/sutra-compiler")
        val extraPath = if (compilerSrc.isDirectory) compilerSrc.absolutePath else null
        val existingPy = System.getenv("PYTHONPATH")
        val pythonPath = listOfNotNull(extraPath, existingPy?.takeIf { it.isNotBlank() })
            .joinToString(File.pathSeparator)

        val vizState = object : CommandLineState(env) {
            override fun startProcess(): ProcessHandler {
                val cmd = GeneralCommandLine(exe)
                    .withParameters(baseArgs)
                    .withParameters("--run-viz", script)
                    .withWorkDirectory(cwd)
                    .withCharset(Charsets.UTF_8)
                    .withEnvironment("PYTHONIOENCODING", "utf-8")
                if (pythonPath.isNotEmpty()) {
                    cmd.withEnvironment("PYTHONPATH", pythonPath)
                }
                val handler = KillableColoredProcessHandler(cmd)
                ProcessTerminatedListener.attach(handler)

                // After process finishes, load the trace into the viz tool window
                handler.addProcessListener(object : ProcessAdapter() {
                    override fun processTerminated(event: ProcessEvent) {
                        if (event.exitCode == 0) {
                            val traceFile = File(script.replaceAfterLast('.', "").dropLast(1) + "_trace.json")
                            if (traceFile.isFile) {
                                loadTraceIntoToolWindow(env, traceFile)
                            } else {
                                LOG.warn("Trace file not found: $traceFile")
                            }
                        }
                    }
                })

                return handler
            }
        }

        return vizState.execute(env.executor, this)
    }

    private fun loadTraceIntoToolWindow(env: ExecutionEnvironment, traceFile: File) {
        val traceJson = traceFile.readText(Charsets.UTF_8)

        ApplicationManager.getApplication().invokeLater {
            val project = env.project
            val toolWindowManager = ToolWindowManager.getInstance(project)
            val toolWindow = toolWindowManager.getToolWindow("Sutra Embedding Space") ?: return@invokeLater

            if (!JBCefApp.isSupported()) {
                LOG.warn("JCEF not available, cannot render 3D visualizer")
                return@invokeLater
            }

            try {
                val browser = JBCefBrowser()
                val html = buildVisualizerHtml(traceJson)
                browser.loadHTML(html, "about:blank")

                val panel = JPanel(BorderLayout())
                panel.add(browser.component, BorderLayout.CENTER)

                val contentFactory = ContentFactory.getInstance()
                val content = contentFactory.createContent(panel, "3D Trace", false)

                toolWindow.contentManager.removeAllContents(true)
                toolWindow.contentManager.addContent(content)
                toolWindow.show()
            } catch (t: Throwable) {
                LOG.warn("Failed to load 3D visualizer", t)
            }
        }
    }

    private fun buildVisualizerHtml(traceJson: String): String {
        val templateStream = javaClass.getResourceAsStream("/viz/embedding-space-3d.html")
        if (templateStream != null) {
            val template = templateStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            return template.replace(
                "<script type=\"module\">",
                "<script>window.SUTRA_TRACE_DATA = $traceJson;</script>\n<script type=\"module\">"
            )
        }

        // Inline fallback if resource not found — minimal Three.js scene
        return """
<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>
html,body{margin:0;padding:0;background:#0d0b1a;color:#e4def0;font-family:sans-serif;height:100%;overflow:hidden;}
#c{width:100%;height:100%;display:block;}
#info{position:absolute;top:12px;left:16px;font-size:13px;color:#7c4dff;}
</style></head><body>
<canvas id="c"></canvas>
<div id="info">Sutra 3D Vector Space</div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}</script>
<script>window.SUTRA_TRACE_DATA = $traceJson;</script>
<script type="module">
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';
const T=window.SUTRA_TRACE_DATA||{vectors:[],operations:[]};
const C={basis:0x7c4dff,bind:0xff4081,bundle:0x00e676,unbind:0xffab40,result:0x40c4ff,other:0x9892b2};
const canvas=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas,antialias:true});r.setPixelRatio(devicePixelRatio);r.setSize(innerWidth,innerHeight);
const s=new THREE.Scene();s.background=new THREE.Color(0x0d0b1a);
const cam=new THREE.PerspectiveCamera(60,innerWidth/innerHeight,0.1,500);cam.position.set(8,6,12);
const ctl=new OrbitControls(cam,canvas);ctl.enableDamping=true;ctl.autoRotate=true;ctl.autoRotateSpeed=0.5;
s.add(new THREE.AmbientLight(0x443366,0.6));const dl=new THREE.DirectionalLight(0x7c4dff,0.8);dl.position.set(5,10,7);s.add(dl);
s.add(new THREE.GridHelper(20,20,0x2a2245,0x1a1630));
for(const v of T.vectors){const g=new THREE.SphereGeometry(0.18,16,16);const m=new THREE.MeshPhongMaterial({color:C[v.type]||C.other,emissive:C[v.type]||C.other,emissiveIntensity:0.3});const mesh=new THREE.Mesh(g,m);mesh.position.set(v.pos[0],v.pos[1],v.pos[2]);s.add(mesh);}
for(const op of T.operations){const o=T.vectors[op.output];if(!o)continue;for(const i of op.inputs){const iv=T.vectors[i];if(!iv)continue;const pts=[new THREE.Vector3(iv.pos[0],iv.pos[1],iv.pos[2]),new THREE.Vector3(o.pos[0],o.pos[1],o.pos[2])];const geo=new THREE.BufferGeometry().setFromPoints(pts);const mat=new THREE.LineBasicMaterial({color:C[op.type]||C.other,opacity:0.4,transparent:true});s.add(new THREE.Line(geo,mat));}}
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();r.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ctl.update();r.render(s,cam);})();
</script></body></html>
        """.trimIndent()
    }

    private fun splitArgs(s: String): List<String> {
        if (s.isBlank()) return emptyList()
        val out = mutableListOf<String>()
        val cur = StringBuilder()
        var quote: Char? = null
        for (c in s) {
            when {
                quote != null -> if (c == quote) quote = null else cur.append(c)
                c == '"' || c == '\'' -> quote = c
                c.isWhitespace() -> if (cur.isNotEmpty()) { out.add(cur.toString()); cur.setLength(0) }
                else -> cur.append(c)
            }
        }
        if (cur.isNotEmpty()) out.add(cur.toString())
        return out
    }
}
