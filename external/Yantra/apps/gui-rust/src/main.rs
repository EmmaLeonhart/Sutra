//! Yantra GUI counter — Rust orchestrator front-end (subprocess bridge to Sutra).
//!
//! Emma's architecture (2026-05-25): this Rust process owns the window, the
//! mouse clicks, and the painting; it spawns the Python + Sutra substrate
//! (`apps/gui/counter_substrate_server.py`) as a child and asks IT for each
//! frame. The count (+1) and the pixel field are computed ON THE SUTRA
//! SUBSTRATE, not here — Rust does only window + event + paint. That is the
//! orchestrator's real job (I/O), with the substrate doing the compute: the
//! same host/substrate split the Python GUIs use, now with Rust as the host.
//! Rust deliberately does NOT redo the arithmetic; it asks the substrate.
//!
//! Protocol (see the server): send "I\n" (init), "C\n" (click = increment),
//! "Q\n" (quit) on the child's stdin; it replies with a "FRAME <count> <size>\n"
//! header then size*size little-endian f64 — the substrate field — which we
//! clamp + colour + blit.
//!
//! Run (from the repo root, so `apps/gui/...` resolves):
//!     cargo run --release                 # open the window; click to count
//!     cargo run --release -- --check      # headless: verify the bridge, no window

use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

const SIZE: usize = 64;

/// The Sutra substrate, running as a child process we talk to over pipes.
struct Substrate {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl Substrate {
    fn spawn(size: usize) -> Substrate {
        // Resolve the server relative to THIS crate (repo/apps/gui-rust). The
        // counter_substrate_server.py migrated to Sutra 2026-05-28 (Yantra commit
        // following Sutra ff5183ef); spawn path is now the Sutra submodule's
        // demos/gui/ rather than Yantra's apps/gui/.
        let server = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../external/Sutra/demos/gui/counter_substrate_server.py");
        let mut child = Command::new("python")
            .arg(&server)
            .arg("--size")
            .arg(size.to_string())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap_or_else(|e| {
                panic!(
                    "failed to launch the Sutra substrate server ({}): need `python` \
                     on PATH. server = {}",
                    e,
                    server.display()
                )
            });
        let stdin = child.stdin.take().expect("child stdin");
        let stdout = BufReader::new(child.stdout.take().expect("child stdout"));
        Substrate { child, stdin, stdout }
    }

    /// Send a one-letter command, read back `(count, field)`. The field is the
    /// substrate's `pixel(x, y, count)` brightness, row-major.
    fn request(&mut self, cmd: &[u8], size: usize) -> (i64, Vec<f64>) {
        self.stdin.write_all(cmd).expect("write to substrate");
        self.stdin.flush().expect("flush to substrate");

        let mut header = String::new();
        self.stdout.read_line(&mut header).expect("read frame header");
        let mut it = header.split_whitespace();
        assert_eq!(it.next(), Some("FRAME"), "bad frame header: {header:?}");
        let count: i64 = it.next().expect("count").parse().expect("count int");
        let sz: usize = it.next().expect("size").parse().expect("size int");
        assert_eq!(sz, size, "frame size {sz} != expected {size}");

        let mut body = vec![0u8; sz * sz * 8];
        self.stdout.read_exact(&mut body).expect("read frame body");
        let field = body
            .chunks_exact(8)
            .map(|c| f64::from_le_bytes(c.try_into().unwrap()))
            .collect();
        (count, field)
    }

    fn quit(&mut self) {
        let _ = self.stdin.write_all(b"Q\n");
        let _ = self.stdin.flush();
        let _ = self.child.wait();
    }
}

/// Clamp a substrate brightness to [0, 1] and map to a green-glow 0RGB u32.
/// Display only — the value is the substrate's; Rust just paints it.
fn paint(field: &[f64], buffer: &mut [u32]) {
    for (px, &v) in buffer.iter_mut().zip(field.iter()) {
        let v = v.clamp(0.0, 1.0);
        let g = (v * 2.0).clamp(0.0, 1.0);
        let rb = (v * 2.0 - 1.0).clamp(0.0, 1.0);
        let r = (rb * 255.0) as u32;
        let gg = (g * 255.0) as u32;
        let b = (rb * 255.0) as u32;
        *px = (r << 16) | (gg << 8) | b;
    }
}

/// Headless bridge self-test (no window). Spawns the substrate, requests init +
/// 3 clicks, and asserts the count increments ON THE SUBSTRATE and the frames
/// come back the right size. Lets the whole bridge be verified without a screen.
fn run_check() {
    let mut sub = Substrate::spawn(SIZE);
    let (c0, f0) = sub.request(b"I\n", SIZE);
    assert_eq!(c0, 0, "init count should be 0");
    assert_eq!(f0.len(), SIZE * SIZE, "init frame wrong size");
    for expected in 1..=3 {
        let (c, f) = sub.request(b"C\n", SIZE);
        assert_eq!(c, expected, "substrate count should increment to {expected}");
        assert_eq!(f.len(), SIZE * SIZE, "frame wrong size");
    }
    sub.quit();
    println!(
        "[gui-rust] bridge OK: substrate counted 0,1,2,3 and returned {SIZE}x{SIZE} frames"
    );
}

/// Open the window and count on clicks.
fn run_window() {
    use minifb::{Key, MouseButton, Scale, Window, WindowOptions};

    let mut sub = Substrate::spawn(SIZE);
    let (mut count, field) = sub.request(b"I\n", SIZE);
    let mut buffer = vec![0u32; SIZE * SIZE];
    paint(&field, &mut buffer);

    let mut window = Window::new(
        &format!("Yantra — count = {count} (counted on the substrate)"),
        SIZE,
        SIZE,
        WindowOptions {
            scale: Scale::X8,
            ..WindowOptions::default()
        },
    )
    .expect("open window");
    window.set_target_fps(60);

    let mut prev_down = false;
    while window.is_open() && !window.is_key_down(Key::Escape) {
        let down = window.get_mouse_down(MouseButton::Left);
        if down && !prev_down {
            let (c, f) = sub.request(b"C\n", SIZE);
            count = c;
            paint(&f, &mut buffer);
            window.set_title(&format!("Yantra — count = {count} (incremented on the substrate)"));
            println!("[gui-rust] click -> substrate step -> count {count}");
        }
        prev_down = down;
        window
            .update_with_buffer(&buffer, SIZE, SIZE)
            .expect("update window");
    }
    sub.quit();
}

fn main() {
    if std::env::args().any(|a| a == "--check") {
        run_check();
    } else {
        run_window();
    }
}
