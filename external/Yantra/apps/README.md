# `apps/` — native Sutra userspace utilities

Per `planning/07-transpilers.md` and `todo.md` § 2: userspace
utilities are written **natively in Sutra** here. GNU coreutils /
util-linux behaviour is the conceptual reference for these native
rewrites; no vendored Linux source is kept in-tree. Each
utility ships as its own subdirectory with a `.su` source +
manifest TOML + (eventually) a CLI shim once Sutra has
stdin/stdout vocabulary that doesn't go through axon-passing.

## What ships today

| Utility | Status | Notes |
|---|---|---|
| `echo/` | First v0 (2026-05-14); content-verified 2026-05-24 | Routes input axon's `stdin_text` key to the output's `stdout_text`. Real Sutra service, real `.su` source, real manifest, admitted by the kernel via the same `Init.admit_from_path` path the kernel-services use. The smallest end-to-end demonstration that `apps/` works as a milestone. **Now content-verified:** `test_echo_echoes_string_content_exactly` binds `make_string(text)` under `stdin_text`, routes through the kernel, and recovers the line verbatim (bit-exact across 46 varied strings under the current pinned Sutra — the earlier 2026-05-14 bundle-decoding regression is stale for this `make_string` path). |

### Host-orchestration demo surfaces (over substrate compute)

Two `apps/` entries are not native-Sutra utilities but **host command/UI
surfaces** that admit utilities through the kernel and show the
substrate's exact output — the CPU-side orchestrator's job (planning/01).
The computation runs on the substrate; the surface is the stand-in for
the eventual Rust-orchestrator / browser layer.

| Surface | Status | Notes |
|---|---|---|
| `calc/` | CLI calculator (2026-05-24) | Full expressions, `+ - * /`, precedence + parens; operator **selected on the substrate** (`switch.su`), float64 so exact integers reach 2⁵³. Exact or refused. Known step-c purity gap (returns a host `Fraction` behind a host-oracle refuse-gate; see `planning/23`). |
| `terminal/` | Stage-2 terminal surface (2026-05-24) | A command reader (`terminal.py`) over kernel-admitted utilities: `echo <text>` carries text bit-exact through `echo.su` and decodes the substrate's output verbatim; `calc <expr>` evaluates on the calc substrate; `help`. `run_script` runs an N-step interaction trace exact at every step (zero drift — the headline-demo measurement, planning/22). Choosing *which utility* a typed command names is admission/routing = host orchestration by design (distinct from calc's *which-operation* dispatch, which is substrate compute). `tests/test_terminal.py` (19 cases); `python apps/terminal/demo.py` prints a transcript. |
| `gui-rust/` | Rust GUI counter front-end | A `minifb` window in Rust that spawns the Sutra substrate server (`external/Sutra/demos/gui/counter_substrate_server.py`) and paints per-frame compute from it. Preserved (parked) — the richer GUI demo lives Sutra-side under `external/Sutra/demos/gui/`. |

`font/` and the Python `gui/` (tkinter) demos **migrated to Sutra** on 2026-05-28
(`external/Sutra/demos/{font,gui}/`) — they were language-level, not OS-level.
The calc substrate-parsing `.su` (`parse_op.su`, `parse_int2.su`) was also copied
to `external/Sutra/demos/calc/` on 2026-06-16 (kept here too — preservation).

## What's coming (not started)

Per `todo.md` § 2 Q-list, in priority order: `cat`, `ls`, `wc`,
`head/tail`, then mid-wave (`grep`, `cut/tr`, `sort/uniq`, `find`,
`mv/cp/rm`), then late-wave (`awk`, `sed`). Each is gated on the
Sutra-side string + IO + FS vocabulary maturing — `echo` works
today because it's pure axon round-trip; `cat` needs real file
reading; `ls` needs directory iteration; `awk` needs an interior
DSL. Nothing's blocked on Yantra-side decisions.

## Pattern for adding a new utility

1. Create `apps/<name>/<name>.su` exporting `function vector
   on_axon(vector input_axon)`.
2. Create `apps/<name>/<name>.toml` with manifest fields:
   `name`, `axon_width`, `compute_units`, `read_roles`,
   `write_roles`, `axon_keys` (optional), `source`.
3. Add a smoke test under `tests/test_apps_<name>.py` that admits
   the service via the kernel and verifies the round-trip.
4. Add a row to the table above.

The kernel admits an `apps/` service the same way it admits a
`kernel/services/` one — the distinction is documentary
(kernel-shaped vs userspace-shaped), not structural.
