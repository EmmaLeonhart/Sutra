@echo off
REM Launch Yantra's GUI counter (apps/gui).
REM A green glow opens in a window; CLICK ANYWHERE to count 0, 1, 2, 3, ... —
REM each click runs count.su's step(n)=n+1 on the Sutra substrate, and the glow
REM steps left->right across the screen (its position chosen FROM the count on
REM the substrate). The window title shows the current count. It does not wrap
REM after 9 (we don't care past the count); the glow just exits the right edge.
REM
REM First launch compiles the .su services and may download the embedding
REM model, so it can take a little while to come up. Close the window to quit.
cd /d "%~dp0"
python apps\gui\counter_demo.py
pause
