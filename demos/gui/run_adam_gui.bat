@echo off
REM ---------------------------------------------------------------------------
REM Launch the Sutra hero Adam-RLHF steering window (GUI rebuild R4).
REM
REM A pixel image rendered entirely by the Sutra substrate; press WARMER / COLDER
REM and Adam backpropagates your preference THROUGH the differentiable Sutra render
REM to morph the picture in real time.
REM
REM Requires: torch, pillow (PIL), and the Sutra compiler runtime deps.
REM Usage:  double-click, or:  run_adam_gui.bat --size 96 --cell 5
REM %~dp0 = this file's folder, so it runs regardless of the current directory.
REM ---------------------------------------------------------------------------
python "%~dp0adam_window.py" %*
pause
