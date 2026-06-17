# Yantra

**Website · [yantraos.org](https://yantraos.org) → rebranding to [noldor.tech](https://noldor.tech)**

> **Note (2026-06-16) — rebrand + preservation.** The public brand is moving to
> **Noldor Technologies** ([noldor.tech](https://noldor.tech)); `yantraos.org`
> redirects there from 2026-06-18. We're stepping back from the "OS company"
> framing on the website — but **the OS/kernel prototype in this repo is
> preserved, not abandoned.** It may still be continued. The language it's built
> in (Sutra) is actively developed in [`external/Sutra`](external/Sutra). Treat
> the code below as parked-and-kept, not deprecated.

An interpretable neural computer: a GPU-native operating system written in Sutra where the whole running system is one inspectable neural network.

## What it is

Yantra is the operating system you get when you take "the symbol *is* the
computation" seriously. The whole running system is one big differentiable
tensor-op graph: kernel, processes, IPC, GUI. There is essentially no
CPU-side runtime — a tiny CPU exists only to boot the system and
orchestrate the GPU. Everything that matters happens as Sutra programs
exchanging **axons** (structured embeddings produced by rotation binding).

Three things that fall out of that:

- **Predictable performance under load.** Once a process has its allocation,
  it doesn't slow down. Adding more processes either fits cleanly or fails
  admission — never degrades what is already running.
- **Verifiable.** The non-AI parts reduce to a compiled tensor-op graph +
  polynomial Kleene logic + tail-recursive loops, which is a much cleaner
  surface for formal arguments than a typical kernel.
- **AI-native by construction.** Every process already takes an axon and
  returns an axon, so local AI integrates without a translation layer.

The kernel is a **Connectome Manager**: it decides what runs on the GPU vs
sits in RAM (loaded but not running, semantically closer to disc than to
traditional RAM) vs lives on disc. It does not schedule and does not
allocate per-instruction memory in the traditional sense — its job is the
storage-tier decision. The CPU-side orchestrator is **Rust**.

## Build sequence

1. **Connectome Manager (kernel).** Python prototype in `kernel/`; production form is Rust. ([planning/01-architecture.md](planning/01-architecture.md))
2. **Command-line userspace utilities** (cat, ls, grep, …) — written natively in Sutra. Initial system access is SSH/serial only; no GUI. ([todo.md § 2](todo.md))
3. **Browser / GUI** — every UI component is a browser-rendered HTML page; HTML5 + CSS + idiomatic TS + WebGL/Three.js. WASM eventually but not for a long time. ([planning/06-gui-stack.md](planning/06-gui-stack.md), [todo.md § 3](todo.md))

**Bare-metal QEMU bootloader (v0.0)** at [`bootloader/`](bootloader/) — first Yantra-authored binary that runs on virtualized bare metal. Build with `scripts/qemu-build.{sh,bat}`, boot with `scripts/qemu-run.{sh,bat}`. See [`bootloader/README.md`](bootloader/README.md).

**Rust orchestrator (incremental)** at [`orchestrator/`](orchestrator/) — the CPU-side Connectome Manager being ported to Rust as small, host-testable `no_std`-ready units, each verified byte-for-byte against the Python `kernel/`. Shipped so far: the full checkpoint wire-codec stack — axon payload (`YAXN`) → envelope (`YAXE`) → per-process cold-store (`YPRC`) → whole-kernel checkpoint (`YKST`) — plus a `no_std` flat-JSON reader for checkpoint manifests, and a `dump-checkpoint` binary that composes the units on a real fixture. See [`orchestrator/README.md`](orchestrator/README.md).

The intended customer is not a consumer desktop user. It is defense,
aerospace, industrial control, medical devices, autonomous systems —
anywhere "predictable latency under load" and "the certifier can read the
code" beat "it runs my favourite app."

## Status

This repo holds **planning documents** plus a v0.0 **Connectome
Manager** under `kernel/` — a Python orchestration layer over real
Sutra compute — and a small set of remaining kernel-coupled `apps/`:
the **calculator** (`apps/calc/`, full expressions on the substrate,
float64 exact to 2⁵³, answer digits decomposed via the Fourier-series
modulus), **echo** (`apps/echo/`, axon round-trip), and the **terminal**
(`apps/terminal/`, kernel-mediated echo/calc).

A **Rust GUI binary** (`apps/gui-rust/`) drives the click-to-count
counter window; it spawns a substrate server from Sutra-side
(`external/Sutra/demos/gui/counter_substrate_server.py`) for the
per-frame substrate compute.

The earlier `apps/font/` (text-input 5×5 pixel font), `apps/gui/`
(Python tkinter GUIs over count.su / frame.su / toggle.su), and their
tests migrated to Sutra under `external/Sutra/demos/{font,gui}/` on
2026-05-28 — the work was language-level (exercising what the substrate
can do), not OS-level, so it lives next to the language now. See Sutra
`DEVLOG.md` 2026-05-28 for the migration and the three substrate-leak
categories that prompted it.

The kernel + apps test gate covers admission control, the axon router,
capability checks, real `.su` programs compiled and executed through
the router (on the real GPU — admit allocates GPU memory,
`_VSA.device == cuda`), the calculator, the terminal, echo content
round-trip, the orchestrator checkpoint + RAM cold-store tier
(`Init.cold_store` / `restore_from_cold`, bit-exact through the
kernel), and 1024/1024-symbol fidelity; it passes (**206 passed, 1
xfailed**, measured 2026-05-28). The one strict `xfail` is the
cross-program axon-projection case — see `planning/18`, `planning/20`.
The Sutra compiler/runtime live in the `external/Sutra` submodule
(pinned at a `main` commit past **v0.7.0**, which ships the
formal-verification tooling `from sutra_compiler import fv`; plus the
TS→Sutra transpiler CLI, axon-keys static analysis, the per-receiver
projection primitive, the `dot` builtin + selectable `runtime_dtype`
(float64), and `MultiProcessRuntime` — N programs sharing one `_VSA`).
Sutra's website: <https://sutra.emmaleonhart.com>. The orchestration layer is
Python here as the near-term implementation; the production target on the
CPU side is Rust.

Yantra is being designed (and now early-prototyped) here so that when
the upstream Sutra-side multi-process runtime + the production Rust
orchestrator land, there is a coherent target.

CI gates every build artifact on every push: the kernel + apps pytest
suite (host + inside the dev container), `cargo test` on the Rust
orchestrator (including a `dump-checkpoint` smoke), an end-to-end
`--check` of the Rust-GUI ↔ Sutra-substrate subprocess bridge, and a
`cargo build` of the bare-metal bootloader on its pinned nightly. See
[.github/workflows/ci.yml](.github/workflows/ci.yml).

## Dev environment

Three modes, pick one:

**1. Host Python** — the path the existing CI runs on.

```bash
# Python 3.13 + the Sutra submodule
pip install pytest numpy
pip install torch --index-url https://download.pytorch.org/whl/cpu
git submodule update --init external/Sutra
pytest tests/ -v          # kernel suite + real-Sutra integration
```

**2. Docker dev container** — reproducible across machines, no host deps beyond Docker. First run builds the image (~5–10 min, dominated by torch CPU wheel); subsequent runs reuse layers.

```bash
# Linux/macOS
./scripts/dev-shell.sh                 # interactive bash inside the container
./scripts/dev-shell.sh pytest          # one-shot test run

# Windows PowerShell
scripts\dev-shell.bat                  # interactive
scripts\dev-shell.bat pytest           # one-shot
```

The container bind-mounts the repo at `/workspace` so edits flow back to the host. `Dockerfile` at the repo root for the curious; CI builds it on every push so it doesn't rot silently.

**3. VS Code Dev Container** — open the folder in VS Code and click "Reopen in Container" when prompted. Uses the same Dockerfile via `.devcontainer/devcontainer.json`; pre-installs the Python + pytest extensions so the test pane lights up automatically.

This is tier 1 of the three "VM tiers" planned for Yantra. Tier 2 (cloud GPU VM, e.g. RunPod) waits on upstream Sutra GPU work being something to test against. Tier 3 (QEMU full-system emulator) waits on a Rust kernel image worth booting. See [planning/18-kernel-browser-readiness.md](planning/18-kernel-browser-readiness.md).

## Where to start reading

- [paper/paper.md](paper/paper.md) — position paper synthesising the
  planning corpus. The fastest single-document entry to what Yantra is
  and why. Auto-submitted to [clawRxiv](https://clawrxiv.io) for AI peer
  review on every push; reviews live in [paper/reviews/](paper/reviews/),
  pipeline details in [paper/README.md](paper/README.md).
- [planning/](planning/README.md) — the design notes, in reading order.
  Start with [`00-vision.md`](planning/00-vision.md).
- [ONBOARDING.md](ONBOARDING.md) — quick setup checklist for getting
  oriented across the Yantra / Sutra / SutraDB / alignment repos.

## Contributing

Not yet open to contribution. The architecture is moving quickly enough
that an issue tracker would be premature; the right place to push back
on ideas is via the planning docs themselves.

## Project conventions

See [CLAUDE.md](CLAUDE.md) for the conventions this repo runs by — the
short version is: commit early, do not enter planning-only mode without
files and commits, keep README and planning docs in sync with the
current state.
