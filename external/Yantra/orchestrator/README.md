# orchestrator — Yantra CPU-side Connectome Manager (Rust)

The incremental Rust port of the orchestrator. The behavioural reference is
the Python `kernel/` package; this crate grows as small, independently
`cargo test`-verified units that each match a slice of that API and compose
toward a freestanding (bare-metal) image over time — the build strategy in
`planning/01-architecture.md` § "CPU side: small, Rust, orchestrator".

`#![cfg_attr(not(test), no_std)]`: `no_std` for real builds (the orchestrator
is bare-metal-bound, like `bootloader/`), with `std` pulled in only for the
test harness so every unit stays host-testable.

## Units

- **`axon`** — the axon wire codecs, byte-for-byte compatible with Python
  `kernel/serialise.py`:
  - `YAXN` payload: `parse_axon_payload` / `write_axon_payload`.
  - `YAXE` envelope (role + from_proc + keys + nested YAXN payload):
    `parse_axon_envelope` / `write_axon_envelope`.

  The tests embed the exact bytes the Python encoder emits and assert both
  decode and byte-for-byte encode match. This is the orchestrator's read/write
  path for checkpointed axon values (see `kernel/checkpoint.py`,
  `planning/26-orchestrator-serialisation.md`).
- **`checkpoint`** — the cold-store / checkpoint codecs, byte-for-byte
  compatible with Python `kernel/checkpoint.py`:
  - `YPRC` per-process cold-store: `parse_process_blob` / `write_process_blob`.
  - `YKST` whole-kernel checkpoint (pool totals + per-process records with a
    storage `Tier` + inbox): `parse_kernel_checkpoint` / `write_kernel_checkpoint`.

  Both read the binary framing (name + manifest/identity JSON + an inbox of
  `YAXE` envelopes); the JSON fields come back as borrowed bytes, read by the
  **`json`** unit (below). Cross-checked against committed fixtures of real
  Python output (`tests/fixtures/echo_process.yprc`,
  `tests/fixtures/kernel_state.ykst`).
- **`json`** — a minimal `no_std`/no-alloc reader for the FLAT JSON schema the
  kernel emits (object of strings, non-negative ints, string arrays):
  `get_str` / `get_u32` / `get_str_array`. A structural scanner (never
  false-matches a key inside a value; escape pairs skipped). Strings come back
  raw; `unescape_into` resolves the common escapes (`\\`, `\"`, `\/`, `\n`,
  `\t`, `\r`, `\b`, `\f`) plus `\uXXXX` for BMP codepoints (1–3 byte UTF-8);
  surrogate pairs are refused, not faked. Turns the codecs' opaque
  manifest/identity bytes into typed fields — verified end-to-end against the
  YKST fixture.

## Build / test

```bash
cd orchestrator
cargo test            # host, default stable toolchain
```

`bootloader/` pins a nightly for its custom bare-metal target; this crate uses
the default stable toolchain for host testing. The format contract is the
point of the cross-check: if `kernel/serialise.py` changes the wire layout,
the embedded-bytes tests here fail by design.

## Inspect a checkpoint

A `dump-checkpoint` binary composes the codecs + `json` reader into a
developer tool that prints what's inside a real `.ykst` file:

```bash
cargo run --bin dump-checkpoint -- <path.ykst>
```

For the committed fixture (echo on GPU with one queued f32 axon + echo2 on DISC):

```text
YKST checkpoint: pool 8/10, 2 process(es)

[0] echo (tier=GPU)
    axon_width    = 768
    compute_units = 1
    source        = echo.su
    read_roles    = ["R_stdin"]
    write_roles   = ["R_stdout"]
    axon_keys     = ["stdin_text"]
    identity.kind = sutra
    source_path   = ..\apps\echo\echo.su
    runtime_dtype = float32
    inbox: 1 axon(s)
      [0] role=R_stdin from=external keys=["stdin_text"] payload=f32x3

[1] echo2 (tier=DISC)
    ...
    inbox: 0 axon(s)
```

The binary uses `std` (for `fs::read` + `println!`); the lib it depends on stays
`no_std`-ready. First real Rust program that composes the orchestrator units as
a developer tool, not just a test.
