//! Behavioural equivalence tests: the Rust isomorph must reproduce the reference
//! WASM execution outputs exactly. The known outputs below are the same traces the
//! transformer is checked against (see devlog / notes/sources.md).

use std::path::PathBuf;

use neural_wasm_iso::{parse_program, run};

fn data_dir() -> PathBuf {
    // crate dir is iso/rust; data lives in the submodule.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../replication_target/transformer-vm/transformer_vm/data")
}

fn run_program(name: &str) -> String {
    let path = data_dir().join(format!("{name}.txt"));
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("read {}: {e} (run `uv run wasm-compile --all` first)", path.display()));
    let (program, input_str) = parse_program(&text);
    run(&program, &input_str, 200_000_000).output_string()
}

#[test]
fn tiny_const_output_halt() {
    // const 0x41 ('A') -> output -> halt
    let text = "{ i32.const 41 00 00 00 output 00 00 00 00 halt 00 00 00 00 }";
    let (program, input) = parse_program(text);
    let res = run(&program, &input, 1000);
    assert_eq!(res.output_string(), "A");
}

#[test]
fn hello() {
    assert_eq!(run_program("hello"), "Hello World!\n");
}

#[test]
fn addition() {
    assert_eq!(run_program("addition"), "19134\n");
}

#[test]
fn fibonacci() {
    assert_eq!(run_program("fibonacci"), "55\n");
}

#[test]
fn collatz() {
    assert_eq!(run_program("collatz"), "7 22 11 34 17 52 26 13 40 20 10 5 16 8 4 2 1\n");
}

#[test]
fn sudoku_solved() {
    let out = run_program("sudoku");
    assert!(out.contains("solved!"), "sudoku did not report solved");
    assert!(
        out.contains("534678912672195348198342567859761423426853791713924856961537284287419635345286179"),
        "sudoku solution grid mismatch"
    );
}
