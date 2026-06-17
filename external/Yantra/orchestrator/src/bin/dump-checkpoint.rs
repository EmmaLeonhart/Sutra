//! `dump-checkpoint` — read a Yantra kernel checkpoint (`.ykst`, the file the
//! Python `kernel/checkpoint.py::serialise_kernel_state` writes) and print its
//! contents. First real Rust program that COMPOSES the orchestrator units —
//! the YKST codec, the YAXE envelope codec it nests, and the `json` reader —
//! end-to-end as a developer tool, not just a test.
//!
//! Usage:
//!     cargo run --manifest-path orchestrator/Cargo.toml --bin dump-checkpoint -- <path.ykst>
//!
//! The binary uses `std` (for `fs::read` + `println!`); the lib it depends on
//! stays `no_std`-ready.

use std::env;
use std::fs;
use std::process;

use yantra_orchestrator::axon::DType;
use yantra_orchestrator::checkpoint::{parse_kernel_checkpoint, Tier};
use yantra_orchestrator::json;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!(
            "usage: {} <path.ykst>",
            args.get(0).map(String::as_str).unwrap_or("dump-checkpoint")
        );
        process::exit(2);
    }
    let path = &args[1];
    let bytes = match fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("read {}: {}", path, e);
            process::exit(1);
        }
    };
    let cp = match parse_kernel_checkpoint(&bytes) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("parse error: {:?}", e);
            process::exit(1);
        }
    };
    println!(
        "YKST checkpoint: pool {}/{}, {} process(es)",
        cp.pool_free, cp.pool_total, cp.process_count
    );
    for (i, rec) in cp.processes().enumerate() {
        let rec = match rec {
            Ok(r) => r,
            Err(e) => {
                eprintln!("record {} error: {:?}", i, e);
                process::exit(1);
            }
        };
        println!();
        let tier_name = match rec.tier {
            Tier::Gpu => "GPU",
            Tier::Disc => "DISC",
            Tier::Ram => "RAM",
        };
        println!("[{}] {} (tier={})", i, rec.name, tier_name);

        if let Some(width) = json::get_u32(rec.manifest_json, "axon_width") {
            println!("    axon_width    = {}", width);
        }
        if let Some(units) = json::get_u32(rec.manifest_json, "compute_units") {
            println!("    compute_units = {}", units);
        }
        if let Some(source) = json::get_str(rec.manifest_json, "source") {
            println!("    source        = {}", source);
        }
        if let Some(it) = json::get_str_array(rec.manifest_json, "read_roles") {
            let v: Vec<&str> = it.collect();
            println!("    read_roles    = {:?}", v);
        }
        if let Some(it) = json::get_str_array(rec.manifest_json, "write_roles") {
            let v: Vec<&str> = it.collect();
            println!("    write_roles   = {:?}", v);
        }
        if let Some(it) = json::get_str_array(rec.manifest_json, "axon_keys") {
            let v: Vec<&str> = it.collect();
            println!("    axon_keys     = {:?}", v);
        }

        if let Some(kind) = json::get_str(rec.identity_json, "kind") {
            println!("    identity.kind = {}", kind);
        }
        if let Some(path_raw) = json::get_str(rec.identity_json, "source_path") {
            let mut buf = vec![0u8; path_raw.len()];
            match json::unescape_into(path_raw.as_bytes(), &mut buf) {
                Some(n) => println!(
                    "    source_path   = {}",
                    String::from_utf8_lossy(&buf[..n])
                ),
                None => println!("    source_path   = <unescape failed; raw={}>", path_raw),
            }
        }
        if let Some(dt) = json::get_str(rec.identity_json, "runtime_dtype") {
            println!("    runtime_dtype = {}", dt);
        }

        println!("    inbox: {} axon(s)", rec.inbox_count());
        for (k, env) in rec.inbox().enumerate() {
            match env {
                Ok(e) => {
                    let keys: Vec<&str> = e.keys().filter_map(Result::ok).collect();
                    let dt = match e.payload.dtype {
                        DType::Float32 => "f32",
                        DType::Float64 => "f64",
                        DType::Complex64 => "c64",
                        DType::Complex128 => "c128",
                    };
                    println!(
                        "      [{}] role={} from={} keys={:?} payload={}x{}",
                        k, e.role, e.from_proc, keys, dt, e.payload.width
                    );
                }
                Err(e) => println!("      [{}] envelope error: {:?}", k, e),
            }
        }
    }
}
