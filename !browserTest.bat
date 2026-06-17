@echo off
REM !browserTest.bat — B8: live trainable-button browser smoke.
REM
REM Launches the Sutra substrate button server (learned-CTR reward head + copy bandit,
REM --live-ctr) and opens the demo in your browser. The button is rendered by the Sutra
REM substrate; press "Owner prefers A|B" to steer the design by owner taste, and CLICK the
REM buttons as a visitor — Adam ascends the blended owner x CTR reward through the substrate
REM render and the copy bandit chases clicks, so the button restyles toward what gets clicked.
REM
REM The browser opens immediately; if it shows "can't connect", give the server a second to
REM bind and refresh. Press Ctrl+C in this window to stop the server.
cd /d "%~dp0"
start "" http://127.0.0.1:8770/
python demos\gui\button_server.py --live-ctr
pause
