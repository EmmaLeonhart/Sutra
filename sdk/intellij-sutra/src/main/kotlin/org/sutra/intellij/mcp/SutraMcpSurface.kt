package org.sutra.intellij.mcp

/**
 * Interface surface for the Sutra MCP tools the IDE will eventually expose
 * to external agents.
 *
 * **Status: design-only.** This file is the *Kotlin-level anchor* for the
 * agent-authoring workflows described in
 * `planning/sutra-spec/20-ide-architecture.md` §"Minimum Agent Workflows
 * The MCP Server Must Support". None of these methods are wired to the
 * IntelliJ MCP server yet — the wiring lives in a later plugin revision
 * and needs the real PSI parser to land first (because `parse` returns
 * the AST shape, not a classified token stream, and `check` needs
 * cross-file name resolution).
 *
 * The reason this interface exists *now*, even though the implementation
 * is empty, is the "agent/human parity" rule from the same spec section:
 *
 * > Every feature must be agent-accessible. If a human can do it through
 * > the UI, an agent must be able to do it through the MCP server. No
 * > human-only affordances.
 *
 * Anchoring the MCP surface in a compile-checked Kotlin interface makes
 * drift between the human-facing plugin features and the agent-facing
 * MCP tools mechanically detectable: when a new `@extensionPoint` or
 * `ToolWindow` ships on the human side, the same capability must appear
 * on this interface or the parity rule has been broken.
 *
 * ## Tool groups
 *
 * Two loops from the spec section, mapped to method groups:
 *
 * - **The syntax-check loop** — [parse], [check], [diagnostics]. Cheap,
 *   side-effect-free feedback the agent can poll continuously while
 *   editing.
 * - **The prototype-build loop** — [scaffold], [compile], [run],
 *   [inspect]. More expensive; drives a project from scaffold through
 *   compiled-and-run with instrumented output.
 *
 * Return types are deliberately declared as `Any` in this skeleton — the
 * final JSON-compatible shape will be filled in when the implementation
 * lands. The method names, parameter lists, and English docstrings are
 * the stable part.
 */
interface SutraMcpSurface {

    // ------------------------------------------------------------------
    // Syntax-check loop (spec §"1. The syntax-check loop")
    // ------------------------------------------------------------------

    /**
     * Pure syntactic parse — no embedding space needed.
     *
     * Expected shape of the returned value: `{ ast, parse_errors }` where
     * `ast` is a JSON-serializable PSI snapshot and `parse_errors` is a
     * list of structured diagnostics with source spans.
     *
     * Corresponds to the spec's `sutra.parse(source)` tool.
     */
    fun parse(source: String): Any

    /**
     * Full semantic check against a target embedding space, including the
     * empirical-initiation probe results.
     *
     * Expected shape: `{ type_errors, probe_warnings, unresolved_entities }`.
     *
     * The `spaceRef` parameter identifies which embedding space the check
     * runs against — it's a string handle, not the space itself, because
     * spaces live in the runtime MCP server, not the IDE MCP server.
     *
     * Corresponds to the spec's `sutra.check(source, space_ref)` tool.
     */
    fun check(source: String, spaceRef: String): Any

    /**
     * Same structured diagnostics the red-squiggle UI layer consumes,
     * queryable at any time against an open file.
     *
     * Takes a file path (or virtual-file URL) and returns the current
     * diagnostic list for that file — the same objects
     * [org.sutra.intellij.SutraExternalAnnotator] produces, just
     * reachable without going through the inspection pipeline.
     *
     * Corresponds to the spec's `sutra.diagnostics(file)` tool.
     */
    fun diagnostics(filePath: String): Any

    // ------------------------------------------------------------------
    // Prototype-build loop (spec §"2. The prototype-build loop")
    // ------------------------------------------------------------------

    /**
     * Bootstrap a new solution/project skeleton from a template.
     *
     * `template` is a named starter (e.g. `"classifier"`, `"similarity-retriever"`,
     * `"cone-traversal-demo"`, `"fly-brain-substrate"`) — see the
     * "Scaffolding templates" open question in 20-ide-architecture.md
     * for the starter set. `params` is a JSON-compatible map of template
     * arguments.
     *
     * Expected shape: `{ project, files }`.
     *
     * Corresponds to the spec's `sutra.scaffold(template, params)` tool.
     */
    fun scaffold(template: String, params: Map<String, Any>): Any

    /**
     * Drive the compiler directly, without going through the UI's run
     * button. Produces a compiled artifact or compile errors.
     *
     * Expected shape: `{ artifact, compile_errors }`.
     *
     * Corresponds to the spec's `sutra.compile(project)` tool.
     */
    fun compile(projectPath: String): Any

    /**
     * Execute a compiled artifact with instrumented output — not just the
     * final vector but the intermediate steps, the S1/Sutra routing
     * decisions, and any empirical-initiation corrections that fired.
     *
     * Expected shape: `{ output, intermediate_vectors, trace }`.
     *
     * Corresponds to the spec's `sutra.run(artifact, input)` tool.
     */
    fun run(artifactPath: String, input: Any): Any

    /**
     * Query the runtime MCP server for "what does this vector mean in the
     * current space": nearest neighbors, cone projections, magnitude,
     * label resolution. The agent's equivalent of a human dragging a
     * point around in the visualizer pane.
     *
     * Expected shape: `{ nearest, cone, magnitude, labels }`.
     *
     * Corresponds to the spec's `sutra.inspect(vector)` tool.
     */
    fun inspect(vector: Any): Any
}
