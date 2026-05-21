@echo off
REM =====================================================================
REM  editor.bat  —  Launch the Sutra IntelliJ plugin in a sandbox IDE.
REM
REM  Lives in sdk\intellij-sutra\ (the plugin dir) and runs from there;
REM  double-click it or invoke it from anywhere.
REM
REM  The Sutra "editor" is not a standalone IDE — it's an IntelliJ
REM  Platform plugin (this directory). "Opening" it means launching
REM  IntelliJ IDEA Community in a sandbox with the Sutra plugin
REM  preinstalled, which is exactly what the gradle task `runIde` does.
REM
REM  First run:
REM    - Downloads the IntelliJ Platform SDK (~700 MB) into Gradle's
REM      cache under %USERPROFILE%\.gradle\. This takes several minutes
REM      but only happens once.
REM    - Compiles the plugin's Kotlin source.
REM    - Starts a sandbox IntelliJ IDEA Community window with the plugin
REM      loaded. Drop any .su file into it (e.g. sutra-demo-program.su
REM      from this repo root) to smoke-test highlighting, completion,
REM      live templates, and diagnostics.
REM
REM  Subsequent runs reuse the cached SDK and are fast.
REM
REM  Requirements:
REM    - JDK 17 or newer on PATH (Java 21 is fine).
REM    - sdk\intellij-sutra\gradlew.bat must exist. If it doesn't yet,
REM      generate it once from sdk\intellij-sutra with:
REM        gradle wrapper
REM      (which requires a system Gradle install), or copy the wrapper
REM      from another project. The wrapper is checked into the repo so
REM      you should not normally need to regenerate it.
REM =====================================================================

setlocal

REM This script now lives inside the plugin dir, so %~dp0 *is* PLUGIN_DIR.
set "PLUGIN_DIR=%~dp0"
if "%PLUGIN_DIR:~-1%"=="\" set "PLUGIN_DIR=%PLUGIN_DIR:~0,-1%"

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
