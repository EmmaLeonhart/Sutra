@echo off
REM Yantra demo launcher -- pick which app/test to run.
REM
REM Lives at the repo root so you can double-click it from Explorer. The
REM individual !run<App>.bat files still work; this is the chooser if you
REM don't remember which.
cd /d "%~dp0"

:menu
echo.
echo ==========================================================
echo   Yantra demo launcher
echo ==========================================================
echo   Apps:
echo     [1] calc       -- CLI calculator (substrate dispatch)
echo     [2] terminal   -- terminal surface (echo/calc/help)
echo     [3] gui        -- static GUI: radial-glow window
echo     [4] gui-toggle -- GUI red/blue toggle (click to flip)
echo     [5] gui-count  -- GUI counter (click to count on substrate)
echo     [6] gui-rust   -- Rust-orchestrator GUI counter
echo     [7] font       -- text-input pixel-font demo (type A-Z, 0-9)
echo     [8] echo-demo  -- echo round-trip via the terminal demo script
echo.
echo   Test gates:
echo     [t] all tests  -- pytest tests/ -v
echo     [tf] font      -- pytest tests/test_font.py -v
echo     [tc] calc      -- pytest tests/test_calc.py -v
echo     [tg] gui       -- pytest tests/test_gui_*.py -v
echo     [tk] kernel    -- pytest tests/test_kernel*.py -v
echo.
echo     [q] quit
echo ==========================================================
set "choice="
set /p choice="pick: "
if /i "%choice%"=="1"  goto :calc
if /i "%choice%"=="2"  goto :terminal
if /i "%choice%"=="3"  goto :gui
if /i "%choice%"=="4"  goto :gui_toggle
if /i "%choice%"=="5"  goto :gui_count
if /i "%choice%"=="6"  goto :gui_rust
if /i "%choice%"=="7"  goto :font
if /i "%choice%"=="8"  goto :echo_demo
if /i "%choice%"=="t"  goto :test_all
if /i "%choice%"=="tf" goto :test_font
if /i "%choice%"=="tc" goto :test_calc
if /i "%choice%"=="tg" goto :test_gui
if /i "%choice%"=="tk" goto :test_kernel
if /i "%choice%"=="q"  goto :end
echo unknown choice "%choice%"
goto :menu

:calc
python apps\calc\calc.py
goto :after

:terminal
python apps\terminal\demo.py
goto :after

:gui
python apps\gui\window.py
goto :after

:gui_toggle
python apps\gui\click_demo.py
goto :after

:gui_count
python apps\gui\counter_demo.py
goto :after

:gui_rust
cd apps\gui-rust
cargo run --bin yantra-gui-counter
cd /d "%~dp0"
goto :after

:font
python apps\font\font_demo.py
goto :after

:echo_demo
python apps\terminal\demo.py
goto :after

:test_all
python -m pytest tests/ -v
goto :after

:test_font
python -m pytest tests/test_font.py -v
goto :after

:test_calc
python -m pytest tests/test_calc.py -v
goto :after

:test_gui
python -m pytest tests/test_gui_render.py tests/test_gui_click.py tests/test_gui_counter.py -v
goto :after

:test_kernel
python -m pytest tests/test_kernel.py tests/test_kernel_sutra.py tests/test_kernel_checkpoint.py tests/test_kernel_ram_tier.py tests/test_kernel_gpu_tiers.py -v
goto :after

:after
echo.
pause
goto :menu

:end
