//! CLI: run a compiled `.txt` WASM program through the Rust isomorph and print its
//! output to stdout (raw bytes); instruction/token counts go to stderr.
//!
//! Usage: wasm-ref <program.txt> [max_tokens]

use std::io::Write;
use std::process::exit;

use neural_wasm_iso::{parse_program, run};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: wasm-ref <program.txt> [max_tokens]");
        exit(2);
    }
    let max_tokens: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(200_000_000);

    let text = match std::fs::read_to_string(&args[1]) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("cannot read {}: {e}", args[1]);
            exit(1);
        }
    };

    let (program, input_str) = parse_program(&text);
    let res = run(&program, &input_str, max_tokens);

    std::io::stdout().write_all(&res.output).unwrap();
    eprintln!(
        "instr_count={} token_count={} out_len={}",
        res.instr_count,
        res.token_count,
        res.output.len()
    );
}
