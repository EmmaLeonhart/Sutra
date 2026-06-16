@echo off
REM ---------------------------------------------------------------------------
REM Launch the Sutra hero RGB Adam-RLHF steering window (GUI rebuild G4).
REM
REM A COLOUR pixel image rendered entirely by the Sutra substrate; press A / B to
REM say which frame you prefer and Adam backpropagates your preference THROUGH the
REM differentiable Sutra render to morph the picture across position, size,
REM brightness AND colour (cr/cg/cb tints) in real time.
REM
REM Requires: torch, pillow (PIL), and the Sutra compiler runtime deps.
REM Usage:  double-click, or:  run_adam_rgb_gui.bat --size 96 --cell 5
REM %~dp0 = this file's folder, so it runs regardless of the current directory.
REM ---------------------------------------------------------------------------
python "%~dp0adam_window_rgb.py" %*
pause
