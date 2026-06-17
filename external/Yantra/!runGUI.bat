@echo off
REM Launch Yantra's first interactive GUI (apps/gui).
REM A radial glow opens in a window; CLICK ANYWHERE to toggle it red <-> blue.
REM Both the glow field (frame.su's pixel(x,y) = 1 - x^2 - y^2) and the colour
REM STATE flip (toggle.su's flip(s) = 1 - s) are computed on the Sutra
REM substrate; the host only delivers the click and paints the result.
REM
REM First launch compiles the .su services and may download the embedding
REM model, so it can take a little while to come up. Close the window to quit.
cd /d "%~dp0"
python apps\gui\click_demo.py
pause
