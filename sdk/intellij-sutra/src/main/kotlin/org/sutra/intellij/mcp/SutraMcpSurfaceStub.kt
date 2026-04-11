package org.sutra.intellij.mcp

/**
 * Stub implementation of [SutraMcpSurface]. Every method throws
 * [NotImplementedError] with a message that points at the spec section
 * and the blocker for the real implementation.
 *
 * This exists so the interface isn't orphaned — any future code that
 * wants to depend on the MCP surface can inject this stub during
 * development and get loud failures in the exact place the real
 * implementation needs to land, instead of silent no-ops.
 *
 * The stub itself is not registered as an application service. Wiring it
 * to the IntelliJ MCP tool registry is part of the full MCP pass, which
 * can't land until at least the syntax-check loop (parse/check/diagnostics)
 * has a real implementation behind it — that requires the PSI parser,
 * which in turn is listed as out of scope for the current plugin
 * revision in `sdk/intellij-sutra/README.md`.
 */
class SutraMcpSurfaceStub : SutraMcpSurface {

    override fun parse(source: String): Any =
        unimplemented("parse", "needs real PSI parser (out of scope this revision)")

    override fun check(source: String, spaceRef: String): Any =
        unimplemented("check", "needs PSI parser + runtime MCP space resolution")

    override fun diagnostics(filePath: String): Any =
        unimplemented("diagnostics", "reachable via SutraExternalAnnotator; needs MCP adapter")

    override fun scaffold(template: String, params: Map<String, Any>): Any =
        unimplemented("scaffold", "needs workspace/project system")

    override fun compile(projectPath: String): Any =
        unimplemented("compile", "needs workspace/project system and compiler driver")

    override fun run(artifactPath: String, input: Any): Any =
        unimplemented("run", "needs compiler driver and instrumented runtime")

    override fun inspect(vector: Any): Any =
        unimplemented("inspect", "needs runtime MCP server bridge")

    private fun unimplemented(name: String, blocker: String): Nothing =
        throw NotImplementedError(
            "SutraMcpSurface.$name is design-only. Blocker: $blocker. " +
                    "See planning/sutra-spec/20-ide-architecture.md §\"Minimum Agent Workflows\"."
        )
}
