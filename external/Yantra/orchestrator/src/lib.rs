//! Yantra orchestrator — the CPU-side Connectome Manager, in Rust.
//!
//! This crate is the incremental Rust port of the orchestrator whose
//! behavioural reference is the Python `kernel/` package (see
//! `planning/01-architecture.md` § "CPU side: small, Rust, orchestrator"
//! and `kernel/README.md`). Per the build strategy it grows as small,
//! independently-verified units that each match a slice of the Python API,
//! merging toward a freestanding image over time.
//!
//! `#![no_std]` for normal builds (the orchestrator is bare-metal-bound, like
//! `bootloader/`); `std` is pulled in only for the test harness so every unit
//! stays host-testable with `cargo test`.

#![cfg_attr(not(test), no_std)]

pub mod axon;
pub mod checkpoint;
pub mod json;
