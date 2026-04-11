package org.sutra.intellij

import com.intellij.codeInsight.completion.CompletionContributor
import com.intellij.codeInsight.completion.CompletionParameters
import com.intellij.codeInsight.completion.CompletionProvider
import com.intellij.codeInsight.completion.CompletionResultSet
import com.intellij.codeInsight.completion.CompletionType
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.patterns.PlatformPatterns
import com.intellij.util.ProcessingContext

/**
 * Keyword / primitive-type / builtin completion. Same word list as the
 * VS Code extension — once the real Kotlin parser lands, this contributor
 * should defer to the PSI tree for symbol-level completion.
 */
class SutraCompletionContributor : CompletionContributor() {

    init {
        extend(
            CompletionType.BASIC,
            PlatformPatterns.psiElement().withLanguage(SutraLanguage),
            SutraWordCompletionProvider(),
        )
    }

    private class SutraWordCompletionProvider : CompletionProvider<CompletionParameters>() {
        override fun addCompletions(
            parameters: CompletionParameters,
            context: ProcessingContext,
            result: CompletionResultSet,
        ) {
            for ((word, doc) in KEYWORDS) {
                result.addElement(
                    LookupElementBuilder.create(word)
                        .withTypeText("keyword")
                        .withTailText("  — ${doc.ifBlank { "Sutra keyword" }}", true)
                        .withBoldness(true),
                )
            }
            for ((word, doc) in PRIMITIVE_TYPES) {
                result.addElement(
                    LookupElementBuilder.create(word)
                        .withTypeText("primitive")
                        .withTailText("  — ${doc.ifBlank { "Sutra primitive type" }}", true),
                )
            }
            for ((word, doc) in BUILTINS) {
                result.addElement(
                    LookupElementBuilder.create(word)
                        .withTypeText("builtin")
                        .withTailText("  — ${doc.ifBlank { "Sutra built-in function" }}", true),
                )
            }
        }
    }

    companion object {
        /**
         * Keyword list — mirrors `sdk/vscode-sutra/src/extension.ts`.
         * Each entry has a one-line hover description so the completion
         * popup can render a tail hint.
         */
        private val KEYWORDS: List<Pair<String, String>> = listOf(
            "function" to "Free function. Public static by default. Return type precedes the name.",
            "method" to "Method attached to the enclosing object file. Public non-static by default.",
            "operator" to "Declare an overloaded operator. Usage: `function operator +(...)`.",
            "static" to "Modifier — class-attached, instance-free.",
            "public" to "Explicit public visibility (default for functions).",
            "private" to "Explicit private visibility.",
            "implicit" to "Mark an implicit cast declaration.",
            "var" to "Inferred-type mutable binding. Never combine with an explicit type.",
            "const" to "Immutable binding. Can be used with or without an explicit type.",
            "new" to "Construct a class instance.",
            "return" to "Return from a function.",
            "if" to "if / else branching. Condition must be bool or fuzzy.",
            "else" to "else branch of an if statement.",
            "while" to "while loop.",
            "for" to "C-style for loop.",
            "foreach" to "foreach loop over a tuple or collection.",
            "in" to "Source-of-iteration keyword inside foreach.",
            "do" to "do-while loop body.",
            "try" to "try block of a try/catch.",
            "catch" to "Catch a failure pattern from the try block.",
            "break" to "Exit the innermost loop.",
            "continue" to "Skip to the next loop iteration.",
            "this" to "Reference to the current object inside a method.",
        )

        private val PRIMITIVE_TYPES: List<Pair<String, String>> = listOf(
            "scalar" to "Plain numeric value. Used for thresholds, loop counters, weights.",
            "vector" to "Hypervector in semantic space. The core Sutra primitive.",
            "matrix" to "2D array. Functions are matrices at the substrate level.",
            "tuple" to "Grouped values without superposition. Different from bundling.",
            "string" to "UTF-8 string literal type.",
            "bool" to "Concrete boolean. Distinct from fuzzy at compile time.",
            "fuzzy" to "Fuzzy truth type — continuous-valued, collapsed via defuzzy.",
            "void" to "No return value.",
            "permutation" to "Permutation over a basis — used by VSA `permute` operations.",
            "map" to "Generic map<K, V> with lookup semantics.",
        )

        private val BUILTINS: List<Pair<String, String>> = listOf(
            "embed" to "Convert a string into a vector by running it through the embedding model.",
            "defuzzy" to "Collapse a fuzzy value into a concrete bool via recursive is_true.",
            "unsafeCast" to "Force a value to be reinterpreted as a different type.",
            "unsafeOverride" to "Override a call site's type acceptance without changing the value.",
            "snap" to "Non-algebraic lookup — closest entity in the space.",
            "similarity" to "Cosine similarity between two vectors.",
            "Cosine" to "Named cosine similarity function.",
            "Bundle" to "VSA bundling (superposition) of vectors.",
            "Bind" to "VSA binding (variable/value pairing).",
            "Blend" to "Weighted interpolation between vectors.",
            "Normalize" to "L2-normalize a vector.",
            // VSA builtins from planning/sutra-spec/21-builtins.md
            "bind" to "VSA bind — pair two vectors into a single compound.",
            "unbind" to "VSA unbind — extract one vector from a bound pair.",
            "bundle" to "VSA bundle — superpose vectors into a set-like composite.",
            "permute" to "Apply a permutation to a vector (rotation / sequence encoding).",
            "compose" to "Compose two permutations.",
            "basis_vector" to "Allocate a fresh basis vector in the VSA space.",
            "permutation_key" to "Allocate a fresh permutation key.",
            "identity_permutation" to "The identity permutation (no rotation).",
            "argmax_cosine" to "Argmax over a codebook by cosine similarity.",
        )
    }
}
