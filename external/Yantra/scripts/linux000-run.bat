@echo off
REM Boot the bare-metal Linux 0.00 replica in QEMU.
REM See scripts/linux000-run.sh for the full doc. Two hardcoded
REM tasks A/B alternated by the real 8253 PIT timer interrupt;
REM output to VGA 0xB8000 + COM1. Halts after LIMIT chars but
REM QEMU stays open — exit with Ctrl+A then X.

setlocal
set "REPO_ROOT=%~dp0.."
set "KERNEL=%REPO_ROOT%\bootloader\target\i686-yantra\release\linux000"

if not exist "%KERNEL%" (
  echo ERROR: kernel not found at %KERNEL%
  echo Run scripts\linux000-build.bat first.
  exit /b 1
)

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

echo ^>^>^> Booting bare-metal Linux 0.00 in QEMU. Ctrl+A then X to exit.
"%QEMU%" -kernel "%KERNEL%" -serial stdio -display none -no-reboot
