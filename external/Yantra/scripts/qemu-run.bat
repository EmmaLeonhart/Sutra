@echo off
REM Boot the Yantra multiboot1 kernel in QEMU.
REM See scripts/qemu-run.sh for the full doc.

setlocal
set "REPO_ROOT=%~dp0.."
set "KERNEL=%REPO_ROOT%\bootloader\target\i686-yantra\release\yantra-bootloader"

if not exist "%KERNEL%" (
  echo ERROR: kernel not found at %KERNEL%
  echo Run scripts\qemu-build.bat first.
  exit /b 1
)

REM Look for qemu-system-x86_64.exe in PATH; if not, check the
REM standard Windows install location.
where qemu-system-x86_64 >nul 2>nul
if errorlevel 1 (
  if exist "C:\Program Files\qemu\qemu-system-x86_64.exe" (
    set "QEMU=C:\Program Files\qemu\qemu-system-x86_64.exe"
  ) else (
    echo ERROR: qemu-system-x86_64 not found in PATH or C:\Program Files\qemu.
    echo Install QEMU: winget install SoftwareFreedomConservancy.QEMU
    exit /b 1
  )
) else (
  set "QEMU=qemu-system-x86_64"
)

echo ^>^>^> Booting Yantra kernel in QEMU. Ctrl+A then X to exit.
"%QEMU%" -kernel "%KERNEL%" -serial stdio -display none -no-reboot
