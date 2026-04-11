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

    // JUnit 4 for the lexer unit tests under src/test/kotlin. The IntelliJ
    // gradle plugin's test classpath ships JUnit 4 transitively, but
    // declaring it explicitly makes the dependency clear and the tests
    // runnable even if the platform dep graph changes.
    testImplementation("junit:junit:4.13.2")
}

// Toolchain is JDK 21 (the lowest JDK we can reasonably require in this repo,
// since JDK 17 isn't installed on the reference development machine). Target
// bytecode is kept at 17 so the compiled plugin still loads on the JetBrains
// Runtime shipped with IntelliJ IDEA Community 2024.1, which is JBR 17. When
// we bump the platform version to an IDEA that ships JBR 21, the `release`
// and `jvmTarget` lines below can be bumped in lockstep.
java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

kotlin {
    jvmToolchain(21)
}

tasks.withType<JavaCompile>().configureEach {
    options.release.set(17)
}

tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    kotlinOptions {
        jvmTarget = "17"
    }
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

    runIde {
        // Auto-open the repo root as a project on launch. Without this,
        // the sandbox IntelliJ boots into a blank "Welcome to IntelliJ"
        // screen and the user has to navigate to the .ak files manually
        // — which is confusing if you don't know the plugin only activates
        // when you touch a .ak file. With this, the sandbox opens straight
        // into the !Claw4S project tree with akasha-demo-program.ak visible
        // at the root, so "is the plugin working?" is one click away.
        //
        // project.rootDir here is sdk/intellij-akasha; parentFile is sdk;
        // parentFile.parentFile is the repo root.
        args = listOf(project.rootDir.parentFile.parentFile.absolutePath)
    }

    wrapper {
        gradleVersion = "8.7"
    }

    buildSearchableOptions {
        // Searchable-options generation spins up a sandbox IDE to walk
        // every Configurable; it's slow but gives us "Akasha" hits in the
        // Settings search box now that AkashaSettingsConfigurable exists.
        // Turn off again only if CI wall-clock becomes a problem.
        enabled = true
    }

    test {
        // The lexer tests are plain JUnit 4 — nothing platform-y, no
        // running test application, just token assertions against
        // AkashaLexer driven directly from unit tests.
        useJUnit()
    }
}
