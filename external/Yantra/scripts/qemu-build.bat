@echo off
REM Build the Yantra multiboot1 kernel.
REM See scripts/qemu-build.sh for the full doc.

setlocal
set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%\bootloader" || exit /b 1

where cargo >nul 2>nul
if errorlevel 1 (
  echo ERROR: cargo not found. Install Rust from https://rustup.rs/
  exit /b 1
)

echo ^>^>^> cargo -Zjson-target-spec build --release...
cargo -Zjson-target-spec build --release
if errorlevel 1 exit /b 1

set "OUT=target\i686-yantra\release\yantra-bootloader"
if exist "%OUT%" (
  echo ^>^>^> Built: %OUT%
  echo ^>^>^> Run with: scripts\qemu-run.bat
) else (
  echo ERROR: expected output %OUT% not found
  exit /b 1
)

popd
