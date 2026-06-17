@echo off
REM Build the bare-metal Linux 0.00 replica (2nd bin in the
REM bootloader crate). See scripts/linux000-build.sh for the doc.

setlocal
set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%\bootloader" || exit /b 1

where cargo >nul 2>nul
if errorlevel 1 (
  echo ERROR: cargo not found. Install Rust from https://rustup.rs/
  exit /b 1
)

echo ^>^>^> cargo -Zjson-target-spec build --release --bin linux000...
cargo -Zjson-target-spec build --release --bin linux000
if errorlevel 1 exit /b 1

set "OUT=target\i686-yantra\release\linux000"
if exist "%OUT%" (
  echo ^>^>^> Built: %OUT%
  echo ^>^>^> Run with: scripts\linux000-run.bat
) else (
  echo ERROR: expected output %OUT% not found
  exit /b 1
)

popd
