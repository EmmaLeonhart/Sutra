@echo off
REM Launch Yantra's RUST GUI counter (apps/gui-rust) — Rust orchestrator front-end.
REM The Rust process owns the window + clicks + painting; it spawns the Python +
REM Sutra substrate (apps/gui/counter_substrate_server.py) as a child and asks IT
REM for each frame. CLICK to count 0,1,2,3,... — the +1 and the pixel field are
REM computed ON THE SUTRA SUBSTRATE; Rust only paints what the substrate sent.
REM The glow steps left->right as the count rises; the title shows the count.
REM Press Esc or close the window to quit.
REM
REM Needs the Rust toolchain (cargo) and python on PATH. The FIRST run builds the
REM crate + downloads minifb (a minute or two), and the .su compile may pull the
REM embedding model, so first launch is slow.
cd /d "%~dp0"
cargo run --release --manifest-path apps\gui-rust\Cargo.toml
pause
