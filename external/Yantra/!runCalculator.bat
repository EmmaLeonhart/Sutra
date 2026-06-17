@echo off
REM Launch the Yantra CLI calculator (apps/calc).
REM Type an expression like "5 * 10 =" or "2 + 3 * 4 =" and it prints the
REM answer, computed on the Sutra substrate through the kernel and verified
REM exact (non-exact results are refused, never guessed).
REM
REM First launch compiles the .su services and may download the embedding
REM model, so it can take a little while to come up. Quit with Ctrl-Z then
REM Enter (end-of-input), or Ctrl-C.
cd /d "%~dp0"
python apps\calc\calc.py
pause
