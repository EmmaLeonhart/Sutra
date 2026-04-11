@echo off
REM =====================================================================
REM  !editor.bat  —  Launch the Akasha IntelliJ plugin in a sandbox IDE.
REM
REM  The Akasha "editor" is not a standalone IDE — it's an IntelliJ
REM  Platform plugin (sdk\intellij-akasha\). "Opening" it means launching
REM  IntelliJ IDEA Community in a sandbox with the Akasha plugin
REM  preinstalled, which is exactly what the gradle task `runIde` does.
REM
REM  First run:
REM    - Downloads the IntelliJ Platform SDK (~700 MB) into Gradle's
REM      cache under %USERPROFILE%\.gradle\. This takes several minutes
REM      but only happens once.
REM    - Compiles the plugin's Kotlin source.
REM    - Starts a sandbox IntelliJ IDEA Community window with the plugin
REM      loaded. Drop any .ak file into it (e.g. akasha-demo-program.ak
REM      from this repo root) to smoke-test highlighting, completion,
REM      live templates, and diagnostics.
REM
REM  Subsequent runs reuse the cached SDK and are fast.
REM
REM  Requirements:
REM    - JDK 17 or newer on PATH (Java 21 is fine).
REM    - sdk\intellij-akasha\gradlew.bat must exist. If it doesn't yet,
REM      generate it once from sdk\intellij-akasha with:
REM        gradle wrapper
REM      (which requires a system Gradle install), or copy the wrapper
REM      from another project. The wrapper is checked into the repo so
REM      you should not normally need to regenerate it.
REM =====================================================================

setlocal

set "PLUGIN_DIR=%~dp0sdk\intellij-akasha"

if not exist "%PLUGIN_DIR%\gradlew.bat" (
    echo.
    echo Error: "%PLUGIN_DIR%\gradlew.bat" does not exist.
    echo.
    echo The Gradle wrapper has not been generated yet. From "%PLUGIN_DIR%"
    echo run:
    echo     gradle wrapper
    echo once with a system Gradle install, commit the resulting
    echo gradlew, gradlew.bat, and gradle\wrapper\ files, and then
    echo re-run this script.
    echo.
    exit /b 1
)

pushd "%PLUGIN_DIR%"
call gradlew.bat runIde
set "RC=%ERRORLEVEL%"
popd

endlocal & exit /b %RC%
