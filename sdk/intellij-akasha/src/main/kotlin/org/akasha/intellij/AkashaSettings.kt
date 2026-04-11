package org.akasha.intellij

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.components.service

/**
 * Application-level persistent settings for the Akasha plugin.
 *
 * Replaces the v0.1 environment-variable-only configuration for the
 * external annotator. The env vars continue to work as a fallback, so
 * existing v0.1 users don't need to migrate — the resolution order is:
 *
 *   1. This settings service (set via Settings → Tools → Akasha)
 *   2. Environment variables AKASHA_COMPILER / AKASHA_COMPILER_ARGS
 *   3. Hardcoded defaults (`python` + `-m akasha_compiler`)
 *
 * Application scope is correct because the compiler is a global
 * toolchain — projects don't each have their own interpreter in the
 * common case. If per-project override turns out to matter, a
 * project-level overlay can be added later without changing the API.
 */
@Service(Service.Level.APP)
@State(
    name = "AkashaSettings",
    storages = [Storage("akasha.xml")],
)
class AkashaSettings : PersistentStateComponent<AkashaSettings.State> {

    /**
     * Serialized settings state. Public no-arg fields so IntelliJ's
     * XML serialization framework can round-trip it without any custom
     * serializer wiring.
     */
    data class State(
        /**
         * Executable to invoke. Blank means "fall back to env var or default".
         * Default is blank so fresh installs pick up [DEFAULT_COMPILER] via
         * the fallback chain in [effectiveCompiler].
         */
        var compilerPath: String = "",

        /**
         * Arguments to pass before `--json <file>`. Blank means "fall back".
         * Default is blank; blank resolves to [DEFAULT_COMPILER_ARGS] through
         * the fallback chain in [effectiveCompilerArgs].
         */
        var compilerArgs: String = "",
    )

    private var myState = State()

    override fun getState(): State = myState

    override fun loadState(state: State) {
        myState = state
    }

    /**
     * Resolve the compiler executable with the three-step fallback chain.
     * Trims whitespace; returns [DEFAULT_COMPILER] on any empty / unset value.
     */
    fun effectiveCompiler(): String {
        val configured = myState.compilerPath.trim()
        if (configured.isNotEmpty()) return configured
        val env = System.getenv("AKASHA_COMPILER")?.trim()
        if (!env.isNullOrEmpty()) return env
        return DEFAULT_COMPILER
    }

    /**
     * Resolve the compiler args with the three-step fallback chain.
     * Trims whitespace; returns [DEFAULT_COMPILER_ARGS] on any empty value.
     */
    fun effectiveCompilerArgs(): String {
        val configured = myState.compilerArgs.trim()
        if (configured.isNotEmpty()) return configured
        val env = System.getenv("AKASHA_COMPILER_ARGS")?.trim()
        if (!env.isNullOrEmpty()) return env
        return DEFAULT_COMPILER_ARGS
    }

    companion object {
        const val DEFAULT_COMPILER = "python"
        const val DEFAULT_COMPILER_ARGS = "-m akasha_compiler"

        /** Convenience accessor: `AkashaSettings.getInstance()` from anywhere. */
        @JvmStatic
        fun getInstance(): AkashaSettings = service()
    }
}
