@echo off
REM Drop into the Yantra dev container with the repo bind-mounted.
REM
REM First run builds the image (~5-10 min, dominated by torch CPU wheel
REM download); subsequent runs reuse the layers.
REM
REM Usage:
REM   scripts\dev-shell.bat                       interactive bash
REM   scripts\dev-shell.bat pytest                one-shot test run
REM   scripts\dev-shell.bat pytest -v -k kernel

setlocal

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul
set "REPO_ROOT=%CD%"
popd >nul

set "IMAGE_TAG=yantra-dev"

REM Build only if image is missing.
docker image inspect %IMAGE_TAG% >nul 2>&1
if errorlevel 1 (
  echo ^>^>^> Building %IMAGE_TAG% ^(first run takes ~5-10 minutes^)...
  docker build -t %IMAGE_TAG% "%REPO_ROOT%"
  if errorlevel 1 exit /b 1
)

docker run --rm -it -v "%REPO_ROOT%:/workspace" -w /workspace %IMAGE_TAG% %*
