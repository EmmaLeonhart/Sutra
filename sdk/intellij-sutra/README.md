# Sutra for IntelliJ Platform

**Status: v0.2 static additions on top of the v0.1 scaffold. Not yet
built or opened in a live IDE.** The first thing you should do is run
`gradle wrapper && ./gradlew test && ./gradlew runIde` and fix whatever
breaks — the scaffold's Kotlin code has not been compiled end-to-end
because the authoring environment hasn't had the IntelliJ Platform SDK
available.

This is the reference IDE for **Sutra** — the fuzzy-by-default vector
programming language whose primitives are hypervectors in embedding space.
See [`planning/sutra-spec/20-ide-architecture.md`](../../planning/sutra-spec/20-ide-architecture.md)
for why the reference IDE targets the IntelliJ Platform instead of a VS
Code extension, and for the much larger design this scaffold is the
foundation of.

## What's in v0.1

- **File type + language registration** for `.su` sources, with a basis-
  vector file icon.
- **Hand-written lexer** covering all four comment forms (`//`, `/* */`,
  `///`, `#`), plain and interpolated strings, keywords, primitive types,
  builtins, numbers, operators, the illegal `|>` pipe-forward token, and
  bracket delimiters. Word lists mirror `sdk/sutra-compiler` and the VS
  Code extension.
- **Syntax highlighter + color settings page** — every token category is
  rebindable under *Settings → Editor → Color Scheme → Sutra*.
- **Brace matcher, commenter, and quote handler** — `Ctrl+/`, `Ctrl+Shift+/`,
  bracket highlighting, and auto-insertion all work.
- **Completion contributor** — keyword, primitive-type, and builtin
  completion with hover-text hints.
- **Live templates** — every snippet from `sdk/vscode-sutra/snippets/sutra.json`
  ported to an IntelliJ-native live-template bundle, activated inside
  `.su` files only.
- **External annotator** that runs `python -m sutra_compiler --json` on
  the current file and surfaces the resulting diagnostics (including the
  `AKA####` codes) in the editor and Problems panel.

## What v0.2 adds on top of v0.1

- **Settings UI** under *Settings → Tools → Sutra*. Replaces the
  env-var-only v0.1 configuration with a proper `Configurable`. Two
  fields (compiler executable, compiler args); blank values fall back
  to `$SUTRA_COMPILER` / `$SUTRA_COMPILER_ARGS`, then to the hardcoded
  defaults (`python` / `-m sutra_compiler`). v0.1 users who only set
  env vars keep working unchanged.
- **Persistent state service** (`SutraSettings`) holding those fields
  application-wide so the compiler path survives IDE restarts.
- **Lexer unit tests** — `src/test/kotlin/org/sutra/intellij/SutraLexerTest.kt`
  covers every token category (comments, literals, keywords, primitive
  types, builtins, operators, brackets, the illegal `|>`) plus a small
  realistic function snippet as an integration test. Pure JUnit 4, no
  platform test-application dependency.
- **MCP surface interface** — `mcp/SutraMcpSurface.kt` declares the
  agent-authoring tool methods (`parse`, `check`, `diagnostics`,
  `scaffold`, `compile`, `run`, `inspect`) named in the spec's
  "Minimum Agent Workflows" section, plus a loud-failure stub
  (`SutraMcpSurfaceStub`). The interface is the stable part; the
  implementation lands with the real PSI parser in a later revision.

## What's explicitly *not* in v0.1

These are all called out in the IDE architecture doc and will land in
later scaffolds:

- Real Kotlin parser + PSI tree. (v0.1 parses as a flat token run.)
- Name resolution, type checking, cross-file analysis.
- Runtime MCP server hosting.
- The IntelliJ MCP server exposing `.su` PSI to external agents.
- Embedding-space visualizer pane (3D hyperplane with user-chosen
  composite basis — see
  [`planning/sutra-spec/20-ide-architecture.md`](../../planning/sutra-spec/20-ide-architecture.md)).
- Fly-brain visualizer pane — see
  [`planning/fly-brain-visualizer.md`](../../planning/fly-brain-visualizer.md).
- Debugger integration, workspace/project system, scaffolding templates,
  bundled vertical stack installer.

## Building

Prereqs:

- JDK 17
- Gradle 8.7+ (or run `gradle wrapper` once to generate a wrapper locally)

```bash
cd sdk/intellij-sutra
gradle wrapper           # first time only
./gradlew runIde         # launches a sandbox IntelliJ IDEA Community
./gradlew buildPlugin    # produces build/distributions/Sutra-0.1.0.zip
```

The sandbox instance opens with the Sutra plugin installed; drop any
`.su` file into it (e.g. anything from `examples/` or
`examples/_legacy_syntax_tour.su` for a full syntax tour) to
smoke-test highlighting, completion, live templates, and diagnostics.

## Compiler path configuration

`SutraExternalAnnotator` shells out to the reference compiler. Its
configuration is resolved by `SutraSettings` through a three-step
fallback chain:

1. **Settings UI**: *Settings → Tools → Sutra* (v0.2+, persistent across
   restarts, application scope).
2. **Environment variables** `SUTRA_COMPILER` / `SUTRA_COMPILER_ARGS`
   (v0.1 behavior; still supported so old installs keep working).
3. **Hardcoded defaults**: `python` and `-m sutra_compiler`.

| Source              | Compiler field | Args field         |
|---------------------|----------------|--------------------|
| Settings UI (blank) | → env var      | → env var          |
| Env var (unset)     | → default      | → default          |
| Default             | `python`       | `-m sutra_compiler` |

So the default command line is effectively:

```
python -m sutra_compiler --json <file>.su
```

Make sure the `sutra_compiler` package is importable from whichever
Python interpreter you point the setting/env var at. The easiest way is:

```bash
cd sdk/sutra-compiler
pip install -e .
```

If `python` isn't on PATH, either set the Settings UI field or set
`SUTRA_COMPILER` to an absolute path before launching IntelliJ.

## Project layout

```
sdk/intellij-sutra/
  build.gradle.kts            Gradle build with org.jetbrains.intellij 1.17.4
  settings.gradle.kts
  gradle.properties           Plugin + platform version pins
  src/main/
    kotlin/org/sutra/intellij/
      SutraLanguage.kt              Language singleton
      SutraFileType.kt              .su file type + icon
      SutraIcons.kt
      SutraTokenType.kt             Base IElementType class
      SutraTokenTypes.kt            Catalog of every leaf token
      SutraLexer.kt                 Hand-written LexerBase subclass
      SutraFile.kt                  PsiFile for .su
      SutraParserDefinition.kt      Flat parser (no real grammar yet)
      SutraBraceMatcher.kt          {}, (), [] pairing
      SutraCommenter.kt             Ctrl+/ toggles //
      SutraQuoteHandler.kt          Quote auto-insertion for "..." and $"..."
      SutraSyntaxHighlighter.kt     Lexer-driven highlight categories
      SutraSyntaxHighlighterFactory.kt
      SutraColorSettingsPage.kt     Settings UI entry
      SutraCompletionContributor.kt Keyword / primitive / builtin completion
      SutraLiveTemplateContext.kt   "SUTRA" context for live templates
      SutraExternalAnnotator.kt     Runs sutrac --json, surfaces diagnostics
      SutraSettings.kt              Persistent compiler-path settings (v0.2)
      SutraSettingsConfigurable.kt  Settings UI under Tools → Sutra (v0.2)
      mcp/
        SutraMcpSurface.kt          Design-only MCP tool interface (v0.2)
        SutraMcpSurfaceStub.kt      Loud-failure stub of the same (v0.2)
    resources/
      META-INF/plugin.xml
      icons/sutra.svg
      liveTemplates/Sutra.xml
  src/test/
    kotlin/org/sutra/intellij/
      SutraLexerTest.kt             Pure-JUnit 4 lexer tests (v0.2)
```

## Keeping in sync with the rest of the SDK

Three lists have to stay aligned, because all three are consumed by
different parts of the toolchain:

1. `sdk/sutra-compiler/sutra_compiler/lexer.py` — the reference
   lexer, which the external annotator shells out to.
2. `sdk/vscode-sutra/syntaxes/sutra.tmLanguage.json` and
   `sdk/vscode-sutra/src/extension.ts` — the VS Code extension.
3. `sdk/intellij-sutra/src/main/kotlin/org/sutra/intellij/SutraLexer.kt`
   and `SutraCompletionContributor.kt` — this plugin.

If you add a keyword, a primitive type, or a builtin to the language,
update all three, plus `planning/sutra-spec/21-builtins.md` if it's a
VSA builtin.

## License

Same as the rest of the Sutra repository.
