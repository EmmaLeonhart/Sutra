/*
 * Akasha IntelliJ Platform plugin — v0.1 scaffold.
 *
 * This build file targets IntelliJ IDEA Community 2024.1 via the classic
 * org.jetbrains.intellij Gradle plugin (1.17.x). The newer
 * org.jetbrains.intellij.platform plugin (2.x) is not yet used because the
 * 1.x plugin has more public documentation and makes the scaffold easier
 * to evolve by hand. Swap it when the plugin grows past v0.1.
 */

plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "1.9.24"
    id("org.jetbrains.intellij") version "1.17.4"
}

group = providers.gradleProperty("pluginGroup").get()
version = providers.gradleProperty("pluginVersion").get()

repositories {
    mavenCentral()
}

dependencies {
    // Gson is used by AkashaExternalAnnotator to parse the `--json` output
    // of the reference compiler. IntelliJ bundles a Gson of its own, but
    // declaring our own copy avoids coupling to platform internals.
    implementation("com.google.code.gson:gson:2.10.1")
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

kotlin {
    jvmToolchain(17)
}

intellij {
    version.set(providers.gradleProperty("platformVersion").get())
    type.set(providers.gradleProperty("platformType").get())
    plugins.set(listOf<String>())
}

tasks {
    patchPluginXml {
        sinceBuild.set(providers.gradleProperty("pluginSinceBuild").get())
        untilBuild.set(providers.gradleProperty("pluginUntilBuild").get())
    }

    wrapper {
        gradleVersion = "8.7"
    }

    buildSearchableOptions {
        // No Configurable UI in v0.1 — skip the expensive searchable-options
        // generation to keep local builds fast.
        enabled = false
    }
}
